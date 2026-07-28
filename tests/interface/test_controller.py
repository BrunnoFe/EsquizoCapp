"""Testes do controller da interface, sem abrir janela.

O `EsquizoController` é um `QObject`, então basta uma `QCoreApplication` viva — nada de
QML, nada de janela. Isso permite cobrir regras que só existem no controller e que nenhum
teste de função pura alcança: o ciclo de vida dos leitores, a propagação do canal ativo e
o travamento do seletor de modo.

Tudo aqui roda com `ESQUIZOCAP_FAKE=tudo`: nenhum teste toca hardware.
"""

import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from esquizocap.aplicacao import catalogo_erros
from esquizocap.aplicacao.catalogo_erros import PapelAcao, Severidade, Situacao
from esquizocap.dominio.ciclo_aquisicao import ModoAnalise
from esquizocap.hardware import fabrica
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.modo_aquisicao import ModoAquisicao
from esquizocap.infraestrutura import log as esquizocap_log
from esquizocap.infraestrutura import preferencias
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.infraestrutura.preferencias import Preferencias
from esquizocap.interface.controller import EsquizoController
from esquizocap.interface.estado import EstadoApp

MAC = '20:17:09:18:60:29'


class LeitorEspiao:
    """Registra o que o controller mandou fazer, sem tocar hardware nenhum.

    Não herda de `LeitorBitalino` de propósito: aqui interessa observar as CHAMADAS, e a
    conformidade com o contrato já é garantida pela bateria em `tests/hardware/`.
    """

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.canais_ativos_recebidos: list[int] = []
        self.encerramentos: int = 0

    def definir_canal_ativo(self, canal: int) -> None:
        self.canais_ativos_recebidos.append(canal)

    def encerrar_stream(self) -> None:
        self.encerramentos += 1


@pytest.fixture(scope='module')
def aplicacao_qt() -> QCoreApplication:
    """Uma `QCoreApplication` por módulo: o Qt não deixa criar duas."""
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture(autouse=True)
def preservar_nivel_de_log() -> Iterator[None]:
    """`log.definir_nivel` mexe no logger `esquizocap`, que é global ao processo.

    Sem restaurar, um teste que liga o DEBUG deixaria a suíte inteira em DEBUG a partir
    dali — barulho no output e, pior, um teste que só passa dependendo da ordem.
    """
    logger_app = logging.getLogger('esquizocap')
    nivel_original = logger_app.level
    niveis_dos_handlers = [(handler, handler.level) for handler in logger_app.handlers]
    yield
    logger_app.setLevel(nivel_original)
    for handler, nivel in niveis_dos_handlers:
        handler.setLevel(nivel)


@pytest.fixture
def caminho_preferencias(tmp_path: Path) -> Path:
    """Preferências sempre em `tmp_path`: o controller grava ao encerrar, e o default
    apontaria para `settings/preferencias.json` dentro do repositório."""
    return tmp_path / 'preferencias.json'


@pytest.fixture
def controlador(
    aplicacao_qt: QCoreApplication,
    monkeypatch: pytest.MonkeyPatch,
    modelo: object,
    caminho_preferencias: Path,
) -> EsquizoController:
    monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'tudo')
    configuracao = Configuracao(macs_bitalino=(MAC,))
    return EsquizoController(  # type: ignore[arg-type]
        configuracao=configuracao,
        modelo=modelo,
        caminho_preferencias=caminho_preferencias,
    )


@pytest.fixture
def controlador_sem_variavel(
    aplicacao_qt: QCoreApplication,
    monkeypatch: pytest.MonkeyPatch,
    modelo: object,
    caminho_preferencias: Path,
) -> Callable[[Preferencias], EsquizoController]:
    """Constrói o controller SEM `ESQUIZOCAP_FAKE`, para exercitar o menu de simulação.

    Com a variável definida ela vence a preferência e os controles ficam travados — que é
    o comportamento certo, mas impede testar a troca em si.
    """
    monkeypatch.delenv(fabrica.NOME_VARIAVEL_FAKE, raising=False)
    configuracao = Configuracao(macs_bitalino=(MAC,))

    def construir(preferencias_usuario: Preferencias) -> EsquizoController:
        return EsquizoController(  # type: ignore[arg-type]
            configuracao=configuracao,
            modelo=modelo,
            preferencias_usuario=preferencias_usuario,
            caminho_preferencias=caminho_preferencias,
        )

    return construir


