"""Implementação real do leitor de EEG: lê o BITalino via OpenSignals + LSL."""

import logging
import re

from pylsl import LostError, StreamInlet, resolve_byprop

from esquizocap.hardware import protocolo_bitalino
from esquizocap.hardware.contratos import ErroConexaoBitalino, ErroStreamPerdido, LeitorBitalino

# O OpenSignals publica o stream LSL usando o MAC do dispositivo como `type`.
PADRAO_MAC: re.Pattern[str] = re.compile(r'\d\d[: ]\d\d[: ]\d\d[: ]\d\d[: ]\d\d[: ]\d\d')
TIMEOUT_RESOLUCAO_SEGUNDOS: float = 2.0

logger = logging.getLogger(__name__)


class BitalinoLSL(LeitorBitalino):
    """Leitor de EEG do Modo OpenSignals, sobre o stream LSL que ele publica.

    O OpenSignals NÃO é iniciado pela aplicação: ele precisa estar aberto, com o
    compartilhamento "Lab Streaming Layer" ativo, ANTES de conectar. Se não
    estiver, a resolução do stream falha e `conectar` levanta `ErroConexaoBitalino`.

    O sinal chega aqui JÁ CONVERTIDO para microvolts — a função de transferência do
    sensor é aplicada pelo OpenSignals, não por nós.
    """

    def __init__(self) -> None:
        self._stream: StreamInlet | None = None

    def conectar(self, endereco: str, taxa_amostragem_hz: int, canais: list[int]) -> None:
        """Resolve o stream LSL publicado pelo OpenSignals para o MAC informado.

        `taxa_amostragem_hz` e `canais` são IGNORADOS de propósito: neste modo, os dois já
        foram escolhidos pelo operador dentro do OpenSignals antes de a aplicação abrir, e
        o stream chega com eles fixados. Aceitá-los e descartá-los é o preço de ter um
        contrato único para os dois modos de aquisição — a alternativa seria a interface
        saber de qual modo veio o leitor antes de mandar conectar.
        """
        del taxa_amostragem_hz, canais  # Fixados no OpenSignals; ver docstring.

        if PADRAO_MAC.match(endereco) is None:
            raise ErroConexaoBitalino(f'Endereço MAC inválido: "{endereco}". Selecione o endereço MAC do Bitalino.')

        logger.info(f'Resolvendo stream LSL do BITalino com MAC "{endereco}" ...')
        streams = resolve_byprop(prop='type', value=endereco, minimum=1, timeout=TIMEOUT_RESOLUCAO_SEGUNDOS)

        if not streams:
            raise ErroConexaoBitalino(
                f'Nenhum stream LSL encontrado para o MAC "{endereco}". Verifique se o BITalino está '
                'conectado ao computador e se o compartilhamento "Lab Streaming Layer" está ativo no OpenSignals.'
            )

        # recover=False para que a queda do stream vire LostError em vez de a leitura
        # ficar travada tentando reconectar sozinha.
        self._stream = StreamInlet(streams[0], recover=False)
        logger.info(f'Stream do BITalino "{endereco}" conectado')

    def _stream_aberto(self) -> StreamInlet:
        """Devolve o stream, exigindo que `conectar` já tenha rodado.

        Sem esta guarda, ler antes de conectar (ou depois de encerrar) estouraria um
        `AttributeError: 'NoneType' has no attribute 'pull_sample'` — justamente o tipo
        de erro cru que o contrato promete não deixar vazar.

        Raises:
            ErroConexaoBitalino: Se o stream não estiver aberto.
        """
        if self._stream is None:
            raise ErroConexaoBitalino('Stream do BITalino não está aberto. Chame `conectar` antes de ler amostras.')
        return self._stream

    def definir_canal_ativo(self, canal: int) -> None:
        """Aceita e IGNORA o canal ativo.

        Neste modo, quem aplica (ou não) a função de transferência é o OpenSignals, canal a
        canal, conforme os sensores configurados nele — um canal com sensor de EEG chega em
        µV, um com EDA chega em µS, e um canal sem sensor chega em ADU cru. Nada disso está
        sob controle da aplicação, então saber o canal ativo não mudaria nada aqui.
        """
        protocolo_bitalino.validar_canal(canal=canal)

    def taxa_amostragem_nominal(self) -> int:
        return int(self._stream_aberto().info().nominal_srate())

    def ler_amostra(self, timeout: float) -> tuple[list[float], float] | tuple[None, None]:
        try:
            amostra, timestamp = self._stream_aberto().pull_sample(timeout=timeout)
        except LostError as erro:
            raise ErroStreamPerdido(f'Stream do BITalino perdido durante a leitura de uma amostra: {erro}') from erro

        # O pylsl devolve `(None, None)` quando o timeout expira sem sinal novo. O tipo
        # de retorno diz isso explicitamente para que quem chama seja OBRIGADO a tratar:
        # antes, o None seguia adiante e estourava um `IndexError` na indexação do canal.
        if amostra is None:
            return None, None

        return amostra, timestamp

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        try:
            amostras, timestamps = self._stream_aberto().pull_chunk(timeout=timeout, max_samples=max_amostras)
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
        logger.info('Stream do BITalino encerrado')
