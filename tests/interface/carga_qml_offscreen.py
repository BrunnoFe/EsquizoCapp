"""Carrega o motor QML de verdade, sem janela, e reporta os avisos que ele emitir.

Roda como PROCESSO SEPARADO (ver `test_qml_carrega.py`), por dois motivos:

- `QT_QPA_PLATFORM=offscreen` e a escolha entre `QCoreApplication` e `QGuiApplication`
  precisam valer desde o primeiro import do PySide6. O resto da suíte já cria uma
  `QCoreApplication`, que não serve para QML, e o Qt não deixa trocar depois.
- Um erro de QML costuma ser um aviso no `stderr`, não uma exceção. Isolar o processo
  permite tratar qualquer aviso como falha sem contaminar os outros testes.

Sai com código 0 se o QML carregou sem nenhum aviso; 1 caso contrário, com os avisos no
`stdout`.
"""

import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
# A simulação precisa valer antes de o controller nascer: o teste não pode tocar hardware.
os.environ.setdefault('ESQUIZOCAP_FAKE', 'tudo')

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from esquizocap.infraestrutura.config import Configuracao  # noqa: E402
from esquizocap.infraestrutura.preferencias import Preferencias  # noqa: E402
from esquizocap.interface import controller as modulo_controller  # noqa: E402


class ModeloDuble:
    """Igual ao de `conftest.py` — duplicado porque o subprocesso não vê as fixtures."""

    def predict(self, X: Any) -> Any:  # noqa: N803 - assinatura do scikit-learn
        return [int(max(0, min(255, abs(float(X[0][0])))))]


def main() -> int:
    avisos: list[str] = []

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda erros: avisos.extend(str(erro.toString()) for erro in erros))

    controlador = modulo_controller.EsquizoController(
        configuracao=Configuracao(macs_bitalino=('20:17:09:18:60:29',)),
        modelo=ModeloDuble(),  # type: ignore[arg-type]
        preferencias_usuario=Preferencias(),
        caminho_preferencias=Path(sys.argv[1]),
    )
    engine.rootContext().setContextProperty('controller', controlador)

    base_qml = Path(modulo_controller.__file__).resolve().parent / 'qml'
    engine.addImportPath(str(base_qml))
    engine.load(QUrl.fromLocalFile(str(base_qml / 'EsquizoCap' / 'App' / 'EsquizoCapView.qml')))

    if not engine.rootObjects():
        print('O QML não produziu nenhum objeto raiz.')
        for aviso in avisos:
            print(aviso)
        return 1

    # Um ciclo de eventos: os bindings só são avaliados quando o item é realizado, e é aí
    # que um nome de `Property` errado vira aviso. Sem isto, a carga passaria em silêncio.
    app.processEvents()
    controlador.encerrarTudo()
    app.processEvents()

    for aviso in avisos:
        print(aviso)
    return 1 if avisos else 0


if __name__ == '__main__':
    sys.exit(main())
