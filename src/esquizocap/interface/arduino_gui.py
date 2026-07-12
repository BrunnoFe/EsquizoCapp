"""Orquestração da GUI em torno do controlador de LED.

Este módulo cuida só do que a interface gráfica precisa (habilitar/desabilitar
widgets, trocar o rótulo do botão, pintar o status). O acesso ao hardware em si
fica atrás de `ControladorLedArduino` — ver `esquizocap/hardware/`.
"""

import logging

from ttkbootstrap.dialogs import Messagebox

from esquizocap.hardware import ControladorLedArduino, ErroConexaoArduino
from esquizocap.hardware.constantes import MODOS_LUMINOSIDADE

logger = logging.getLogger(__name__)


def connect(
    arduino: ControladorLedArduino,
    port: str,
    baudrate: int,
    modo: str,
    **kwargs,
) -> None:
    """Conecta ou desconecta o Arduino, refletindo o resultado nos widgets da GUI.

    Serve de callback para o botão de conexão: alterna entre conectar e desconectar
    conforme o estado atual do controlador.

    Args:
        arduino: Controlador da fita de LED (real ou simulado).
        port: Porta escolhida no combobox, no formato "COM5 - descrição".
        baudrate: Velocidade da porta serial.
        modo: Modo de luminosidade, entre os de `constantes.MODOS_LUMINOSIDADE`.
    """
    if arduino.esta_conectado is False:
        logger.info('Conectando o arduino')

        if 'COM' not in port:
            return Messagebox.show_warning(
                title='Arduino error!', message='Selecione a porta que o Arduino está conectado.'
            )
        if modo not in MODOS_LUMINOSIDADE:
            return Messagebox.show_warning(title='Arduino error!', message='Selecione um modo de luminosidade.')

        kwargs['botao']['state'] = 'disabled'
        logger.info(f'Porta selecionada = {port}, Baudrate = {baudrate}')

        try:
            arduino.conectar(porta=port, baudrate=baudrate)
        except ErroConexaoArduino as erro:
            kwargs['string'].set('Conectar')
            kwargs['botao']['state'] = 'enabled'
            logger.error(f'Não foi possível conectar ao Arduino: {erro}')
            return Messagebox.show_error(
                title='Arduino error!', message=f'Não foi possível conectar ao Arduino\nErro={erro}'
            )

        logger.info('Conexão com o arduino estabelecida com sucesso!')

        kwargs['string'].set('Desconectar')
        kwargs['botao']['state'] = 'enabled'
        for box in kwargs['boxes']:
            box['state'] = 'disabled'

        kwargs['status']['labelimg'].configure(image=kwargs['status']['green'])

    else:
        # Desconectar ANTES de mexer no rótulo. A GUI reage à escrita da variável (trace)
        # para reavaliar se dá para começar a aquisição, e essa avaliação pergunta ao
        # controlador se ele está conectado. Na ordem inversa, o trace rodaria com o
        # Arduino ainda aberto e liberaria o botão "Começar aquisição" para um Arduino
        # que, um instante depois, estaria desconectado.
        arduino.desconectar()
        logger.info('Conexão com o arduino encerrada')

        kwargs['string'].set('Conectar')
        for box in kwargs['boxes']:
            box['state'] = 'readonly'
        kwargs['status']['labelimg'].configure(image=kwargs['status']['red'])


def listar_portas(controlador: ControladorLedArduino, **kwargs) -> None:
    """Preenche o combobox de portas com as portas que o controlador enxerga.

    Serve de `postcommand` do combobox, então roda a cada abertura da lista.
    """
    kwargs['list']['values'] = controlador.listar_portas()
