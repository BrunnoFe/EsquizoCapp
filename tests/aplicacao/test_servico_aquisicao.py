"""Testes da thread de aquisição: produtor/consumidor, parada e propagação de erro.

Testar concorrência exige cuidado com o relógio. A estratégia aqui é NÃO depender de
`sleep` para sincronizar: cada teste espera por uma CONDIÇÃO (um evento chegou, a thread
morreu), com um limite de tempo generoso. Um teste que dorme 0,1 s e torce para o
resultado ter chegado é um teste que falha aleatoriamente na máquina de outra pessoa.
"""

import time

import pytest
from conftest import conectar_leitor

from esquizocap.aplicacao.servico_aquisicao import (
    EventoErro,
    EventoParado,
    EventoResultado,
    ServicoAquisicao,
)
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ModoAnalise
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.contratos import ErroStreamPerdido, LeitorBitalino

PORTA_VALIDA = 'COM99 - Arduino simulado (fake)'
CONTROLES = ControlesUsuario(saturacao=255, brilho=120)

# Folga generosa: o objetivo é evitar que o teste trave para sempre, não medir desempenho.
LIMITE_SEGUNDOS = 5.0


class LeitorQueCai(BitalinoSintetico):
    """Um leitor que funciona por N amostras e depois perde o stream.

    Simula o cabo arrancado / OpenSignals fechado no meio da aquisição — o caminho de
    erro que, sem esta classe, só seria exercitável desplugando hardware na mão.
    """

    def __init__(self, cair_apos: int) -> None:
        super().__init__()
        self._cair_apos = cair_apos

    def ler_amostra(self, timeout: float) -> tuple[list[float], float] | tuple[None, None]:
        if self.amostras_geradas >= self._cair_apos:
            raise ErroStreamPerdido('Stream do BITalino perdido (simulado)')
        return super().ler_amostra(timeout=timeout)


def montar_servico(
    modelo: ModeloPreditor,
    modo: ModoAnalise = ModoAnalise.AMPLITUDE,
    gravar: bool = False,
    leitor: LeitorBitalino | None = None,
    tamanho_fila: int = 64,
) -> tuple[ServicoAquisicao, ArduinoFake]:
    leitor = leitor if leitor is not None else BitalinoSintetico()
    arduino = ArduinoFake()
    conectar_leitor(leitor)
    arduino.conectar(porta=PORTA_VALIDA, baudrate=9600)

    ciclo = CicloAquisicao(
        leitor=leitor,
        arduino=arduino,
        modelo=modelo,
        modo_analise=modo,
        canal_bitalino=1,
        modo_luminosidade=2,
        tamanho_amostra_frequencia=1000,
    )

    servico = ServicoAquisicao(ciclo=ciclo, gravar=gravar, tamanho_fila=tamanho_fila)
    servico.atualizar_controles(CONTROLES)
    return servico, arduino


def coletar_ate(servico: ServicoAquisicao, condicao, limite: float = LIMITE_SEGUNDOS) -> list:
    """Drena a fila como a GUI faria, até `condicao(eventos)` ser verdade ou estourar o limite.

    Substitui o `sleep` cego: o teste avança assim que o que ele espera acontece.
    """
    eventos: list = []
    prazo = time.monotonic() + limite

    while time.monotonic() < prazo:
        eventos.extend(servico.drenar())
        if condicao(eventos):
            return eventos
        time.sleep(0.005)

    return eventos


class TestCicloDeVida:
    def test_produz_resultados_numa_thread(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo)
        servico.iniciar()

        eventos = coletar_ate(servico, lambda e: len(e) >= 5)
        servico.parar()

        assert any(isinstance(evento, EventoResultado) for evento in eventos)
        assert servico.esta_rodando is False

    def test_parar_publica_evento_parado(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo)
        servico.iniciar()

        coletar_ate(servico, lambda e: len(e) >= 1)
        servico.parar()

        # O EventoParado é a ÚLTIMA coisa que a thread publica: ele pode ainda estar na
        # fila depois do join.
        finais = coletar_ate(servico, lambda e: any(isinstance(x, EventoParado) for x in e))
        assert any(isinstance(evento, EventoParado) for evento in finais)

    def test_a_thread_realmente_morre(self, modelo: ModeloPreditor) -> None:
        """Uma thread que não morre no `parar()` deixa o hardware aberto e o app pendurado."""
        servico, _arduino = montar_servico(modelo)
        servico.iniciar()
        assert servico.esta_rodando is True

        servico.parar()

        assert servico.esta_rodando is False

    def test_iniciar_duas_vezes_nao_cria_duas_threads(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo)
        servico.iniciar()
        primeira = servico._thread

        servico.iniciar()

        assert servico._thread is primeira
        servico.parar()

    def test_parar_sem_ter_iniciado_nao_explode(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo)
        servico.parar()  # não deve levantar nada