class TestCanalAtivoChegaAoLeitor:
    """No Modo Direto, o canal ativo decide QUAL canal vira microvolts.

    Se a troca de canal não chegar ao leitor, ele segue convertendo o canal antigo e
    entregando o novo em ADU — números plausíveis, cor errada, e nenhum erro. É a falha
    silenciosa que o Modo Direto inteiro existe para evitar.
    """

    def test_trocar_o_canal_avisa_todos_os_leitores(self, controlador: EsquizoController) -> None:
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]

        controlador.canalBitalino = '4'

        for espiao in espioes.values():
            assert espiao.canais_ativos_recebidos == [4]

    def test_trocar_o_canal_nao_reconecta(self, controlador: EsquizoController) -> None:
        """O canal é estado de INTERFACE: mexer nele não pode interromper a aquisição."""
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]

        controlador.canalBitalino = '5'

        for espiao in espioes.values():
            assert espiao.encerramentos == 0

    def test_canal_invalido_nao_derruba_a_interface(self, controlador: EsquizoController) -> None:
        """O combobox só oferece 1 a 6, mas um valor estranho vindo do QML não pode
        estourar dentro de um setter de propriedade."""
        controlador.canalBitalino = 'Selecione o canal ativo do Bitalino'

        assert controlador.canalBitalino == 'Selecione o canal ativo do Bitalino'


class TestSeletorDeCanal:
    """O rótulo mostra a resolução ("3 · 10 bits"), então não serve de valor.

    A escolha vai pela POSIÇÃO na lista, e é aí que um erro passaria despercebido: um
    deslocamento de um faria o operador escolher o canal 3 e adquirir o 4, sem erro nenhum.
    """

    def test_o_seletor_mostra_a_resolucao_de_cada_canal(self, controlador: EsquizoController) -> None:
        rotulos = controlador.canaisBitalinoDisponiveis

        assert len(rotulos) == 6
        assert '10 bits' in rotulos[0]
        assert '6 bits' in rotulos[4], 'o canal 5 tem 6 bits'
        assert 'evite' in rotulos[5].lower(), 'o canal 6 precisa do aviso'

    def test_escolher_pela_posicao_seleciona_o_canal_certo(self, controlador: EsquizoController) -> None:
        controlador.definirCanalPorIndice(2)

        assert controlador.canalBitalino == '3', 'a posição 2 é o canal 3'
        assert controlador.canalBitalinoIndice == 2

    def test_a_posicao_e_o_canal_fecham_o_ciclo(self, controlador: EsquizoController) -> None:
        """Ida e volta: escolher por posição e ler a posição de volta tem que bater, senão o
        dropdown mostra um canal e a aquisição usa outro."""
        for posicao in range(6):
            controlador.definirCanalPorIndice(posicao)

            assert controlador.canalBitalinoIndice == posicao

    def test_posicao_fora_da_lista_e_ignorada(self, controlador: EsquizoController) -> None:
        controlador.definirCanalPorIndice(2)

        controlador.definirCanalPorIndice(99)

        assert controlador.canalBitalino == '3', 'a escolha anterior permanece'

    def test_escolher_um_canal_de_baixa_resolucao_avisa_mas_deixa(self, controlador: EsquizoController) -> None:
        """O eletrodo é físico: negar a leitura de quem plugou no A5 é pior que avisar."""
        controlador.definirCanalPorIndice(4)

        assert controlador.canalBitalino == '5'
        assert 'bits' in controlador.avisoDoCanal

    def test_canal_de_dez_bits_nao_avisa_nada(self, controlador: EsquizoController) -> None:
        controlador.definirCanalPorIndice(0)

        assert controlador.avisoDoCanal == ''

    def test_trocar_o_canal_pela_posicao_avisa_os_leitores(self, controlador: EsquizoController) -> None:
        """O caminho da GUI é `definirCanalPorIndice`; ele precisa propagar como o setter."""
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]

        controlador.definirCanalPorIndice(3)

        for espiao in espioes.values():
            assert espiao.canais_ativos_recebidos == [4]


