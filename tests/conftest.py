"""Fixtures compartilhadas pela suíte."""

from typing import Any

import numpy
import pytest

from esquizocap.dominio.predicao import ModeloPreditor

TAXA_AMOSTRAGEM_HZ = 1000
"""Taxa de amostragem usada nos sinais sintéticos dos testes."""


class ModeloDuble:
    """Modelo previsível, que devolve a métrica truncada em 0–255.

    Os testes do domínio NÃO usam o `BestModel_HSV_v1.pickle`: ele foi treinado em outra
    versão do scikit-learn, emite `InconsistentVersionWarning` e a própria biblioteca
    admite que a predição pode ser inválida. Testar contra ele mediria o artefato, não o
    nosso código. Aqui interessa que o ciclo chame o modelo e propague o resultado — não
    quanto o modelo acerta.
    """

    def predict(self, X: Any) -> Any:  # noqa: N803 - assinatura do scikit-learn
        metrica = float(X[0][0])
        return [int(max(0, min(255, abs(metrica))))]


@pytest.fixture
def modelo() -> ModeloPreditor:
    return ModeloDuble()


def gerar_senoide(frequencia_hz: float, duracao_amostras: int, taxa_hz: int = TAXA_AMOSTRAGEM_HZ) -> numpy.ndarray:
    """Gera uma senoide pura, sem ruído, para testar a análise espectral.

    Sem ruído de propósito: o pico do espectro fica determinístico, e o teste não fica
    intermitente.
    """
    instantes = numpy.arange(duracao_amostras) / taxa_hz
    return numpy.sin(2 * numpy.pi * frequencia_hz * instantes).astype('float32')
