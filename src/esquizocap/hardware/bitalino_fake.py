"""Implementação fake do leitor de EEG: gera sinal sintético, sem BITalino nem OpenSignals."""

import logging
import math
import random
import time

from esquizocap.hardware import protocolo_bitalino
from esquizocap.hardware.contratos import ErroConexaoBitalino, LeitorBitalino

TAXA_AMOSTRAGEM_SIMULADA: int = 1000
# O dispositivo real entrega um valor por canal; a interface oferece os canais 1 a 6,
# então o vetor precisa cobrir os índices 0..6.
CANAIS_SIMULADOS: int = 7

FREQUENCIA_DOMINANTE_HZ: float = 10.0  # banda Alpha, para a análise cair em "Relaxamento, calma"
AMPLITUDE_MICROVOLTS: float = 50.0
RUIDO_MICROVOLTS: float = 6.0

logger = logging.getLogger(__name__)


class BitalinoSintetico(LeitorBitalino):
    """Gera um EEG sintético plausível em vez de ler o hardware.

    O sinal é uma senoide na banda Alpha (10 Hz) com ruído gaussiano, de modo que a
    análise espectral encontre uma frequência dominante estável e classificável.
    Serve para exercitar aquisição, modelo e saídas sem BITalino nem OpenSignals.

    Substituível por reprodução de gravações reais: basta trocar `_valor_no_instante`
    por uma leitura das amostras gravadas.
    """

    def __init__(self, tempo_real: bool = False) -> None:
        """
        Args:
            tempo_real: Se `True`, a leitura BLOQUEIA até que o sinal "exista", como faz
                o dispositivo de verdade — 1000 amostras levam 1 segundo. É obrigatório
                para quem lê em laço (a thread de aquisição): sem isso, o gerador entrega
                amostras infinitamente rápido e o laço consome uma CPU inteira, além de
                simular horas de EEG em segundos.

                O padrão é `False` porque os testes querem justamente o contrário: sinal
                instantâneo, sem gastar segundos de relógio. A fábrica liga o tempo real.
        """
        self._conectado: bool = False
        self._amostras_geradas: int = 0
        self._tempo_real: bool = tempo_real
        self._instante_inicial: float = 0.0

    def conectar(self, endereco: str, taxa_amostragem_hz: int, canais: list[int]) -> None:
        """Abre o stream simulado, validando o endereço como o leitor real validaria.

        Como responde pelos DOIS modos de aquisição quando `ESQUIZOCAP_FAKE` está ligado,
        aceita `taxa_amostragem_hz` e `canais` e os ignora: o sinal sintético tem taxa
        própria (`TAXA_AMOSTRAGEM_SIMULADA`) e sempre entrega todos os canais.
        """
        del taxa_amostragem_hz, canais  # Ver docstring.

        # Mantém a mesma validação do leitor real, para que um endereço inválido falhe
        # igual nos dois modos.
        if len(endereco.split(':')) != 6:
            raise ErroConexaoBitalino(
                f'Endereço MAC inválido: "{endereco}". Selecione o endereço MAC do Bitalino.'
            )

        self._conectado = True
        self._amostras_geradas = 0
        self._instante_inicial = time.monotonic()
        logger.info(
            f'[FAKE] Stream simulado aberto para o MAC "{endereco}" '
            f'({FREQUENCIA_DOMINANTE_HZ} Hz, {TAXA_AMOSTRAGEM_SIMULADA} Hz de amostragem)'
            f'{", em tempo real" if self._tempo_real else ""}'
        )

    @property
    def amostras_geradas(self) -> int:
        """Quantas amostras já saíram deste leitor. Existe para os testes observarem.

        É o análogo do `comandos_enviados` do `ArduinoFake`: sem isto, não haveria como
        provar que a aquisição consome o stream inteiro, e não só as amostras que viram
        predição.
        """
        return self._amostras_geradas

    def definir_canal_ativo(self, canal: int) -> None:
        """Aceita e IGNORA o canal ativo: todos os canais sintéticos carregam o mesmo sinal,
        já em microvolts."""
        protocolo_bitalino.validar_canal(canal=canal)

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

    def _amostras_ja_existentes(self) -> int:
        """Quantas amostras o dispositivo simulado já teria produzido até agora."""
        decorrido: float = time.monotonic() - self._instante_inicial
        return int(decorrido * TAXA_AMOSTRAGEM_SIMULADA)

    def _aguardar_ate_amostra(self, indice: int, timeout: float) -> bool:
        """Bloqueia até a amostra de índice `indice` "existir" no tempo simulado.

        Returns:
            `True` se a amostra ficou disponível; `False` se o timeout venceu antes —
            exatamente como o `pull_chunk` do LSL, que devolve o que tiver e não espera
            o resto.
        """
        if self._tempo_real is False:
            return True

        faltam: float = (indice / TAXA_AMOSTRAGEM_SIMULADA) - (time.monotonic() - self._instante_inicial)

        if faltam <= 0.0:
            return True

        if faltam > timeout:
            time.sleep(timeout)
            return False

        time.sleep(faltam)
        return True

    def ler_amostra(self, timeout: float) -> tuple[list[float], float] | tuple[None, None]:
        # O leitor real devolve `(None, None)` quando o timeout expira sem sinal. O fake
        # tem que ser capaz de fazer o mesmo, senão esse caminho nunca é exercitado.
        if self._aguardar_ate_amostra(indice=self._amostras_geradas + 1, timeout=timeout) is False:
            return None, None

        return self._proxima_linha()

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        if self._aguardar_ate_amostra(indice=self._amostras_geradas + max_amostras, timeout=timeout) is False:
            # Timeout: entrega só o que já existe, como o `pull_chunk` real.
            disponiveis: int = self._amostras_ja_existentes() - self._amostras_geradas
            max_amostras = max(0, min(max_amostras, disponiveis))

        amostras: list[list[float]] = []
        timestamps: list[float] = []

        for _ in range(max_amostras):
            canais, timestamp = self._proxima_linha()
            amostras.append(canais)
            timestamps.append(timestamp)

        return amostras, timestamps

    def encerrar_stream(self) -> None:
        self._conectado = False
        logger.info(
            f'[FAKE] Stream simulado encerrado após {self._amostras_geradas} amostras'
        )