class TestSeletorDeModo:
    def test_com_bitalino_simulado_o_seletor_fica_travado(self, controlador: EsquizoController) -> None:
        """Com o fake, o mesmo leitor responde pelos dois modos: a escolha não teria efeito,
        e fingir que tem é pior do que desabilitar."""
        assert controlador.seletorDeModoHabilitado is False
        assert 'simulado' in controlador.avisoDoModoAquisicao.lower()

    def test_o_seletor_trava_enquanto_conectado(self, controlador: EsquizoController) -> None:
        controlador._leitores_por_modo = {  # type: ignore[assignment]
            modo: LeitorEspiao(modo.name) for modo in ModoAquisicao
        }
        controlador._conexoes.bitalino_conectado = True

        assert controlador.seletorDeModoHabilitado is False
        assert 'desconecte' in controlador.avisoDoModoAquisicao.lower()

    def test_o_seletor_trava_durante_a_tentativa_de_conexao(self, controlador: EsquizoController) -> None:
        """A conexão roda numa thread auxiliar e demora. Trocar de modo nesse intervalo faria
        a aquisição subir com um leitor que nunca conectou."""
        controlador._leitores_por_modo = {  # type: ignore[assignment]
            modo: LeitorEspiao(modo.name) for modo in ModoAquisicao
        }
        controlador._conectando_bitalino = True

        assert controlador.seletorDeModoHabilitado is False

    def test_os_dois_modos_sao_oferecidos(self, controlador: EsquizoController) -> None:
        assert controlador.modosAquisicaoDisponiveis == [modo.value for modo in ModoAquisicao]

    def test_o_padrao_e_o_modo_comprovado(self, controlador: EsquizoController) -> None:
        """Quem quiser o Modo Direto escolhe de propósito."""
        assert controlador.modoAquisicao == ModoAquisicao.OPENSIGNALS.value


