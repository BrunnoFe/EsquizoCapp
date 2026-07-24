"""Testes da carga do modelo e da predição do matiz."""

import pickle
from pathlib import Path

import pytest

from esquizocap.dominio.predicao import ErroDeModelo, ModeloPreditor, carregar_modelo, prever_hue


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
        """Falha com a exceção do MÓDULO, não com a do sistema de arquivos.

        `carregar_modelo` traduz de propósito: um pickle corrompido levanta uma família
        inteira de exceções diferentes (`EOFError`, `AttributeError`, `UnpicklingError`...),
        e arquivo ausente é só mais um caso dessa família. Quem chama trata "modelo
        inválido" num lugar só.

        Este teste esperava `FileNotFoundError` e falhava desde antes desta sessão — ele
        contradizia o `Raises:` documentado em `carregar_modelo`.
        """
        caminho = tmp_path / 'nao_existe.pickle'

        with pytest.raises(ErroDeModelo, match='nao_existe.pickle') as erro:
            carregar_modelo(caminho_modelo=caminho)

        # A causa original é preservada: sem ela, "não foi possível carregar" não diria se o
        # arquivo sumiu ou se o conteúdo está corrompido.
        assert isinstance(erro.value.__cause__, FileNotFoundError)

    def test_pickle_corrompido_falha_com_o_mesmo_erro(self, tmp_path: Path) -> None:
        """A razão de traduzir: arquivo ausente e conteúdo inválido chegam iguais a quem chama."""
        caminho = tmp_path / 'corrompido.pickle'
        caminho.write_bytes(b'isto nao e um pickle')

        with pytest.raises(ErroDeModelo):
            carregar_modelo(caminho_modelo=caminho)
