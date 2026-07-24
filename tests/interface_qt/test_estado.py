"""Testes da máquina de estados da interface.

Estes testes existem porque a regra virou uma função PURA. Antes, ela era uma cascata de
comparações de string dentro de um `after(10 ms)` da GUI: para testá-la seria preciso
abrir uma janela Tk e simular cliques. Agora é entrada -> saída.
"""

import pytest

from esquizocap.dominio.ciclo_aquisicao import ModoAnalise
from esquizocap.hardware.constantes import (
    CANAIS_BITALINO,
    TAXA_AMOSTRAGEM_PADRAO_HZ,
    TAXAS_AMOSTRAGEM_SUPORTADAS,
)
from esquizocap.hardware.modo_aquisicao import ModoAquisicao
from esquizocap.interface_qt.estado import (
    CANAIS_COM_ROTULO,
    CANAIS_NA_ORDEM_DO_SELETOR,
    ROTULOS_DOS_CANAIS,
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    aviso_de_taxa,
    aviso_do_canal,
    mensagem_de_aquisicao,
    rotulo_do_canal,
    taxas_selecionaveis,
)

MACS = ('20:17:09:18:60:29', '98:D3:B1:FD:3D:1F')
MODELO = 'Preditor HSV baseado em Amplitude'


def selecao(**mudancas: object) -> SelecaoUsuario:
    """Uma seleção COMPLETA, com um campo estragado por vez nos testes."""
    campos = {
        'modelo': MODELO,
        'porta_arduino': 'COM99 - Arduino simulado (fake)',
        'modo_luminosidade': 'Todos',
        'arduino_conectado': True,
        'canal_bitalino': '3',
        'mac_bitalino': MACS[0],
        'modo_aquisicao': ModoAquisicao.OPENSIGNALS.value,
        'porta_bitalino': '',
        'modo_analise': ModoAnalise.FREQUENCIA.value,
        'taxa_amostragem_hz': TAXA_AMOSTRAGEM_PADRAO_HZ,
    }
    campos.update(mudancas)
    return SelecaoUsuario(**campos)  # type: ignore[arg-type]


def test_tudo_escolhido_fica_pronto() -> None:
    estado, mensagem = avaliar_prontidao(selecao=selecao(), macs_validos=MACS)

    assert estado is EstadoApp.PRONTO
    assert 'Começar aquisição' in mensagem