class TestPortasSeriais:
    """A porta do BITalino não pode ser oferecida ao Arduino.

    As duas conexões disputariam o mesmo recurso e nenhuma funcionaria — e, pior, o
    operador não teria como saber por quê: as portas Bluetooth têm todas a mesma descrição.
    """

    HWID_BITALINO = r'BTHENUM\{0000}_LOCALMFG&0002\7&2B886E8&2&201709186029_C00000000'

    def _com_portas_reais(self, controlador: EsquizoController, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simula uma máquina com o BITalino na COM6 e um Arduino na COM10."""
        from esquizocap.hardware import portas_bluetooth

        monkeypatch.setattr(
            portas_bluetooth,
            'listar_portas_do_sistema',
            lambda: [('COM6', self.HWID_BITALINO), ('COM10', 'USB VID:PID=1A86:7523')],
        )
        controlador._portas_seriais_disponiveis = ['COM6', 'COM10 - CH340']

    def test_a_porta_do_bitalino_sai_da_lista_do_arduino(
        self, controlador: EsquizoController, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._com_portas_reais(controlador, monkeypatch)
        controlador.modoAquisicao = ModoAquisicao.DIRETO.value

        oferecidas = controlador.portasSeriaisDisponiveis

        assert 'COM6' not in oferecidas
        assert 'COM10 - CH340' in oferecidas

    def test_no_modo_opensignals_nenhuma_porta_e_escondida(
        self, controlador: EsquizoController, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem Modo Direto não há porta do BITalino a excluir — o Arduino pode usar todas."""
        self._com_portas_reais(controlador, monkeypatch)
        controlador.modoAquisicao = ModoAquisicao.OPENSIGNALS.value

        assert 'COM6' in controlador.portasSeriaisDisponiveis


class TestTaxaAcordada:
    def test_o_dropdown_so_aparece_no_modo_direto(self, controlador: EsquizoController) -> None:
        """No Modo OpenSignals quem fixa a taxa é o OpenSignals; oferecer a escolha aqui
        seria mentir sobre o que ela faz."""
        controlador.modoAquisicao = ModoAquisicao.OPENSIGNALS.value
        assert controlador.taxaAmostragemVisivel is False

        controlador.modoAquisicao = ModoAquisicao.DIRETO.value
        assert controlador.taxaAmostragemVisivel is True

    def test_trocar_para_frequencia_conserta_uma_taxa_que_deixou_de_servir(
        self, controlador: EsquizoController
    ) -> None:
        """O operador escolhe 10 Hz em Amplitude e depois muda para Frequência. Deixar a
        seleção inválida só barraria o botão, sem explicar; subir a taxa e avisar resolve."""
        controlador.definirModoAnalise(ModoAnalise.AMPLITUDE.value)
        controlador.definirTaxaAmostragem(10)
        assert controlador.taxaAmostragem == '10'

        controlador.definirModoAnalise(ModoAnalise.FREQUENCIA.value)

        assert int(controlador.taxaAmostragem) >= 100
        assert controlador.taxaAmostragem in controlador.taxasSelecionaveis

    def test_o_dropdown_sempre_oferece_as_quatro_taxas_do_dispositivo(self, controlador: EsquizoController) -> None:
        """A lista não encolhe com o modo de predição — o que muda é quais estão
        habilitadas. Ver `test_as_taxas_invalidas_aparecem_desabilitadas_e_nao_somem`."""
        for modo in (ModoAnalise.AMPLITUDE.value, ModoAnalise.FREQUENCIA.value):
            controlador.definirModoAnalise(modo)

            assert controlador.taxasSelecionaveis == ['1', '10', '100', '1000']

    def test_a_duracao_da_janela_acompanha_a_taxa(self, controlador: EsquizoController) -> None:
        """O ponto do indicador: a mesma janela vale segundos ou dezenas deles conforme a
        taxa, e é o que faz a instalação parecer travada."""
        controlador.modoAquisicao = ModoAquisicao.DIRETO.value
        controlador.definirModoAnalise(ModoAnalise.FREQUENCIA.value)
        controlador.tamanhoJanelaAmostras = 1000

        controlador.definirTaxaAmostragem(1000)
        assert '1.0 s' in controlador.duracaoDaJanela

        controlador.definirTaxaAmostragem(100)
        assert '10.0 s' in controlador.duracaoDaJanela

    def test_a_taxa_escolhida_chega_ao_leitor(self, controlador: EsquizoController) -> None:
        """O teste que fecha o circuito: sem ele, uma regressão para a taxa padrão passaria
        despercebida — o leitor sintético descarta o parâmetro, então nenhum outro teste da
        suíte notaria."""
        conexoes: list[dict[str, object]] = []

        class ConectorEspiao:
            def conectar(self, **argumentos: object) -> None:
                conexoes.append(argumentos)

        controlador._conector_bitalino = ConectorEspiao()  # type: ignore[assignment]
        controlador.modoAquisicao = ModoAquisicao.DIRETO.value
        controlador.definirModoAnalise(ModoAnalise.AMPLITUDE.value)
        controlador.definirTaxaAmostragem(10)

        controlador._conectar_bitalino()

        assert conexoes[-1]['taxa_amostragem_hz'] == 10

    def test_a_taxa_nao_e_editavel_com_o_dispositivo_conectado(self, controlador: EsquizoController) -> None:
        """A taxa é acordada no `conectar`. Aceitar a troca depois seria mentir: nada mudaria
        até reconectar, e a duração exibida passaria a descrever uma taxa que não está em uso."""
        controlador._leitores_por_modo = {  # type: ignore[assignment]
            modo: LeitorEspiao(modo.name) for modo in ModoAquisicao
        }
        controlador._conexoes.bitalino_conectado = True

        assert controlador.taxaAmostragemEditavel is False

    def test_as_taxas_invalidas_aparecem_desabilitadas_e_nao_somem(self, controlador: EsquizoController) -> None:
        """Sumir com a opção esconde a informação: quem procura 10 Hz precisa ver que ela
        existe e está indisponível, não achar que a aplicação a esqueceu."""
        controlador.definirModoAnalise(ModoAnalise.FREQUENCIA.value)

        assert controlador.taxasSelecionaveis == ['1', '10', '100', '1000']
        assert controlador.taxasDesabilitadas == ['1', '10']

    def test_em_amplitude_nenhuma_taxa_fica_desabilitada(self, controlador: EsquizoController) -> None:
        controlador.definirModoAnalise(ModoAnalise.AMPLITUDE.value)

        assert controlador.taxasDesabilitadas == []

    def test_o_ajuste_automatico_escolhe_a_taxa_padrao_e_nao_a_menor_valida(
        self, controlador: EsquizoController
    ) -> None:
        """A menor válida é justamente a que deixa Gamma na borda de Nyquist. Cair nela por
        acidente daria ao operador a pior opção ainda aceitável."""
        controlador.definirModoAnalise(ModoAnalise.AMPLITUDE.value)
        controlador.definirTaxaAmostragem(1)

        controlador.definirModoAnalise(ModoAnalise.FREQUENCIA.value)

        assert controlador.taxaAmostragem == '1000'
        assert controlador.avisoDeTaxa == '', 'a taxa padrão não deve disparar aviso'

    def test_sem_taxa_conhecida_a_duracao_fica_vazia(self, controlador: EsquizoController) -> None:
        """No Modo OpenSignals desconectado ninguém sabe a taxa — inventar um número seria
        pior que não mostrar nada."""
        controlador.modoAquisicao = ModoAquisicao.OPENSIGNALS.value
        controlador._conexoes.bitalino_conectado = False

        assert controlador.duracaoDaJanela == ''


class TestEncerramento:
    def test_encerrar_tudo_fecha_todos_os_leitores(self, controlador: EsquizoController) -> None:
        """Fecha o de TODOS os modos, não só o escolhido: o modo pode ter mudado entre
        conectar e sair, e uma porta serial esquecida fica presa até o processo morrer."""
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]

        controlador.encerrarTudo()

        for espiao in espioes.values():
            assert espiao.encerramentos >= 1

    def test_o_estado_inicial_pede_configuracao(self, controlador: EsquizoController) -> None:
        assert controlador._estado_app is EstadoApp.CONFIGURANDO


