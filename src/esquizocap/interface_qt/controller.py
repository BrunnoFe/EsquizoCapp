"""EsquizoCap — controller (bridge) para a view QML.

Fonte única de verdade da interface: liga a aquisição real (`aplicacao.ServicoAquisicao`,
rodando numa thread própria) à tela, e nada mais. A view NUNCA toca no domínio/hardware —
só lê propriedades e chama slots daqui, mantendo a separação de camadas do projeto.

Este arquivo é propositalmente uma FACHADA FINA: o estado propriamente dito vive em
dataclasses tipados (`estado_configuracao.ConfiguracaoSelecionada`,
`estado_aparencia_visual.AparenciaVisual`, `estado_ao_vivo.LeituraAoVivo`,
`estado_conexoes_hardware.EstadoConexoesHardware`), e a lógica que não é "colar Qt"
vive em módulos próprios (`simulador_fita_led`, `conexao_bitalino_assincrona`,
`gerenciador_gravacao_pendente`, `cores_visuais`, `bandas_eeg`). O que sobra aqui é:
sinalização Qt, orquestração da aquisição, e a definição das `Property`/`Slot` que a
QML enxerga.

A ponte com a thread de aquisição segue o mesmo desenho que a antiga `janela_principal.py`
usava com o `after()` do Tk: um `QTimer` dreno a fila publicada pelo `ServicoAquisicao` a
cada `INTERVALO_DRENAGEM_MS`, e nunca bloqueia — se não houver evento, sai na hora. A única
exceção é `conectar()` do BITalino, que bloqueia (resolução LSL); por isso roda numa
`threading.Thread` auxiliar (via `ConectorBitalinoAssincrono`), que sinaliza a volta à GUI
thread através de um sinal Qt (sinais Qt são thread-safe para cruzar de thread, viram
`Qt.QueuedConnection` automaticamente).
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor

from esquizocap import hardware
from esquizocap.aplicacao import EventoErro, EventoParado, EventoResultado, ServicoAquisicao
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ModoAnalise, ResultadoCiclo
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware import constantes, portas_bluetooth
from esquizocap.hardware.contratos import ErroConexaoArduino, LeitorBitalino
from esquizocap.hardware.modo_aquisicao import (
    MODO_AQUISICAO_PADRAO,
    MODOS_AQUISICAO,
    ModoAquisicao,
    modo_do_rotulo,
)
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.interface_qt import bandas_eeg
from esquizocap.interface_qt.conexao_bitalino_assincrona import ConectorBitalinoAssincrono
from esquizocap.interface_qt.constantes_gui import (
    DURACAO_TRANSICAO_MATIZ_MS,
    INTERVALO_DRENAGEM_MS,
    LIMITE_BRILHO,
    LIMITE_INTERVALO_AMOSTRAGEM_MS,
    LIMITE_SATURACAO,
    LIMITE_TAMANHO_JANELA_AMOSTRAS,
    LimiteNumerico,
)
from esquizocap.interface_qt.cores_visuais import hsv_para_qcolor, limitar, qcolor_para_hex
from esquizocap.interface_qt.estado import (
    CANAIS_NA_ORDEM_DO_SELETOR,
    CANAIS_VALIDOS,
    MODELOS_DISPONIVEIS,
    ROTULOS_DOS_CANAIS,
    TEXTO_PORTA_NAO_ENCONTRADA,
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    aviso_de_taxa,
    aviso_do_canal,
    mensagem_de_aquisicao,
    taxas_selecionaveis,
)
from esquizocap.interface_qt.estado_ao_vivo import LeituraAoVivo
from esquizocap.interface_qt.estado_aparencia_visual import LIMITES_APARENCIA_VISUAL, AparenciaVisual
from esquizocap.interface_qt.estado_conexoes_hardware import EstadoConexoesHardware
from esquizocap.interface_qt.estado_configuracao import ConfiguracaoSelecionada, criar_configuracao_inicial
from esquizocap.interface_qt.gerenciador_gravacao_pendente import ErroDeGravacao, GerenciadorGravacaoPendente
from esquizocap.interface_qt.simulador_fita_led import ParametrosQuadroLed, SimuladorFitaLed

logger = logging.getLogger(__name__)

# índice base 1 (o que o firmware espera) -> nome do modo, na ordem certa
_NOME_DO_MODO_LUMINOSIDADE_POR_INDICE = {indice + 1: nome for indice, nome in enumerate(constantes.MODOS_LUMINOSIDADE)}

# Campos de `ConfiguracaoSelecionada` que, ao mudar durante uma aquisição em curso,
# precisam ser empurrados para a thread via `ServicoAquisicao.atualizar_controles`.
_CAMPOS_QUE_ATUALIZAM_CONTROLES_AO_VIVO = frozenset(
    {'saturacao', 'brilho', 'intervalo_amostragem_ms', 'tamanho_janela_amostras'}
)


def _obter_selecao(controller: EsquizoController) -> ConfiguracaoSelecionada:
    return controller._selecao


def _obter_aparencia(controller: EsquizoController) -> AparenciaVisual:
    return controller._aparencia


def _propriedade_editavel(
    obter_dono: Callable[[EsquizoController], Any],
    atributo: str,
    tipo: type,
    limite: LimiteNumerico | None = None,
):
    """Fábrica de getter+setter para uma `Property` editável apoiada num atributo de
    um dos dataclasses de estado internos.

    O setter passa por `EsquizoController._definir_e_notificar`, que só notifica a
    view quando o valor muda de fato, reavalia a prontidão e — para os campos de
    `ConfiguracaoSelecionada` que afetam a aquisição ao vivo — empurra o novo valor
    para a thread.
    """

    def fget(self: EsquizoController) -> Any:
        return tipo(getattr(obter_dono(self), atributo))

    def fset(self: EsquizoController, valor: Any) -> None:
        valor_convertido = tipo(valor)
        if limite is not None:
            valor_convertido = tipo(limitar(valor_convertido, limite.minimo, limite.maximo))
        self._definir_e_notificar(obter_dono(self), atributo, valor_convertido)

    return fget, fset


class EsquizoController(QObject):
    """Fonte única de verdade para a view.

    Há dois sinais de mudança, e a separação existe por performance:

    - `estadoMudou`: só quando a configuração/estado muda de fato (um slider, um
      dropdown, conectar um aparelho). É o `notify` das properties de configuração.
    - `quadroMudou`: a cada quadro **durante a aquisição**. É o `notify` só das
      properties que variam no tempo (cor viva, pulsação, cores dos LEDs...).
    """

    estadoMudou = Signal()
    quadroMudou = Signal()
    erroOcorreu = Signal(str)
    bitalinoConexaoFinalizada = Signal(bool, str)
    """Emitido ao final de uma tentativa de conexão do BITalino: (sucesso, mensagem de
    erro — vazia se sucesso). A thread auxiliar de conexão emite este sinal Qt para
    voltar à GUI thread; ver `conexao_bitalino_assincrona.ConectorBitalinoAssincrono`."""

    def __init__(self, configuracao: Configuracao, modelo: ModeloPreditor) -> None:
        super().__init__()
        self._configuracao_app = configuracao
        self._modelo = modelo
        self._arduino = hardware.criar_arduino()
        # Os dois modos nascem juntos: os construtores são inertes, nada toca o hardware
        # até `conectar`. Assim a troca de modo é só escolher outra chave deste mapa.
        self._leitores_por_modo = hardware.criar_leitores_por_modo()
        self._conector_bitalino = ConectorBitalinoAssincrono()
        self._simulador_leds = SimuladorFitaLed()
        self._gravacao_pendente = GerenciadorGravacaoPendente()

        self._servico: ServicoAquisicao | None = None
        self._ciclo: CicloAquisicao | None = None
        self._estado_app: EstadoApp = EstadoApp.CONFIGURANDO
        self._mensagem_status: str = ''
        self._erro_atual: str = ''
        self._continuacao_apos_conectar_bitalino: Callable[[], None] | None = None
        self._conectando_bitalino: bool = False
        """Ligado enquanto a thread de conexão roda.

        Sem isto, o seletor de modo continuaria liberado durante a tentativa — e trocar de
        modo nesse intervalo faria a aquisição subir com um leitor que nunca conectou.
        """

        self._porta_bitalino_em_cache: tuple[str, str] | None = None
        """`(mac, porta)` da última derivação, para não varrer as portas do sistema a cada
        ajuste de slider: a prontidão é reavaliada a cada mudança de qualquer campo, e a
        varredura do SetupAPI custa dezenas de milissegundos na GUI thread."""

        # listas reais do setup — calculadas uma vez aqui; portas plugadas depois da
        # abertura da app não aparecem sem reiniciar (limitação aceita, não é regressão:
        # o Tkinter também nunca detectou hotplug).
        self._portas_seriais_disponiveis: list[str] = self._arduino.listar_portas()
        # Rótulos, e não números: os seis canais não são equivalentes, e o seletor precisa
        # dizer isso. O valor guardado segue sendo o número — ver `canalBitalinoIndice`.
        self._canais_bitalino_disponiveis: list[str] = list(ROTULOS_DOS_CANAIS)
        self._macs_bitalino_disponiveis: list[str] = list(configuracao.macs_bitalino)
        self._modos_aquisicao_disponiveis: list[str] = list(MODOS_AQUISICAO)
        self._baud_rates_disponiveis: list[str] = [str(baud) for baud in constantes.BAUDRATES_SUPORTADOS]

        self._selecao = criar_configuracao_inicial(
            porta_arduino_inicial=self._portas_seriais_disponiveis[0] if self._portas_seriais_disponiveis else '',
            canal_bitalino_inicial=str(constantes.CANAIS_BITALINO[0]),
            mac_bitalino_inicial=self._macs_bitalino_disponiveis[0],
        )
        self._aparencia = AparenciaVisual()
        self._ao_vivo = LeituraAoVivo()
        self._conexoes = EstadoConexoesHardware()

        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_DRENAGEM_MS)
        self._timer.timeout.connect(self._ao_bater_o_relogio)
        self._timer.start()

        self.bitalinoConexaoFinalizada.connect(self._ao_concluir_conexao_bitalino)

        self._reavaliar_prontidao()

    # ---- relógio / drenagem da fila de aquisição --------------------------
    @staticmethod
    def _agora_ms() -> float:
        return time.monotonic() * 1000.0

    def _ao_bater_o_relogio(self) -> None:
        """Chamado a cada `INTERVALO_DRENAGEM_MS` pelo `QTimer` — nunca bloqueia."""
        if self._ao_vivo.adquirindo:
            progresso = (self._agora_ms() - self._ao_vivo.inicio_transicao_ms) / DURACAO_TRANSICAO_MATIZ_MS
            self._ao_vivo.fase_transicao = min(1.0, progresso)
            self.quadroMudou.emit()
        if self._servico is not None:
            self._drenar_eventos_da_aquisicao()

    def _drenar_eventos_da_aquisicao(self) -> None:
        assert self._servico is not None
        for evento in self._servico.drenar():
            match evento:
                case EventoResultado():
                    self._pintar_resultado(evento.resultado)
                case EventoErro():
                    logger.error(f'A thread de aquisição reportou: {evento.erro}')
                    self._reportar_erro(evento.mensagem_usuario)
                case EventoParado():
                    logger.info(f'Aquisição encerrada. {evento.total_gravado} resultados gravados.')
                    self._finalizar_aquisicao(evento.total_gravado)

    def _pintar_resultado(self, resultado: ResultadoCiclo) -> None:
        """Reflete um `ResultadoCiclo` real no estado ao vivo. Nenhuma lógica de negócio aqui."""
        ao_vivo = self._ao_vivo
        ao_vivo.matiz_anterior = ao_vivo.matiz_atual
        ao_vivo.matiz_atual = resultado.hue
        self._selecao.saturacao, self._selecao.brilho = resultado.saturacao, resultado.brilho
        if resultado.faixa_frequencia is None:
            ao_vivo.amplitude_texto = f'{resultado.metrica_bruta:.1f}'
        else:
            ao_vivo.frequencia_dominante_texto = f'{resultado.metrica_bruta:.1f}'
            ao_vivo.indice_banda = bandas_eeg.indice_da_banda(resultado.faixa_frequencia)
        ao_vivo.inicio_transicao_ms = self._agora_ms()
        self._emitir_todos_os_sinais()

    # ---- transporte ---------------------------------------------------------
    @Slot()
    def iniciarAquisicao(self) -> None:
        """Começa a aquisição — ou, se o BITalino ainda não estiver conectado, conecta
        primeiro e encadeia o início assim que a conexão terminar."""
        if not self.podeIniciarAquisicao:
            logger.warning(f'"Começar aquisição" pressionado no estado {self._estado_app.name}; ignorando.')
            return
        if self._conexoes.bitalino_conectado:
            self._iniciar_aquisicao_de_fato()
        else:
            self._conectar_bitalino(ao_concluir=self._iniciar_aquisicao_de_fato)

    def _iniciar_aquisicao_de_fato(self) -> None:
        """Monta o núcleo e entrega a aquisição à thread. Só chega aqui com o BITalino conectado."""
        selecao = self._selecao
        self._ciclo = CicloAquisicao(
            leitor=self._leitor_do_modo_escolhido(),
            arduino=self._arduino,
            modelo=self._modelo,
            modo_analise=ModoAnalise(selecao.modo_analise),
            canal_bitalino=int(selecao.canal_bitalino),
            modo_luminosidade=selecao.modo_luminosidade,
            tamanho_amostra_frequencia=selecao.tamanho_janela_amostras,
        )
        # A gravação vive DENTRO do serviço — é o que permite a fila de desenho descartar
        # resultados sem perder o que já foi gravado.
        self._servico = ServicoAquisicao(ciclo=self._ciclo, gravar=selecao.gravar_aquisicao)
        self._servico.atualizar_controles(self._controles_usuario_atuais())

        self._estado_app = EstadoApp.ADQUIRINDO
        self._ao_vivo.adquirindo = True
        self._ao_vivo.matiz_anterior = self._ao_vivo.matiz_atual
        self._ao_vivo.inicio_transicao_ms = self._agora_ms()
        self._ao_vivo.fase_transicao = 0.0
        self._servico.iniciar()
        self._emitir_todos_os_sinais()

    def _controles_usuario_atuais(self) -> ControlesUsuario:
        selecao = self._selecao
        intervalo_segundos = (selecao.intervalo_amostragem_ms / 1000.0) if self._em_modo_amplitude() else 0.0
        return ControlesUsuario(
            saturacao=selecao.saturacao, brilho=selecao.brilho, intervalo_predicao_segundos=intervalo_segundos
        )

    @Slot()
    def pararAquisicao(self) -> None:
        """Pede a parada. NÃO espera o hardware fechar — quem conclui é o `EventoParado`.

        `ServicoAquisicao.parar()` bloqueia a thread da GUI por até ~1-3 s enquanto a
        leitura bloqueante percebe o pedido. É comportamento herdado da interface Tkinter
        (que fazia a mesma chamada síncrona), não uma regressão introduzida aqui.
        """
        if self._servico is None or self._estado_app is not EstadoApp.ADQUIRINDO:
            return
        self._estado_app = EstadoApp.PARANDO
        self.estadoMudou.emit()
        self._servico.parar()
        self.estadoMudou.emit()

    def _finalizar_aquisicao(self, total_gravado: int) -> None:
        """Fecha o ciclo, oferece a gravação e devolve a interface ao estado ocioso.

        O hardware NÃO é desconectado aqui — só no fechamento da janela
        (`encerrarTudo`), igual à interface Tkinter: parar a aquisição não exige
        reconectar para começar de novo.
        """
        resultados = list(self._servico.gravacao) if self._servico is not None else []
        modo = self._ciclo.modo_analise if self._ciclo is not None else ModoAnalise.FREQUENCIA
        self._servico = None
        self._ciclo = None
        self._ao_vivo.adquirindo = False
        self._estado_app = EstadoApp.CONFIGURANDO

        if self._selecao.gravar_aquisicao:
            self._gravacao_pendente.oferecer(resultados, modo.value)

        self._reavaliar_prontidao()
        self._emitir_todos_os_sinais()

    # ---- conexão do hardware -------------------------------------------------
    @Slot()
    def alternarConexaoArduino(self) -> None:
        """Conecta ou desconecta o Arduino pela porta serial. Rápido — roda direto na GUI thread."""
        if self._conexoes.arduino_conectado:
            self._arduino.desconectar()
            self._definir_e_notificar(self._conexoes, 'arduino_conectado', False)
            return
        try:
            self._arduino.conectar(porta=self._selecao.porta_arduino, baudrate=constantes.BAUDRATE_PADRAO)
        except ErroConexaoArduino as erro:
            self._reportar_erro(f'Não foi possível conectar ao Arduino: {erro}')
            return
        self._definir_e_notificar(self._conexoes, 'arduino_conectado', True)

    @Slot()
    def alternarConexaoBitalino(self) -> None:
        """Conecta ou desconecta o BITalino.

        Conveniência opcional: a interface Tkinter conectava automaticamente ao clicar
        "Começar aquisição" (ver `iniciarAquisicao`), sem botão manual — este botão
        permite testar a conexão antes, usando os mesmos métodos reais do contrato.
        """
        if self._conexoes.bitalino_conectado:
            self._encerrar_todos_os_leitores()
            self._definir_e_notificar(self._conexoes, 'bitalino_conectado', False)
            return
        self._conectar_bitalino()

    def _bitalino_esta_simulado(self) -> bool:
        """Com o BITalino simulado, o MESMO leitor responde pelos dois modos."""
        return len(set(self._leitores_por_modo.values())) == 1

    def _seletor_de_modo_habilitado(self) -> bool:
        """O modo só pode mudar com o dispositivo desconectado.

        Trocar de modo com um stream aberto deixaria o outro leitor segurando socket ou
        porta serial — e, no Modo Direto, isso trava o dispositivo para a próxima conexão.
        Desconectar primeiro elimina a classe inteira de bugs.
        """
        if self._bitalino_esta_simulado():
            return False
        if self._estado_app in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO):
            return False
        if self._conectando_bitalino:
            return False
        return not self._conexoes.bitalino_conectado

    def _aviso_do_modo_aquisicao(self) -> str:
        """O que o operador precisa saber sobre o modo escolhido, agora.

        Vazio quando não há nada a dizer — a interface esconde o aviso nesse caso.
        """
        if self._bitalino_esta_simulado():
            return 'BITalino simulado (ESQUIZOCAP_FAKE): o sinal é sintético e a escolha de modo não tem efeito.'

        if self._conexoes.bitalino_conectado:
            return 'Desconecte o Bitalino para trocar de modo.'

        if not self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return 'Requer o OpenSignals aberto, com "Lab Streaming Layer" ativo e gravação iniciada.'

        porta = self._porta_derivada_do_bitalino()
        if not porta:
            return f'{TEXTO_PORTA_NAO_ENCONTRADA}.'

        return f'Porta {porta}. Requer o OpenSignals FECHADO — o dispositivo aceita um cliente por vez.'

    def _encerrar_todos_os_leitores(self) -> None:
        """Fecha o leitor de TODOS os modos, não só o do modo escolhido agora.

        Encerrar é idempotente por contrato, então fechar um leitor que nunca conectou é
        inofensivo — e cobre o caso de o modo ter mudado entre conectar e desconectar, que
        deixaria uma porta serial presa até o processo morrer.
        """
        for leitor in set(self._leitores_por_modo.values()):
            leitor.encerrar_stream()

    def _modo_aquisicao_escolhido(self) -> ModoAquisicao:
        """O modo escolhido na tela. Cai no padrão se o rótulo não for reconhecido."""
        try:
            return modo_do_rotulo(self._selecao.modo_aquisicao)
        except ValueError:
            return MODO_AQUISICAO_PADRAO

    def _leitor_do_modo_escolhido(self) -> LeitorBitalino:
        return self._leitores_por_modo[self._modo_aquisicao_escolhido()]

    def _porta_derivada_do_bitalino(self) -> str:
        """Descobre a porta de acesso do BITalino a partir do MAC escolhido.

        Derivada a cada consulta, e não guardada: a porta muda se o operador trocar de
        dispositivo ou repareá-lo, e um valor guardado envelheceria em silêncio.

        Devolve string vazia quando não há porta — dispositivo não pareado, desligado, ou
        sistema fora do Windows.
        """
        if not self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return ''

        mac = self._selecao.mac_bitalino
        if self._porta_bitalino_em_cache is not None and self._porta_bitalino_em_cache[0] == mac:
            return self._porta_bitalino_em_cache[1]

        porta = (
            portas_bluetooth.derivar_porta(mac=mac, portas_do_sistema=portas_bluetooth.listar_portas_do_sistema()) or ''
        )
        self._porta_bitalino_em_cache = (mac, porta)
        return porta

    def _endereco_do_modo_escolhido(self) -> str:
        """Onde encontrar o dispositivo, conforme o modo: MAC no OpenSignals, porta no Direto."""
        if self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return self._porta_derivada_do_bitalino()
        return self._selecao.mac_bitalino

    def _conectar_bitalino(self, ao_concluir: Callable[[], None] | None = None) -> None:
        """Pede ao `ConectorBitalinoAssincrono` para conectar numa thread auxiliar.

        Args:
            ao_concluir: Roda na GUI thread, só em caso de sucesso — usado por
                `iniciarAquisicao` para encadear o início da aquisição assim que a
                conexão terminar.
        """
        self._continuacao_apos_conectar_bitalino = ao_concluir
        self._conectando_bitalino = True
        leitor = self._leitor_do_modo_escolhido()

        # O canal ativo é informado ANTES de conectar porque, no Modo Direto, é ele que
        # decide qual canal vira microvolts. Trocá-lo depois não reconecta — ver
        # `LeitorBitalino.definir_canal_ativo`.
        leitor.definir_canal_ativo(canal=int(self._selecao.canal_bitalino))

        self._conector_bitalino.conectar(
            leitor=leitor,
            endereco=self._endereco_do_modo_escolhido(),
            taxa_amostragem_hz=self._selecao.taxa_amostragem_hz,
            canais=list(constantes.CANAIS_BITALINO),
            ao_concluir=lambda sucesso, mensagem_erro: self.bitalinoConexaoFinalizada.emit(sucesso, mensagem_erro),
        )

    def _ao_concluir_conexao_bitalino(self, sucesso: bool, mensagem_erro: str) -> None:
        """Slot conectado ao próprio sinal `bitalinoConexaoFinalizada`; roda na GUI
        thread mesmo quando emitido pela thread auxiliar (Qt enfileira a chamada
        automaticamente)."""
        self._conectando_bitalino = False
        continuacao = self._continuacao_apos_conectar_bitalino
        self._continuacao_apos_conectar_bitalino = None
        if not sucesso:
            self._reportar_erro(f'Não foi possível conectar ao BITalino: {mensagem_erro}')
            return
        self._definir_e_notificar(self._conexoes, 'bitalino_conectado', True)
        if continuacao is not None:
            continuacao()

    # ---- erros -----------------------------------------------------------
    def _reportar_erro(self, mensagem: str) -> None:
        self._erro_atual = mensagem
        self.erroOcorreu.emit(mensagem)
        self.estadoMudou.emit()

    @Slot()
    def limparErro(self) -> None:
        self._erro_atual = ''
        self.estadoMudou.emit()

    erroTexto = Property(str, lambda self: self._erro_atual, notify=estadoMudou)

    # ---- gravação (Excel) -------------------------------------------------
    gravacaoPendente = Property(bool, lambda self: self._gravacao_pendente.pendente, notify=estadoMudou)
    nomeSugeridoGravacao = Property(str, lambda self: self._gravacao_pendente.nome_sugerido, notify=estadoMudou)

    @Slot(str)
    def salvarGravacao(self, caminho: str) -> None:
        """Recebe o caminho escolhido no `FileDialog` da view (pode vir como `file://` URL)."""
        caminho_local = QUrl(caminho).toLocalFile() or caminho
        destino = Path(caminho_local)
        if destino.suffix.lower() != '.xlsx':
            destino = destino.with_suffix('.xlsx')
        try:
            self._gravacao_pendente.salvar_em(destino)
        except ErroDeGravacao as erro:
            self._reportar_erro(str(erro))
        self.estadoMudou.emit()

    @Slot()
    def descartarGravacao(self) -> None:
        logger.warning('Usuário cancelou o salvamento. A gravação foi descartada.')
        self._gravacao_pendente.descartar()
        self.estadoMudou.emit()

    # ---- encerramento -------------------------------------------------------
    @Slot()
    def encerrarTudo(self) -> None:
        """Fecha o hardware antes da janela morrer. Chamar em `onClosing` do `ApplicationWindow`."""
        if self._servico is not None:
            self._servico.parar()
            self._servico = None
        self._encerrar_todos_os_leitores()
        self._arduino.desconectar()
        self._conexoes.arduino_conectado = False
        self._conexoes.bitalino_conectado = False

    # ---- notificação e setters genéricos -----------------------------------
    def _emitir_todos_os_sinais(self) -> None:
        """Avisa a view de que tanto a configuração quanto o quadro podem ter mudado.

        Mexer num controle de config (saturação, brilho, nº de LEDs) também altera o
        que é desenhado no quadro, então os dois sinais precisam sair juntos.
        """
        self.estadoMudou.emit()
        self.quadroMudou.emit()

    def _definir_e_notificar(self, dono: Any, atributo: str, valor: Any) -> None:
        """Escreve `valor` em `dono.atributo` só se for diferente do atual, e propaga
        os efeitos colaterais: atualizar a thread de aquisição (para os campos que ela
        lê ao vivo), reavaliar a prontidão, e notificar a view."""
        if getattr(dono, atributo) == valor:
            return
        setattr(dono, atributo, valor)
        if dono is self._selecao and atributo in _CAMPOS_QUE_ATUALIZAM_CONTROLES_AO_VIVO and self._servico is not None:
            self._servico.atualizar_controles(self._controles_usuario_atuais())
        self._reavaliar_prontidao()
        self._emitir_todos_os_sinais()

    @Slot(int)
    def definirModoLuminosidade(self, valor: int) -> None:
        self._definir_e_notificar(self._selecao, 'modo_luminosidade', int(valor))

    @Slot(str)
    def definirModoAnalise(self, valor: str) -> None:
        """Troca o modo de predição, ajustando a taxa acordada se ela deixar de servir.

        Ir para Frequência com uma taxa que não alcança as bandas de EEG deixaria a seleção
        num estado inválido. Em vez de só barrar o início da aquisição, a taxa sobe para a
        menor válida — e o aviso na tela explica o que aconteceu. Corrigir em silêncio seria
        pior: o operador escolheu aquela taxa de propósito.
        """
        if valor == self._selecao.modo_analise:
            return

        self._selecao.modo_analise = valor

        validas = taxas_selecionaveis(valor)
        if self._selecao.taxa_amostragem_hz not in validas:
            # Sobe para a taxa PADRÃO, não para a menor válida: a menor é justamente a que
            # deixa a banda mais alta na borda de Nyquist, e cair nela por acidente daria
            # ao operador a pior opção ainda aceitável.
            self._selecao.taxa_amostragem_hz = (
                constantes.TAXA_AMOSTRAGEM_PADRAO_HZ
                if constantes.TAXA_AMOSTRAGEM_PADRAO_HZ in validas
                else max(validas)
            )

        self._reavaliar_prontidao()
        self.estadoMudou.emit()

    @Slot(int)
    def definirTaxaAmostragem(self, valor: int) -> None:
        self._definir_e_notificar(self._selecao, 'taxa_amostragem_hz', valor)

    @Slot(str)
    def definirSensor(self, valor: str) -> None:
        # Não alimenta nada no backend hoje: não existe conceito de "tipo de sensor" em
        # hardware/ nem dominio/ além do canal do BITalino. Mantido como estado de UI puro.
        self._definir_e_notificar(self._selecao, 'sensor', valor)

    @Slot()
    def alternarGravacao(self) -> None:
        self._definir_e_notificar(self._selecao, 'gravar_aquisicao', not self._selecao.gravar_aquisicao)

    @Slot()
    def alternarTelaCheia(self) -> None:
        self._definir_e_notificar(self._selecao, 'tela_cheia', not self._selecao.tela_cheia)

    # ---- máquina de estados de prontidão -----------------------------------
    def _reavaliar_prontidao(self) -> None:
        if self._estado_app in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO):
            return  # durante a aquisição o status pertence à thread, não à seleção
        selecao = self._selecao
        selecao_usuario = SelecaoUsuario(
            modelo=selecao.modelo_selecionado,
            porta_arduino=selecao.porta_arduino,
            modo_luminosidade=_NOME_DO_MODO_LUMINOSIDADE_POR_INDICE[selecao.modo_luminosidade],
            arduino_conectado=self._conexoes.arduino_conectado,
            canal_bitalino=selecao.canal_bitalino,
            mac_bitalino=selecao.mac_bitalino,
            modo_aquisicao=selecao.modo_aquisicao,
            modo_analise=selecao.modo_analise,
            taxa_amostragem_hz=selecao.taxa_amostragem_hz,
            porta_bitalino=self._porta_derivada_do_bitalino(),
        )
        estado, mensagem = avaliar_prontidao(selecao_usuario, macs_validos=self._configuracao_app.macs_bitalino)
        self._estado_app = estado
        self._mensagem_status = mensagem

    def _texto_do_estado(self) -> str:
        if self._estado_app is EstadoApp.ADQUIRINDO:
            return mensagem_de_aquisicao(gravando=self._selecao.gravar_aquisicao)
        if self._estado_app is EstadoApp.PARANDO:
            return 'Parando a aquisição...'
        return self._mensagem_status or 'Aguardando início da aquisição'

    podeIniciarAquisicao = Property(bool, lambda self: self._estado_app is EstadoApp.PRONTO, notify=estadoMudou)
    estadoTexto = Property(str, _texto_do_estado, notify=estadoMudou)

    # ---- propriedades: estado --------------------------------------------
    adquirindo = Property(bool, lambda self: self._ao_vivo.adquirindo, notify=estadoMudou)
    gravando = Property(bool, lambda self: self._selecao.gravar_aquisicao, notify=estadoMudou)
    telaCheia = Property(bool, lambda self: self._selecao.tela_cheia, notify=estadoMudou)
    modoAnalise = Property(str, lambda self: self._selecao.modo_analise, notify=estadoMudou)
    sensor = Property(str, lambda self: self._selecao.sensor, notify=estadoMudou)
    modoLuminosidade = Property(int, lambda self: self._selecao.modo_luminosidade, notify=estadoMudou)
    arduinoConectado = Property(bool, lambda self: self._conexoes.arduino_conectado, notify=estadoMudou)
    bitalinoConectado = Property(bool, lambda self: self._conexoes.bitalino_conectado, notify=estadoMudou)
    faseTransicao = Property(float, lambda self: self._ao_vivo.fase_transicao, notify=quadroMudou)

    # ---- propriedades: setup do hardware ---------------------------------
    @staticmethod
    def _rotulo_de_conexao(conectado: bool) -> str:
        return 'conectado' if conectado else 'desconectado'

    arduinoStatusTexto = Property(
        str, lambda self: self._rotulo_de_conexao(self._conexoes.arduino_conectado), notify=estadoMudou
    )
    bitalinoStatusTexto = Property(
        str, lambda self: self._rotulo_de_conexao(self._conexoes.bitalino_conectado), notify=estadoMudou
    )

    modelosDisponiveis = Property('QVariantList', lambda self: list(MODELOS_DISPONIVEIS), constant=True)

    def _portas_oferecidas_ao_arduino(self) -> list[str]:
        """As portas do Arduino, MENOS a que o BITalino está usando.

        Oferecer a porta do BITalino aqui deixaria as duas conexões disputando o mesmo
        recurso — e o operador não teria como descobrir por quê, já que todas as portas
        Bluetooth carregam a mesma descrição.

        Só filtra no Modo Direto: no Modo OpenSignals o BITalino não ocupa porta serial
        nenhuma, e esconder uma opção ali seria mentira.
        """
        porta_do_bitalino = self._porta_derivada_do_bitalino()

        if not porta_do_bitalino:
            return self._portas_seriais_disponiveis

        # As portas do Arduino vêm como "COM5 - descrição"; comparar só até o " - ".
        return [
            porta
            for porta in self._portas_seriais_disponiveis
            if porta.split(' - ')[0].strip().upper() != porta_do_bitalino.upper()
        ]

    portasSeriaisDisponiveis = Property('QVariantList', _portas_oferecidas_ao_arduino, notify=estadoMudou)
    baudRatesDisponiveis = Property('QVariantList', lambda self: self._baud_rates_disponiveis, constant=True)
    canaisBitalinoDisponiveis = Property('QVariantList', lambda self: self._canais_bitalino_disponiveis, constant=True)
    macsBitalinoDisponiveis = Property('QVariantList', lambda self: self._macs_bitalino_disponiveis, constant=True)
    modosAquisicaoDisponiveis = Property('QVariantList', lambda self: self._modos_aquisicao_disponiveis, constant=True)

    modoAquisicao = Property(str, *_propriedade_editavel(_obter_selecao, 'modo_aquisicao', str), notify=estadoMudou)

    def _taxas_oferecidas(self) -> list[str]:
        """TODAS as taxas que o dispositivo aceita, sempre as mesmas.

        As inválidas para o modo de predição atual aparecem desabilitadas, e não somem:
        quem procura 10 Hz precisa ver que ela existe e está indisponível, em vez de achar
        que a aplicação a esqueceu.
        """
        return [str(taxa) for taxa in constantes.TAXAS_AMOSTRAGEM_SUPORTADAS]

    def _taxas_desabilitadas(self) -> list[str]:
        """As taxas que não servem ao modo de predição atual."""
        validas = taxas_selecionaveis(self._selecao.modo_analise)
        return [str(taxa) for taxa in constantes.TAXAS_AMOSTRAGEM_SUPORTADAS if taxa not in validas]

    def _taxa_em_vigor(self) -> int:
        """A taxa que a aquisição está REALMENTE usando, e não a que está selecionada.

        Enquanto conectado, quem manda é o dispositivo: no Modo OpenSignals a taxa foi
        fixada lá, e no Modo Direto ela foi acordada no `conectar` — trocar o dropdown
        depois disso não muda nada até reconectar. Devolve 0 quando ninguém sabe ainda.
        """
        if self._conexoes.bitalino_conectado:
            return self._leitor_do_modo_escolhido().taxa_amostragem_nominal()

        if self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return self._selecao.taxa_amostragem_hz

        return 0

    def _duracao_da_janela_texto(self) -> str:
        """Quanto tempo de sinal cabe na janela de análise, na taxa em vigor.

        Existe porque a janela é medida em AMOSTRAS, e o que ela significa em segundos muda
        com a taxa: 2048 amostras são 2 s a 1000 Hz e 20 s a 100 Hz. Sem isto, o operador
        configura uma janela achando que a peça responde em segundos e ela responde em
        dezenas deles — parecendo travada.

        Vazio quando a taxa em vigor ainda não é conhecida (Modo OpenSignals desconectado,
        onde quem a fixa é o OpenSignals).
        """
        taxa = self._taxa_em_vigor()

        if taxa <= 0:
            return ''

        segundos = self._selecao.tamanho_janela_amostras / taxa
        return f'{self._selecao.tamanho_janela_amostras} amostras ≈ {segundos:.1f} s por predição'

    taxasSelecionaveis = Property('QVariantList', _taxas_oferecidas, notify=estadoMudou)
    taxasDesabilitadas = Property('QVariantList', _taxas_desabilitadas, notify=estadoMudou)
    taxaAmostragem = Property(str, lambda self: str(self._selecao.taxa_amostragem_hz), notify=estadoMudou)
    taxaAmostragemVisivel = Property(
        bool, lambda self: self._modo_aquisicao_escolhido().exige_porta_de_acesso, notify=estadoMudou
    )
    taxaAmostragemEditavel = Property(bool, lambda self: self._seletor_de_modo_habilitado(), notify=estadoMudou)
    """A taxa é acordada no `conectar`: trocá-la com o dispositivo conectado não teria
    efeito nenhum até reconectar, e a interface estaria mentindo ao aceitar a mudança."""
    avisoDeTaxa = Property(
        str,
        lambda self: aviso_de_taxa(taxa_hz=self._selecao.taxa_amostragem_hz, modo_analise=self._selecao.modo_analise),
        notify=estadoMudou,
    )
    duracaoDaJanela = Property(str, _duracao_da_janela_texto, notify=estadoMudou)

    seletorDeModoHabilitado = Property(bool, lambda self: self._seletor_de_modo_habilitado(), notify=estadoMudou)
    avisoDoModoAquisicao = Property(str, lambda self: self._aviso_do_modo_aquisicao(), notify=estadoMudou)

    modeloSelecionado = Property(
        str, *_propriedade_editavel(_obter_selecao, 'modelo_selecionado', str), notify=estadoMudou
    )
    portaArduino = Property(str, *_propriedade_editavel(_obter_selecao, 'porta_arduino', str), notify=estadoMudou)
    baudRateArduino = Property(str, *_propriedade_editavel(_obter_selecao, 'baud_rate', str), notify=estadoMudou)

    def _obter_canal_bitalino(self) -> str:
        return self._selecao.canal_bitalino

    def _definir_canal_bitalino(self, valor: str) -> None:
        """Guarda o canal ativo E o informa aos leitores.

        O setter genérico não serve aqui: ele só escreveria em `_selecao`. No Modo Direto é
        o leitor quem aplica a função de transferência, e ela depende de QUAL canal
        converter — sem esta propagação, trocar de canal no meio da sessão faria o leitor
        seguir convertendo o canal antigo e entregar o novo em ADU. Números plausíveis, cor
        errada, nenhum erro.

        Avisa TODOS os leitores, e não só o do modo escolhido: assim o modo pode ser trocado
        depois sem que o canal ativo fique para trás.
        """
        if valor == self._selecao.canal_bitalino:
            return

        self._selecao.canal_bitalino = valor

        # O combobox oferece só 1 a 6, mas o QML pode mandar o texto de "nada escolhido".
        # Nesse caso não há canal a informar — a prontidão já barra o início da aquisição.
        if valor in CANAIS_VALIDOS:
            for leitor in set(self._leitores_por_modo.values()):
                leitor.definir_canal_ativo(canal=int(valor))

        self._reavaliar_prontidao()
        self.estadoMudou.emit()

    canalBitalino = Property(str, _obter_canal_bitalino, _definir_canal_bitalino, notify=estadoMudou)

    def _canal_ativo(self) -> int | None:
        """O canal ativo como número, ou `None` se nada válido estiver escolhido.

        A interface guarda o canal como TEXTO, e o texto pode ser o placeholder de "nada
        escolhido" — daí o opcional em vez de um `int()` solto em cada uso.
        """
        try:
            return int(self._selecao.canal_bitalino)
        except ValueError:
            return None

    def _indice_do_canal_ativo(self) -> int:
        """Posição do canal ativo no seletor. O rótulo mostra "3 · 10 bits", mas o valor
        guardado é o número puro — a posição é a ponte entre os dois."""
        canal = self._canal_ativo()

        if canal is None or canal not in CANAIS_NA_ORDEM_DO_SELETOR:
            return -1

        return CANAIS_NA_ORDEM_DO_SELETOR.index(canal)

    @Slot(int)
    def definirCanalPorIndice(self, indice: int) -> None:
        """Escolhe o canal pela POSIÇÃO no seletor, já que o rótulo não é o valor."""
        if 0 <= indice < len(CANAIS_NA_ORDEM_DO_SELETOR):
            self.canalBitalino = str(CANAIS_NA_ORDEM_DO_SELETOR[indice])

    canalBitalinoIndice = Property(int, _indice_do_canal_ativo, notify=estadoMudou)

    def _aviso_do_canal_ativo(self) -> str:
        canal = self._canal_ativo()
        return aviso_do_canal(canal) if canal in CANAIS_NA_ORDEM_DO_SELETOR else ''

    avisoDoCanal = Property(str, _aviso_do_canal_ativo, notify=estadoMudou)
    macBitalino = Property(str, *_propriedade_editavel(_obter_selecao, 'mac_bitalino', str), notify=estadoMudou)

    def _em_modo_amplitude(self) -> bool:
        return self._selecao.modo_analise == ModoAnalise.AMPLITUDE.value

    modoAmplitude = Property(bool, _em_modo_amplitude, notify=estadoMudou)

    # ---- propriedades: cor -----------------------------------------------
    def _cor_ao_vivo(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#39424a')
        return hsv_para_qcolor(self._ao_vivo.matiz_atual, self._selecao.saturacao, self._selecao.brilho)

    corAoVivo = Property(QColor, _cor_ao_vivo, notify=quadroMudou)

    def _cor_clara(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#3a444c')
        return hsv_para_qcolor(
            self._ao_vivo.matiz_atual, round(self._selecao.saturacao * 0.55), min(self._selecao.brilho + 60, 255)
        )

    corClara = Property(QColor, _cor_clara, notify=quadroMudou)

    def _cor_escura(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#1a2026')
        return hsv_para_qcolor(self._ao_vivo.matiz_atual, self._selecao.saturacao, round(self._selecao.brilho * 0.45))

    corEscura = Property(QColor, _cor_escura, notify=quadroMudou)

    corHex = Property(str, lambda self: qcolor_para_hex(self._cor_ao_vivo()), notify=quadroMudou)

    def _leitura_hsv(self) -> str:
        if not self._ao_vivo.adquirindo:
            return 'HSV — · — · —'
        return f'HSV {self._ao_vivo.matiz_atual} · {self._selecao.saturacao} · {self._selecao.brilho}'

    leituraHsv = Property(str, _leitura_hsv, notify=quadroMudou)

    # ---- propriedades: órbita/banda --------------------------------------
    def _orbita_texto_principal(self) -> str:
        if not self._ao_vivo.adquirindo:
            return '—'
        if self._em_modo_amplitude():
            return self._ao_vivo.amplitude_texto
        return bandas_eeg.BANDAS_EEG[self._ao_vivo.indice_banda].nome

    orbitaTextoPrincipal = Property(str, _orbita_texto_principal, notify=quadroMudou)

    def _orbita_unidade(self) -> str:
        if not self._ao_vivo.adquirindo:
            return ''
        return 'µV' if self._em_modo_amplitude() else ''

    orbitaUnidade = Property(str, _orbita_unidade, notify=quadroMudou)

    def _orbita_subtexto(self) -> str:
        if not self._ao_vivo.adquirindo:
            return 'sinal parado'
        if self._em_modo_amplitude():
            return f'HUE {self._ao_vivo.matiz_atual} · amplitude bruta'
        banda = bandas_eeg.BANDAS_EEG[self._ao_vivo.indice_banda]
        return f'{self._ao_vivo.frequencia_dominante_texto} Hz · {banda.faixa_frequencia}'

    orbitaSubtexto = Property(str, _orbita_subtexto, notify=quadroMudou)

    def _modelo_das_bandas_eeg(self) -> list[dict[str, Any]]:
        ativo = self._ao_vivo.adquirindo and not self._em_modo_amplitude()
        apagado = self._ao_vivo.adquirindo and self._em_modo_amplitude()
        return [
            {'name': banda.nome, 'active': ativo and indice == self._ao_vivo.indice_banda, 'dim': apagado}
            for indice, banda in enumerate(bandas_eeg.BANDAS_EEG)
        ]

    bandasEegModel = Property('QVariantList', _modelo_das_bandas_eeg, notify=quadroMudou)

    # ---- propriedades: LEDs (fiel ao firmware) ---------------------------
    def _cores_dos_leds(self) -> list[QColor]:
        parametros = ParametrosQuadroLed(
            adquirindo=self._ao_vivo.adquirindo,
            quantidade_leds=self._aparencia.quantidade_leds,
            matiz_atual=self._ao_vivo.matiz_atual,
            matiz_anterior=self._ao_vivo.matiz_anterior,
            fase_transicao=round(self._ao_vivo.fase_transicao, 3),
            saturacao=self._selecao.saturacao,
            brilho=self._selecao.brilho,
            modo_luminosidade=self._selecao.modo_luminosidade,
        )
        return self._simulador_leds.cores_para_quadro(parametros)

    coresLeds = Property('QVariantList', _cores_dos_leds, notify=quadroMudou)

    # ---- pulsação --------------------------------------------------------
    def _pulsacao(self) -> float:
        if not self._ao_vivo.adquirindo:
            return 1.0
        aparencia = self._aparencia
        ciclo_em_ms = aparencia.velocidade_pulso_segundos * 1000.0
        amplitude = aparencia.amplitude_pulso_percentual / 100.0
        return 1.0 + amplitude * math.sin((self._agora_ms() / ciclo_em_ms) * 2 * math.pi)

    pulsacao = Property(float, _pulsacao, notify=quadroMudou)

    # ---- controles ao vivo (sinal/protocolo) -------------------------------
    saturacao = Property(
        int, *_propriedade_editavel(_obter_selecao, 'saturacao', int, LIMITE_SATURACAO), notify=estadoMudou
    )
    brilho = Property(int, *_propriedade_editavel(_obter_selecao, 'brilho', int, LIMITE_BRILHO), notify=estadoMudou)
    intervaloAmostragemMs = Property(
        int,
        *_propriedade_editavel(_obter_selecao, 'intervalo_amostragem_ms', int, LIMITE_INTERVALO_AMOSTRAGEM_MS),
        notify=estadoMudou,
    )
    tamanhoJanelaAmostras = Property(
        int,
        *_propriedade_editavel(_obter_selecao, 'tamanho_janela_amostras', int, LIMITE_TAMANHO_JANELA_AMOSTRAS),
        notify=estadoMudou,
    )

    def _rotulo_do_controle_de_amostragem(self) -> str:
        return 'Amostragem' if self._em_modo_amplitude() else 'Janela de amostra'

    rotuloControleAmostragem = Property(str, _rotulo_do_controle_de_amostragem, notify=estadoMudou)

    def _leitura_do_controle_de_amostragem(self) -> str:
        if self._em_modo_amplitude():
            return f'{self._selecao.intervalo_amostragem_ms} ms'
        return f'{self._selecao.tamanho_janela_amostras} amostras'

    leituraControleAmostragem = Property(str, _leitura_do_controle_de_amostragem, notify=estadoMudou)

    # ---- animação & feel (read/write, puramente visual) -------------------
    tamanhoOrbita = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'tamanho_orbita', int, LIMITES_APARENCIA_VISUAL['tamanho_orbita']),
        notify=estadoMudou,
    )
    intensidadeGlow = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia, 'intensidade_glow', float, LIMITES_APARENCIA_VISUAL['intensidade_glow']
        ),
        notify=estadoMudou,
    )
    velocidadeAnelSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'velocidade_anel_segundos', int, LIMITES_APARENCIA_VISUAL['velocidade_anel_segundos']
        ),
        notify=estadoMudou,
    )
    larguraAnelPx = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'largura_anel_px', int, LIMITES_APARENCIA_VISUAL['largura_anel_px']),
        notify=estadoMudou,
    )
    velocidadePulsoSegundos = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia,
            'velocidade_pulso_segundos',
            float,
            LIMITES_APARENCIA_VISUAL['velocidade_pulso_segundos'],
        ),
        notify=estadoMudou,
    )
    amplitudePulsoPercentual = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'amplitude_pulso_percentual',
            int,
            LIMITES_APARENCIA_VISUAL['amplitude_pulso_percentual'],
        ),
        notify=estadoMudou,
    )
    larguraTracoEeg = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia, 'largura_traco_eeg', float, LIMITES_APARENCIA_VISUAL['largura_traco_eeg']
        ),
        notify=estadoMudou,
    )
    opacidadeTracoEegPercentual = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'opacidade_traco_eeg_percentual',
            int,
            LIMITES_APARENCIA_VISUAL['opacidade_traco_eeg_percentual'],
        ),
        notify=estadoMudou,
    )
    duracaoTransicaoCorSegundos = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia,
            'duracao_transicao_cor_segundos',
            float,
            LIMITES_APARENCIA_VISUAL['duracao_transicao_cor_segundos'],
        ),
        notify=estadoMudou,
    )
    brilhoLedsPx = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'brilho_leds_px', int, LIMITES_APARENCIA_VISUAL['brilho_leds_px']),
        notify=estadoMudou,
    )
    espacamentoLedsPx = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'espacamento_leds_px', int, LIMITES_APARENCIA_VISUAL['espacamento_leds_px']
        ),
        notify=estadoMudou,
    )
    quantidadeLeds = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'quantidade_leds', int, LIMITES_APARENCIA_VISUAL['quantidade_leds']),
        notify=estadoMudou,
    )
    quantidadeFitas = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'quantidade_fitas', int, LIMITES_APARENCIA_VISUAL['quantidade_fitas']),
        notify=estadoMudou,
    )
    escalaEixoYMicroVolts = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'escala_eixo_y_microvolts',
            int,
            LIMITES_APARENCIA_VISUAL['escala_eixo_y_microvolts'],
        ),
        notify=estadoMudou,
    )
    janelaGraficoSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'janela_grafico_segundos', int, LIMITES_APARENCIA_VISUAL['janela_grafico_segundos']
        ),
        notify=estadoMudou,
    )
    velocidadeAnimacaoSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'velocidade_animacao_segundos',
            int,
            LIMITES_APARENCIA_VISUAL['velocidade_animacao_segundos'],
        ),
        notify=estadoMudou,
    )
