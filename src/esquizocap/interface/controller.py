"""EsquizoCap — controller (bridge) para a view QML.

Fonte única de verdade da interface: liga a aquisição real (`aplicacao.ServicoAquisicao`,
rodando numa thread própria) à tela, e nada mais. A view NUNCA toca no domínio/hardware —
só lê propriedades e chama slots daqui, mantendo a separação de camadas do projeto.

Este arquivo é propositalmente uma FACHADA FINA: o estado propriamente dito vive em
dataclasses tipados (`estado.configuracao.ConfiguracaoSelecionada`,
`estado.aparencia_visual.AparenciaVisual`, `estado.ao_vivo.LeituraAoVivo`,
`estado.conexoes_hardware.EstadoConexoesHardware`), e a lógica que não é "colar Qt"
vive em módulos próprios (`visual.simulador_fita_led`, `ponte.conexao_bitalino_assincrona`,
`ponte.gerenciador_gravacao_pendente`, `visual.cores`, `visual.bandas`). O que sobra aqui é:
sinalização Qt, orquestração da aquisição, e a definição das `Property`/`Slot` que a
QML enxerga.

Para não empilhar ~950 linhas num só corpo de classe, a superfície de `Property` está
quebrada em MIXINS de classe simples por concern (`_PropriedadesAparenciaVisual`,
`_PropriedadesQuadroAoVivo`, `_PropriedadesConfiguracao`), herdados por um ÚNICO
`EsquizoController` (QObject). A QML segue ligando a um só objeto de contexto — nada de
sub-QObjects, o contrato dos bindings é o mesmo. Os `Signal`s de mudança vivem numa base
`_Sinais` para que os mixins consigam nomeá-los como `notify=` no corpo da classe (ver
`_Sinais`). O núcleo — `__init__`, orquestração/transporte, conexão, erro, gravação e os
`Slot`s — fica no `EsquizoController` concreto.

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
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, SignalInstance, Slot
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication

from esquizocap import hardware
from esquizocap.aplicacao import EventoErro, EventoParado, EventoResultado, ServicoAquisicao, catalogo_erros
from esquizocap.aplicacao.catalogo_erros import EspecificacaoCaixa, PapelAcao
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ModoAnalise, ResultadoCiclo
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware import constantes, portas_bluetooth
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.contratos import ControladorLedArduino, ErroConexaoArduino, LeitorBitalino
from esquizocap.hardware.modo_aquisicao import (
    MODO_AQUISICAO_PADRAO,
    MODOS_AQUISICAO,
    ModoAquisicao,
    modo_do_rotulo,
)
from esquizocap.infraestrutura import log, persistencia, preferencias, recursos
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.infraestrutura.preferencias import Preferencias
from esquizocap.interface.constantes import (
    DURACAO_TRANSICAO_MATIZ_MS,
    INTERVALO_DRENAGEM_MS,
    LIMITE_BRILHO,
    LIMITE_INTERVALO_AMOSTRAGEM_MS,
    LIMITE_SATURACAO,
    LIMITE_TAMANHO_JANELA_AMOSTRAS,
    LimiteNumerico,
)
from esquizocap.interface.estado import (
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
from esquizocap.interface.estado.ao_vivo import LeituraAoVivo
from esquizocap.interface.estado.aparencia_visual import (
    LIMITES_APARENCIA_VISUAL,
    ROTULOS_DAS_SECOES_APARENCIA,
    SECAO_APARENCIA_TUDO,
    SECOES_APARENCIA,
    AparenciaVisual,
)
from esquizocap.interface.estado.conexoes_hardware import EstadoConexoesHardware
from esquizocap.interface.estado.configuracao import ConfiguracaoSelecionada, criar_configuracao_inicial
from esquizocap.interface.ponte.conexao_bitalino_assincrona import ConectorBitalinoAssincrono
from esquizocap.interface.ponte.gerenciador_gravacao_pendente import ErroDeGravacao, GerenciadorGravacaoPendente
from esquizocap.interface.ponte.varredura_portas_assincrona import ResultadoVarredura, VarredorDePortasAssincrono
from esquizocap.interface.visual import bandas as bandas_eeg
from esquizocap.interface.visual.cores import hsv_para_qcolor, limitar, qcolor_para_hex
from esquizocap.interface.visual.simulador_fita_led import ParametrosQuadroLed, SimuladorFitaLed

logger = logging.getLogger(__name__)

# índice base 1 (o que o firmware espera) -> nome do modo, na ordem certa
_NOME_DO_MODO_LUMINOSIDADE_POR_INDICE = {indice + 1: nome for indice, nome in enumerate(constantes.MODOS_LUMINOSIDADE)}

# Campos de `ConfiguracaoSelecionada` que, ao mudar durante uma aquisição em curso,
# precisam ser empurrados para a thread via `ServicoAquisicao.atualizar_controles`.
_CAMPOS_QUE_ATUALIZAM_CONTROLES_AO_VIVO = frozenset(
    {'saturacao', 'brilho', 'intervalo_amostragem_ms', 'tamanho_janela_amostras'}
)

_SITUACOES_EM_ANDAMENTO = frozenset({catalogo_erros.Situacao.CONECTANDO_BITALINO})
"""As mensagens que anunciam uma espera ainda em curso, e não um fato consumado.

Conjunto, e não um `if` solto, porque a diferença é de CATEGORIA e não de caso: toda
mensagem em andamento troca o glifo de severidade pelo indicador de carregamento e perde o
auto-fechamento. Ver `EsquizoController._toast_descreve_algo_em_curso`."""

INTERVALO_GRAVACAO_PREFERENCIAS_MS: int = 1000
"""Silêncio necessário antes de gravar as preferências em disco.

Sem esta espera, arrastar um slider gravaria o arquivo dezenas de vezes por segundo, na
GUI thread. O encerramento grava incondicionalmente, então nada se perde por esperar."""


def _aparencia_das_preferencias(valores: dict[str, float]) -> AparenciaVisual:
    """Monta a `AparenciaVisual` a partir do que foi salvo, limitando cada valor à sua faixa.

    O clamp acontece aqui, e não na infraestrutura: a tabela de faixas é da camada de
    interface. Chaves desconhecidas (de uma versão anterior, ou de um slider removido) são
    descartadas — a alternativa seria um `TypeError` no construtor e a app não subindo por
    causa de uma preferência cosmética.
    """
    aparencia = AparenciaVisual()
    for nome, valor in valores.items():
        limite = LIMITES_APARENCIA_VISUAL.get(nome)
        if limite is None:
            logger.warning(f'Preferência de aparência desconhecida, descartada: "{nome}".')
            continue
        tipo = type(getattr(aparencia, nome))
        setattr(aparencia, nome, tipo(limitar(valor, limite.minimo, limite.maximo)))
    return aparencia


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

    Funciona igual dentro de um mixin ou da classe concreta: `fget`/`fset` recebem
    `self` e agem sobre a instância, então a classe onde a `Property` é DECLARADA é
    irrelevante em runtime.
    """

    def fget(self: EsquizoController) -> Any:
        return tipo(getattr(obter_dono(self), atributo))

    def fset(self: EsquizoController, valor: Any) -> None:
        valor_convertido = tipo(valor)
        if limite is not None:
            valor_convertido = tipo(limitar(valor_convertido, limite.minimo, limite.maximo))
        self._definir_e_notificar(obter_dono(self), atributo, valor_convertido)

    return fget, fset


class _Sinais:
    """Sinais de mudança que o controller e os mixins de `Property` compartilham.

    Vive numa base própria — e não na classe concreta — porque os mixins referenciam
    estes sinais como `notify=` no CORPO da classe, e nesse momento (import) o
    `EsquizoController` concreto ainda não existe. Pôr o `Signal` aqui dá aos mixins um
    nome que resolve no import (`_Sinais.estadoMudou`), sem forward reference. O Shiboken
    registra os sinais pela MRO quando `EsquizoController` herda esta base.

    Há dois sinais de mudança, e a separação existe por performance:

    - `estadoMudou`: só quando a configuração/estado muda de fato (um slider, um
      dropdown, conectar um aparelho). É o `notify` das properties de configuração.
    - `quadroMudou`: a cada quadro **durante a aquisição**. É o `notify` só das
      properties que variam no tempo (cor viva, pulsação, cores dos LEDs...).
    """

    estadoMudou = Signal()
    quadroMudou = Signal()