class TestOQueFaltaVemNaOrdemDePreenchimento:
    """A mensagem tem que apontar o PRÓXIMO passo, não uma pendência qualquer.

    A ordem das checagens é a ordem visual da tela — modelo, Arduino, BITalino. Se ela se
    inverter, o usuário que ainda não escolheu o modelo será mandado a "Configurar o
    Bitalino", e vai preencher a tela de trás para frente.
    """

    def test_sem_modelo(self) -> None:
        estado, mensagem = avaliar_prontidao(
            # Nada mais está escolhido também, mas o modelo é o primeiro passo.
            selecao=selecao(modelo='Selecione um modelo ...', porta_arduino='', mac_bitalino=''),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'modelo' in mensagem

    def test_sem_porta_do_arduino(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(porta_arduino='Selecione a porta do Arduino'), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Arduino'

    def test_sem_modo_de_luminosidade(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(modo_luminosidade='Selecione um modo de luminosidade'),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Arduino'

    def test_arduino_configurado_mas_nao_conectado(self) -> None:
        """O caso mais fácil de errar: tudo escolhido, mas o botão "Conectar" não foi clicado."""
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(arduino_conectado=False), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'Conectar' in mensagem

    def test_sem_canal_do_bitalino(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(canal_bitalino='Selecione o canal ativo do Bitalino'),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Bitalino'

    def test_mac_fora_da_configuracao(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(mac_bitalino='00:00:00:00:00:00'), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO


@pytest.mark.parametrize('canal', ['1', '2', '3', '4', '5', '6'])
def test_todos_os_canais_do_dispositivo_sao_aceitos(canal: str) -> None:
    estado, _mensagem = avaliar_prontidao(selecao=selecao(canal_bitalino=canal), macs_validos=MACS)

    assert estado is EstadoApp.PRONTO


@pytest.mark.parametrize('canal', ['0', '7', '', 'A1'])
def test_canal_inexistente_no_dispositivo_e_recusado(canal: str) -> None:
    estado, _mensagem = avaliar_prontidao(selecao=selecao(canal_bitalino=canal), macs_validos=MACS)

    assert estado is EstadoApp.CONFIGURANDO


class TestModoDeAquisicao:
    """O Modo Direto alcança o dispositivo por porta de acesso; o Modo OpenSignals, não.

    A porta NÃO é escolhida pelo operador: a aplicação a deriva do MAC, lendo o hwid que o
    sistema já expõe. Mas ela pode não existir — dispositivo não pareado, desligado, ou um
    sistema fora do Windows —, e nesse caso o Modo Direto não tem como conectar.
    """

    def test_o_modo_opensignals_nao_precisa_de_porta(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(modo_aquisicao=ModoAquisicao.OPENSIGNALS.value, porta_bitalino=''),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.PRONTO

    def test_o_modo_direto_com_porta_derivada_fica_pronto(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(modo_aquisicao=ModoAquisicao.DIRETO.value, porta_bitalino='COM6'),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.PRONTO

    def test_o_modo_direto_sem_porta_nao_fica_pronto(self) -> None:
        """Sem porta, conectar falharia lá na frente, com uma mensagem do sistema
        operacional. Barrar aqui explica o que fazer."""
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(modo_aquisicao=ModoAquisicao.DIRETO.value, porta_bitalino=''),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'parea' in mensagem.lower() or 'porta' in mensagem.lower()

    def test_modo_desconhecido_nao_fica_pronto(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(modo_aquisicao='Telepatia'), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO

    def test_a_porta_do_bitalino_nao_pode_ser_a_do_arduino(self) -> None:
        """As duas conexões disputariam o mesmo recurso e nenhuma funcionaria. A derivação
        já exclui a porta do BITalino da lista do Arduino, mas a configuração pode vir de um
        JSON antigo — a regra fica aqui para valer nos dois caminhos."""
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(
                modo_aquisicao=ModoAquisicao.DIRETO.value,
                porta_bitalino='COM6',
                porta_arduino='COM6 - CH340',
            ),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'mesma porta' in mensagem.lower()


class TestTaxasSelecionaveis:
    """Qual taxa acordada faz sentido depende do MODO DE PREDIÇÃO, não do gosto.

    A análise espectral do modo Frequência classifica bandas de EEG até 50 Hz, e Nyquist
    exige amostrar acima do dobro disso. Abaixo dessa taxa a FFT continua rodando e
    devolvendo uma "banda dominante" — que é artefato puro. Nada falha, nada avisa: a fita
    só acende na cor errada.
    """

    def test_no_modo_amplitude_todas_as_taxas_servem(self) -> None:
        """Amplitude não faz análise espectral: cada amostra vira uma cor, e taxa baixa é
        até desejável — casa o ritmo de leitura com o do dispositivo e evita acumular
        atraso no buffer."""
        assert taxas_selecionaveis(ModoAnalise.AMPLITUDE.value) == TAXAS_AMOSTRAGEM_SUPORTADAS

    def test_no_modo_frequencia_so_as_que_alcancam_as_bandas(self) -> None:
        taxas = taxas_selecionaveis(ModoAnalise.FREQUENCIA.value)

        assert taxas == (100, 1000)
        assert 10 not in taxas, '10 Hz enxerga só até 5 Hz: nem Delta inteiro'
        assert 1 not in taxas

    def test_a_taxa_padrao_serve_aos_dois_modos(self) -> None:
        for modo in (ModoAnalise.AMPLITUDE.value, ModoAnalise.FREQUENCIA.value):
            assert TAXA_AMOSTRAGEM_PADRAO_HZ in taxas_selecionaveis(modo)


class TestAvisoDeTaxa:
    def test_cem_hertz_em_frequencia_avisa_sobre_gamma(self) -> None:
        """100 Hz dá Nyquist exatamente em 50 Hz, o topo de Gamma. Passa no gate, mas a
        banda fica na borda e sofre aliasing — o operador precisa saber."""
        aviso = aviso_de_taxa(taxa_hz=100, modo_analise=ModoAnalise.FREQUENCIA.value)

        assert 'Gamma' in aviso

    def test_mil_hertz_em_frequencia_nao_avisa_nada(self) -> None:
        assert aviso_de_taxa(taxa_hz=1000, modo_analise=ModoAnalise.FREQUENCIA.value) == ''

    def test_taxa_baixa_em_amplitude_nao_avisa_sobre_bandas(self) -> None:
        """Não há banda nenhuma em jogo no modo Amplitude."""
        assert 'Gamma' not in aviso_de_taxa(taxa_hz=10, modo_analise=ModoAnalise.AMPLITUDE.value)


class TestTaxaNaProntidao:
    def test_taxa_valida_para_o_modo_fica_pronto(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(
                modo_aquisicao=ModoAquisicao.DIRETO.value,
                porta_bitalino='COM6',
                modo_analise=ModoAnalise.FREQUENCIA.value,
                taxa_amostragem_hz=1000,
            ),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.PRONTO

    def test_taxa_incompativel_com_o_modo_de_predicao_barra(self) -> None:
        """Sem esta barreira, a análise espectral rodaria sobre um sinal que não contém as
        bandas que ela diz encontrar."""
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(
                modo_aquisicao=ModoAquisicao.DIRETO.value,
                porta_bitalino='COM6',
                modo_analise=ModoAnalise.FREQUENCIA.value,
                taxa_amostragem_hz=10,
            ),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'taxa' in mensagem.lower()

    def test_no_modo_opensignals_a_taxa_escolhida_e_irrelevante(self) -> None:
        """Lá quem fixa a taxa é o OpenSignals; a escolha desta tela nem chega ao leitor."""
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(
                modo_aquisicao=ModoAquisicao.OPENSIGNALS.value,
                modo_analise=ModoAnalise.FREQUENCIA.value,
                taxa_amostragem_hz=1,
            ),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.PRONTO


class TestRotuloDoCanal:
    """Os seis canais NÃO são equivalentes, e a interface os apresentava como se fossem.

    A1–A4 têm 10 bits (1024 níveis); A5 e A6, apenas 6 (64 níveis). Para um sinal de
    microvolts, 64 níveis são quase todos degrau de quantização — e a FFT de um sinal assim
    espalha energia por todo o espectro, tornando a banda dominante um sorteio.

    Isto vale nos DOIS modos de aquisição: é uma armadilha que já existia, não algo que o
    Modo Direto trouxe.
    """

    @pytest.mark.parametrize('canal', [1, 2, 3, 4])
    def test_os_canais_de_dez_bits_dizem_a_resolucao(self, canal: int) -> None:
        rotulo = rotulo_do_canal(canal)

        assert rotulo.startswith(str(canal))
        assert '10 bits' in rotulo

    @pytest.mark.parametrize('canal', [5, 6])
    def test_os_canais_de_seis_bits_saem_marcados(self, canal: int) -> None:
        rotulo = rotulo_do_canal(canal)

        assert '6 bits' in rotulo
        assert 'evite' in rotulo.lower()

    def test_todo_canal_do_dispositivo_tem_rotulo(self) -> None:
        assert len(ROTULOS_DOS_CANAIS) == len(CANAIS_BITALINO)

    def test_rotulos_e_canais_saem_da_mesma_fonte(self) -> None:
        """A interface escolhe o canal pela POSIÇÃO, porque o rótulo não serve de valor.

        Se a lista de rótulos e a de canais pudessem divergir, um filtro ou reordenação num
        dos lados deslocaria tudo — e o operador escolheria o canal 3 adquirindo o 4, sem
        erro nenhum. Por isso as duas derivam de `CANAIS_COM_ROTULO`, e este teste prova que
        continuam alinhadas.
        """
        assert len(ROTULOS_DOS_CANAIS) == len(CANAIS_NA_ORDEM_DO_SELETOR)

        for posicao, (canal, rotulo) in enumerate(CANAIS_COM_ROTULO):
            assert CANAIS_NA_ORDEM_DO_SELETOR[posicao] == canal
            assert ROTULOS_DOS_CANAIS[posicao] == rotulo
            assert rotulo.startswith(str(canal))

    def test_o_rotulo_comeca_pelo_numero_do_canal(self) -> None:
        """A barra de status mostra "Canal 3": o dropdown tem que combinar com ela."""
        for canal, rotulo in zip(CANAIS_BITALINO, ROTULOS_DOS_CANAIS, strict=True):
            assert rotulo.startswith(str(canal))


class TestAvisoDoCanal:
    @pytest.mark.parametrize('canal', [5, 6])
    def test_escolher_um_canal_de_baixa_resolucao_avisa(self, canal: int) -> None:
        aviso = aviso_do_canal(canal)

        assert 'bits' in aviso
        assert aviso != ''

    @pytest.mark.parametrize('canal', [1, 2, 3, 4])
    def test_os_canais_de_dez_bits_nao_avisam_nada(self, canal: int) -> None:
        assert aviso_do_canal(canal) == ''

    def test_canal_de_baixa_resolucao_continua_pronto_para_adquirir(self) -> None:
        """O eletrodo é físico: se já está plugado no A5, negar a leitura é pior que avisar."""
        estado, _mensagem = avaliar_prontidao(selecao=selecao(canal_bitalino='5'), macs_validos=MACS)

        assert estado is EstadoApp.PRONTO


def test_a_mensagem_de_aquisicao_diz_se_esta_gravando() -> None:
    assert 'gravando' in mensagem_de_aquisicao(gravando=True)
    assert 'gravando' not in mensagem_de_aquisicao(gravando=False)