class TestPropagacaoDeErro:
    def test_o_stream_perdido_vira_evento_e_nao_mata_a_thread_em_silencio(self, modelo: ModeloPreditor) -> None:
        """REGRESSÃO: um erro dentro da thread NÃO pode sumir.

        Sem isto, o BITalino cair no meio da aquisição faria a thread morrer calada: a
        GUI seguiria pintando o último valor para sempre, sem nenhum aviso.
        """
        servico, _arduino = montar_servico(modelo, leitor=LeitorQueCai(cair_apos=10))
        servico.iniciar()

        eventos = coletar_ate(servico, lambda e: any(isinstance(x, EventoErro) for x in e))

        erros = [evento for evento in eventos if isinstance(evento, EventoErro)]
        assert len(erros) == 1
        assert isinstance(erros[0].erro, ErroStreamPerdido)
        assert 'OpenSignals' in erros[0].mensagem_usuario

    def test_apos_o_erro_ainda_vem_o_evento_parado(self, modelo: ModeloPreditor) -> None:
        """É o EventoParado que devolve a GUI ao estado ocioso e FECHA O HARDWARE.

        Se ele não viesse no caminho de erro, uma queda do BITalino deixaria a porta
        serial aberta e a interface travada em "Parar aquisição".
        """
        servico, _arduino = montar_servico(modelo, leitor=LeitorQueCai(cair_apos=10))
        servico.iniciar()

        eventos = coletar_ate(servico, lambda e: any(isinstance(x, EventoParado) for x in e))

        assert any(isinstance(evento, EventoErro) for evento in eventos)
        assert any(isinstance(evento, EventoParado) for evento in eventos)
        assert servico.esta_rodando is False


class TestGravacao:
    def test_a_gravacao_e_acumulada_pela_thread(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo, gravar=True)
        servico.iniciar()

        coletar_ate(servico, lambda e: len(e) >= 20)
        servico.parar()

        assert len(servico.gravacao) >= 20

    def test_sem_gravar_nada_e_acumulado(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo, gravar=False)
        servico.iniciar()

        coletar_ate(servico, lambda e: len(e) >= 10)
        servico.parar()

        assert servico.gravacao == []

    def test_a_fila_cheia_nao_perde_gravacao(self, modelo: ModeloPreditor) -> None:
        """REGRESSÃO: o descarte por fila cheia só pode atingir o DESENHO.

        A fila é minúscula aqui (2) e ninguém drena, então ela vive cheia — é o cenário
        de uma GUI que não acompanha o ritmo. A gravação tem que sair intacta mesmo assim.
        Se alguém mover a gravação de volta para a GUI, este teste cai.
        """
        servico, _arduino = montar_servico(modelo, gravar=True, tamanho_fila=2)
        servico.iniciar()

        prazo = time.monotonic() + 1.0
        while time.monotonic() < prazo and len(servico.gravacao) < 50:
            time.sleep(0.005)

        servico.parar()

        assert len(servico.gravacao) >= 50, 'A gravação foi vítima do descarte da fila de desenho'


class TestControles:
    def test_a_troca_de_controles_chega_na_thread(self, modelo: ModeloPreditor) -> None:
        servico, _arduino = montar_servico(modelo)
        servico.iniciar()

        coletar_ate(servico, lambda e: len(e) >= 3)
        servico.atualizar_controles(ControlesUsuario(saturacao=10, brilho=20))

        eventos = coletar_ate(
            servico,
            lambda e: any(isinstance(x, EventoResultado) and x.resultado.saturacao == 10 for x in e),
        )
        servico.parar()

        atualizados = [
            evento for evento in eventos if isinstance(evento, EventoResultado) and evento.resultado.saturacao == 10
        ]
        assert atualizados, 'A thread continuou usando os controles antigos'
        assert atualizados[0].resultado.brilho == 20


@pytest.mark.parametrize('modo', [ModoAnalise.AMPLITUDE, ModoAnalise.FREQUENCIA])
def test_os_dois_modos_rodam_na_thread(modelo: ModeloPreditor, modo: ModoAnalise) -> None:
    servico, arduino = montar_servico(modelo, modo=modo)
    servico.iniciar()

    coletar_ate(servico, lambda e: any(isinstance(x, EventoResultado) for x in e))
    servico.parar()

    assert arduino.comandos_enviados >= 1