class _NucleoControlador:
    """Base **só-para-tipos** herdada pelos mixins de `Property`.

    Os métodos dos mixins acessam estado e helpers que só existem no `EsquizoController`
    concreto (`self._selecao`, `self._reavaliar_prontidao()`, ...). Em runtime a MRO resolve
    tudo, mas um verificador estático que olha o mixin isolado não sabe disso e acusa
    "atributo desconhecido". Este bloco `TYPE_CHECKING` **declara** essa superfície — sem
    implementar nada — para o pyright/Pylance resolver `self.*` (e dar autocomplete). No
    runtime a classe é vazia: o bloco é ignorado, então nada aqui sobrescreve o que o
    controller concreto (ou `_Sinais`) provê.

    NÃO herda `_Sinais`: os `Signal`s reais chegam ao `EsquizoController` por ele listar
    `_Sinais` diretamente. Duplicar `_Sinais` aqui e lá quebraria a MRO (C3). Os sinais
    aparecem abaixo apenas como `SignalInstance` — o tipo que a instância enxerga —, o que
    faz `self.estadoMudou.emit()` resolver mesmo num mixin que não é `QObject`.
    """

    if TYPE_CHECKING:
        estadoMudou: SignalInstance
        quadroMudou: SignalInstance
        # Atributos criados no `EsquizoController.__init__`.
        _selecao: ConfiguracaoSelecionada
        _aparencia: AparenciaVisual
        _ao_vivo: LeituraAoVivo
        _conexoes: EstadoConexoesHardware
        _estado_app: EstadoApp
        _mensagem_status: str
        _simulador_leds: SimuladorFitaLed
        _arduino: ControladorLedArduino
        _leitores_por_modo: dict[ModoAquisicao, LeitorBitalino]
        _preferencias: Preferencias
        _conectando_bitalino: bool
        _varrendo_portas: bool
        _portas_seriais_disponiveis: list[str]
        _baud_rates_disponiveis: list[str]
        _canais_bitalino_disponiveis: list[str]
        _macs_bitalino_disponiveis: list[str]
        _modos_aquisicao_disponiveis: list[str]

        # Helpers do núcleo (e o cross-mixin `_em_modo_amplitude`) que os mixins chamam
        # via `self`; a implementação real vive no controller concreto ou no mixin de config.
        @staticmethod
        def _agora_ms() -> float: ...
        @staticmethod
        def _rotulo_de_conexao(conectado: bool) -> str: ...
        def _reavaliar_prontidao(self) -> None: ...
        def _reconstruir_hardware(self) -> None: ...
        def _reaplicar_canal_ativo_nos_leitores(self) -> None: ...
        def _agendar_gravacao_de_preferencias(self) -> None: ...
        def _reportar(self, caixa: EspecificacaoCaixa) -> None: ...
        def _aquisicao_em_curso(self) -> bool: ...
        def _porta_derivada_do_bitalino(self, *, bloqueando: bool = False) -> str: ...
        def _pedir_varredura_de_portas(self) -> None: ...
        def _modo_aquisicao_escolhido(self) -> ModoAquisicao: ...
        def _leitor_do_modo_escolhido(self) -> LeitorBitalino: ...
        def _seletor_de_modo_habilitado(self) -> bool: ...
        def _aviso_do_modo_aquisicao(self) -> str: ...
        def _em_modo_amplitude(self) -> bool: ...


