"""Orquestração da GUI em torno do controlador de LED.

Este módulo cuida só do que a interface gráfica precisa (habilitar/desabilitar
widgets, trocar o rótulo do botão, pintar o status). O acesso ao hardware em si
fica atrás de `ControladorLedArduino` — ver `tools/hardware/`.
"""

from tools.guitools import Messagebox, SetLogger
from tools.hardware import ControladorLedArduino, ErroConexaoArduino

arduinoLogger: SetLogger = SetLogger(namelogger='arduinoLogger', logfilepath=r'logs\EsquizoCapLogs.log')


def connect(
    arduino: ControladorLedArduino,
    port: str,
    baudrate: int,
    modo: str,
    configsfile: dict,
    **kwargs,
) -> None:
    """Conecta ou desconecta o Arduino, refletindo o resultado nos widgets da GUI.

    Serve de callback para o botão de conexão: alterna entre conectar e desconectar
    conforme o estado atual do controlador.

    Args:
        arduino: Controlador da fita de LED (real ou simulado).
        port: Porta escolhida no combobox, no formato "COM5 - descrição".
        baudrate: Velocidade da porta serial.
        modo: Modo de luminosidade escolhido, entre os nomes de `configsfile['modos']`.
        configsfile: Configuração carregada de `settings/configs.json`.
    """
    if arduino.esta_conectado is False:
        arduinoLogger.logger.info('Conectando o arduino')

        if 'COM' not in port:
            return Messagebox.show_warning(
                title='Arduino error!', message='Selecione a porta que o Arduino está conectado.'
            )
        if modo not in configsfile['modos']:
            return Messagebox.show_warning(title='Arduino error!', message='Selecione um modo de luminosidade.')

        for index, modo_str in enumerate(configsfile['modos'], start=1):
            if modo_str == modo:
                kwargs['selfmode'] = index
                arduinoLogger.logger.info(f'Modo de luminosidade selecionado = {modo} id = {index}')

        kwargs['botao']['state'] = 'disabled'
        arduinoLogger.logger.info(f'Porta selecionada = {port}, Baudrate = {baudrate}')

        try:
            arduino.conectar(porta=port, baudrate=baudrate)
        except ErroConexaoArduino as erro:
            kwargs['string'].set('Conectar')
            kwargs['botao']['state'] = 'enabled'
            arduinoLogger.logger.error(f'Não foi possível conectar ao Arduino: {erro}')
            return Messagebox.show_error(
                title='Arduino error!', message=f'Não foi possível conectar ao Arduino\nErro={erro}'
            )

        arduinoLogger.logger.info('Conexão com o arduino estabelecida com sucesso!')

        kwargs['string'].set('Desconectar')
        kwargs['botao']['state'] = 'enabled'
        for box in kwargs['boxes']:
            box['state'] = 'disabled'

        kwargs['status']['labelimg'].configure(image=kwargs['status']['green'])

    else:
        kwargs['string'].set('Conectar')
        for box in kwargs['boxes']:
            box['state'] = 'readonly'
        kwargs['status']['labelimg'].configure(image=kwargs['status']['red'])
        arduino.desconectar()
        arduinoLogger.logger.info('Conexão com o arduino encerrada')


def listar_portas(controlador: ControladorLedArduino, **kwargs) -> None:
    """Preenche o combobox de portas com as portas que o controlador enxerga.

    Serve de `postcommand` do combobox, então roda a cada abertura da lista.
    """
    kwargs['list']['values'] = controlador.listar_portas()
