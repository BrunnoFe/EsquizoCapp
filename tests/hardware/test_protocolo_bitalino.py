"""Testes do protocolo do BITalino.

Tudo aqui é função pura sobre bytes: nenhum teste precisa de dispositivo plugado. É a
ÚNICA costura capaz de pegar os dois erros silenciosos do Modo Direto — canal deslocado e
unidade errada —, porque a bateria de contrato exige um dispositivo conectado e o leitor
sintético responde igual pelos dois modos por construção.
"""

import pytest

from esquizocap.hardware import protocolo_bitalino as protocolo

# Frame de referência, montado à mão a partir do empacotamento do protocolo, com um valor
# DISTINTO em cada canal. É o que faz um deslocamento de coluna aparecer: se A3 e A4
# trocarem de lugar, 256 e 128 trocam junto, e a asserção quebra.
#
#   seq = 5 | digitais = 1,0,1,0
#   A1 = 1023 (máximo de 10 bits)   A4 = 128
#   A2 = 512                        A5 = 63 (máximo de 6 bits)
#   A3 = 256                        A6 = 1
#   O nibble baixo do último byte é o CRC-4 do próprio frame (0x5 aqui).
FRAME_SEIS_CANAIS: bytes = bytes([0xC1, 0x0F, 0x08, 0x40, 0x00, 0xFE, 0xAF, 0x55])
ADU_ESPERADOS_SEIS_CANAIS: list[int] = [1023, 512, 256, 128, 63, 1]
SEQUENCIA_ESPERADA: int = 5
DIGITAIS_ESPERADOS: list[int] = [1, 0, 1, 0]


class TestComandosDeControle:
    @pytest.mark.parametrize(
        ('taxa_hz', 'codigo_esperado'),
        [(1, 0b00_000011), (10, 0b01_000011), (100, 0b10_000011), (1000, 0b11_000011)],
    )
    def test_comando_de_taxa_codifica_nos_dois_bits_mais_altos(self, taxa_hz: int, codigo_esperado: int) -> None:
        assert protocolo.comando_definir_taxa(taxa_hz=taxa_hz) == codigo_esperado

    @pytest.mark.parametrize('taxa_invalida', [0, 2, 50, 500, 2000, -1])
    def test_taxa_nao_suportada_falha_alto(self, taxa_invalida: int) -> None:
        """O firmware não interpola: pedir 500 Hz é erro, não arredondamento para 1000."""
        with pytest.raises(ValueError, match='Taxa de amostragem'):
            protocolo.comando_definir_taxa(taxa_hz=taxa_invalida)

    def test_comando_iniciar_liga_um_bit_por_canal(self) -> None:
        """Canal N (1 a 6) ocupa o bit (N + 1), e o bit 0 marca o comando."""
        assert protocolo.comando_iniciar(canais=[1]) == 0b00000101
        assert protocolo.comando_iniciar(canais=[6]) == 0b10000001
        assert protocolo.comando_iniciar(canais=[1, 2, 3, 4, 5, 6]) == 0b11111101

    def test_comando_iniciar_ignora_a_ordem_e_as_repeticoes(self) -> None:
        assert protocolo.comando_iniciar(canais=[3, 1, 3]) == protocolo.comando_iniciar(canais=[1, 3])

    @pytest.mark.parametrize('canais_invalidos', [[], [0], [7], [1, 9]])
    def test_canais_fora_da_faixa_falham_alto(self, canais_invalidos: list[int]) -> None:
        with pytest.raises(ValueError, match='[Cc]anal'):
            protocolo.comando_iniciar(canais=canais_invalidos)


class TestTamanhoDoFrame:
    @pytest.mark.parametrize(
        ('quantidade_canais', 'bytes_esperados'),
        [(1, 3), (2, 4), (3, 6), (4, 7), (5, 8), (6, 8)],
    )
    def test_tamanho_segue_o_empacotamento_do_firmware(self, quantidade_canais: int, bytes_esperados: int) -> None:
        """Os canais 1 a 4 são de 10 bits e os canais 5 e 6 de 6 bits, então o frame NÃO
        cresce de forma linear — 5 e 6 canais cabem nos MESMOS 8 bytes. Errar isto
        dessincroniza a leitura para sempre."""
        assert protocolo.tamanho_frame_bytes(quantidade_canais=quantidade_canais) == bytes_esperados


class TestCrc:
    def test_o_crc_do_frame_de_referencia_confere(self) -> None:
        assert protocolo.crc_confere(frame=FRAME_SEIS_CANAIS) is True

    @pytest.mark.parametrize('posicao', range(8))
    def test_qualquer_byte_corrompido_reprova(self, posicao: int) -> None:
        """É para isto que o CRC existe: um byte trocado no ar não pode virar amostra."""
        corrompido = bytearray(FRAME_SEIS_CANAIS)
        corrompido[posicao] ^= 0b0001_0000

        assert protocolo.crc_confere(frame=bytes(corrompido)) is False


