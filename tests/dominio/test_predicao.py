"""Testes da carga do modelo e da predição do matiz."""

import pickle
from pathlib import Path

import pytest

from esquizocap.dominio.predicao import ModeloPreditor, carregar_modelo, prever_hue


class ModeloConstante:
    """Devolve sempre o mesmo matiz, seja qual for a entrada."""

    def __init__(self, hue: int) -> None:
        self.hue = hue
        self.metricas_recebidas: list[float] = []

    def predict(self, X: list[list[float]]) -> list[int]:  # noqa: N803
        self.metricas_recebidas.append(X[0][0])
        return [self.hue]


class TestPreverHue:
    def test_devolve_o_matiz_do_modelo_como_inteiro(self) -> None:
        hue = prever_hue(modelo=ModeloConstante(hue=205), metrica=9.77)

        assert hue == 205
        assert isinstance(hue, int)

    def test_entrega_a_metrica_ao_modelo_como_escalar(self) -> None:
        """O modelo recebe um único número — amplitude (uV) ou frequência (Hz)."""
        modelo = ModeloConstante(hue=100)

        prever_hue(modelo=modelo, metrica=9.77)

        assert modelo.metricas_recebidas == [9.77]

    def test_converte_saida_nao_inteira_do_modelo(self) -> None:
        """O scikit-learn pode devolver numpy.int64 ou float; o contrato promete int."""

        class ModeloQueDevolveFloat:
            def predict(self, X: list[list[float]]) -> list[float]:  # noqa: N803
                return [205.0]

        assert prever_hue(modelo=ModeloQueDevolveFloat(), metrica=1.0) == 205


class TestCarregarModelo:
    def test_carrega_um_pickle(self, tmp_path: Path) -> None:
        caminho = tmp_path / 'modelo.pickle'
        with open(caminho, 'wb') as arquivo:
            pickle.dump(ModeloConstante(hue=42), arquivo)

        modelo: ModeloPreditor = carregar_modelo(caminho_modelo=caminho)

        assert prever_hue(modelo=modelo, metrica=1.0) == 42

    def test_arquivo_inexistente_falha_alto(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            carregar_modelo(caminho_modelo=tmp_path / 'nao_existe.pickle')
