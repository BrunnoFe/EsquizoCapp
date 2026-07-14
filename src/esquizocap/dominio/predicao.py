"""Carga do modelo de árvore de decisão e predição do matiz (HUE)."""

import pickle
from pathlib import Path
from typing import Any, Protocol, cast


class ErroDeModelo(Exception):
    """O arquivo do modelo existe no caminho configurado, mas não pôde ser carregado."""


class ModeloPreditor(Protocol):
    """Contrato mínimo do modelo: só o `predict` do scikit-learn é usado.

    Segue Protocol (e não ABC como os contratos de hardware) porque quem o cumpre é um
    objeto do scikit-learn, que obviamente não vai herdar de uma classe nossa. Aqui a
    tipagem estrutural é a única opção.
    """

    def predict(self, X: Any) -> Any:  # noqa: N803 - assinatura do scikit-learn
        ...


def carregar_modelo(caminho_modelo: str | Path) -> ModeloPreditor:
    """Carrega o modelo serializado em pickle.

    O modelo foi treinado fora deste repositório: só o artefato existe aqui. Carregar
    um pickle treinado em outra versão do scikit-learn emite `InconsistentVersionWarning`
    e pode gerar predições inválidas em silêncio — ver DECISOES_PENDENTES.md.

    Raises:
        ErroDeModelo: Se o arquivo não puder ser lido ou não contiver um pickle válido.
            Um pickle corrompido levanta uma família inteira de exceções diferentes
            (`EOFError`, `AttributeError`, `UnpicklingError`, ...); traduzi-las para um
            erro só é o que permite a quem chama tratar "modelo inválido" num lugar.
    """
    try:
        with open(file=caminho_modelo, mode='rb') as arquivo_modelo:
            # `pickle.load` devolve `Any` por natureza: o que vem do arquivo só é conhecido
            # em runtime. O cast afirma o contrato que esperamos; se o pickle contiver outra
            # coisa, o erro aparece na primeira chamada a `predict`.
            return cast(ModeloPreditor, pickle.load(file=arquivo_modelo))
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError) as erro:
        raise ErroDeModelo(
            f'Não foi possível carregar o modelo em "{caminho_modelo}": {erro}'
        ) from erro


def prever_hue(modelo: ModeloPreditor, metrica: float) -> int:
    """Prediz o matiz (HUE) a partir de uma única métrica do sinal.

    O modelo recebe um escalar — a amplitude em microvolts (modo Amplitude) ou a
    frequência dominante em Hz (modo Frequência) — e devolve o matiz.

    Args:
        modelo: Modelo carregado por `carregar_modelo`.
        metrica: Amplitude (uV) ou frequência dominante (Hz).

    Returns:
        O matiz previsto, de 0 a 255.
    """
    return int(modelo.predict([[metrica]])[0])
