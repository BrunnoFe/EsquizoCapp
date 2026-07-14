"""Ponto de entrada do EsquizoCap.

Este arquivo NÃO tem lógica de interface, de aquisição ou de negócio: ele só prepara o
ambiente e sobe a janela. A janela vive em `esquizocap.interface.janela_principal` — que
é onde ela pode ser lida, movida e mantida junto com o resto da camada de interface.
"""

import logging

from esquizocap.dominio.predicao import ErroDeModelo, carregar_modelo
from esquizocap.infraestrutura import config, log, recursos
from esquizocap.interface import loading_screen
from esquizocap.interface.janela_principal import JanelaPrincipal

logger = logging.getLogger(__name__)

DURACAO_TELA_CARREGAMENTO_MS: int = 4500


def main() -> None:
    """Prepara o ambiente e sobe a interface.

    A ordem importa. Logging, configuração, assets e MODELO são preparados ANTES de a GUI
    existir, para que um recurso faltando ou um pickle inválido falhem com uma mensagem
    clara — e não virem um erro obscuro do Tkinter, ou um estouro no meio da aquisição,
    com o BITalino já conectado.
    """
    log.configurar_logging(pasta_logs=recursos.PASTA_LOGS)

    try:
        recursos.validar()
        configuracao = config.carregar()
        modelo = carregar_modelo(caminho_modelo=configuracao.caminho_modelo)
    except (recursos.ErroDeRecurso, config.ErroDeConfiguracao, ErroDeModelo) as erro:
        logger.critical(str(erro))
        raise SystemExit(f'EsquizoCap não pôde iniciar:\n\n{erro}') from erro

    loading_screen.LoadingScreen().execute(
        folderpath=str(recursos.PASTA_GIF_CARREGAMENTO), duration=DURACAO_TELA_CARREGAMENTO_MS
    )

    JanelaPrincipal(configuracao=configuracao, modelo=modelo).executar()


if __name__ == '__main__':
    main()
