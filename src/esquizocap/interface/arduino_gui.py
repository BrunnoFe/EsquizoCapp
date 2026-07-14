"""Orquestração da GUI em torno do controlador de LED.

Este módulo cuida só do que a interface gráfica precisa (habilitar/desabilitar
widgets, trocar o rótulo do botão, pintar o status). O acesso ao hardware em si
fica atrás de `ControladorLedArduino` — ver `esquizocap/hardware/`.
"""

import logging
from dataclasses import dataclass

import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from esquizocap.hardware import ControladorLedArduino, ErroConexaoArduino
from esquizocap.hardware.constantes import MODOS_LUMINOSIDADE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WidgetsArduino:
    """Os widgets que a conexão do Arduino precisa mexer.

    Existe para que `alternar_conexao` não receba um `**kwargs` com chaves mágicas
    (`kwargs['status']['green']`): ali, um erro de digitação numa chave só aparecia como
    `KeyError` no clique do usuário, e nem o mypy nem o editor ajudavam.
    """

    botao: ttk.Button
    rotulo_botao: ttk.StringVar
    caixas: tuple[ttk.Combobox, ...]
    """Comboboxes travados enquanto o Arduino está conectado (porta, velocidade, modo)."""

    rotulo_status: ttk.Label
    imagem_conectado: ttk.PhotoImage
    imagem_desconectado: ttk.PhotoImage


def alternar_conexao(
    arduino: ControladorLedArduino,
    porta: str,
    baudrate: int,
    modo: str,
    widgets: WidgetsArduino,
) -> None:
    """Conecta ou desconecta o Arduino, refletindo o resultado nos widgets da GUI.

    Serve de callback para o botão de conexão: alterna entre conectar e desconectar
    conforme o estado atual do controlador.

    Args:
        porta: Porta escolhida no combobox, no formato "COM5 - descrição".
        modo: Modo de luminosidade, entre os de `constantes.MODOS_LUMINOSIDADE`.
    """
    if arduino.esta_conectado:
        _desconectar(arduino=arduino, widgets=widgets)
        return

    _conectar(arduino=arduino, porta=porta, baudrate=baudrate, modo=modo, widgets=widgets)


def _conectar(
    arduino: ControladorLedArduino,
    porta: str,
    baudrate: int,
    modo: str,
    widgets: WidgetsArduino,
) -> None:
    logger.info(f'Conectando o Arduino na porta "{porta}" a {baudrate} bauds ...')

    if 'COM' not in porta:
        Messagebox.show_warning(
            title='Arduino error!', message='Selecione a porta que o Arduino está conectado.'
        )
        return

    if modo not in MODOS_LUMINOSIDADE:
        Messagebox.show_warning(
            title='Arduino error!', message='Selecione um modo de luminosidade.'
        )
        return

    widgets.botao['state'] = 'disabled'

    try:
        arduino.conectar(porta=porta, baudrate=baudrate)
    except ErroConexaoArduino as erro:
        widgets.rotulo_botao.set('Conectar')
        widgets.botao['state'] = 'normal'
        logger.error(f'Não foi possível conectar ao Arduino na porta "{porta}": {erro}')
        Messagebox.show_error(
            title='Arduino error!', message=f'Não foi possível conectar ao Arduino\nErro={erro}'
        )
        return

    logger.info('Conexão com o Arduino estabelecida com sucesso!')

    widgets.rotulo_botao.set('Desconectar')
    widgets.botao['state'] = 'normal'
    for caixa in widgets.caixas:
        caixa['state'] = 'disabled'

    widgets.rotulo_status.configure(image=widgets.imagem_conectado)


def _desconectar(arduino: ControladorLedArduino, widgets: WidgetsArduino) -> None:
    # Desconectar ANTES de mexer no rótulo. A GUI reage à escrita da variável (trace)
    # para reavaliar se dá para começar a aquisição, e essa avaliação pergunta ao
    # controlador se ele está conectado. Na ordem inversa, o trace rodaria com o
    # Arduino ainda aberto e liberaria o botão "Começar aquisição" para um Arduino
    # que, um instante depois, estaria desconectado.
    arduino.desconectar()
    logger.info('Conexão com o Arduino encerrada')

    widgets.rotulo_botao.set('Conectar')
    for caixa in widgets.caixas:
        caixa['state'] = 'readonly'
    widgets.rotulo_status.configure(image=widgets.imagem_desconectado)


def listar_portas(controlador: ControladorLedArduino, caixa: ttk.Combobox) -> None:
    """Preenche o combobox de portas com as portas que o controlador enxerga.

    Serve de `postcommand` do combobox, então roda a cada abertura da lista.
    """
    caixa['values'] = controlador.listar_portas()
