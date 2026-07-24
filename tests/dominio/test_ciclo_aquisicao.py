"""Testes do ciclo de aquisição: ler -> pré-processar -> prever -> enviar ao Arduino."""

import pytest
from conftest import conectar_leitor

from esquizocap.dominio.ciclo_aquisicao import (
    CicloAquisicao,
    ControlesUsuario,
    ModoAnalise,
    ResultadoCiclo,
    gerar_parametros_visual,
)
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.bitalino_fake import BitalinoSintetico

PORTA_VALIDA = 'COM99 - Arduino simulado (fake)'
SATURACAO = 255
BRILHO = 120

# Sem intervalo: uma predição por amostra lida. É o padrão da maioria dos testes.
CONTROLES = ControlesUsuario(saturacao=SATURACAO, brilho=BRILHO)


def montar_ciclo(
    modelo: ModeloPreditor,
    modo: ModoAnalise,
    canal: int = 1,
    tamanho_janela: int = 1000,
) -> tuple[CicloAquisicao, BitalinoSintetico, ArduinoFake]:
    leitor = BitalinoSintetico()
    arduino = ArduinoFake()
    conectar_leitor(leitor)
    arduino.conectar(porta=PORTA_VALIDA, baudrate=9600)

    ciclo = CicloAquisicao(
        leitor=leitor,
        arduino=arduino,
        modelo=modelo,
        modo_analise=modo,
        canal_bitalino=canal,
        modo_luminosidade=2,
        tamanho_amostra_frequencia=tamanho_janela,
    )
    return ciclo, leitor, arduino


class TestModoAmplitude:
    def test_um_ciclo_produz_um_resultado(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, _arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)

        resultado = ciclo.processar_amostra(controles=CONTROLES)

        assert isinstance(resultado, ResultadoCiclo)
        assert resultado.faixa_frequencia is None, 'Amplitude não faz análise espectral'
        assert resultado.potencia is None
        assert resultado.janela is None

    def test_a_cor_prevista_chega_ao_arduino(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)

        resultado = ciclo.processar_amostra(controles=CONTROLES)
        assert resultado is not None

        assert arduino.comandos_enviados == 1
        assert arduino.ultimo_comando == f'(2,{resultado.hue},{SATURACAO},{BRILHO})\n'

    def test_saturacao_e_brilho_vem_de_quem_chama_nao_do_modelo(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, _arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)

        resultado = ciclo.processar_amostra(controles=ControlesUsuario(saturacao=10, brilho=20))
        assert resultado is not None

        assert resultado.saturacao == 10
        assert resultado.brilho == 20


class TestIntervaloDePredicao:
    """O intervalo espaça as PREDIÇÕES sem espaçar as LEITURAS.

    Essa distinção é o coração da correção do atraso: o LSL entrega a amostra mais
    ANTIGA do buffer, então ler mais devagar do que o dispositivo produz faz o atraso
    crescer para sempre. O ciclo lê tudo e só decide, a cada leitura, se já é hora de
    prever.
    """

    def test_uma_predicao_por_intervalo_de_sinal(self, modelo: ModeloPreditor) -> None:
        # O fake gera 1000 Hz, então 100 amostras = 100 ms de sinal.
        ciclo, _leitor, arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)
        controles = ControlesUsuario(
            saturacao=SATURACAO, brilho=BRILHO, intervalo_predicao_segundos=0.1
        )

        resultados = [ciclo.processar_amostra(controles=controles) for _ in range(1000)]
        previstos = [r for r in resultados if r is not None]

        # 1000 amostras = 1 s de sinal. A 1 predição por 100 ms: a primeira sai de cara,
        # e depois uma a cada 100 amostras.
        assert len(previstos) == 10
        assert arduino.comandos_enviados == 10, 'Só as predições vão ao Arduino'

    def test_todas_as_amostras_sao_lidas_mesmo_sem_predicao(self, modelo: ModeloPreditor) -> None:
        """REGRESSÃO: a leitura NÃO pode ser espaçada junto com a predição.

        Se alguém "otimizar" isto pulando a leitura quando não vai prever, o buffer do
        LSL volta a acumular atraso — e a app volta a prever cor a partir de sinal velho.
        """
        ciclo, leitor, _arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)
        controles = ControlesUsuario(
            saturacao=SATURACAO, brilho=BRILHO, intervalo_predicao_segundos=0.5
        )

        for _ in range(300):
            ciclo.processar_amostra(controles=controles)

        # O leitor tem que ter sido consumido 300 vezes, ainda que quase nada tenha
        # virado predição.
        assert leitor.amostras_geradas == 300

    def test_intervalo_zero_preve_a_cada_amostra(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)

        for _ in range(20):
            ciclo.processar_amostra(controles=CONTROLES)

        assert arduino.comandos_enviados == 20


