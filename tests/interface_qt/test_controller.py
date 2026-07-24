"""Testes do controller da interface, sem abrir janela.

O `EsquizoController` é um `QObject`, então basta uma `QCoreApplication` viva — nada de
QML, nada de janela. Isso permite cobrir regras que só existem no controller e que nenhum
teste de função pura alcança: o ciclo de vida dos leitores, a propagação do canal ativo e
o travamento do seletor de modo.

Tudo aqui roda com `ESQUIZOCAP_FAKE=tudo`: nenhum teste toca hardware.
"""

import pytest
from PySide6.QtCore import QCoreApplication

from esquizocap.hardware import fabrica
from esquizocap.hardware.modo_aquisicao import ModoAquisicao
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.interface_qt.controller import EsquizoController
from esquizocap.interface_qt.estado import EstadoApp

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


@pytest.fixture
def controlador(
    aplicacao_qt: QCoreApplication, monkeypatch: pytest.MonkeyPatch, modelo: object
) -> EsquizoController:
    monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'tudo')
    configuracao = Configuracao(macs_bitalino=(MAC,))
    return EsquizoController(configuracao=configuracao, modelo=modelo)  # type: ignore[arg-type]


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

    def _com_portas_reais(
        self, controlador: EsquizoController, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
