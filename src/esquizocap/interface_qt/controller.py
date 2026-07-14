"""EsquizoCap — controller (bridge) para a view QML.

Fonte única de verdade da interface: liga a aquisição real (`aplicacao.ServicoAquisicao`,
rodando numa thread própria) à tela, e nada mais. A view NUNCA toca no domínio/hardware —
só lê propriedades e chama slots daqui, mantendo a separação de camadas do projeto.

A ponte com a thread de aquisição segue o mesmo desenho que a antiga `janela_principal.py`
usava com o `after()` do Tk: um `QTimer` dreno a fila publicada pelo `ServicoAquisicao` a
cada `INTERVALO_DRENAGEM_MS`, e nunca bloqueia — se não houver evento, sai na hora. A única
exceção é `conectar()` do BITalino, que bloqueia (resolução LSL); por isso roda numa
`threading.Thread` auxiliar, que sinaliza a volta à GUI thread via um sinal Qt (sinais Qt
são thread-safe para cruzar de thread, viram `Qt.QueuedConnection` automaticamente).
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor

from esquizocap import hardware
from esquizocap.aplicacao import EventoErro, EventoParado, EventoResultado, ServicoAquisicao
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ModoAnalise, ResultadoCiclo
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware import constantes
from esquizocap.hardware.contratos import ErroConexaoArduino, ErroConexaoBitalino
from esquizocap.infraestrutura import persistencia
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.infraestrutura.persistencia import ErroDeGravacao
from esquizocap.interface_qt.estado import (
    MODELOS_DISPONIVEIS,
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    mensagem_de_aquisicao,
)

logger = logging.getLogger(__name__)

# --- dados fixos (bandas de EEG exibidas na órbita) --------------------------
BANDS = [("Delta", "0.5–4 Hz"), ("Theta", "4–8 Hz"), ("Alpha", "8–13 Hz"),
         ("Beta", "13–30 Hz"), ("Gamma", "30–45 Hz")]
NOMES_BANDAS = [nome for nome, _faixa in BANDS]

# índice base 1 (o que o firmware espera) -> nome do modo, na ordem certa
LUM_NOMES = {indice + 1: nome for indice, nome in enumerate(constantes.MODOS_LUMINOSIDADE)}

INTERVALO_DRENAGEM_MS = 33
"""Cadência de leitura da fila de eventos, ~30 fps — mesmo valor que a interface Tkinter
usava (`layout.INTERVALO_DRENAGEM_MS`, hoje arquivada)."""


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def hsv2rgb(h: float, s: float, v: float) -> QColor:
    """h,s,v em 0-255 (escala do firmware/GUI) -> QColor."""
    hq = int(round(_clamp(h, 0, 255) / 255.0 * 359.0))
    return QColor.fromHsv(hq, int(_clamp(s, 0, 255)), int(_clamp(v, 0, 255)))


def _hexs(c: QColor) -> str:
    return c.name().upper()


def _indice_da_faixa(faixa: str) -> int:
    """Traduz a string de banda do domínio (ex.: "Alpha (Relaxamento, calma)") para o
    índice usado pela órbita (0=Delta..4=Gamma).
    """
    primeira_palavra = faixa.split(" ", 1)[0]
    try:
        return NOMES_BANDAS.index(primeira_palavra)
    except ValueError:
        return 0


class EsquizoController(QObject):
    """Fonte única de verdade para a view.

    Há dois sinais, e a separação existe por performance:

    - `changed`: só quando a configuração/estado muda de fato (um slider, um dropdown,
      conectar um aparelho). É o `notify` das properties de config.
    - `quadroMudou`: a cada quadro **durante a aquisição**. É o `notify` só das properties
      que variam no tempo (cor viva, pulsação, cores dos LEDs...).
    """

    changed = Signal()
    quadroMudou = Signal()
    erroOcorreu = Signal(str)
    bitalinoConectado = Signal(bool, str)  # sucesso, mensagem de erro (vazia se sucesso)

    def __init__(self, configuracao: Configuracao, modelo: ModeloPreditor) -> None:
        super().__init__()
        self._configuracao = configuracao
        self._modelo = modelo
        self._arduino = hardware.criar_arduino()
        self._bitalino = hardware.criar_bitalino()
        self._servico: ServicoAquisicao | None = None
        self._ciclo: CicloAquisicao | None = None
        self._estado: EstadoApp = EstadoApp.CONFIGURANDO
        self._continuacao_bitalino: Callable[[], None] | None = None
        self._resultados_pendentes: list[ResultadoCiclo] = []

        # cache das cores dos LEDs: só recalcula quando alguma entrada muda. Devolver o
        # MESMO objeto quando nada mudou é o que faz o Canvas da fita não repintar à toa.
        self._chave_leds: tuple | None = None
        self._cache_leds: list[QColor] = []

        # listas reais do setup — calculadas uma vez aqui; portas plugadas depois da
        # abertura da app não aparecem sem reiniciar (limitação aceita, não é regressão:
        # o Tkinter também nunca detectou hotplug).
        self._portas_seriais: list[str] = self._arduino.listar_portas()
        self._canais_bitalino: list[str] = [str(c) for c in constantes.CANAIS_BITALINO]
        self._macs_bitalino: list[str] = list(configuracao.macs_bitalino)

        porta_inicial = self._portas_seriais[0] if self._portas_seriais else ""
        canal_inicial = self._canais_bitalino[0]
        mac_inicial = self._macs_bitalino[0]

        self._s = {
            "acquiring": False, "analysis": "Frequência", "lumin": 2,
            "sat": 227, "val": 196, "amostragem": 900, "janela": 500,
            "gravar": True, "sensor": "EEG",
            "hue": 128, "prevHue": 128, "phase": 1.0, "transStart": 0.0,
            "freq": "0.0", "band": 2, "uv": "0.0",
            "connARD": False, "connBIT": False,
            "modeloMl": MODELOS_DISPONIVEIS[0], "porta": porta_inicial,
            "baud": str(constantes.BAUDRATE_PADRAO),
            "canal": canal_inicial, "mac": mac_inicial,
            "fullscreen": False,
            "erro": "", "mensagemStatus": "",
            "pendenteGravar": False, "nomeSugeridoGravacao": "",
            # animação & feel — puramente visual, nada a ver com hardware
            "orbSize": 300, "glow": 1.0, "ringSpeed": 18, "ringWidth": 18,
            "pulseSpeed": 3.2, "pulseAmt": 3, "eegWidth": 1.5, "eegOpacity": 16,
            "colorFade": 0.5, "ledGlow": 6, "ledGap": 2,
            "numLeds": 60, "numFitas": 3, "yScale": 100, "graphWin": 6, "animSpeed": 9,
        }

        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_DRENAGEM_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.bitalinoConectado.connect(self._ao_conectar_bitalino)

        self._reavaliar_prontidao()

    # ---- relógio / drenagem da fila de aquisição --------------------------
    @staticmethod
    def _now() -> float:
        return time.monotonic() * 1000.0

    def _tick(self) -> None:
        s = self._s
        now = self._now()
        if s["acquiring"]:
            s["phase"] = min(1.0, (now - s["transStart"]) / 650.0)
            self.quadroMudou.emit()
        if self._servico is not None:
            self._drenar_eventos()

    def _drenar_eventos(self) -> None:
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
        """Reflete um `ResultadoCiclo` real no estado da view. Nenhuma lógica de negócio aqui."""
        s = self._s
        s["prevHue"] = s["hue"]
        s["hue"] = resultado.hue
        s["sat"], s["val"] = resultado.saturacao, resultado.brilho
        if resultado.faixa_frequencia is None:
            s["uv"] = f'{resultado.metrica_bruta:.1f}'
        else:
            s["freq"] = f'{resultado.metrica_bruta:.1f}'
            s["band"] = _indice_da_faixa(resultado.faixa_frequencia)
        s["transStart"] = self._now()
        self._emitir_tudo()

    # ---- transporte ---------------------------------------------------------
    @Slot()
    def start(self) -> None:
        if not self.podeIniciar:
            logger.warning(f'"Começar aquisição" pressionado no estado {self._estado.name}; ignorando.')
            return
        if self._s["connBIT"]:
            self._iniciar_aquisicao_de_fato()
        else:
            self._conectar_bitalino_em_thread(ao_concluir=self._iniciar_aquisicao_de_fato)

    def _iniciar_aquisicao_de_fato(self) -> None:
        """Monta o núcleo e entrega a aquisição à thread. Só chega aqui com o BITalino conectado."""
        s = self._s
        modo = ModoAnalise(s["analysis"])
        self._ciclo = CicloAquisicao(
            leitor=self._bitalino,
            arduino=self._arduino,
            modelo=self._modelo,
            modo_analise=modo,
            canal_bitalino=int(s["canal"]),
            modo_luminosidade=s["lumin"],
            tamanho_amostra_frequencia=s["janela"],
        )
        # A gravação vive DENTRO do serviço — é o que permite a fila de desenho descartar
        # resultados sem perder o que já foi gravado.
        self._servico = ServicoAquisicao(ciclo=self._ciclo, gravar=s["gravar"])
        self._servico.atualizar_controles(self._controles_usuario())

        self._estado = EstadoApp.ADQUIRINDO
        s.update(acquiring=True, prevHue=s["hue"], transStart=self._now(), phase=0.0)
        self._servico.iniciar()
        self._emitir_tudo()

    def _controles_usuario(self) -> ControlesUsuario:
        s = self._s
        intervalo = (s["amostragem"] / 1000.0) if self._is_amp() else 0.0
        return ControlesUsuario(saturacao=s["sat"], brilho=s["val"], intervalo_predicao_segundos=intervalo)

    @Slot()
    def stop(self) -> None:
        """Pede a parada. NÃO espera o hardware fechar — quem conclui é o `EventoParado`.

        `ServicoAquisicao.parar()` bloqueia a thread da GUI por até ~1-3 s enquanto a
        leitura bloqueante percebe o pedido. É comportamento herdado da interface Tkinter
        (que fazia a mesma chamada síncrona), não uma regressão introduzida aqui.
        """
        if self._servico is None or self._estado is not EstadoApp.ADQUIRINDO:
            return
        self._estado = EstadoApp.PARANDO
        self.changed.emit()
        self._servico.parar()
        self.changed.emit()

    def _finalizar_aquisicao(self, total_gravado: int) -> None:
        """Fecha o ciclo, oferece a gravação e devolve a interface ao estado ocioso.

        O hardware NÃO é desconectado aqui — só no fechamento da janela (`encerrarTudo`),
        igual à interface Tkinter: parar a aquisição não exige reconectar para começar de novo.
        """
        resultados = list(self._servico.gravacao) if self._servico is not None else []
        modo = self._ciclo.modo_analise if self._ciclo is not None else ModoAnalise.FREQUENCIA
        self._servico = None
        self._ciclo = None
        self._s["acquiring"] = False
        self._estado = EstadoApp.CONFIGURANDO

        if self._s["gravar"] and resultados:
            self._resultados_pendentes = resultados
            self._s["pendenteGravar"] = True
            self._s["nomeSugeridoGravacao"] = persistencia.nome_sugerido(modo.value)

        self._reavaliar_prontidao()
        self._emitir_tudo()

    # ---- conexão do hardware -------------------------------------------------
    @Slot()
    def alternar_conexao_arduino(self) -> None:
        """Conecta ou desconecta o Arduino pela porta serial. Rápido — roda direto na GUI thread."""
        if self._s["connARD"]:
            self._arduino.desconectar()
            self._set("connARD", False)
            return
        try:
            self._arduino.conectar(porta=self._s["porta"], baudrate=constantes.BAUDRATE_PADRAO)
        except ErroConexaoArduino as erro:
            self._reportar_erro(f'Não foi possível conectar ao Arduino: {erro}')
            return
        self._set("connARD", True)

    @Slot()
    def alternar_conexao_bitalino(self) -> None:
        """Conecta ou desconecta o BITalino.

        Conveniência opcional: a interface Tkinter conectava automaticamente ao clicar
        "Começar aquisição" (ver `start`), sem botão manual — este botão permite testar a
        conexão antes, usando os mesmos métodos reais do contrato.
        """
        if self._s["connBIT"]:
            self._bitalino.encerrar_stream()
            self._set("connBIT", False)
            return
        self._conectar_bitalino_em_thread()

    def _conectar_bitalino_em_thread(self, ao_concluir: Callable[[], None] | None = None) -> None:
        """Conecta o BITalino numa thread auxiliar — `conectar()` bloqueia (resolução LSL).

        `ao_concluir` roda na GUI thread, só em caso de sucesso (usado por `start()` para
        encadear o início da aquisição assim que a conexão terminar).
        """
        self._continuacao_bitalino = ao_concluir
        mac = self._s["mac"]

        def alvo() -> None:
            try:
                self._bitalino.conectar(mac_addr=mac)
            except ErroConexaoBitalino as erro:
                self.bitalinoConectado.emit(False, str(erro))
            else:
                self.bitalinoConectado.emit(True, "")

        threading.Thread(target=alvo, name='conectar-bitalino', daemon=True).start()

    def _ao_conectar_bitalino(self, sucesso: bool, mensagem_erro: str) -> None:
        """Slot conectado ao próprio sinal `bitalinoConectado`; roda na GUI thread mesmo
        quando emitido pela thread auxiliar (Qt enfileira a chamada automaticamente)."""
        continuacao = self._continuacao_bitalino
        self._continuacao_bitalino = None
        if not sucesso:
            self._reportar_erro(f'Não foi possível conectar ao BITalino: {mensagem_erro}')
            return
        self._set("connBIT", True)
        if continuacao is not None:
            continuacao()

    # ---- erros -----------------------------------------------------------
    def _reportar_erro(self, mensagem: str) -> None:
        self._s["erro"] = mensagem
        self.erroOcorreu.emit(mensagem)
        self.changed.emit()

    @Slot()
    def limparErro(self) -> None:
        self._s["erro"] = ""
        self.changed.emit()

    erroTexto = Property(str, lambda self: self._s["erro"], notify=changed)

    # ---- gravação (Excel) -------------------------------------------------
    pendenteGravar = Property(bool, lambda self: self._s["pendenteGravar"], notify=changed)
    nomeSugeridoGravacao = Property(str, lambda self: self._s["nomeSugeridoGravacao"], notify=changed)

    @Slot(str)
    def salvarGravacao(self, caminho: str) -> None:
        """Recebe o caminho escolhido no `FileDialog` da view (pode vir como `file://` URL)."""
        if not self._resultados_pendentes:
            self._s["pendenteGravar"] = False
            self.changed.emit()
            return
        caminho_local = QUrl(caminho).toLocalFile() or caminho
        destino = Path(caminho_local)
        if destino.suffix.lower() != '.xlsx':
            destino = destino.with_suffix('.xlsx')
        try:
            persistencia.salvar_gravacao(resultados=self._resultados_pendentes, destino=destino)
        except (ErroDeGravacao, ValueError) as erro:
            self._reportar_erro(str(erro))
        self._resultados_pendentes = []
        self._s["pendenteGravar"] = False
        self.changed.emit()

    @Slot()
    def descartarGravacao(self) -> None:
        logger.warning('Usuário cancelou o salvamento. A gravação foi descartada.')
        self._resultados_pendentes = []
        self._s["pendenteGravar"] = False
        self.changed.emit()

    # ---- encerramento -------------------------------------------------------
    @Slot()
    def encerrarTudo(self) -> None:
        """Fecha o hardware antes da janela morrer. Chamar em `onClosing` do `ApplicationWindow`."""
        if self._servico is not None:
            self._servico.parar()
            self._servico = None
        self._bitalino.encerrar_stream()
        self._arduino.desconectar()
        self._s["connARD"] = False
        self._s["connBIT"] = False

    # ---- setters de configuração/feel -----------------------------------
    def _emitir_tudo(self) -> None:
        """Avisa a view de que tanto a configuração quanto o quadro podem ter mudado.

        Mexer num controle de config (saturação, brilho, nº de LEDs) também altera o que é
        desenhado no quadro, então os dois sinais precisam sair juntos.
        """
        self.changed.emit()
        self.quadroMudou.emit()

    def _set(self, key, value):
        if self._s.get(key) != value:
            self._s[key] = value
            if self._servico is not None and key in ("sat", "val", "amostragem", "janela"):
                self._servico.atualizar_controles(self._controles_usuario())
            self._reavaliar_prontidao()
            self._emitir_tudo()

    @Slot(int)
    def setLumin(self, v):
        self._set("lumin", int(v))

    @Slot(str)
    def setAnalysis(self, v):
        self._set("analysis", v)

    @Slot(str)
    def setSensor(self, v):
        # Não alimenta nada no backend hoje: não existe conceito de "tipo de sensor" em
        # hardware/ nem dominio/ além do canal do BITalino. Mantido como estado de UI puro.
        self._set("sensor", v)

    @Slot()
    def toggleGravar(self):
        self._set("gravar", not self._s["gravar"])

    @Slot()
    def toggleFullscreen(self):
        self._set("fullscreen", not self._s["fullscreen"])

    # ---- máquina de estados de prontidão -----------------------------------
    def _reavaliar_prontidao(self) -> None:
        if self._estado in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO):
            return  # durante a aquisição o status pertence à thread, não à seleção
        s = self._s
        selecao = SelecaoUsuario(
            modelo=s["modeloMl"],
            porta_arduino=s["porta"],
            modo_luminosidade=LUM_NOMES[s["lumin"]],
            arduino_conectado=s["connARD"],
            canal_bitalino=s["canal"],
            mac_bitalino=s["mac"],
        )
        estado, mensagem = avaliar_prontidao(selecao, macs_validos=self._configuracao.macs_bitalino)
        self._estado = estado
        self._s["mensagemStatus"] = mensagem

    def _estado_texto(self) -> str:
        if self._estado is EstadoApp.ADQUIRINDO:
            return mensagem_de_aquisicao(gravando=self._s["gravar"])
        if self._estado is EstadoApp.PARANDO:
            return 'Parando a aquisição...'
        return self._s["mensagemStatus"] or 'Aguardando início da aquisição'

    podeIniciar = Property(bool, lambda self: self._estado is EstadoApp.PRONTO, notify=changed)
    estadoTexto = Property(str, _estado_texto, notify=changed)

    # ---- propriedades: estado --------------------------------------------
    def _g(k, cast=lambda x: x):
        return lambda self: cast(self._s[k])

    acquiring = Property(bool, _g("acquiring"), notify=changed)
    recording = Property(bool, _g("gravar"), notify=changed)
    fullscreen = Property(bool, _g("fullscreen"), notify=changed)
    analysis = Property(str, _g("analysis"), notify=changed)
    sensor = Property(str, _g("sensor"), notify=changed)
    lumin = Property(int, _g("lumin"), notify=changed)
    connARD = Property(bool, _g("connARD"), notify=changed)
    connBIT = Property(bool, _g("connBIT"), notify=changed)
    phase = Property(float, _g("phase", float), notify=quadroMudou)

    # ---- propriedades: setup do hardware ---------------------------------
    def _rotulo_conexao(self, conectado: bool) -> str:
        return "conectado" if conectado else "desconectado"

    arduinoStatusTexto = Property(
        str, lambda self: self._rotulo_conexao(self._s["connARD"]), notify=changed)
    bitalinoStatusTexto = Property(
        str, lambda self: self._rotulo_conexao(self._s["connBIT"]), notify=changed)

    modelosMl = Property("QVariantList", lambda self: list(MODELOS_DISPONIVEIS), constant=True)
    portasSeriais = Property("QVariantList", lambda self: self._portas_seriais, constant=True)
    baudRates = Property("QVariantList", lambda self: [str(constantes.BAUDRATE_PADRAO)], constant=True)
    canaisBitalino = Property("QVariantList", lambda self: self._canais_bitalino, constant=True)
    macsBitalino = Property("QVariantList", lambda self: self._macs_bitalino, constant=True)

    def _mk_str(k):
        return (lambda self: self._s[k]), (lambda self, v: self._set(k, v))

    modeloMl = Property(str, *_mk_str("modeloMl"), notify=changed)
    porta = Property(str, *_mk_str("porta"), notify=changed)
    baud = Property(str, *_mk_str("baud"), notify=changed)
    canal = Property(str, *_mk_str("canal"), notify=changed)
    mac = Property(str, *_mk_str("mac"), notify=changed)

    def _is_amp(self):
        return self._s["analysis"] == "Amplitude"
    isAmp = Property(bool, _is_amp, notify=changed)

    # ---- propriedades: cor -----------------------------------------------
    def _live(self):
        s = self._s
        return hsv2rgb(s["hue"], s["sat"], s["val"]) if s["acquiring"] else QColor("#39424a")
    liveColor = Property(QColor, _live, notify=quadroMudou)

    def _light(self):
        s = self._s
        if not s["acquiring"]:
            return QColor("#3a444c")
        return hsv2rgb(s["hue"], round(s["sat"] * 0.55), min(s["val"] + 60, 255))
    lightColor = Property(QColor, _light, notify=quadroMudou)

    def _dark(self):
        s = self._s
        if not s["acquiring"]:
            return QColor("#1a2026")
        return hsv2rgb(s["hue"], s["sat"], round(s["val"] * 0.45))
    darkColor = Property(QColor, _dark, notify=quadroMudou)

    colorHex = Property(str, lambda self: _hexs(self._live()), notify=quadroMudou)

    def _hsvReadout(self):
        s = self._s
        return f"HSV {s['hue']} · {s['sat']} · {s['val']}" if s["acquiring"] else "HSV — · — · —"
    hsvReadout = Property(str, _hsvReadout, notify=quadroMudou)

    # ---- propriedades: órbita/banda --------------------------------------
    def _orbBig(self):
        s = self._s
        if not s["acquiring"]:
            return "—"
        return s["uv"] if self._is_amp() else BANDS[s["band"]][0]
    orbBig = Property(str, _orbBig, notify=quadroMudou)

    def _orbUnit(self):
        if not self._s["acquiring"]:
            return ""
        return "µV" if self._is_amp() else ""
    orbUnit = Property(str, _orbUnit, notify=quadroMudou)

    def _orbSub(self):
        s = self._s
        if not s["acquiring"]:
            return "sinal parado"
        if self._is_amp():
            return f"HUE {s['hue']} · amplitude bruta"
        return f"{s['freq']} Hz · {BANDS[s['band']][1]}"
    orbSub = Property(str, _orbSub, notify=quadroMudou)

    def _bandModel(self):
        s = self._s
        active = s["acquiring"] and not self._is_amp()
        dim = s["acquiring"] and self._is_amp()
        return [{"name": n, "active": active and i == s["band"], "dim": dim}
                for i, (n, _r) in enumerate(BANDS)]
    bandModel = Property("QVariantList", _bandModel, notify=quadroMudou)

    # ---- propriedades: LEDs (fiel ao firmware) ---------------------------
    def _led_colors(self):
        """Cores de cada LED da fita, no modo de luminosidade escolhido.

        O resultado é memorizado: enquanto nenhuma das entradas mudar, devolve o MESMO
        objeto de lista — é o que faz o Canvas da fita não repintar à toa (identidade
        nova = mudança, aos olhos do QML).

        Returns:
            Uma cor por LED, do primeiro ao último da fita.
        """
        s = self._s
        n = int(_clamp(s["numLeds"], 6, 120))
        chave = (s["acquiring"], n, s["hue"], s["prevHue"], round(s["phase"], 3),
                 s["sat"], s["val"], s["lumin"])
        if chave == self._chave_leds:
            return self._cache_leds

        self._chave_leds = chave
        self._cache_leds = self._calcular_cores_leds(n)
        return self._cache_leds

    def _calcular_cores_leds(self, n: int) -> list[QColor]:
        """Roda o mesmo algoritmo do firmware para colorir `n` LEDs.

        Args:
            n: Quantidade de LEDs da fita.

        Returns:
            Uma cor por LED. Com a aquisição parada, todos apagados.
        """
        s = self._s
        if not s["acquiring"]:
            return [QColor(26, 32, 38)] * n
        c = n // 2
        margem = max(2, round(n * 0.08))
        led_v = min(s["val"], 150)
        phase, hue, prev, sat, lum = s["phase"], s["hue"], s["prevHue"], s["sat"], s["lumin"]
        out = []
        for i in range(n):
            lv = led_v
            if lum == 2:                     # Todos
                lh = hue
            elif lum == 1:                   # Um a um
                lh = hue if i / n <= phase else prev
            elif lum == 4:                   # A partir do centro
                d = abs(i - c)
                lh = hue if (d / max(1, c)) <= phase else prev
                if d <= margem and (d / max(1, c)) <= phase:
                    lv = min(s["val"] + 50, 150)
            else:                            # Gradiente
                lh = round(prev + (hue - prev) * phase)
            out.append(hsv2rgb(lh, sat, lv))
        return out
    ledColors = Property("QVariantList", _led_colors, notify=quadroMudou)

    # ---- pulsação --------------------------------------------------------
    def _pulse(self):
        s = self._s
        if not s["acquiring"]:
            return 1.0
        return 1.0 + (s["pulseAmt"] / 100.0) * math.sin((self._now() / (s["pulseSpeed"] * 1000.0)) * 2 * math.pi)
    pulse = Property(float, _pulse, notify=quadroMudou)

    # ---- controles ao vivo ----------------------------------------------
    def _mk(k, cast, lo=None, hi=None):
        def fget(self):
            return cast(self._s[k])

        def fset(self, v):
            v = cast(v)
            if lo is not None:
                v = _clamp(v, lo, hi)
            self._set(k, v)
        return fget, fset

    sat = Property(int, *_mk("sat", int, 0, 255), notify=changed)
    val = Property(int, *_mk("val", int, 0, 255), notify=changed)
    amostragem = Property(int, *_mk("amostragem", int, 100, 2000), notify=changed)
    # NOTA: o tamanho típico de janela usado no domínio é ~3000 amostras (ver
    # DECISOES_PENDENTES.md); o teto de 2048 aqui é herdado do protótipo visual e pode
    # merecer revisão de produto — não ajustado neste plano por não ter sido pedido.
    janela = Property(int, *_mk("janela", int, 128, 2048), notify=changed)

    def _third_label(self):
        return "Amostragem" if self._is_amp() else "Janela de amostra"
    thirdLabel = Property(str, _third_label, notify=changed)

    def _third_readout(self):
        s = self._s
        return f"{s['amostragem']} ms" if self._is_amp() else f"{s['janela']} amostras"
    thirdReadout = Property(str, _third_readout, notify=changed)

    # ---- animação & feel (read/write, puramente visual) -------------------
    orbSize = Property(int, *_mk("orbSize", int, 200, 380), notify=changed)
    glow = Property(float, *_mk("glow", float, 0.3, 1.8), notify=changed)
    ringSpeed = Property(int, *_mk("ringSpeed", int, 4, 40), notify=changed)
    ringWidth = Property(int, *_mk("ringWidth", int, 6, 30), notify=changed)
    pulseSpeed = Property(float, *_mk("pulseSpeed", float, 1.5, 6), notify=changed)
    pulseAmt = Property(int, *_mk("pulseAmt", int, 0, 12), notify=changed)
    eegWidth = Property(float, *_mk("eegWidth", float, 0.5, 4), notify=changed)
    eegOpacity = Property(int, *_mk("eegOpacity", int, 5, 60), notify=changed)
    colorFade = Property(float, *_mk("colorFade", float, 0.1, 1.5), notify=changed)
    ledGlow = Property(int, *_mk("ledGlow", int, 0, 16), notify=changed)
    ledGap = Property(int, *_mk("ledGap", int, 0, 6), notify=changed)
    numLeds = Property(int, *_mk("numLeds", int, 6, 120), notify=changed)
    numFitas = Property(int, *_mk("numFitas", int, 1, 6), notify=changed)
    yScale = Property(int, *_mk("yScale", int, 20, 300), notify=changed)
    graphWin = Property(int, *_mk("graphWin", int, 2, 20), notify=changed)
    animSpeed = Property(int, *_mk("animSpeed", int, 3, 16), notify=changed)