class TestDecodificacaoDoFrame:
    def test_cada_canal_sai_na_sua_posicao(self) -> None:
        """O teste central do Modo Direto.

        Com um valor distinto por canal, qualquer troca de posição no desempacotamento
        aparece aqui — e é a falha que, solta, produziria cor errada sem erro nenhum.
        """
        leitura = protocolo.decodificar_frame(frame=FRAME_SEIS_CANAIS, quantidade_canais=6)

        assert leitura.analogicos == ADU_ESPERADOS_SEIS_CANAIS

    def test_preserva_o_numero_de_sequencia_e_os_digitais(self) -> None:
        leitura = protocolo.decodificar_frame(frame=FRAME_SEIS_CANAIS, quantidade_canais=6)

        assert leitura.sequencia == SEQUENCIA_ESPERADA
        assert leitura.digitais == DIGITAIS_ESPERADOS

    def test_cada_canal_respeita_a_resolucao_do_seu_conversor(self) -> None:
        """A1..A4 chegam a 1023; A5 e A6, só a 63. Não é bug do sinal, é o conversor.

        Um valor acima do teto de 6 bits em A5/A6 denunciaria desempacotamento errado —
        bits de outro canal vazando para dentro deste.
        """
        leitura = protocolo.decodificar_frame(frame=FRAME_SEIS_CANAIS, quantidade_canais=6)

        for indice in range(4):
            assert leitura.analogicos[indice] <= protocolo.ADU_MAXIMO_CANAIS_PRINCIPAIS

        for indice in (4, 5):
            assert leitura.analogicos[indice] <= protocolo.ADU_MAXIMO_CANAIS_AUXILIARES

    @pytest.mark.parametrize('quantidade_canais', [1, 2, 3, 4, 5, 6])
    def test_todos_os_ramos_de_desempacotamento_rodam(self, quantidade_canais: int) -> None:
        """O desempacotamento tem um ramo por canal, escrito à mão. Sem este teste, quatro
        deles nunca rodariam — num módulo cuja razão de existir é justamente o erro que não
        levanta exceção."""
        tamanho = protocolo.tamanho_frame_bytes(quantidade_canais=quantidade_canais)
        frame = FRAME_SEIS_CANAIS[-tamanho:]

        leitura = protocolo.decodificar_frame(frame=frame, quantidade_canais=quantidade_canais)

        assert len(leitura.analogicos) == quantidade_canais
        assert len(leitura.digitais) == len(protocolo.DESLOCAMENTOS_DIGITAIS)
        for canal, adu in enumerate(leitura.analogicos, start=1):
            assert 0 <= adu <= 2 ** protocolo.resolucao_bits(canal=canal) - 1

    def test_frame_de_tamanho_errado_falha_alto(self) -> None:
        """Um frame curto significa leitura dessincronizada; decodificar mesmo assim
        produziria amostras plausíveis e erradas."""
        with pytest.raises(ValueError, match='[Tt]amanho'):
            protocolo.decodificar_frame(frame=FRAME_SEIS_CANAIS[:-1], quantidade_canais=6)