class _PropriedadesConfiguracao(_NucleoControlador):
    """Properties de configuração, estado da app e setup de hardware (`notify=estadoMudou`).

    Taxa/canal/modo de aquisição, portas, e os controles de sinal/protocolo. Os métodos
    aqui só leem/escrevem os dataclasses de estado e delegam a orquestração ao núcleo via
    `self.<...>` — resolvido em runtime pela MRO do `EsquizoController`.
    """

    # ---- máquina de estados de prontidão -----------------------------------
    def _texto_do_estado(self) -> str:
        if self._estado_app is EstadoApp.ADQUIRINDO:
            return mensagem_de_aquisicao(gravando=self._selecao.gravar_aquisicao)
        if self._estado_app is EstadoApp.PARANDO:
            return 'Parando a aquisição...'
        return self._mensagem_status or 'Aguardando início da aquisição'

    podeIniciarAquisicao = Property(bool, lambda self: self._estado_app is EstadoApp.PRONTO, notify=_Sinais.estadoMudou)
    estadoTexto = Property(str, _texto_do_estado, notify=_Sinais.estadoMudou)

    # ---- propriedades: estado --------------------------------------------
    adquirindo = Property(bool, lambda self: self._ao_vivo.adquirindo, notify=_Sinais.estadoMudou)
    gravando = Property(bool, lambda self: self._selecao.gravar_aquisicao, notify=_Sinais.estadoMudou)
    telaCheia = Property(bool, lambda self: self._selecao.tela_cheia, notify=_Sinais.estadoMudou)
    modoAnalise = Property(str, lambda self: self._selecao.modo_analise, notify=_Sinais.estadoMudou)
    sensor = Property(str, lambda self: self._selecao.sensor, notify=_Sinais.estadoMudou)
    modoLuminosidade = Property(int, lambda self: self._selecao.modo_luminosidade, notify=_Sinais.estadoMudou)
    arduinoConectado = Property(bool, lambda self: self._conexoes.arduino_conectado, notify=_Sinais.estadoMudou)
    bitalinoConectado = Property(bool, lambda self: self._conexoes.bitalino_conectado, notify=_Sinais.estadoMudou)

    # ---- propriedades: setup do hardware ---------------------------------
    arduinoStatusTexto = Property(
        str, lambda self: self._rotulo_de_conexao(self._conexoes.arduino_conectado), notify=_Sinais.estadoMudou
    )
    bitalinoStatusTexto = Property(
        str, lambda self: self._rotulo_de_conexao(self._conexoes.bitalino_conectado), notify=_Sinais.estadoMudou
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

    portasSeriaisDisponiveis = Property('QVariantList', _portas_oferecidas_ao_arduino, notify=_Sinais.estadoMudou)

    varrendoPortas = Property(bool, lambda self: self._varrendo_portas, notify=_Sinais.estadoMudou)
    """Ligado enquanto a thread de varredura de portas roda.

    É o gate de espera visível dos seletores de porta e do texto de diagnóstico: até a
    varredura voltar, a lista do Arduino está vazia e a porta de acesso do BITalino é
    desconhecida. Sem isto, os dois apareceriam vazios como se o sistema não tivesse porta
    nenhuma — que é uma resposta, e errada."""

    conectandoBitalino = Property(bool, lambda self: self._conectando_bitalino, notify=_Sinais.estadoMudou)
    """Ligado enquanto a thread de conexão do BITalino roda.

    Já existia como estado interno (travando o seletor de modo); agora é público para que o
    botão de conectar mostre a espera em vez de ficar mudo por vários segundos."""
    baudRatesDisponiveis = Property('QVariantList', lambda self: self._baud_rates_disponiveis, constant=True)
    canaisBitalinoDisponiveis = Property('QVariantList', lambda self: self._canais_bitalino_disponiveis, constant=True)
    macsBitalinoDisponiveis = Property('QVariantList', lambda self: self._macs_bitalino_disponiveis, constant=True)
    modosAquisicaoDisponiveis = Property('QVariantList', lambda self: self._modos_aquisicao_disponiveis, constant=True)

    modoAquisicao = Property(
        str, *_propriedade_editavel(_obter_selecao, 'modo_aquisicao', str), notify=_Sinais.estadoMudou
    )

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

    taxasSelecionaveis = Property('QVariantList', _taxas_oferecidas, notify=_Sinais.estadoMudou)
    taxasDesabilitadas = Property('QVariantList', _taxas_desabilitadas, notify=_Sinais.estadoMudou)
    taxaAmostragem = Property(str, lambda self: str(self._selecao.taxa_amostragem_hz), notify=_Sinais.estadoMudou)
    taxaAmostragemVisivel = Property(
        bool, lambda self: self._modo_aquisicao_escolhido().exige_porta_de_acesso, notify=_Sinais.estadoMudou
    )
    taxaAmostragemEditavel = Property(bool, lambda self: self._seletor_de_modo_habilitado(), notify=_Sinais.estadoMudou)
    """A taxa é acordada no `conectar`: trocá-la com o dispositivo conectado não teria
    efeito nenhum até reconectar, e a interface estaria mentindo ao aceitar a mudança."""
    avisoDeTaxa = Property(
        str,
        lambda self: aviso_de_taxa(taxa_hz=self._selecao.taxa_amostragem_hz, modo_analise=self._selecao.modo_analise),
        notify=_Sinais.estadoMudou,
    )
    duracaoDaJanela = Property(str, _duracao_da_janela_texto, notify=_Sinais.estadoMudou)

    seletorDeModoHabilitado = Property(
        bool, lambda self: self._seletor_de_modo_habilitado(), notify=_Sinais.estadoMudou
    )
    avisoDoModoAquisicao = Property(str, lambda self: self._aviso_do_modo_aquisicao(), notify=_Sinais.estadoMudou)

    modeloSelecionado = Property(
        str, *_propriedade_editavel(_obter_selecao, 'modelo_selecionado', str), notify=_Sinais.estadoMudou
    )
    portaArduino = Property(
        str, *_propriedade_editavel(_obter_selecao, 'porta_arduino', str), notify=_Sinais.estadoMudou
    )
    baudRateArduino = Property(
        str, *_propriedade_editavel(_obter_selecao, 'baud_rate', str), notify=_Sinais.estadoMudou
    )

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
        self._reaplicar_canal_ativo_nos_leitores()

        self._reavaliar_prontidao()
        self.estadoMudou.emit()

    canalBitalino = Property(str, _obter_canal_bitalino, _definir_canal_bitalino, notify=_Sinais.estadoMudou)

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

    canalBitalinoIndice = Property(int, _indice_do_canal_ativo, notify=_Sinais.estadoMudou)

    def _aviso_do_canal_ativo(self) -> str:
        canal = self._canal_ativo()
        return aviso_do_canal(canal) if canal in CANAIS_NA_ORDEM_DO_SELETOR else ''

    avisoDoCanal = Property(str, _aviso_do_canal_ativo, notify=_Sinais.estadoMudou)
    macBitalino = Property(str, *_propriedade_editavel(_obter_selecao, 'mac_bitalino', str), notify=_Sinais.estadoMudou)

    def _em_modo_amplitude(self) -> bool:
        return self._selecao.modo_analise == ModoAnalise.AMPLITUDE.value

    modoAmplitude = Property(bool, _em_modo_amplitude, notify=_Sinais.estadoMudou)

    # ---- controles ao vivo (sinal/protocolo) -------------------------------
    saturacao = Property(
        int, *_propriedade_editavel(_obter_selecao, 'saturacao', int, LIMITE_SATURACAO), notify=_Sinais.estadoMudou
    )
    brilho = Property(
        int, *_propriedade_editavel(_obter_selecao, 'brilho', int, LIMITE_BRILHO), notify=_Sinais.estadoMudou
    )
    intervaloAmostragemMs = Property(
        int,
        *_propriedade_editavel(_obter_selecao, 'intervalo_amostragem_ms', int, LIMITE_INTERVALO_AMOSTRAGEM_MS),
        notify=_Sinais.estadoMudou,
    )
    tamanhoJanelaAmostras = Property(
        int,
        *_propriedade_editavel(_obter_selecao, 'tamanho_janela_amostras', int, LIMITE_TAMANHO_JANELA_AMOSTRAS),
        notify=_Sinais.estadoMudou,
    )

    def _rotulo_do_controle_de_amostragem(self) -> str:
        return 'Amostragem' if self._em_modo_amplitude() else 'Janela de amostra'

    rotuloControleAmostragem = Property(str, _rotulo_do_controle_de_amostragem, notify=_Sinais.estadoMudou)

    def _leitura_do_controle_de_amostragem(self) -> str:
        if self._em_modo_amplitude():
            return f'{self._selecao.intervalo_amostragem_ms} ms'
        return f'{self._selecao.tamanho_janela_amostras} amostras'

    leituraControleAmostragem = Property(str, _leitura_do_controle_de_amostragem, notify=_Sinais.estadoMudou)


class _PropriedadesQuadroAoVivo(_NucleoControlador):
    """Properties que variam A CADA QUADRO durante a aquisição (`notify=quadroMudou`).

    Cor viva, órbita/banda, cores dos LEDs e pulsação — o que a peça mostra em movimento.
    Separadas das de configuração para que o quadro emita só o sinal barato.
    """

    faseTransicao = Property(float, lambda self: self._ao_vivo.fase_transicao, notify=_Sinais.quadroMudou)

    # ---- propriedades: cor -----------------------------------------------
    def _cor_ao_vivo(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#39424a')
        return hsv_para_qcolor(self._ao_vivo.matiz_atual, self._selecao.saturacao, self._selecao.brilho)

    corAoVivo = Property(QColor, _cor_ao_vivo, notify=_Sinais.quadroMudou)

    def _cor_clara(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#3a444c')
        return hsv_para_qcolor(
            self._ao_vivo.matiz_atual, round(self._selecao.saturacao * 0.55), min(self._selecao.brilho + 60, 255)
        )

    corClara = Property(QColor, _cor_clara, notify=_Sinais.quadroMudou)

    def _cor_escura(self) -> QColor:
        if not self._ao_vivo.adquirindo:
            return QColor('#1a2026')
        return hsv_para_qcolor(self._ao_vivo.matiz_atual, self._selecao.saturacao, round(self._selecao.brilho * 0.45))

    corEscura = Property(QColor, _cor_escura, notify=_Sinais.quadroMudou)

    corHex = Property(str, lambda self: qcolor_para_hex(self._cor_ao_vivo()), notify=_Sinais.quadroMudou)

    def _leitura_hsv(self) -> str:
        if not self._ao_vivo.adquirindo:
            return 'HSV — · — · —'
        return f'HSV {self._ao_vivo.matiz_atual} · {self._selecao.saturacao} · {self._selecao.brilho}'

    leituraHsv = Property(str, _leitura_hsv, notify=_Sinais.quadroMudou)

    # ---- propriedades: órbita/banda --------------------------------------
    def _orbita_texto_principal(self) -> str:
        if not self._ao_vivo.adquirindo:
            return '—'
        if self._em_modo_amplitude():
            return self._ao_vivo.amplitude_texto
        return bandas_eeg.BANDAS_EEG[self._ao_vivo.indice_banda].nome

    orbitaTextoPrincipal = Property(str, _orbita_texto_principal, notify=_Sinais.quadroMudou)

    def _orbita_unidade(self) -> str:
        if not self._ao_vivo.adquirindo:
            return ''
        return 'µV' if self._em_modo_amplitude() else ''

    orbitaUnidade = Property(str, _orbita_unidade, notify=_Sinais.quadroMudou)

    def _orbita_subtexto(self) -> str:
        if not self._ao_vivo.adquirindo:
            return 'sinal parado'
        if self._em_modo_amplitude():
            return f'HUE {self._ao_vivo.matiz_atual} · amplitude bruta'
        banda = bandas_eeg.BANDAS_EEG[self._ao_vivo.indice_banda]
        return f'{self._ao_vivo.frequencia_dominante_texto} Hz · {banda.faixa_frequencia}'

    orbitaSubtexto = Property(str, _orbita_subtexto, notify=_Sinais.quadroMudou)

    def _modelo_das_bandas_eeg(self) -> list[dict[str, Any]]:
        ativo = self._ao_vivo.adquirindo and not self._em_modo_amplitude()
        apagado = self._ao_vivo.adquirindo and self._em_modo_amplitude()
        return [
            {'name': banda.nome, 'active': ativo and indice == self._ao_vivo.indice_banda, 'dim': apagado}
            for indice, banda in enumerate(bandas_eeg.BANDAS_EEG)
        ]

    bandasEegModel = Property('QVariantList', _modelo_das_bandas_eeg, notify=_Sinais.quadroMudou)

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

    coresLeds = Property('QVariantList', _cores_dos_leds, notify=_Sinais.quadroMudou)

    # ---- pulsação --------------------------------------------------------
    def _pulsacao(self) -> float:
        if not self._ao_vivo.adquirindo:
            return 1.0
        aparencia = self._aparencia
        ciclo_em_ms = aparencia.velocidade_pulso_segundos * 1000.0
        amplitude = aparencia.amplitude_pulso_percentual / 100.0
        return 1.0 + amplitude * math.sin((self._agora_ms() / ciclo_em_ms) * 2 * math.pi)

    pulsacao = Property(float, _pulsacao, notify=_Sinais.quadroMudou)


class _PropriedadesAparenciaVisual(_NucleoControlador):
    """As ~16 properties de animação & feel, puramente visuais e editáveis (`notify=estadoMudou`).

    Bloco mecânico: cada uma é um `_propriedade_editavel` sobre um campo de `AparenciaVisual`,
    com seu limite. Nenhuma toca aquisição ou hardware — só afetam o desenho.
    """

    tamanhoOrbita = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'tamanho_orbita', int, LIMITES_APARENCIA_VISUAL['tamanho_orbita']),
        notify=_Sinais.estadoMudou,
    )
    intensidadeGlow = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia, 'intensidade_glow', float, LIMITES_APARENCIA_VISUAL['intensidade_glow']
        ),
        notify=_Sinais.estadoMudou,
    )
    velocidadeAnelSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'velocidade_anel_segundos', int, LIMITES_APARENCIA_VISUAL['velocidade_anel_segundos']
        ),
        notify=_Sinais.estadoMudou,
    )
    larguraAnelPx = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'largura_anel_px', int, LIMITES_APARENCIA_VISUAL['largura_anel_px']),
        notify=_Sinais.estadoMudou,
    )
    velocidadePulsoSegundos = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia,
            'velocidade_pulso_segundos',
            float,
            LIMITES_APARENCIA_VISUAL['velocidade_pulso_segundos'],
        ),
        notify=_Sinais.estadoMudou,
    )
    amplitudePulsoPercentual = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'amplitude_pulso_percentual',
            int,
            LIMITES_APARENCIA_VISUAL['amplitude_pulso_percentual'],
        ),
        notify=_Sinais.estadoMudou,
    )
    larguraTracoEeg = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia, 'largura_traco_eeg', float, LIMITES_APARENCIA_VISUAL['largura_traco_eeg']
        ),
        notify=_Sinais.estadoMudou,
    )
    opacidadeTracoEegPercentual = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'opacidade_traco_eeg_percentual',
            int,
            LIMITES_APARENCIA_VISUAL['opacidade_traco_eeg_percentual'],
        ),
        notify=_Sinais.estadoMudou,
    )
    duracaoTransicaoCorSegundos = Property(
        float,
        *_propriedade_editavel(
            _obter_aparencia,
            'duracao_transicao_cor_segundos',
            float,
            LIMITES_APARENCIA_VISUAL['duracao_transicao_cor_segundos'],
        ),
        notify=_Sinais.estadoMudou,
    )
    brilhoLedsPx = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'brilho_leds_px', int, LIMITES_APARENCIA_VISUAL['brilho_leds_px']),
        notify=_Sinais.estadoMudou,
    )
    espacamentoLedsPx = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'espacamento_leds_px', int, LIMITES_APARENCIA_VISUAL['espacamento_leds_px']
        ),
        notify=_Sinais.estadoMudou,
    )
    quantidadeLeds = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'quantidade_leds', int, LIMITES_APARENCIA_VISUAL['quantidade_leds']),
        notify=_Sinais.estadoMudou,
    )
    quantidadeFitas = Property(
        int,
        *_propriedade_editavel(_obter_aparencia, 'quantidade_fitas', int, LIMITES_APARENCIA_VISUAL['quantidade_fitas']),
        notify=_Sinais.estadoMudou,
    )
    escalaEixoYMicroVolts = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'escala_eixo_y_microvolts',
            int,
            LIMITES_APARENCIA_VISUAL['escala_eixo_y_microvolts'],
        ),
        notify=_Sinais.estadoMudou,
    )
    janelaGraficoSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia, 'janela_grafico_segundos', int, LIMITES_APARENCIA_VISUAL['janela_grafico_segundos']
        ),
        notify=_Sinais.estadoMudou,
    )
    velocidadeAnimacaoSegundos = Property(
        int,
        *_propriedade_editavel(
            _obter_aparencia,
            'velocidade_animacao_segundos',
            int,
            LIMITES_APARENCIA_VISUAL['velocidade_animacao_segundos'],
        ),
        notify=_Sinais.estadoMudou,
    )


