"""Implementação real do controlador de LED: fala com o Arduino via porta serial."""

import logging

import serial
import serial.tools.list_ports

from esquizocap.hardware.constantes import ENCODING_SERIAL
from esquizocap.hardware.contratos import ControladorLedArduino, ErroConexaoArduino

TIMEOUT_SERIAL_SEGUNDOS: int = 1

logger = logging.getLogger(__name__)


class ArduinoSerial(ControladorLedArduino):
    """Controlador real da fita de LED, sobre uma porta serial (pyserial).

    O firmware do Arduino não está neste repositório: ele espera exatamente a
    string `(modo,hue,saturacao,brilho)\\n` a 9600 baud. Mudar esse formato quebra
    a fita de LED sem gerar erro nenhum do lado Python.
    """

    def __init__(self) -> None:
        self._porta_serial: serial.Serial = serial.Serial()

    @property
    def esta_conectado(self) -> bool:
        # `bool(...)` porque o pyserial não tem type stubs: `is_open` chega como `Any`,
        # e sem isso o `Any` vazaria para quem consome o contrato.
        return bool(self._porta_serial.is_open)

    def listar_portas(self) -> list[str]:
        portas: list[str] = [str(porta) for porta in serial.tools.list_ports.comports()]
        logger.info(f'Portas seriais disponíveis = {portas}')
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

        logger.info(f'Arduino conectado na porta "{porta}" a {baudrate} baud')

    def desconectar(self) -> None:
        # Idempotente: o `__exit__` pode chamar isto mesmo se `conectar` nunca rodou
        # (ex.: o `with` falhou antes). Sem a guarda, o log mentiria dizendo que
        # encerrou uma conexão que nunca existiu.
        if self._porta_serial.is_open is False:
            return

        self._porta_serial.close()
        logger.info('Conexão serial com o Arduino encerrada')

    def enviar_comando_cor(self, modo: int, hue: int, saturacao: int, brilho: int) -> None:
        # Escrever numa porta fechada levanta `serial.PortNotOpenError` — uma exceção do
        # pyserial, exatamente o que o contrato promete não deixar vazar. E o cabo USB
        # arrancado no meio da aquisição vira `SerialException`. Os dois são a mesma coisa
        # para quem chama: o Arduino sumiu.
        if self._porta_serial.is_open is False:
            raise ErroConexaoArduino(
                'A porta serial do Arduino está fechada. Conecte o Arduino antes de enviar uma cor.'
            )

        comando: str = f'({modo},{hue},{saturacao},{brilho})\n'

        try:
            self._porta_serial.write(comando.encode(ENCODING_SERIAL))
        except serial.SerialException as erro:
            raise ErroConexaoArduino(
                f'Falha ao enviar a cor para o Arduino: {erro}. Verifique se o cabo segue conectado.'
            ) from erro