ConstrutorDeControlador = Callable[[Preferencias], EsquizoController]


class TestModoSimulacaoPelaInterface:
    """Trocar entre hardware real e simulado sem reiniciar o processo.

    É a única operação da app que substitui os objetos de borda em pleno voo. Errar aqui
    não levanta exceção: sobra um leitor órfão segurando a porta, ou os leitores novos
    convertem um canal diferente do que a tela mostra.
    """

    def test_a_preferencia_decide_o_hardware_do_arranque(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias(componentes_simulados=frozenset({'arduino'})))

        assert isinstance(controlador._arduino, ArduinoFake)
        assert controlador.arduinoSimulado is True
        assert controlador.bitalinoSimulado is False

    def test_sem_preferencia_o_hardware_e_real(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """O default TEM que ser real: simular por acidente é o pior cenário."""
        controlador = controlador_sem_variavel(Preferencias())

        assert isinstance(controlador._arduino, ArduinoSerial)
        assert controlador.emModoSimulacao is False

    def test_ligar_a_simulacao_troca_os_objetos_na_hora(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        arduino_antes = controlador._arduino

        controlador.definirSimulacao('arduino', True)

        assert controlador._arduino is not arduino_antes
        assert isinstance(controlador._arduino, ArduinoFake)
        assert controlador.arduinoSimulado is True

    def test_desligar_a_simulacao_volta_ao_hardware_real(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """O caminho de volta é o que hoje exige reiniciar o processo."""
        controlador = controlador_sem_variavel(Preferencias(componentes_simulados=frozenset({'bitalino'})))

        controlador.definirSimulacao('bitalino', False)

        assert controlador.bitalinoSimulado is False
        assert isinstance(controlador._leitores_por_modo[ModoAquisicao.OPENSIGNALS], BitalinoLSL)

    def test_desligar_a_simulacao_reabilita_o_seletor_de_modo(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """Sob fake o seletor fica travado porque um leitor só responde pelos dois modos.
        Essa trava era decisão de arranque e agora precisa acompanhar a troca."""
        controlador = controlador_sem_variavel(Preferencias(componentes_simulados=frozenset({'bitalino'})))
        assert controlador.seletorDeModoHabilitado is False

        controlador.definirSimulacao('bitalino', False)

        assert controlador.seletorDeModoHabilitado is True

    def test_ligar_a_simulacao_do_bitalino_trava_o_seletor_de_modo(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias())

        controlador.definirSimulacao('bitalino', True)

        assert isinstance(controlador._leitores_por_modo[ModoAquisicao.DIRETO], BitalinoSintetico)
        assert controlador.seletorDeModoHabilitado is False

    def test_a_reconstrucao_fecha_os_leitores_antigos(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """Um leitor não encerrado seguraria porta serial ou socket até o processo morrer,
        e a próxima conexão falharia sem motivo aparente."""
        controlador = controlador_sem_variavel(Preferencias())
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]

        controlador.definirSimulacao('bitalino', True)

        for espiao in espioes.values():
            assert espiao.encerramentos >= 1

    def test_o_canal_ativo_e_reaplicado_nos_leitores_novos(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """A falha silenciosa desta feature: os leitores novos nascem no canal 1 enquanto a
        tela mostra outro. Números plausíveis, cor errada, nenhum erro."""
        controlador = controlador_sem_variavel(Preferencias())
        controlador.canalBitalino = '5'

        controlador.definirSimulacao('bitalino', True)
        espioes = {modo: LeitorEspiao(modo.name) for modo in ModoAquisicao}
        controlador._leitores_por_modo = espioes  # type: ignore[assignment]
        controlador._reaplicar_canal_ativo_nos_leitores()

        assert controlador.canalBitalino == '5'
        for espiao in espioes.values():
            assert espiao.canais_ativos_recebidos == [5]

    def test_a_reconstrucao_marca_tudo_como_desconectado(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """Os objetos novos nunca conectaram; herdar o estado anterior mostraria um ponto
        verde ao lado de um dispositivo que não está aberto."""
        controlador = controlador_sem_variavel(Preferencias())

        controlador.definirSimulacao('arduino', True)

        assert controlador._conexoes.arduino_conectado is False
        assert controlador._conexoes.bitalino_conectado is False

    def test_componente_desconhecido_e_ignorado(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        arduino_antes = controlador._arduino

        controlador.definirSimulacao('godot', True)

        assert controlador._arduino is arduino_antes


class TestTravaDaSimulacao:
    """A troca só pode acontecer com tudo desconectado e parado."""

    def test_travada_com_o_bitalino_conectado(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        controlador._conexoes.bitalino_conectado = True

        assert controlador.podeAlterarSimulacao is False
        assert 'Desconecte' in controlador.motivoSimulacaoTravada

    def test_travada_com_o_arduino_conectado(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        controlador._conexoes.arduino_conectado = True

        assert controlador.podeAlterarSimulacao is False

    def test_travada_durante_a_aquisicao(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        controlador._estado_app = EstadoApp.ADQUIRINDO

        assert controlador.podeAlterarSimulacao is False
        assert 'Pare a aquisição' in controlador.motivoSimulacaoTravada

    def test_a_troca_recusada_nao_mexe_no_hardware(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())
        controlador._conexoes.bitalino_conectado = True
        arduino_antes = controlador._arduino

        controlador.definirSimulacao('arduino', True)

        assert controlador._arduino is arduino_antes
        assert controlador.toastAberto, 'a recusa precisa aparecer na tela, não só no log'
        assert controlador.toastSituacao == Situacao.SIMULACAO_BLOQUEADA.value

    def test_a_variavel_de_ambiente_trava_os_controles(self, controlador: EsquizoController) -> None:
        """`controlador` roda com ESQUIZOCAP_FAKE=tudo: o ambiente vence, e o menu tem que
        dizer isso em vez de oferecer um botão que não faz nada."""
        assert controlador.podeAlterarSimulacao is False
        assert fabrica.NOME_VARIAVEL_FAKE in controlador.motivoSimulacaoTravada
        assert controlador.emModoSimulacao is True


class TestPersistenciaDasPreferencias:
    def test_a_aparencia_salva_volta_no_proximo_arranque(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias(aparencia={'quantidade_leds': 90.0}))

        assert controlador.quantidadeLeds == 90

    def test_valor_fora_da_faixa_e_limitado_ao_aplicar(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """A infraestrutura não conhece as faixas; o clamp é responsabilidade daqui."""
        controlador = controlador_sem_variavel(Preferencias(aparencia={'quantidade_leds': 99999.0}))

        assert controlador.quantidadeLeds == 120

    def test_slider_desconhecido_nao_derruba_o_arranque(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """Uma preferência de uma versão anterior não pode impedir a instalação de subir."""
        controlador = controlador_sem_variavel(Preferencias(aparencia={'slider_que_nao_existe_mais': 1.0}))

        assert controlador.quantidadeLeds == 60

    def test_encerrar_grava_a_aparencia_em_disco(
        self, controlador_sem_variavel: ConstrutorDeControlador, caminho_preferencias: Path
    ) -> None:
        """O debounce ainda estaria contando quando a janela fecha."""
        controlador = controlador_sem_variavel(Preferencias())
        controlador.quantidadeLeds = 42

        controlador.encerrarTudo()

        assert preferencias.carregar(caminho_preferencias).aparencia['quantidade_leds'] == 42

    def test_a_escolha_de_simulacao_e_gravada_na_hora(
        self, controlador_sem_variavel: ConstrutorDeControlador, caminho_preferencias: Path
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias())

        controlador.definirSimulacao('arduino', True)

        assert preferencias.carregar(caminho_preferencias).componentes_simulados == frozenset({'arduino'})

    def test_restaurar_aparencia_volta_aos_padroes(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias(aparencia={'quantidade_leds': 90.0}))

        controlador.restaurarAparenciaPadrao()

        assert controlador.quantidadeLeds == 60

    def test_preferencias_de_arranque_chegam_a_selecao(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """Guardar a preferência sem aplicá-la no arranque a tornaria decorativa."""
        controlador = controlador_sem_variavel(Preferencias(gravar_por_padrao=True, iniciar_em_tela_cheia=True))

        assert controlador._selecao.gravar_aquisicao is True
        assert controlador.telaCheia is True

    def test_alternar_tela_cheia_vai_e_volta(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """O ESC e o F11 do QML chamam isto; a janela só espelha `telaCheia`."""
        controlador = controlador_sem_variavel(Preferencias(iniciar_em_tela_cheia=False))

        controlador.alternarTelaCheia()
        assert controlador.telaCheia is True

        controlador.alternarTelaCheia()
        assert controlador.telaCheia is False

    def test_nivel_de_log_salvo_e_aplicado_no_arranque(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias(nivel_log='DEBUG'))

        assert controlador.nivelLog == 'DEBUG'
        assert logging.getLogger('esquizocap').level == logging.DEBUG

    def test_nivel_de_log_desconhecido_nao_derruba_o_arranque(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias(nivel_log='VERBOSO'))

        assert controlador.nivelLog == 'VERBOSO', 'o valor guardado é preservado'


class TestNomeDoArquivoDeGravacao:
    def test_a_previa_reflete_o_formato_escolhido(self, controlador: EsquizoController) -> None:
        """A prévia é o que denuncia um marcador digitado errado ANTES da gravação."""
        controlador.definirCanalPorIndice(3)

        controlador.definirFormatoNomeGravacao('sessao_{canal}_{taxa}')

        assert controlador.previaNomeGravacao == 'sessao_A4_1000Hz.xlsx'

    def test_a_previa_acompanha_a_troca_de_canal(self, controlador: EsquizoController) -> None:
        controlador.definirFormatoNomeGravacao('{canal}')
        controlador.definirCanalPorIndice(0)
        assert controlador.previaNomeGravacao == 'A1.xlsx'

        controlador.definirCanalPorIndice(4)

        assert controlador.previaNomeGravacao == 'A5.xlsx'

    def test_formato_invalido_nao_estoura_na_previa(self, controlador: EsquizoController) -> None:
        controlador.definirFormatoNomeGravacao('{nao_existe}')

        assert controlador.previaNomeGravacao.startswith('Gravação ')

    def test_o_formato_e_persistido(
        self, controlador_sem_variavel: ConstrutorDeControlador, caminho_preferencias: Path
    ) -> None:
        controlador = controlador_sem_variavel(Preferencias())

        controlador.definirFormatoNomeGravacao('coleta_{data}')
        controlador.encerrarTudo()

        assert preferencias.carregar(caminho_preferencias).formato_nome_gravacao == 'coleta_{data}'


class TestGeometriaDaJanela:
    def test_guarda_e_devolve_a_geometria(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())

        controlador.salvarGeometriaJanela(120, 80, 1000, 700)

        assert controlador.temGeometriaSalva is True
        assert (controlador.janelaX, controlador.janelaY) == (120, 80)
        assert (controlador.janelaLargura, controlador.janelaAltura) == (1000, 700)

    def test_nao_guarda_nada_com_a_opcao_desligada(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias(lembrar_geometria_janela=False))

        controlador.salvarGeometriaJanela(120, 80, 1000, 700)

        assert controlador.temGeometriaSalva is False

    def test_desligar_a_opcao_descarta_a_geometria_guardada(
        self, controlador_sem_variavel: ConstrutorDeControlador
    ) -> None:
        """Manter a geometria antiga faria a opção parecer quebrada ao ser religada depois."""
        controlador = controlador_sem_variavel(
            Preferencias(geometria_janela={'x': 1, 'y': 2, 'largura': 3, 'altura': 4})
        )

        controlador.definirLembrarGeometriaJanela(False)

        assert controlador._preferencias.geometria_janela == {}

    def test_geometria_incompleta_nao_conta_como_salva(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        """Restaurar com altura faltando abriria a janela com dimensão zero."""
        controlador = controlador_sem_variavel(Preferencias(geometria_janela={'x': 1, 'y': 2}))

        assert controlador.temGeometriaSalva is False


class TestDiagnostico:
    def test_reune_o_que_sempre_e_perguntado_de_volta(self, controlador: EsquizoController) -> None:
        texto = controlador.textoDiagnostico

        for esperado in ('Modo de aquisição', 'Taxa acordada', 'Canal ativo', 'Simulação', 'Arquivo de log'):
            assert esperado in texto

    def test_diz_quando_esta_simulado(self, controlador: EsquizoController) -> None:
        """O `controlador` roda com ESQUIZOCAP_FAKE=tudo."""
        assert 'arduino' in controlador.textoDiagnostico
        assert 'bitalino' in controlador.textoDiagnostico

    def test_diz_quando_o_hardware_e_real(self, controlador_sem_variavel: ConstrutorDeControlador) -> None:
        controlador = controlador_sem_variavel(Preferencias())

        assert 'hardware real' in controlador.textoDiagnostico

    def test_copiar_sem_area_de_transferencia_nao_estoura(self, controlador: EsquizoController) -> None:
        """Sob `QCoreApplication` não há área de transferência; um recurso de conveniência
        não pode derrubar a aplicação."""
        controlador.copiarDiagnostico()

    def test_abrir_log_sem_arquivo_avisa_em_vez_de_estourar(
        self, controlador: EsquizoController, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(esquizocap_log, 'arquivo_atual', lambda: None)

        controlador.abrirLogAtual()

        assert controlador.toastAberto
        assert controlador.toastSituacao == Situacao.SEM_ARQUIVO_DE_LOG.value


class TestMensagensAoUsuario:
    """As duas superfícies de mensagem e o que decide entre elas.

    O que existia antes era um banner só, de altura fixa, que cortava a metade acionável do
    texto e era sobrescrito em silêncio pela mensagem seguinte. Estes testes fixam o
    comportamento que substituiu isso.
    """

    def test_erro_grave_abre_a_caixa_e_nao_o_toast(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('porta ocupada')))

        assert controlador.caixaAberta
        assert not controlador.toastAberto
        assert controlador.caixaSituacao == Situacao.FALHA_CONEXAO_ARDUINO.value
        assert controlador.caixaSeveridade == Severidade.ERRO.value

    def test_recado_leve_vira_toast_e_nao_a_caixa(self, controlador: EsquizoController) -> None:
        """Não abrir uma pasta não pode congelar a tela no meio de uma performance."""
        controlador._reportar(catalogo_erros.pasta_logs_inacessivel(Path('C:/logs')))

        assert controlador.toastAberto
        assert not controlador.caixaAberta

    def test_um_toast_nao_apaga_uma_caixa_por_ler(self, controlador: EsquizoController) -> None:
        """REGRESSÃO: com uma variável só, o recado seguinte apagava o erro anterior."""
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('x')))
        controlador._reportar(catalogo_erros.sem_arquivo_de_log())

        assert controlador.caixaAberta, 'o recado passageiro não pode engolir o erro'
        assert controlador.toastAberto

    def test_a_mensagem_chega_inteira_na_propriedade(self, controlador: EsquizoController) -> None:
        """O defeito central do banner antigo: a remediação vinha depois da linha em branco
        e nunca cabia nos 40px de altura fixa."""
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('porta ocupada')))

        assert '\n\n' in controlador.caixaMensagem
        assert len(controlador.caixaMensagem.split('\n\n')[1]) > 0

    def test_as_acoes_atravessam_com_papel_e_rotulo(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('x')))

        assert controlador.caixaAcoes == [{'papel': PapelAcao.ACEITAR.value, 'rotulo': 'OK'}]

    def test_responder_fecha_a_caixa(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('x')))

        controlador.responderCaixa(PapelAcao.ACEITAR.value)

        assert not controlador.caixaAberta

    def test_sem_caixa_as_propriedades_ficam_vazias(self, controlador: EsquizoController) -> None:
        """A view lê estas propriedades mesmo com a caixa fechada; `None` viraria aviso do
        motor QML, que é o que `test_qml_carrega` proíbe."""
        assert controlador.caixaTitulo == ''
        assert controlador.caixaMensagem == ''
        assert controlador.caixaDetalhe == ''
        assert controlador.caixaAcoes == []

    def test_caixa_fechada_e_considerada_dispensavel(self, controlador: EsquizoController) -> None:
        """Sem isto, a view começaria com um ESC inibido por uma caixa que nem existe."""
        assert controlador.caixaDispensavel

    def test_falha_inesperada_nao_e_dispensavel(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_inesperada(RuntimeError('bug')))

        assert controlador.caixaAberta
        assert not controlador.caixaDispensavel

    def test_fechar_toast_limpa_so_o_toast(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_conexao_arduino(OSError('x')))
        controlador._reportar(catalogo_erros.sem_arquivo_de_log())

        controlador.fecharToast()

        assert not controlador.toastAberto
        assert controlador.caixaAberta

    def test_detalhe_tecnico_chega_para_ser_copiado(self, controlador: EsquizoController) -> None:
        controlador._reportar(catalogo_erros.falha_conexao_arduino(PermissionError('porta ocupada')))

        assert 'PermissionError' in controlador.caixaDetalhe