class EsquizoController(
    _Sinais, _PropriedadesAparenciaVisual, _PropriedadesQuadroAoVivo, _PropriedadesConfiguracao, QObject
):
    """Fonte única de verdade para a view.

    Compõe os mixins de `Property` (aparência visual, quadro ao vivo, configuração) num só
    QObject e guarda aqui o núcleo: `__init__`, os `Signal`s (via `_Sinais`), a orquestração
    da aquisição, a conexão do hardware, o tratamento de erro, a gravação e os `Slot`s. A
    ordem de herança — `_Sinais` primeiro, `QObject` por último — é a validada para o
    Shiboken registrar os sinais e as properties dos mixins.
    """

    erroOcorreu = Signal(str)
    """Emitido com a `situacao` da mensagem sempre que algo é reportado ao usuário."""

    mensagemSolicitada = Signal(object)
    """Porta de entrada para mensagens vindas de FORA da GUI thread.

    Quem está noutra thread não pode escrever `_caixa_atual` direto. Emitindo este sinal, o
    Qt enfileira a chamada de `_reportar` na thread do controller — é o mesmo mecanismo já
    usado por `bitalinoConexaoFinalizada`. Hoje o único cliente é a rede de segurança de
    exceções não tratadas (`ponte/rede_de_seguranca.py`)."""

    bitalinoConexaoFinalizada = Signal(bool, str)
    """Emitido ao final de uma tentativa de conexão do BITalino: (sucesso, mensagem de
    erro — vazia se sucesso). A thread auxiliar de conexão emite este sinal Qt para
    voltar à GUI thread; ver `conexao_bitalino_assincrona.ConectorBitalinoAssincrono`."""

    def __init__(
        self,
        configuracao: Configuracao,
        modelo: ModeloPreditor,
        preferencias_usuario: Preferencias | None = None,
        caminho_preferencias: Path = preferencias.CAMINHO_PADRAO,
    ) -> None:
        super().__init__()
        self._configuracao_app = configuracao
        self._modelo = modelo
        # Opcional para os testes, que constroem o controller sem tocar em disco. Na
        # aplicação real quem carrega é o `main`, junto da configuração.
        self._preferencias = preferencias_usuario if preferencias_usuario is not None else Preferencias()
        self._caminho_preferencias = caminho_preferencias
        self._arduino = hardware.criar_arduino(self._preferencias.componentes_simulados)
        # Os dois modos nascem juntos: os construtores são inertes, nada toca o hardware
        # até `conectar`. Assim a troca de modo é só escolher outra chave deste mapa.
        self._leitores_por_modo = hardware.criar_leitores_por_modo(self._preferencias.componentes_simulados)
        self._conector_bitalino = ConectorBitalinoAssincrono()
        self._varredor_portas = VarredorDePortasAssincrono()
        self._simulador_leds = SimuladorFitaLed()
        self._gravacao_pendente = GerenciadorGravacaoPendente()

        self._servico: ServicoAquisicao | None = None
        self._ciclo: CicloAquisicao | None = None
        self._estado_app: EstadoApp = EstadoApp.CONFIGURANDO
        self._mensagem_status: str = ''
        # As duas superfícies de mensagem. Separadas porque um recado passageiro não pode
        # apagar uma caixa que ainda não foi lida, nem vice-versa.
        self._caixa_atual: EspecificacaoCaixa | None = None
        self._toast_atual: EspecificacaoCaixa | None = None
        self._desfazer_aparencia: tuple[str, dict[str, float]] | None = None
        """A seção restaurada por último e os valores que ela tinha antes.

        Um só, e não uma pilha: o gesto que está na cabeça de quem opera é o mais recente,
        e histórico de desfazer num painel cosmético custa mais do que resolve."""
        self._continuacao_apos_conectar_bitalino: Callable[[], None] | None = None
        self._varrendo_portas: bool = False
        """Ligado enquanto a thread de varredura de portas roda. Ver `varrendoPortas`."""

        self._conectando_bitalino: bool = False
        """Ligado enquanto a thread de conexão roda.

        Sem isto, o seletor de modo continuaria liberado durante a tentativa — e trocar de
        modo nesse intervalo faria a aquisição subir com um leitor que nunca conectou.
        """

        self._porta_bitalino_em_cache: tuple[str, str] | None = None
        """`(mac, porta)` da última derivação, para não varrer as portas do sistema a cada
        ajuste de slider: a prontidão é reavaliada a cada mudança de qualquer campo, e a
        varredura do SetupAPI custa dezenas de milissegundos na GUI thread."""

        # Nasce VAZIA e é preenchida pela varredura assíncrona disparada no fim deste
        # construtor. Listar aqui custava dezenas de milissegundos na GUI thread antes do
        # primeiro quadro — e, sendo síncrono, não havia instante em que a espera pudesse
        # ser desenhada. Ver `_pedir_varredura_de_portas` e `reexaminarPortas`.
        self._portas_seriais_disponiveis: list[str] = []
        # Rótulos, e não números: os seis canais não são equivalentes, e o seletor precisa
        # dizer isso. O valor guardado segue sendo o número — ver `canalBitalinoIndice`.
        self._canais_bitalino_disponiveis: list[str] = list(ROTULOS_DOS_CANAIS)
        self._macs_bitalino_disponiveis: list[str] = list(configuracao.macs_bitalino)
        self._modos_aquisicao_disponiveis: list[str] = list(MODOS_AQUISICAO)
        self._baud_rates_disponiveis: list[str] = [str(baud) for baud in constantes.BAUDRATES_SUPORTADOS]

        # Sem porta inicial: a lista ainda não existe. Quem escolhe a primeira é o retorno
        # da varredura, em `_ao_concluir_varredura_de_portas`.
        self._selecao = criar_configuracao_inicial(
            porta_arduino_inicial='',
            canal_bitalino_inicial=str(constantes.CANAIS_BITALINO[0]),
            mac_bitalino_inicial=self._macs_bitalino_disponiveis[0],
        )
        self._selecao.gravar_aquisicao = self._preferencias.gravar_por_padrao
        self._selecao.tela_cheia = self._preferencias.iniciar_em_tela_cheia
        if self._preferencias.nivel_log:
            log.definir_nivel(self._preferencias.nivel_log)

        self._aparencia = _aparencia_das_preferencias(self._preferencias.aparencia)
        self._ao_vivo = LeituraAoVivo()
        self._conexoes = EstadoConexoesHardware()

        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_DRENAGEM_MS)
        self._timer.timeout.connect(self._ao_bater_o_relogio)
        self._timer.start()

        self._timer_preferencias = QTimer(self)
        self._timer_preferencias.setSingleShot(True)
        self._timer_preferencias.setInterval(INTERVALO_GRAVACAO_PREFERENCIAS_MS)
        self._timer_preferencias.timeout.connect(self._salvar_preferencias)

        self.bitalinoConexaoFinalizada.connect(self._ao_concluir_conexao_bitalino)
        self.mensagemSolicitada.connect(self._reportar)

        self._reavaliar_prontidao()
        # Por último: o relógio que colhe o resultado já precisa estar de pé, e a prontidão
        # inicial já calculada — a varredura a reavalia sozinha quando chegar.
        self._pedir_varredura_de_portas()

    # ---- relógio / drenagem da fila de aquisição --------------------------
    @staticmethod
    def _agora_ms() -> float:
        return time.monotonic() * 1000.0

    def _ao_bater_o_relogio(self) -> None:
        """Chamado a cada `INTERVALO_DRENAGEM_MS` pelo `QTimer` — nunca bloqueia."""
        if self._varrendo_portas:
            resultado = self._varredor_portas.coletar()
            if resultado is not None:
                self._ao_concluir_varredura_de_portas(resultado)
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
                    self._reportar(evento.caixa)
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
            self._gravacao_pendente.oferecer(
                resultados,
                modo.value,
                formato_nome=self._preferencias.formato_nome_gravacao,
                contexto_nome=self._contexto_do_nome(),
            )

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
            self._reportar(catalogo_erros.falha_conexao_arduino(erro))
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

    # ---- modo simulação ------------------------------------------------------
    def _componentes_simulados_agora(self) -> set[str]:
        """O que está simulado de fato, deduzido dos objetos vivos.

        Deduzido, e não lido da preferência: depois de uma reconstrução é o objeto que
        manda, e a preferência pode estar sobreposta por `ESQUIZOCAP_FAKE`. Perguntar ao
        estado real elimina a chance de a interface anunciar "real" com um fake em uso —
        que é justamente o aviso que não pode mentir.
        """
        simulados: set[str] = set()
        if isinstance(self._arduino, ArduinoFake):
            simulados.add('arduino')
        if self._bitalino_esta_simulado():
            simulados.add('bitalino')
        return simulados

    def _aquisicao_em_curso(self) -> bool:
        return self._estado_app in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO)

    def _motivo_para_nao_alterar_simulacao(self) -> str:
        """Por que os controles de simulação estão travados agora. Vazio = destravados."""
        if hardware.simulacao_vem_do_ambiente():
            return (
                f'Definido pela variável de ambiente {hardware.NOME_VARIAVEL_FAKE}, '
                'que tem precedência. Remova-a do terminal para escolher aqui.'
            )
        if self._aquisicao_em_curso():
            return 'Pare a aquisição para trocar entre hardware real e simulado.'
        if self._conectando_bitalino:
            return 'Aguarde a conexão do BITalino terminar.'
        if self._conexoes.arduino_conectado or self._conexoes.bitalino_conectado:
            return 'Desconecte o Arduino e o BITalino para trocar entre hardware real e simulado.'
        return ''

    componentesSimulados = Property(
        list, lambda self: sorted(self._componentes_simulados_agora()), notify=_Sinais.estadoMudou
    )
    arduinoSimulado = Property(
        bool, lambda self: 'arduino' in self._componentes_simulados_agora(), notify=_Sinais.estadoMudou
    )
    bitalinoSimulado = Property(bool, lambda self: self._bitalino_esta_simulado(), notify=_Sinais.estadoMudou)
    emModoSimulacao = Property(bool, lambda self: bool(self._componentes_simulados_agora()), notify=_Sinais.estadoMudou)
    podeAlterarSimulacao = Property(
        bool, lambda self: not self._motivo_para_nao_alterar_simulacao(), notify=_Sinais.estadoMudou
    )
    motivoSimulacaoTravada = Property(
        str, lambda self: self._motivo_para_nao_alterar_simulacao(), notify=_Sinais.estadoMudou
    )
    bordaDeSimulacao = Property(bool, lambda self: self._preferencias.borda_de_simulacao, notify=_Sinais.estadoMudou)

    @Slot(bool)
    def definirBordaDeSimulacao(self, valor: bool) -> None:
        if bool(valor) == self._preferencias.borda_de_simulacao:
            return
        self._preferencias.borda_de_simulacao = bool(valor)
        self._salvar_preferencias()
        self.estadoMudou.emit()

    # ---- reset da aparência ------------------------------------------------
    # Um único caminho para os quatro botões (três seções + o global da aba Interface), e a
    # razão é a rede: o desfazer nasce no slot, então nenhum gesto de reset pode existir sem
    # ele. Um segundo caminho paralelo deixaria justamente o mais destrutivo desprotegido.
    @Slot(str)
    def restaurarSecaoAparencia(self, secao: str) -> None:
        """Devolve os controles de uma seção do painel "Aparência" aos valores de fábrica.

        Guarda o estado anterior para o "Desfazer" do toast. Chave desconhecida é logada e
        ignorada, na mesma política tolerante de `_aparencia_das_preferencias`: preferência
        cosmética não derruba a app.
        """
        campos = SECOES_APARENCIA.get(secao)
        if campos is None:
            logger.warning(f'Pedido de restauração de uma seção de aparência desconhecida: "{secao}".')
            return

        padrao = AparenciaVisual()
        anterior = {campo: getattr(self._aparencia, campo) for campo in campos}
        if all(valor == getattr(padrao, campo) for campo, valor in anterior.items()):
            return

        for campo in campos:
            setattr(self._aparencia, campo, getattr(padrao, campo))
        self._desfazer_aparencia = (secao, anterior)
        self._salvar_preferencias()
        self._reportar(catalogo_erros.aparencia_restaurada(ROTULOS_DAS_SECOES_APARENCIA[secao]))
        self._emitir_todos_os_sinais()

    @Slot()
    def restaurarAparenciaPadrao(self) -> None:
        """Devolve os 16 controles do painel "Aparência" aos valores de fábrica."""
        self.restaurarSecaoAparencia(SECAO_APARENCIA_TUDO)

    @Slot()
    def desfazerRestauracaoAparencia(self) -> None:
        """Reaplica os valores que a última restauração jogou fora."""
        if self._desfazer_aparencia is None:
            return
        _secao, anterior = self._desfazer_aparencia
        self._desfazer_aparencia = None
        for campo, valor in anterior.items():
            setattr(self._aparencia, campo, valor)
        self._salvar_preferencias()
        self._toast_atual = None
        self._emitir_todos_os_sinais()

    def _descartar_desfazer_se_a_secao_foi_editada(self, atributo: str) -> None:
        """Invalida o desfazer pendente quando o usuário mexe num controle da mesma seção.

        Sem isto haveria sobrescrita silenciosa: restaurar "Animação", gostar do padrão mas
        subir o glow para 1.4, e então clicar em "Desfazer" descartaria o 1.4 junto — sem
        erro, sem aviso, só a instalação num estado que ninguém pediu. Editar uma seção é
        uma decisão mais nova que a restauração, então ela vence.
        """
        if self._desfazer_aparencia is None:
            return
        secao, _anterior = self._desfazer_aparencia
        if atributo not in SECOES_APARENCIA[secao]:
            return
        self._desfazer_aparencia = None
        self._toast_atual = None

    def _secoes_de_aparencia_modificadas(self) -> list[str]:
        """As seções cujos valores diferem da fábrica — é o que acende os botões "Resetar".

        Um botão esmaecido diz de relance "aqui você não mexeu", informação que hoje não
        existe em lugar nenhum: um brilho em 6 pode ser o padrão ou um ajuste deliberado, e
        a fita acende igual nos dois casos.
        """
        padrao = AparenciaVisual()
        return [
            secao
            for secao, campos in SECOES_APARENCIA.items()
            if any(getattr(self._aparencia, campo) != getattr(padrao, campo) for campo in campos)
        ]

    secoesAparenciaModificadas = Property('QStringList', _secoes_de_aparencia_modificadas, notify=_Sinais.estadoMudou)

    @Slot(str, bool)
    def definirSimulacao(self, componente: str, ativo: bool) -> None:
        """Liga ou desliga a simulação de um componente, reconstruindo o hardware na hora.

        Recusa com aviso na tela quando há dispositivo conectado ou aquisição em curso: a
        troca substitui os objetos de borda, e fazê-la com um stream aberto deixaria o
        objeto antigo segurando porta serial ou socket até o processo morrer.
        """
        if componente not in hardware.COMPONENTES_CONHECIDOS:
            logger.warning(f'Pedido para simular um componente desconhecido: "{componente}". Ignorado.')
            return

        motivo = self._motivo_para_nao_alterar_simulacao()
        if motivo:
            logger.info(f'Troca de simulação de "{componente}" recusada: {motivo}')
            self._reportar(catalogo_erros.simulacao_bloqueada(motivo))
            return

        desejados = set(self._preferencias.componentes_simulados)
        desejados.add(componente) if ativo else desejados.discard(componente)
        if frozenset(desejados) == self._preferencias.componentes_simulados:
            return

        self._preferencias.componentes_simulados = frozenset(desejados)
        self._reconstruir_hardware()
        self._salvar_preferencias()

    def _reconstruir_hardware(self) -> None:
        """Descarta os objetos de borda e cria novos conforme as preferências.

        Só é seguro com tudo desconectado — quem chama garante isso. O encerramento dos
        antigos é feito mesmo assim, porque um leitor que conectou e desconectou pode ter
        recurso pendente, e um objeto órfão segurando a porta é invisível até a próxima
        tentativa de conexão falhar sem motivo aparente.
        """
        simulados = self._preferencias.componentes_simulados
        logger.info(f'Reconstruindo o hardware. Componentes simulados: {sorted(simulados) or "nenhum"}.')

        self._encerrar_todos_os_leitores()
        self._arduino.desconectar()

        self._arduino = hardware.criar_arduino(simulados)
        self._leitores_por_modo = hardware.criar_leitores_por_modo(simulados)
        self._conexoes.arduino_conectado = False
        self._conexoes.bitalino_conectado = False

        # A porta em cache foi derivada para o hardware anterior, e a lista de portas
        # seriais muda quando o Arduino deixa de ser o fake (que anuncia portas fictícias).
        # A lista é esvaziada AGORA, e não só quando a varredura voltar: manter as portas
        # fictícias do fake visíveis depois de voltar ao hardware real ofereceria uma porta
        # que não existe, e o erro só apareceria na tentativa de conexão.
        self._porta_bitalino_em_cache = None
        self._portas_seriais_disponiveis = []
        self._selecao.porta_arduino = ''
        self._pedir_varredura_de_portas()

        # O canal ativo é estado da SELEÇÃO, não do leitor: sem reaplicá-lo, os leitores
        # novos converteriam o canal 1 enquanto a tela mostra outro. Nenhum erro, cor errada.
        self._reaplicar_canal_ativo_nos_leitores()

        self._reavaliar_prontidao()
        self._emitir_todos_os_sinais()

    def _reaplicar_canal_ativo_nos_leitores(self) -> None:
        """Informa aos leitores o canal que já está escolhido na tela."""
        canal = self._selecao.canal_bitalino
        if canal not in CANAIS_VALIDOS:
            return
        for leitor in set(self._leitores_por_modo.values()):
            leitor.definir_canal_ativo(canal=int(canal))

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
            return 'BITalino simulado: o sinal é sintético e a escolha de modo não tem efeito.'

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

    def _porta_derivada_do_bitalino(self, *, bloqueando: bool = False) -> str:
        """Descobre a porta de acesso do BITalino a partir do MAC escolhido.

        Devolve string vazia quando não há porta — dispositivo não pareado, desligado, ou
        sistema fora do Windows — e também enquanto a varredura ainda não voltou.

        Args:
            bloqueando: Se pode varrer o sistema aqui mesmo, na thread de quem chamou. Só
                o caminho de CONECTAR usa isto: ali a porta é a resposta, e devolver vazio
                faria a conexão tentar um endereço em branco. Os BINDINGS da view usam o
                padrão (`False`), que apenas dispara a varredura em segundo plano e deixa
                `varrendoPortas` acender — varrer dentro de um binding congelaria o event
                loop, e com ele o próprio indicador que anuncia a espera.
        """
        if not self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return ''

        mac = self._selecao.mac_bitalino
        if self._porta_bitalino_em_cache is not None and self._porta_bitalino_em_cache[0] == mac:
            return self._porta_bitalino_em_cache[1]

        if not bloqueando:
            self._pedir_varredura_de_portas()
            return ''

        porta = (
            portas_bluetooth.derivar_porta(mac=mac, portas_do_sistema=portas_bluetooth.listar_portas_do_sistema()) or ''
        )
        self._porta_bitalino_em_cache = (mac, porta)
        return porta

    # ---- varredura de portas -------------------------------------------------
    def _pedir_varredura_de_portas(self) -> None:
        """Manda varrer as portas numa thread auxiliar, se já não houver uma varredura em curso.

        Chamável de dentro de um binding: a guarda de reentrância é o que impede o ciclo
        "binding lê vazio → pede varredura → varredura emite → binding lê vazio de novo".
        """
        if self._varrendo_portas:
            return

        self._varrendo_portas = True
        self._varredor_portas.varrer(listar_portas_seriais=self._arduino.listar_portas, mac=self._selecao.mac_bitalino)
        self.estadoMudou.emit()

    @Slot()
    def reexaminarPortas(self) -> None:
        """Varre as portas de novo, a pedido de quem está operando.

        A interface Tkinter nunca detectou hotplug e a Qt herdou isso: as portas eram
        listadas uma vez, na abertura, e um Arduino plugado depois só aparecia reiniciando o
        app. Com a varredura já fora da GUI thread, repetir passou a custar nada — e num
        cabo que caiu no meio da montagem, reiniciar a obra é o pior momento possível.
        """
        self._porta_bitalino_em_cache = None
        self._pedir_varredura_de_portas()

    def _ao_concluir_varredura_de_portas(self, resultado: ResultadoVarredura) -> None:
        """Aplica o que a varredura encontrou. Sempre na GUI thread — quem chama é o
        `QTimer` de drenagem, ver `_ao_bater_o_relogio`."""
        self._varrendo_portas = False
        self._portas_seriais_disponiveis = resultado.portas_seriais
        self._porta_bitalino_em_cache = (resultado.mac, resultado.porta_bitalino)

        # A porta escolhida pode ter sumido entre uma varredura e outra (cabo removido), e
        # deixá-la selecionada faria a conexão falhar apontando para uma porta inexistente.
        if self._selecao.porta_arduino not in self._portas_seriais_disponiveis:
            self._selecao.porta_arduino = (
                self._portas_seriais_disponiveis[0] if self._portas_seriais_disponiveis else ''
            )

        self._reavaliar_prontidao()
        self._emitir_todos_os_sinais()

    def _endereco_do_modo_escolhido(self) -> str:
        """Onde encontrar o dispositivo, conforme o modo: MAC no OpenSignals, porta no Direto.

        Varre bloqueando se preciso: aqui a porta não pode ser "ainda não sei". Já estamos
        no gesto de conectar, que o operador sabe que demora.
        """
        if self._modo_aquisicao_escolhido().exige_porta_de_acesso:
            return self._porta_derivada_do_bitalino(bloqueando=True)
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
        # Espera visível: o toast anuncia que algo está em curso mesmo quando quem disparou
        # foi "Começar aquisição", com o painel de setup fechado.
        self._reportar(catalogo_erros.conectando_bitalino())
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

        # Retira o toast "conectando…" — ele descreve uma espera que acabou. Só o dele: um
        # recado que tenha chegado por cima no meio da tentativa é notícia mais nova, e
        # apagá-lo faria uma mensagem sumir sem ninguém ter lido.
        if self._toast_atual is not None and self._toast_atual.situacao is catalogo_erros.Situacao.CONECTANDO_BITALINO:
            self._toast_atual = None
        self.estadoMudou.emit()

        if not sucesso:
            self._reportar(catalogo_erros.falha_conexao_bitalino(mensagem_erro))
            return
        self._definir_e_notificar(self._conexoes, 'bitalino_conectado', True)
        if continuacao is not None:
            continuacao()

    # ---- mensagens ao usuário --------------------------------------------
    # Duas superfícies, e quem escolhe entre elas é a severidade da mensagem (ver
    # `Severidade.abre_caixa`): o que interrompe a obra vai para a caixa modal central; o
    # recado de ferramenta vira um toast que sai sozinho. A view não decide nada disso —
    # ela só desenha o que estiver em `_caixa_atual` e `_toast_atual`.
    def _reportar(self, caixa: EspecificacaoCaixa) -> None:
        """Põe uma mensagem na tela, na superfície que a severidade dela pedir.

        Chamado também pela drenagem de eventos da thread de aquisição, que roda na GUI
        thread via `QTimer` — nenhuma thread de fora toca este estado diretamente.
        """
        if caixa.severidade.abre_caixa:
            self._caixa_atual = caixa
        else:
            self._toast_atual = caixa
        self.erroOcorreu.emit(caixa.situacao.value)
        self.estadoMudou.emit()

    @Slot()
    def fecharCaixa(self) -> None:
        """Fecha a caixa modal. A view só chama isto quando a caixa é dispensável."""
        self._caixa_atual = None
        self.estadoMudou.emit()

    @Slot(str)
    def responderCaixa(self, papel: str) -> None:
        """Recebe o botão que foi clicado, identificado pelo PAPEL e não pelo rótulo.

        Hoje todas as caixas são notícia consumada e qualquer papel só fecha. O parâmetro
        existe porque é aqui que uma confirmação futura ("descartar a gravação?") vai
        ramificar, sem precisar mexer no QML de novo.
        """
        logger.debug(f'Caixa de mensagem respondida com "{papel}"')
        self.fecharCaixa()

    @Slot()
    def fecharToast(self) -> None:
        """Fecha o recado passageiro — pelo X ou porque os 7 segundos venceram."""
        self._toast_atual = None
        self.estadoMudou.emit()

    caixaAberta = Property(bool, lambda self: self._caixa_atual is not None, notify=_Sinais.estadoMudou)
    caixaSituacao = Property(str, lambda self: self._campo_da_caixa('situacao'), notify=_Sinais.estadoMudou)
    caixaSeveridade = Property(str, lambda self: self._campo_da_caixa('severidade'), notify=_Sinais.estadoMudou)
    caixaTitulo = Property(str, lambda self: self._campo_da_caixa('titulo'), notify=_Sinais.estadoMudou)
    caixaMensagem = Property(str, lambda self: self._campo_da_caixa('mensagem'), notify=_Sinais.estadoMudou)
    caixaDetalhe = Property(str, lambda self: self._campo_da_caixa('detalhe'), notify=_Sinais.estadoMudou)
    caixaDispensavel = Property(
        bool, lambda self: self._caixa_atual is None or self._caixa_atual.dispensavel, notify=_Sinais.estadoMudou
    )
    caixaAcoes = Property(list, lambda self: self._acoes_da_caixa(), notify=_Sinais.estadoMudou)

    @Slot()
    def acionarAcaoDoToast(self) -> None:
        """Aciona o botão de ação do toast — hoje só existe o "Desfazer" da aparência.

        Ramifica por papel, e não por rótulo, como a caixa modal já faz: quando um segundo
        toast com ação aparecer, ele entra aqui sem que o QML precise saber o que a ação
        significa.
        """
        if self._toast_atual is None:
            return
        papeis = {acao.papel for acao in self._toast_atual.acoes}
        if PapelAcao.DESFAZER in papeis:
            self.desfazerRestauracaoAparencia()

    toastAberto = Property(bool, lambda self: self._toast_atual is not None, notify=_Sinais.estadoMudou)

    def _toast_descreve_algo_em_curso(self) -> bool:
        """Se o toast atual anuncia uma espera que ainda não terminou.

        Muda o desenho do toast (indicador no lugar do glifo de severidade) e desliga o
        auto-fechamento: um recado que sai sozinho depois de 7 s mentiria sobre uma espera
        que ainda está acontecendo. Quem abre uma mensagem em andamento é responsável por
        retirá-la — ver `_ao_concluir_conexao_bitalino`.
        """
        return self._toast_atual is not None and self._toast_atual.situacao in _SITUACOES_EM_ANDAMENTO

    toastEmAndamento = Property(bool, _toast_descreve_algo_em_curso, notify=_Sinais.estadoMudou)
    toastAcaoRotulo = Property(str, lambda self: self._rotulo_da_acao_do_toast(), notify=_Sinais.estadoMudou)
    toastSituacao = Property(str, lambda self: self._campo_do_toast('situacao'), notify=_Sinais.estadoMudou)
    toastSeveridade = Property(str, lambda self: self._campo_do_toast('severidade'), notify=_Sinais.estadoMudou)
    toastTitulo = Property(str, lambda self: self._campo_do_toast('titulo'), notify=_Sinais.estadoMudou)
    toastMensagem = Property(str, lambda self: self._campo_do_toast('mensagem'), notify=_Sinais.estadoMudou)

    @staticmethod
    def _texto_do_campo(caixa: EspecificacaoCaixa | None, campo: str) -> str:
        """Lê um campo da caixa como string, devolvendo vazio quando não há caixa.

        `situacao` e `severidade` são `Enum`; o QML só entende o valor deles.
        """
        if caixa is None:
            return ''
        valor = getattr(caixa, campo)
        return str(valor.value) if isinstance(valor, Enum) else str(valor)

    def _campo_da_caixa(self, campo: str) -> str:
        return self._texto_do_campo(self._caixa_atual, campo)

    def _campo_do_toast(self, campo: str) -> str:
        return self._texto_do_campo(self._toast_atual, campo)

    def _rotulo_da_acao_do_toast(self) -> str:
        """O rótulo do botão de ação do toast, ou vazio quando ele não tem ação.

        Só ações de papel `DESFAZER` viram botão aqui, e não é detalhe: toda entrada do
        catálogo ganha um `ACAO_OK` por padrão, então aceitar qualquer papel poria um botão
        "OK" inútil em cada recado de ferramenta que já existe.
        """
        if self._toast_atual is None:
            return ''
        return next((acao.rotulo for acao in self._toast_atual.acoes if acao.papel is PapelAcao.DESFAZER), '')

    def _acoes_da_caixa(self) -> list[dict[str, str]]:
        """Os botões, como dicionários simples — é o que atravessa para o QML."""
        if self._caixa_atual is None:
            return []
        return [{'papel': acao.papel.value, 'rotulo': acao.rotulo} for acao in self._caixa_atual.acoes]

    # ---- gravação (Excel) -------------------------------------------------
    gravacaoPendente = Property(bool, lambda self: self._gravacao_pendente.pendente, notify=_Sinais.estadoMudou)
    nomeSugeridoGravacao = Property(str, lambda self: self._gravacao_pendente.nome_sugerido, notify=_Sinais.estadoMudou)
    perguntarOndeSalvar = Property(
        bool, lambda self: self._preferencias.perguntar_onde_salvar, notify=_Sinais.estadoMudou
    )
    pastaGravacoes = Property(str, lambda self: str(self._preferencias.pasta_gravacoes), notify=_Sinais.estadoMudou)
    pastaGravacoesUrl = Property(
        str,
        lambda self: QUrl.fromLocalFile(str(self._preferencias.pasta_gravacoes)).toString(),
        notify=_Sinais.estadoMudou,
    )

    formatoNomeGravacao = Property(
        str, lambda self: self._preferencias.formato_nome_gravacao, notify=_Sinais.estadoMudou
    )
    formatoNomePadrao = Property(str, lambda self: persistencia.FORMATO_NOME_PADRAO, constant=True)
    marcadoresDoNome = Property(list, lambda self: list(persistencia.MARCADORES_DO_NOME), constant=True)
    previaNomeGravacao = Property(str, lambda self: self._previa_do_nome(), notify=_Sinais.estadoMudou)
    gravarPorPadrao = Property(bool, lambda self: self._preferencias.gravar_por_padrao, notify=_Sinais.estadoMudou)

    def _contexto_do_nome(self) -> dict[str, str]:
        """Canal e taxa da sessão, para os marcadores do nome do arquivo."""
        return {
            'canal': f'A{self._selecao.canal_bitalino}',
            'taxa': f'{self._selecao.taxa_amostragem_hz}Hz',
        }

    def _previa_do_nome(self) -> str:
        """Como o arquivo se chamaria se a gravação terminasse agora.

        A prévia ao vivo é o que torna um campo de formato usável: sem ela o operador só
        descobre que digitou `{cannal}` quando a gravação já acabou e o nome saiu errado.
        """
        return f'{persistencia.nome_sugerido(self._selecao.modo_analise, self._preferencias.formato_nome_gravacao, self._contexto_do_nome())}.xlsx'

    @Slot(str)
    def definirFormatoNomeGravacao(self, valor: str) -> None:
        if valor == self._preferencias.formato_nome_gravacao:
            return
        self._preferencias.formato_nome_gravacao = valor
        self._agendar_gravacao_de_preferencias()
        self.estadoMudou.emit()

    @Slot(bool)
    def definirGravarPorPadrao(self, valor: bool) -> None:
        """Liga o "gravar aquisição" desta sessão junto, para o efeito ser visível na hora."""
        if bool(valor) == self._preferencias.gravar_por_padrao:
            return
        self._preferencias.gravar_por_padrao = bool(valor)
        self._salvar_preferencias()
        self._definir_e_notificar(self._selecao, 'gravar_aquisicao', bool(valor))
        self.estadoMudou.emit()

    @Slot(bool)
    def definirPerguntarOndeSalvar(self, valor: bool) -> None:
        if bool(valor) == self._preferencias.perguntar_onde_salvar:
            return
        self._preferencias.perguntar_onde_salvar = bool(valor)
        self._salvar_preferencias()
        self.estadoMudou.emit()

    @Slot(str)
    def definirPastaGravacoes(self, caminho: str) -> None:
        """Recebe a pasta escolhida no `FolderDialog` (pode vir como `file://` URL)."""
        caminho_local = QUrl(caminho).toLocalFile() or caminho
        if not caminho_local.strip():
            return
        self._preferencias.pasta_gravacoes = Path(caminho_local)
        self._salvar_preferencias()
        self.estadoMudou.emit()

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
            self._reportar(catalogo_erros.falha_ao_salvar_gravacao(erro))
        self.estadoMudou.emit()

    @Slot()
    def salvarGravacaoNaPastaPadrao(self) -> None:
        """Grava sem diálogo, na pasta configurada, com o nome sugerido.

        Usado quando "perguntar onde salvar" está desligado — o caso da instalação que roda
        sozinha e não pode parar esperando alguém clicar em "Salvar".
        """
        pasta = self._preferencias.pasta_gravacoes
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            self._reportar(catalogo_erros.pasta_gravacoes_nao_criada(pasta, erro))
            return
        self.salvarGravacao(str(pasta / f'{self._gravacao_pendente.nome_sugerido}.xlsx'))

    @Slot()
    def descartarGravacao(self) -> None:
        logger.warning('Usuário cancelou o salvamento. A gravação foi descartada.')
        self._gravacao_pendente.descartar()
        self.estadoMudou.emit()

    # ---- diagnóstico --------------------------------------------------------
    nivelLog = Property(str, lambda self: self._preferencias.nivel_log or log.NIVEL_PADRAO, notify=_Sinais.estadoMudou)
    niveisLogDisponiveis = Property(list, lambda self: list(log.NIVEIS_DISPONIVEIS), constant=True)
    temArquivoDeLog = Property(bool, lambda self: log.arquivo_atual() is not None, notify=_Sinais.estadoMudou)

    @Slot(str)
    def definirNivelLog(self, valor: str) -> None:
        """Troca o nível dos logs na hora — sem reiniciar, que é o ponto de ter isto aqui."""
        if valor == self.nivelLog:
            return
        log.definir_nivel(valor)
        self._preferencias.nivel_log = valor
        self._salvar_preferencias()
        self.estadoMudou.emit()

    @staticmethod
    def _abrir_no_sistema(caminho: Path) -> bool:
        """Abre um arquivo ou pasta no explorador. Devolve se deu certo."""
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho.resolve()))))

    @Slot()
    def abrirPastaGravacoes(self) -> None:
        pasta = self._preferencias.pasta_gravacoes
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            self._reportar(catalogo_erros.pasta_gravacoes_inacessivel(pasta, erro))
            return
        if not self._abrir_no_sistema(pasta):
            self._reportar(catalogo_erros.pasta_gravacoes_inacessivel(pasta))

    @Slot()
    def abrirPastaLogs(self) -> None:
        if not self._abrir_no_sistema(recursos.PASTA_LOGS):
            self._reportar(catalogo_erros.pasta_logs_inacessivel(recursos.PASTA_LOGS))

    @Slot()
    def abrirLogAtual(self) -> None:
        arquivo = log.arquivo_atual()
        if arquivo is None:
            self._reportar(catalogo_erros.sem_arquivo_de_log())
            return
        if not self._abrir_no_sistema(arquivo):
            self._reportar(catalogo_erros.log_inacessivel(arquivo))

    textoDiagnostico = Property(str, lambda self: self._texto_diagnostico(), notify=_Sinais.estadoMudou)

    def _texto_diagnostico(self) -> str:
        """Resumo colável do estado da aplicação, para acompanhar um relato de problema.

        Reúne o que sempre acaba sendo perguntado de volta ("qual modo? qual taxa? estava
        simulado?"), incluindo o caminho do log desta execução.
        """
        simulados = sorted(self._componentes_simulados_agora())
        linhas = [
            'EsquizoCap — diagnóstico',
            f'Modo de aquisição: {self._selecao.modo_aquisicao}',
            f'Modo de predição: {self._selecao.modo_analise}',
            f'Taxa acordada: {self._selecao.taxa_amostragem_hz} Hz',
            f'Canal ativo: {self._selecao.canal_bitalino}',
            f'MAC: {self._selecao.mac_bitalino}',
            f'Porta de acesso: {self._porta_derivada_do_bitalino() or "(não encontrada)"}',
            f'Porta do Arduino: {self._selecao.porta_arduino or "(nenhuma)"}',
            f'Arduino conectado: {self._rotulo_de_conexao(self._conexoes.arduino_conectado)}',
            f'BITalino conectado: {self._rotulo_de_conexao(self._conexoes.bitalino_conectado)}',
            f'Simulação: {", ".join(simulados) if simulados else "nenhuma (hardware real)"}',
            f'Estado: {self._estado_app.name}',
            f'Modelo: {self._configuracao_app.caminho_modelo}',
            f'Nível de log: {self.nivelLog}',
            f'Arquivo de log: {log.arquivo_atual() or "(não configurado)"}',
        ]
        return '\n'.join(linhas)

    @Slot()
    def copiarDiagnostico(self) -> None:
        """Copia o diagnóstico para a área de transferência.

        A área de transferência só existe numa `QGuiApplication`; sob a `QCoreApplication`
        dos testes não há nenhuma, e falhar aqui derrubaria um teste por um recurso de
        conveniência. Nesse caso, o diagnóstico vai para o log.
        """
        aplicacao = QGuiApplication.instance()
        area = aplicacao.clipboard() if isinstance(aplicacao, QGuiApplication) else None
        if area is None:
            logger.info(f'Sem área de transferência disponível. Diagnóstico:\n{self._texto_diagnostico()}')
            return
        area.setText(self._texto_diagnostico())

    # ---- geometria e chrome da janela ---------------------------------------
    lembrarGeometriaJanela = Property(
        bool, lambda self: self._preferencias.lembrar_geometria_janela, notify=_Sinais.estadoMudou
    )
    iniciarEmTelaCheia = Property(
        bool, lambda self: self._preferencias.iniciar_em_tela_cheia, notify=_Sinais.estadoMudou
    )
    mostrarSeloExposicao = Property(
        bool, lambda self: self._preferencias.mostrar_selo_exposicao, notify=_Sinais.estadoMudou
    )
    temGeometriaSalva = Property(
        bool,
        lambda self: (
            self._preferencias.lembrar_geometria_janela
            and {'x', 'y', 'largura', 'altura'} <= set(self._preferencias.geometria_janela)
        ),
        notify=_Sinais.estadoMudou,
    )
    janelaX = Property(int, lambda self: self._preferencias.geometria_janela.get('x', 0), notify=_Sinais.estadoMudou)
    janelaY = Property(int, lambda self: self._preferencias.geometria_janela.get('y', 0), notify=_Sinais.estadoMudou)
    janelaLargura = Property(
        int, lambda self: self._preferencias.geometria_janela.get('largura', 0), notify=_Sinais.estadoMudou
    )
    janelaAltura = Property(
        int, lambda self: self._preferencias.geometria_janela.get('altura', 0), notify=_Sinais.estadoMudou
    )

    @Slot(bool)
    def definirLembrarGeometriaJanela(self, valor: bool) -> None:
        if bool(valor) == self._preferencias.lembrar_geometria_janela:
            return
        self._preferencias.lembrar_geometria_janela = bool(valor)
        if not valor:
            # Descarta o que já estava guardado: manter a geometria antiga faria a opção
            # parecer que não funcionou quando fosse religada meses depois.
            self._preferencias.geometria_janela = {}
        self._salvar_preferencias()
        self.estadoMudou.emit()

    @Slot(bool)
    def definirIniciarEmTelaCheia(self, valor: bool) -> None:
        if bool(valor) == self._preferencias.iniciar_em_tela_cheia:
            return
        self._preferencias.iniciar_em_tela_cheia = bool(valor)
        self._salvar_preferencias()
        self.estadoMudou.emit()

    @Slot(bool)
    def definirMostrarSeloExposicao(self, valor: bool) -> None:
        if bool(valor) == self._preferencias.mostrar_selo_exposicao:
            return
        self._preferencias.mostrar_selo_exposicao = bool(valor)
        self._salvar_preferencias()
        self.estadoMudou.emit()

    @Slot(int, int, int, int)
    def salvarGeometriaJanela(self, x: int, y: int, largura: int, altura: int) -> None:
        """Guarda a geometria da janela. Chamado pela view a cada mover/redimensionar.

        Passa pelo debounce em vez de gravar direto: arrastar a janela dispara isto dezenas
        de vezes por segundo.
        """
        if not self._preferencias.lembrar_geometria_janela:
            return
        nova = {'x': int(x), 'y': int(y), 'largura': int(largura), 'altura': int(altura)}
        if nova == self._preferencias.geometria_janela:
            return
        self._preferencias.geometria_janela = nova
        self._agendar_gravacao_de_preferencias()

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
        # Incondicional: um ajuste feito no último segundo ainda estaria em debounce.
        self._salvar_preferencias()

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
        if dono is self._aparencia:
            self._agendar_gravacao_de_preferencias()
            self._descartar_desfazer_se_a_secao_foi_editada(atributo)
        self._reavaliar_prontidao()
        self._emitir_todos_os_sinais()

    # ---- preferências do usuário -------------------------------------------
    def _agendar_gravacao_de_preferencias(self) -> None:
        """Reinicia a contagem do debounce. Só o último ajuste de uma rajada chega ao disco."""
        self._timer_preferencias.start()

    def _salvar_preferencias(self) -> None:
        self._timer_preferencias.stop()
        self._preferencias.aparencia = asdict(self._aparencia)
        preferencias.salvar(self._preferencias, self._caminho_preferencias)

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

    @Slot(int)
    def definirCanalPorIndice(self, indice: int) -> None:
        """Escolhe o canal pela POSIÇÃO no seletor, já que o rótulo não é o valor."""
        if 0 <= indice < len(CANAIS_NA_ORDEM_DO_SELETOR):
            self.canalBitalino = str(CANAIS_NA_ORDEM_DO_SELETOR[indice])

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

    @staticmethod
    def _rotulo_de_conexao(conectado: bool) -> str:
        return 'conectado' if conectado else 'desconectado'
