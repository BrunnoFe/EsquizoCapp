"""Ponto de entrada do EsquizoCap.

Este arquivo NÃO tem lógica de interface, de aquisição ou de negócio: ele só prepara o
ambiente e sobe a janela Qt. A janela vive em `esquizocap.interface_qt` — que é onde ela
pode ser lida, movida e mantida junto com o resto da camada de interface.

A antiga interface Tkinter está arquivada em `interface_tkinter_legado/`, na raiz do
projeto — não é mais importada nem executada por este bootstrap.
"""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine

from esquizocap.dominio.predicao import ErroDeModelo, carregar_modelo
from esquizocap.infraestrutura import config, log, recursos
from esquizocap.interface_qt.controller import EsquizoController

logger = logging.getLogger(__name__)


def main() -> int:
    """Prepara o ambiente e sobe a interface.

    A ordem importa. Logging, configuração, ícone e MODELO são preparados ANTES de a GUI
    existir, para que um recurso faltando ou um pickle inválido falhem com uma mensagem
    clara — e não virem um estouro no meio da aquisição, com o BITalino já conectado.
    """
    log.configurar_logging(pasta_logs=recursos.PASTA_LOGS)

    try:
        recursos.validar()
        configuracao = config.carregar()
        modelo = carregar_modelo(caminho_modelo=configuracao.caminho_modelo)
    except (recursos.ErroDeRecurso, config.ErroDeConfiguracao, ErroDeModelo) as erro:
        logger.critical(str(erro))
        raise SystemExit(f'EsquizoCap não pôde iniciar:\n\n{erro}') from erro

    app = QGuiApplication(sys.argv)
    app.setApplicationName('EsquizoCap')
    app.setWindowIcon(QIcon(str(recursos.ICONE)))

    engine = QQmlApplicationEngine()
    controller = EsquizoController(configuracao=configuracao, modelo=modelo)
    engine.rootContext().setContextProperty('controller', controller)

    qml = Path(__file__).resolve().parent / 'src' / 'esquizocap' / 'interface_qt' / 'EsquizoCapView.qml'
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        return -1
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
