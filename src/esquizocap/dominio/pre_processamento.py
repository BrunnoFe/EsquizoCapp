"""Pré-processamento do sinal EEG antes da predição.

Dois caminhos, conforme o modo de análise escolhido: no modo Amplitude uma amostra
vira um escalar direto; no modo Frequência um bloco acumulado passa por filtragem e
análise espectral até virar a frequência dominante.
"""

from dataclasses import dataclass
from typing import cast

import numpy
from numpy.typing import NDArray
from scipy.signal import butter, filtfilt, welch

SinalEEG = NDArray[numpy.floating]
"""Vetor unidimensional de amostras de EEG."""

FREQUENCIA_CORTE_INFERIOR_HZ: float = 0.1
FREQUENCIA_CORTE_SUPERIOR_HZ: float = 50.0
ORDEM_FILTRO: int = 5
AMOSTRAS_POR_SEGMENTO_WELCH: int = 250
PONTOS_FFT: int = 2048


@dataclass
class ResultadoAnaliseFrequencia:
    """Saída da análise espectral de um bloco de EEG."""

    frequencia: float
    """Frequência dominante do bloco, em Hz."""

    potencia: float
    """Potência da frequência dominante, na densidade espectral."""

    faixa: str
    """Banda de EEG correspondente (Delta, Theta, Alpha, Beta, Gamma)."""


def extrair_amplitude(amostra: list[float], canal: int) -> numpy.float32:
    """Extrai a amplitude do canal ativo de uma única amostra do BITalino.

    Args:
        amostra: Um valor por canal, como o dispositivo entrega.
        canal: Índice do canal escolhido na interface (1 a 6).

    Returns:
        A amplitude do canal, em microvolts.
    """
    return numpy.float32(amostra[canal])


def extrair_sinal_do_bloco(bloco: list[list[float]], canal: int) -> SinalEEG:
    """Extrai o sinal do canal ativo de um bloco de amostras, para a análise de frequência.

    O bloco tem uma coluna por canal e NENHUMA coluna de timestamp — o LSL devolve os
    timestamps num vetor separado. Por isso o índice da coluna é o próprio canal, igual
    ao modo Amplitude.

    Args:
        bloco: Uma linha por amostra, um valor por canal.
        canal: Índice do canal escolhido na interface (1 a 6).
    """
    coluna: SinalEEG = numpy.array(bloco)[:, canal].astype(dtype='float32')
    return coluna


def filtro_passa_baixa(
    dados: SinalEEG, corte: float, taxa_amostragem: float, ordem: int = ORDEM_FILTRO
) -> SinalEEG:
    """Aplica um filtro Butterworth passa-baixa, sem defasagem (filtfilt)."""
    frequencia_nyquist: float = 0.5 * taxa_amostragem
    corte_normalizado: float = corte / frequencia_nyquist
    b, a = butter(ordem, corte_normalizado, btype='low', analog=False)
    # O scipy não publica type stubs, então `filtfilt` devolve `Any`. O cast declara o
    # tipo que a função de fato retorna, em vez de deixar o `Any` vazar para o resto.
    return cast(SinalEEG, filtfilt(b, a, dados))


def filtro_passa_alta(
    dados: SinalEEG, corte: float, taxa_amostragem: float, ordem: int = ORDEM_FILTRO
) -> SinalEEG:
    """Aplica um filtro Butterworth passa-alta, sem defasagem (filtfilt)."""
    frequencia_nyquist: float = 0.5 * taxa_amostragem
    corte_normalizado: float = corte / frequencia_nyquist
    b, a = butter(ordem, corte_normalizado, btype='high', analog=False)
    return cast(SinalEEG, filtfilt(b, a, dados))


def categorizar_frequencia(frequencia: float) -> str:
    """Classifica uma frequência dominante na banda de EEG correspondente."""
    if 0.1 <= frequencia < 4:
        return 'Delta (Sono profundo, sono não REM)'
    elif 4 <= frequencia < 8:
        return 'Theta (Sonolência, relaxamento)'
    elif 8 <= frequencia < 12:
        return 'Alpha (Relaxamento, calma)'
    elif 12 <= frequencia < 30:
        return 'Beta (Atenção, concentração)'
    elif 30 <= frequencia < 50:
        return 'Gamma (Processamento cognitivo)'
    else:
        return 'Fora das bandas de EEG típicas'


def analisar_frequencia(
    eeg: SinalEEG,
    taxa_amostragem: int,
    corte_inferior: float = FREQUENCIA_CORTE_INFERIOR_HZ,
    corte_superior: float = FREQUENCIA_CORTE_SUPERIOR_HZ,
) -> ResultadoAnaliseFrequencia:
    """Encontra a frequência dominante de um bloco de EEG e a classifica em banda.

    Filtra o sinal na faixa útil de EEG, calcula a densidade espectral de potência
    por Welch e toma o pico como frequência dominante.

    Args:
        eeg: Bloco de amostras já acumulado.
        taxa_amostragem: Taxa real do dispositivo, em Hz (`taxa_amostragem_nominal`).
            É o que define a escala do eixo de frequência: passar aqui qualquer outro
            número faz o resultado sair em "Hz" que não são Hz.
    """
    sinal_filtrado = filtro_passa_alta(dados=eeg, corte=corte_inferior, taxa_amostragem=taxa_amostragem)
    sinal_filtrado = filtro_passa_baixa(dados=sinal_filtrado, corte=corte_superior, taxa_amostragem=taxa_amostragem)

    frequencias, densidade_potencia = welch(
        sinal_filtrado, fs=taxa_amostragem, nperseg=AMOSTRAS_POR_SEGMENTO_WELCH, nfft=PONTOS_FFT
    )

    frequencias_limitadas = frequencias[frequencias <= corte_superior]
    densidade_limitada = densidade_potencia[: len(frequencias_limitadas)]

    frequencia_dominante = frequencias_limitadas[numpy.argmax(densidade_limitada)]
    potencia_dominante = numpy.max(densidade_limitada)
    faixa: str = categorizar_frequencia(frequencia_dominante)

    # Mantido do código original: a saída no console é usada para acompanhar a
    # aquisição ao vivo. Ver DECISOES_PENDENTES.md.
    print(
        f'Frequência dominante: {frequencia_dominante:.2f} Hz com potência: {potencia_dominante:.2f}. {faixa}\n'
        f'Média de ativação = {numpy.mean(eeg, dtype="float16")}'
    )

    return ResultadoAnaliseFrequencia(
        frequencia=frequencia_dominante, potencia=potencia_dominante, faixa=faixa
    )
