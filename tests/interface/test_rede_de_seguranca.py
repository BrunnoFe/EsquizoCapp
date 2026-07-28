"""A rede que impede uma exceção não tratada de sumir no console.

O cenário que estes testes protegem: exceção escapa, o Qt imprime no `stderr` e segue, a
janela continua viva e a fita de LED continua acesa na última cor. Sem aviso na tela, isso
passa por escolha artística — a classe de falha mais cara deste projeto.
"""

import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication

from esquizocap.aplicacao.catalogo_erros import Situacao
from esquizocap.infraestrutura import preferencias
from esquizocap.infraestrutura.config import Configuracao
from esquizocap.infraestrutura.preferencias import Preferencias
from esquizocap.interface.controller import EsquizoController
from esquizocap.interface.ponte import rede_de_seguranca

MAC = '20:17:09:18:60:29'


class ModeloDuble:
    def predict(self, X: Any) -> Any:  # noqa: N803 - assinatura do scikit-learn
        return [128]


@pytest.fixture(scope='module')
def aplicacao_qt() -> QCoreApplication:
    """Uma `QCoreApplication` por módulo: o Qt não deixa criar duas."""
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def controlador(aplicacao_qt: QCoreApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EsquizoController:
    monkeypatch.setenv('ESQUIZOCAP_FAKE', 'tudo')
    monkeypatch.setattr(preferencias, 'CAMINHO_PADRAO', tmp_path / 'preferencias.json')
    return EsquizoController(
        configuracao=Configuracao(macs_bitalino=(MAC,)),
        modelo=ModeloDuble(),  # type: ignore[arg-type]
        preferencias_usuario=Preferencias(),
        caminho_preferencias=tmp_path / 'preferencias.json',
    )


@pytest.fixture
def hooks_restaurados() -> Any:
    """Os hooks são estado global do processo: deixá-los instalados contaminaria a suíte."""
    antes_sys, antes_thread = sys.excepthook, threading.excepthook
    yield
    sys.excepthook, threading.excepthook = antes_sys, antes_thread


class TestRedeDeSeguranca:
    def test_excecao_no_topo_vira_caixa_na_tela(self, controlador: EsquizoController, hooks_restaurados: Any) -> None:
        rede_de_seguranca.instalar(controlador)

        sys.excepthook(ValueError, ValueError('canal fora da faixa'), None)

        assert controlador.caixaAberta, 'a exceção precisa aparecer na tela, não só no console'
        assert controlador.caixaSituacao == Situacao.FALHA_INESPERADA.value

    def test_a_caixa_da_falha_inesperada_exige_ciencia(
        self, controlador: EsquizoController, hooks_restaurados: Any
    ) -> None:
        """Seguir usando um programa cujo estado é desconhecido é pior que ser interrompido."""
        rede_de_seguranca.instalar(controlador)

        sys.excepthook(RuntimeError, RuntimeError('bug'), None)

        assert not controlador.caixaDispensavel
        assert controlador.caixaAcoes, 'não dispensável sem botão prenderia o usuário'

    def test_o_detalhe_tecnico_acompanha(self, controlador: EsquizoController, hooks_restaurados: Any) -> None:
        rede_de_seguranca.instalar(controlador)

        sys.excepthook(ValueError, ValueError('canal 7 não existe'), None)

        assert 'ValueError' in controlador.caixaDetalhe
        assert 'canal 7 não existe' in controlador.caixaDetalhe

    def test_interrupcao_do_usuario_nao_vira_erro(self, controlador: EsquizoController, hooks_restaurados: Any) -> None:
        """Ctrl+C é o usuário mandando parar; abrir uma caixa sobre isso é ruído."""
        rede_de_seguranca.instalar(controlador)

        try:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        except SystemExit:  # pragma: no cover - depende do hook anterior do ambiente
            pass

        assert not controlador.caixaAberta

    def test_o_hook_anterior_continua_sendo_chamado(
        self, controlador: EsquizoController, hooks_restaurados: Any
    ) -> None:
        """A caixa ACRESCENTA um aviso visível; não pode custar o traceback no log."""
        chamadas: list[BaseException] = []
        sys.excepthook = lambda tipo, erro, tb: chamadas.append(erro)  # type: ignore[assignment]

        rede_de_seguranca.instalar(controlador)
        erro = ValueError('x')
        sys.excepthook(ValueError, erro, None)

        assert chamadas == [erro]

    # O aviso é do próprio pytest, que instala um hook de thread e agora está no fim da
    # nossa cadeia: vê-lo aqui é a prova de que não engolimos o hook anterior.
    @pytest.mark.filterwarnings('ignore::pytest.PytestUnhandledThreadExceptionWarning')
    def test_excecao_em_thread_tambem_avisa(self, controlador: EsquizoController, hooks_restaurados: Any) -> None:
        """A aquisição roda em thread própria: é justamente lá que morrer calado dói mais."""
        rede_de_seguranca.instalar(controlador)

        def estourar() -> None:
            raise ValueError('o leitor devolveu lixo')

        thread = threading.Thread(target=estourar, name='thread-de-teste')
        thread.start()
        thread.join()
        # O sinal atravessa threads pela fila do Qt; sem drenar, ele ainda não chegou.
        QCoreApplication.processEvents()

        assert controlador.caixaAberta
        assert controlador.caixaSituacao == Situacao.FALHA_INESPERADA.value
