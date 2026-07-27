"""Instancia cada `IconGlyph` usado na interface e conta quantas formas ficam visíveis.

Roda como PROCESSO SEPARADO pelos mesmos motivos de `carga_qml_offscreen.py`: o
`QT_QPA_PLATFORM=offscreen` e a `QGuiApplication` precisam valer desde o primeiro import.

O `IconGlyph` é um switch sobre `name` sem caso padrão: um nome desconhecido deixa todos os
`Shape` invisíveis e **não emite aviso nenhum**. Na tela o sintoma é um botão vazio, que a
carga do QML não distingue de um botão certo. Daí este teste.

Imprime uma linha `nome<TAB>formas_visíveis` por ícone no `stdout`; sai com 1 se o próprio
motor QML falhar em compilar o componente.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from esquizocap.interface import controller as modulo_controller  # noqa: E402


def _formas_visiveis(item: QQuickItem) -> int:
    """Quantos filhos do tipo `Shape` estão visíveis — os dentes da engrenagem são
    `Rectangle`, então não entram na conta e cada ícone deve dar exatamente 1.

    Duas sutilezas do PySide, ambas silenciosas se erradas:

    - o tipo vem do `metaObject`, não de `type(filho)`: `QtQuick.Shapes` não tem módulo
      Python, então todo filho chega como um `QQuickItem` genérico;
    - lê a propriedade `visible` local, e não `isVisible()`: fora de uma janela nenhum item
      é de fato visível, e o que interessa aqui é o binding `visible: g.name === "..."`.
    """
    return sum(
        1
        for filho in item.childItems()
        if filho.metaObject().className() == 'QQuickShape' and bool(filho.property('visible'))
    )


def main() -> int:
    app = QGuiApplication(sys.argv)
    engine = QQmlEngine()

    base_qml = Path(modulo_controller.__file__).resolve().parent / 'qml'
    engine.addImportPath(str(base_qml))

    for nome in sys.argv[1:]:
        componente = QQmlComponent(engine)
        componente.setData(
            f'import QtQuick\nimport EsquizoCap.Base\nIconGlyph {{ name: "{nome}" }}'.encode(),
            QUrl(),
        )
        if componente.isError():
            print(componente.errorString(), file=sys.stderr)
            return 1

        item = componente.create()
        if not isinstance(item, QQuickItem):
            print(f'IconGlyph "{nome}" não instanciou.', file=sys.stderr)
            return 1

        app.processEvents()
        print(f'{nome}\t{_formas_visiveis(item)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