class TestModoFrequencia:
    def test_acumula_antes_de_produzir_resultado(self, modelo: ModeloPreditor) -> None:
        """Blocos são de 500 amostras; com janela de 1000, só o 2º ciclo produz resultado."""
        ciclo, _leitor, arduino = montar_ciclo(modelo, ModoAnalise.FREQUENCIA, tamanho_janela=1000)

        assert ciclo.processar_amostra(controles=CONTROLES) is None
        assert ciclo.amostras_acumuladas == 500
        assert arduino.comandos_enviados == 0, 'Nada deve ir ao Arduino enquanto acumula'

        resultado = ciclo.processar_amostra(controles=CONTROLES)

        assert resultado is not None
        assert arduino.comandos_enviados == 1

    def test_zera_o_acumulador_apos_analisar(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, _arduino = montar_ciclo(modelo, ModoAnalise.FREQUENCIA, tamanho_janela=1000)

        ciclo.processar_amostra(controles=CONTROLES)
        ciclo.processar_amostra(controles=CONTROLES)

        assert ciclo.amostras_acumuladas == 0

    def test_o_resultado_traz_a_janela_bruta_para_a_gravacao(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, _arduino = montar_ciclo(modelo, ModoAnalise.FREQUENCIA, tamanho_janela=1000)

        ciclo.processar_amostra(controles=CONTROLES)
        resultado = ciclo.processar_amostra(controles=CONTROLES)
        assert resultado is not None

        assert resultado.janela is not None
        assert resultado.janela.amostras.size == 1000
        assert resultado.janela.timestamps.size == 1000
        assert resultado.potencia is not None
        assert resultado.faixa_frequencia is not None

    def test_o_intervalo_de_predicao_nao_afeta_a_frequencia(self, modelo: ModeloPreditor) -> None:
        """No modo Frequência a cadência já vem do tamanho da janela: o intervalo é ignorado."""
        ciclo, _leitor, arduino = montar_ciclo(modelo, ModoAnalise.FREQUENCIA, tamanho_janela=1000)
        controles = ControlesUsuario(
            saturacao=SATURACAO, brilho=BRILHO, intervalo_predicao_segundos=999.0
        )

        ciclo.processar_amostra(controles=controles)
        resultado = ciclo.processar_amostra(controles=controles)

        assert resultado is not None
        assert arduino.comandos_enviados == 1

    @pytest.mark.parametrize('tamanho_janela', [1000, 2000, 3000])
    def test_regressao_usa_a_taxa_real_do_leitor_e_nao_o_tamanho_da_janela(
        self, modelo: ModeloPreditor, tamanho_janela: int
    ) -> None:
        """REGRESSÃO (DECISOES_PENDENTES #5), agora no nível do ciclo.

        O `BitalinoSintetico` gera 10 Hz a 1000 Hz de amostragem. Independentemente do
        tamanho da janela, o ciclo tem que reportar ~10 Hz (banda Alpha) — porque a taxa
        vem de `leitor.taxa_amostragem_nominal()`, e não do medidor da interface.

        Antes da correção, a janela de 3000 reportava ~29,3 Hz e classificava como Beta.
        """
        ciclo, leitor, _arduino = montar_ciclo(
            modelo, ModoAnalise.FREQUENCIA, tamanho_janela=tamanho_janela
        )
        assert leitor.taxa_amostragem_nominal() == 1000

        resultado = None
        while resultado is None:
            resultado = ciclo.processar_amostra(controles=CONTROLES)

        assert resultado.metrica_bruta == pytest.approx(10.0, abs=0.5), (
            f'Com janela de {tamanho_janela} o ciclo reportou '
            f'{resultado.metrica_bruta:.2f} Hz para um sinal de 10 Hz.'
        )
        assert resultado.faixa_frequencia is not None
        assert resultado.faixa_frequencia.startswith('Alpha')


class TestParametrosVisual:
    """A engine foi desligada, mas os parâmetros seguem sendo calculados."""

    def test_o_rgb_vem_da_cor_prevista(self, modelo: ModeloPreditor) -> None:
        ciclo, _leitor, _arduino = montar_ciclo(modelo, ModoAnalise.AMPLITUDE)

        resultado = ciclo.processar_amostra(controles=CONTROLES)
        assert resultado is not None

        visual = resultado.parametros_visual
        esperado = f'#{visual.vermelho:02X}{visual.verde:02X}{visual.azul:02X}'
        assert resultado.cor_hex == esperado

    def test_os_seis_parametros_de_shader_ficam_nas_faixas_do_protocolo(self) -> None:
        """Não derivam do sinal: são sorteados. Aqui só garantimos as faixas."""
        for _ in range(50):
            visual = gerar_parametros_visual(rgb=(10, 20, 30))

            assert 100 <= visual.octaves <= 310
            assert 10.0 <= visual.zoom_fator <= 18.5
            assert 1.2 <= visual.zoom_coeficiente <= 1.32
            assert 1 <= visual.brilho_shader <= 3
            assert 1 <= visual.potencia <= 3
            assert 0.0 <= visual.intensidade <= 0.1
