"""Implementação real do controlador de LED: fala com o Arduino via porta serial."""

import serial
import serial.tools.list_ports

from tools.guitools import ENCODING_FORMAT, SetLogger
from tools.hardware.interfaces import ErroConexaoArduino

arduinoRealLogger: SetLogger = SetLogger(namelogger='arduinoReal', logfilepath=r'logs\EsquizoCapLogs.log')

TIMEOUT_SERIAL_SEGUNDOS: int = 1


class ArduinoSerial:
    """Controlador real da fita de LED, sobre uma porta serial (pyserial).

    O firmware do Arduino não está neste repositório: ele espera exatamente a
    string `(modo,hue,saturacao,brilho)\\n` a 9600 baud. Mudar esse formato quebra
    a fita de LED sem gerar erro nenhum do lado Python.
    """

    def __init__(self) -> None:
        self._porta_serial: serial.Serial = serial.Serial()

    @property
    def esta_conectado(self) -> bool:
        return self._porta_serial.is_open

    def listar_portas(self) -> list[str]:
        portas: list[str] = [str(porta) for porta in serial.tools.list_ports.comports()]
        arduinoRealLogger.logger.info(f'Portas seriais disponíveis = {portas}')
        return portas

    def conectar(self, porta: str, baudrate: int) -> None:
        # O combobox entrega "COM5 - CH340"; o pyserial só aceita o identificador ("COM5").
        self._porta_serial.port = porta.split(' - ')[0]
        self._porta_serial.baudrate = baudrate
        self._porta_serial.timeout = TIMEOUT_SERIAL_SEGUNDOS

        try:
            self._porta_serial.open()
        except (serial.SerialException, PermissionError) as erro:
            raise ErroConexaoArduino(
                f'Falha ao abrir a porta serial "{porta}" a {baudrate} baud: {erro}'
            ) from erro

        if self._porta_serial.is_open is False:
            raise ErroConexaoArduino(
                f'A porta serial "{porta}" foi aberta sem erro, mas segue fechada. '
                'Verifique se outro programa está usando a porta.'
            )

        arduinoRealLogger.logger.info(f'Arduino conectado na porta "{porta}" a {baudrate} baud')

    def desconectar(self) -> None:
        self._porta_serial.close()
        arduinoRealLogger.logger.info('Conexão serial com o Arduino encerrada')

    def enviar_comando_cor(self, modo: int, hue: int, saturacao: int, brilho: int) -> None:
        comando: str = f'({modo},{hue},{saturacao},{brilho})\n'
        self._porta_serial.write(comando.encode(ENCODING_FORMAT))