class TestMontagemDaLinha:
    """O ponto onde o Modo Direto se disfarça de Modo OpenSignals.

    Se algo aqui estiver errado, NADA levanta exceção: a fita simplesmente acende na cor
    errada, e não há como distinguir isso de uma escolha artística.
    """

    def _leitura(self) -> protocolo.LeituraBruta:
        return protocolo.decodificar_frame(frame=FRAME_SEIS_CANAIS, quantidade_canais=6)

    def test_o_canal_N_sai_no_indice_N(self) -> None:
        """O teste que justifica o ticket.

        O stream do OpenSignals publica `[nSeq, A1..A6]`, e o domínio indexa `amostra[canal]`
        com canal de 1 a 6 — sem subtrair 1. Se a sequência fosse descartada, todo canal
        andaria uma casa e o canal 1 leria A2.
        """
        linha = protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2, 3, 4, 5, 6], canal_ativo=2)

        assert len(linha) == 7, 'a linha tem a sequência mais um valor por canal'
        # O canal 2 é o ativo, então sai convertido; os outros seguem em ADU e batem
        # posição a posição com os valores distintos do frame de referência.
        assert linha[1] == ADU_ESPERADOS_SEIS_CANAIS[0]
        assert linha[3] == ADU_ESPERADOS_SEIS_CANAIS[2]
        assert linha[4] == ADU_ESPERADOS_SEIS_CANAIS[3]
        assert linha[5] == ADU_ESPERADOS_SEIS_CANAIS[4]
        assert linha[6] == ADU_ESPERADOS_SEIS_CANAIS[5]

    def test_a_sequencia_ocupa_o_indice_zero(self) -> None:
        linha = protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2, 3, 4, 5, 6], canal_ativo=1)

        assert linha[0] == SEQUENCIA_ESPERADA

    def test_os_canais_digitais_nao_entram_na_linha(self) -> None:
        """O frame carrega quatro digitais que o sistema não consome. Se vazassem para a
        linha, empurrariam todos os analógicos quatro casas adiante."""
        linha = protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2, 3, 4, 5, 6], canal_ativo=1)

        assert len(linha) == 1 + 6

    @pytest.mark.parametrize('canal_ativo', [1, 2, 3, 4])
    def test_so_o_canal_ativo_vira_microvolts(self, canal_ativo: int) -> None:
        """Os demais saem em ADU de propósito: converter sem saber o sensor não significa nada."""
        linha = protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2, 3, 4, 5, 6], canal_ativo=canal_ativo)

        adu_do_ativo = ADU_ESPERADOS_SEIS_CANAIS[canal_ativo - 1]
        esperado = protocolo.converter_para_microvolts(adu=adu_do_ativo, canal=canal_ativo)
        assert linha[canal_ativo] == pytest.approx(esperado)

        for canal in (1, 2, 3, 4, 5, 6):
            if canal != canal_ativo:
                assert linha[canal] == ADU_ESPERADOS_SEIS_CANAIS[canal - 1]

    def test_o_canal_ativo_sai_na_faixa_do_sensor_e_nao_na_do_conversor(self) -> None:
        """A prova de que a conversão aconteceu: ADU vai de 0 a 1023, sempre positivo; o EEG
        convertido vive em ±39,49 µV, com média zero. São faixas que não se confundem."""
        linha = protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2, 3, 4, 5, 6], canal_ativo=1)

        assert linha[1] == pytest.approx(39.41, abs=0.05), 'ADU 1023 do canal 1 vira o topo da faixa'
        assert linha[2] == 512, 'canal 2 não é o ativo: segue em ADU'

    def test_adquirir_um_subconjunto_de_canais_mantem_a_ordem(self) -> None:
        """Adquirir só alguns canais é permitido pelo firmware. A linha encolhe, mas a ordem
        segue a dos canais pedidos — quem chama é que sabe o que pediu."""
        leitura = protocolo.decodificar_frame(
            frame=FRAME_SEIS_CANAIS[-protocolo.tamanho_frame_bytes(quantidade_canais=2) :],
            quantidade_canais=2,
        )

        linha = protocolo.montar_linha(leitura=leitura, canais=[1, 2], canal_ativo=1)

        assert len(linha) == 3

    def test_canais_e_valores_em_quantidades_diferentes_falham_alto(self) -> None:
        with pytest.raises(ValueError, match='não batem'):
            protocolo.montar_linha(leitura=self._leitura(), canais=[1, 2], canal_ativo=1)


class TestConversaoParaMicrovolts:
    @pytest.mark.parametrize('canal', [1, 2, 3, 4])
    def test_os_extremos_de_10_bits_batem_com_a_faixa_do_datasheet(self, canal: int) -> None:
        """Datasheet do sensor EEG: ganho 41782, VCC 3,3 V, faixa ±39,49 µV."""
        assert protocolo.converter_para_microvolts(adu=1023, canal=canal) == pytest.approx(39.41, abs=0.05)
        assert protocolo.converter_para_microvolts(adu=0, canal=canal) == pytest.approx(-39.49, abs=0.05)

    @pytest.mark.parametrize('canal', [1, 2, 3, 4])
    def test_o_meio_da_escala_de_10_bits_vira_zero(self, canal: int) -> None:
        """O ADU é sempre positivo e centrado; o EEG tem média zero. É a conversão que
        remove esse offset — sem ela, o domínio recebe um degrau de ~512."""
        assert protocolo.converter_para_microvolts(adu=512, canal=canal) == pytest.approx(0.0, abs=0.05)

    @pytest.mark.parametrize('canal', [5, 6])
    def test_os_canais_de_6_bits_usam_a_propria_escala(self, canal: int) -> None:
        """Usar 10 bits em A5/A6 comprimiria o sinal a 1/16 da faixa, sem erro nenhum.

        O topo fica em ~38,3 µV, e não nos 39,4 dos canais de 10 bits: o maior ADU de 6 bits
        é 63/64 da escala, contra 1023/1024. A assimetria é do conversor, não do sinal.
        """
        assert protocolo.converter_para_microvolts(adu=63, canal=canal) == pytest.approx(38.26, abs=0.05)
        assert protocolo.converter_para_microvolts(adu=0, canal=canal) == pytest.approx(-39.49, abs=0.05)
        assert protocolo.converter_para_microvolts(adu=32, canal=canal) == pytest.approx(0.0, abs=0.05)

    def test_o_passo_de_6_bits_e_16x_mais_grosso_que_o_de_10(self) -> None:
        """A razão de ser do aviso na interface: 64 níveis contra 1024 para o mesmo sinal."""
        passo_dez_bits = protocolo.converter_para_microvolts(adu=513, canal=1) - protocolo.converter_para_microvolts(
            adu=512, canal=1
        )
        passo_seis_bits = protocolo.converter_para_microvolts(adu=33, canal=5) - protocolo.converter_para_microvolts(
            adu=32, canal=5
        )

        assert passo_seis_bits == pytest.approx(passo_dez_bits * 16, rel=0.01)

    def test_canal_fora_da_faixa_falha_alto(self) -> None:
        with pytest.raises(ValueError, match='[Cc]anal'):
            protocolo.converter_para_microvolts(adu=512, canal=7)
