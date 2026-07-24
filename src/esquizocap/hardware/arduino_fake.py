"""Implementação fake do controlador de LED: simula o Arduino, sem hardware."""

import logging

from esquizocap.hardware.contratos import ControladorLedArduino, ErroConexaoArduino

# A GUI só libera a conexão se a string da porta contiver "COM", então a porta simulada
# precisa respeitar esse formato.
PORTA_SIMULADA: str = 'COM99 - Arduino simulado (fake)'

logger = logging.getLogger(__name__)


class ArduinoFake(ControladorLedArduino):
    """Simula a fita de LED registrando em log o comando que seria enviado.

    Não desenha nada nem abre porta serial: serve para exercitar a GUI, o modelo e
    o fluxo de aquisição sem o Arduino plugado. O comando é montado com o mesmo
    formato do controlador real, de modo que uma divergência de protocolo apareça
    aqui também.
    """

    def __init__(self) -> None:
        self._conectado: bool = False
        self.ultimo_comando: str | None = None
        self.comandos_enviados: int = 0

    @property
    def esta_conectado(self) -> bool:
        return self._conectado

    def listar_portas(self) -> list[str]:
        logger.info(f'[FAKE] Porta simulada disponível = {PORTA_SIMULADA}')
        return [PORTA_SIMULADA]

    def conectar(self, porta: str, baudrate: int) -> None:
        if 'COM' not in porta:
            raise ErroConexaoArduino(
                f'Porta "{porta}" inválida para o Arduino simulado: esperado um nome contendo "COM".'
            )

        self._conectado = True
        logger.info(f'[FAKE] Arduino simulado conectado na porta "{porta}" a {baudrate} baud')

    def desconectar(self) -> None:
        self._conectado = False
        logger.info(f'[FAKE] Arduino simulado desconectado após {self.comandos_enviados} comandos')

    def enviar_comando_cor(self, modo: int, hue: int, saturacao: int, brilho: int) -> None:
        # Espelha o controlador real: enviar numa porta fechada é `ErroConexaoArduino` lá,
        # e precisa ser aqui também. Um fake que aceita o que o real recusa deixa passar
        # justamente o bug que ele deveria ter pego.
        if self._conectado is False:
            raise ErroConexaoArduino(
                'A porta serial do Arduino está fechada. Conecte o Arduino antes de enviar uma cor.'
            )

        self.ultimo_comando = f'({modo},{hue},{saturacao},{brilho})\n'
        self.comandos_enviados += 1
        logger.debug(f'[FAKE] Comando que iria para a serial = {self.ultimo_comando!r}')
