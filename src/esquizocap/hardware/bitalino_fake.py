"""Implementação fake do leitor de EEG: gera sinal sintético, sem BITalino nem OpenSignals."""

import math
import random

from esquizocap.hardware.contratos import ErroConexaoBitalino, LeitorBitalino
from esquizocap.infraestrutura.guitools import SetLogger

bitalinoFakeLogger: SetLogger = SetLogger(namelogger='bitalinoFake', logfilepath=r'logs\EsquizoCapLogs.log')

TAXA_AMOSTRAGEM_SIMULADA: int = 1000
# O dispositivo real entrega um valor por canal; a GUI oferece os canais 1 a 6 e a
# análise de frequência lê a coluna 1, então o vetor precisa cobrir os índices 0..6.
CANAIS_SIMULADOS: int = 7

FREQUENCIA_DOMINANTE_HZ: float = 10.0  # banda Alpha, para a análise cair em "Relaxamento, calma"
AMPLITUDE_MICROVOLTS: float = 50.0
RUIDO_MICROVOLTS: float = 6.0


class BitalinoSintetico(LeitorBitalino):
    """Gera um EEG sintético plausível em vez de ler o hardware.

    O sinal é uma senoide na banda Alpha (10 Hz) com ruído gaussiano, de modo que a
    análise espectral encontre uma frequência dominante estável e classificável.
    Serve para exercitar aquisição, modelo e saídas sem BITalino nem OpenSignals.

    Substituível por reprodução de gravações reais: basta trocar `_valor_no_instante`
    por uma leitura das amostras gravadas.
    """

    def __init__(self) -> None:
        self._conectado: bool = False
        self._amostras_geradas: int = 0

    def conectar(self, mac_addr: str) -> None:
        # Mantém a mesma validação do leitor real, para que um MAC inválido falhe
        # igual nos dois modos.
        if len(mac_addr.split(':')) != 6:
            raise ErroConexaoBitalino(
                f'Endereço MAC inválido: "{mac_addr}". Selecione o endereço MAC do Bitalino.'
            )

        self._conectado = True
        self._amostras_geradas = 0
        bitalinoFakeLogger.logger.info(
            f'[FAKE] Stream simulado aberto para o MAC "{mac_addr}" '
            f'({FREQUENCIA_DOMINANTE_HZ} Hz, {TAXA_AMOSTRAGEM_SIMULADA} Hz de amostragem)'
        )

    def taxa_amostragem_nominal(self) -> int:
        return TAXA_AMOSTRAGEM_SIMULADA

    def _valor_no_instante(self, indice_amostra: int) -> float:
        """Valor do EEG sintético, em microvolts, para o n-ésimo instante amostrado."""
        instante_segundos: float = indice_amostra / TAXA_AMOSTRAGEM_SIMULADA
        onda: float = AMPLITUDE_MICROVOLTS * math.sin(2 * math.pi * FREQUENCIA_DOMINANTE_HZ * instante_segundos)
        return onda + random.gauss(0.0, RUIDO_MICROVOLTS)

    def _proxima_linha(self) -> tuple[list[float], float]:
        valor: float = self._valor_no_instante(self._amostras_geradas)
        timestamp: float = self._amostras_geradas / TAXA_AMOSTRAGEM_SIMULADA
        self._amostras_geradas += 1
        # Todos os canais carregam o mesmo sinal: a aquisição só usa um canal por vez.
        return [valor] * CANAIS_SIMULADOS, timestamp

    def ler_amostra(self, timeout: float) -> tuple[list[float], float]:
        return self._proxima_linha()

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        amostras: list[list[float]] = []
        timestamps: list[float] = []

        for _ in range(max_amostras):
            canais, timestamp = self._proxima_linha()
            amostras.append(canais)
            timestamps.append(timestamp)

        return amostras, timestamps

    def encerrar_stream(self) -> None:
        self._conectado = False
        bitalinoFakeLogger.logger.info(
            f'[FAKE] Stream simulado encerrado após {self._amostras_geradas} amostras'
        )
