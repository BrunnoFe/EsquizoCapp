"""Implementação real do leitor de EEG: lê o BITalino via OpenSignals + LSL."""

import re

from pylsl import LostError, StreamInlet, resolve_byprop

from esquizocap.hardware.contratos import ErroConexaoBitalino, ErroStreamPerdido, LeitorBitalino
from esquizocap.infraestrutura.guitools import SetLogger

bitalinoRealLogger: SetLogger = SetLogger(namelogger='bitalinoReal', logfilepath=r'logs\EsquizoCapLogs.log')

# O OpenSignals publica o stream LSL usando o MAC do dispositivo como `type`.
PADRAO_MAC: re.Pattern[str] = re.compile(r'\d\d[: ]\d\d[: ]\d\d[: ]\d\d[: ]\d\d[: ]\d\d')
TIMEOUT_RESOLUCAO_SEGUNDOS: float = 2.0


class BitalinoLSL(LeitorBitalino):
    """Leitor real de EEG, sobre o stream LSL publicado pelo OpenSignals.

    O OpenSignals NÃO é iniciado pela aplicação: ele precisa estar aberto, com o
    compartilhamento "Lab Streaming Layer" ativo, ANTES de conectar. Se não
    estiver, a resolução do stream falha e `conectar` levanta `ErroConexaoBitalino`.
    """

    def __init__(self) -> None:
        self._stream: StreamInlet | None = None

    def conectar(self, mac_addr: str) -> None:
        if PADRAO_MAC.match(mac_addr) is None:
            raise ErroConexaoBitalino(
                f'Endereço MAC inválido: "{mac_addr}". Selecione o endereço MAC do Bitalino.'
            )

        bitalinoRealLogger.logger.info(f'Resolvendo stream LSL do BITalino com MAC "{mac_addr}" ...')
        streams = resolve_byprop(prop='type', value=mac_addr, minimum=1, timeout=TIMEOUT_RESOLUCAO_SEGUNDOS)

        if not streams:
            raise ErroConexaoBitalino(
                f'Nenhum stream LSL encontrado para o MAC "{mac_addr}". Verifique se o BITalino está '
                'conectado ao computador e se o compartilhamento "Lab Streaming Layer" está ativo no OpenSignals.'
            )

        # recover=False para que a queda do stream vire LostError em vez de a leitura
        # ficar travada tentando reconectar sozinha.
        self._stream = StreamInlet(streams[0], recover=False)
        bitalinoRealLogger.logger.info(f'Stream do BITalino "{mac_addr}" conectado')

    def _stream_aberto(self) -> StreamInlet:
        """Devolve o stream, exigindo que `conectar` já tenha rodado.

        Sem esta guarda, ler antes de conectar (ou depois de encerrar) estouraria um
        `AttributeError: 'NoneType' has no attribute 'pull_sample'` — justamente o tipo
        de erro cru que o contrato promete não deixar vazar.

        Raises:
            ErroConexaoBitalino: Se o stream não estiver aberto.
        """
        if self._stream is None:
            raise ErroConexaoBitalino(
                'Stream do BITalino não está aberto. Chame `conectar` antes de ler amostras.'
            )
        return self._stream

    def taxa_amostragem_nominal(self) -> int:
        return int(self._stream_aberto().info().nominal_srate())

    def ler_amostra(self, timeout: float) -> tuple[list[float], float]:
        try:
            amostra, timestamp = self._stream_aberto().pull_sample(timeout=timeout)
        except LostError as erro:
            raise ErroStreamPerdido(f'Stream do BITalino perdido durante a leitura de uma amostra: {erro}') from erro

        return amostra, timestamp

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        try:
            amostras, timestamps = self._stream_aberto().pull_chunk(
                timeout=timeout, max_samples=max_amostras
            )
        except LostError as erro:
            raise ErroStreamPerdido(
                f'Stream do BITalino perdido durante a leitura de um bloco de {max_amostras} amostras: {erro}'
            ) from erro

        return amostras, timestamps

    def encerrar_stream(self) -> None:
        # Idempotente: zera a referência depois de fechar, para que uma segunda chamada
        # (ou o `__exit__` de um `with` que falhou antes de conectar) caia fora aqui em
        # vez de fechar um inlet já fechado.
        if self._stream is None:
            return

        self._stream.close_stream()
        self._stream = None
        bitalinoRealLogger.logger.info('Stream do BITalino encerrado')
