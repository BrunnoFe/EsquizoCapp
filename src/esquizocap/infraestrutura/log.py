"""Configuração de logging da aplicação.

Um único ponto configura os handlers, e uma única vez, na inicialização. Os módulos
apenas pedem `logging.getLogger(__name__)` — sem criar handlers, sem escrever em disco no
momento do import.

Isso corrige dois defeitos do desenho anterior: cada módulo instanciava o próprio logger
com um nome de arquivo carimbado com timestamp, o que produzia **um arquivo de log por
módulo, por execução** (seis ou mais, cada um com um pedaço da história); e a
configuração acontecia como efeito colateral de import.
"""

import logging
import logging.config
import time
from pathlib import Path

FORMATO = '%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s | %(message)s'
NIVEL_PADRAO = 'INFO'

NIVEIS_DISPONIVEIS: tuple[str, ...] = ('DEBUG', 'INFO', 'WARNING', 'ERROR')
"""Níveis oferecidos na interface. `CRITICAL` fica de fora: um nível que esconde erros
não é uma escolha que ajude alguém a diagnosticar coisa nenhuma."""

_arquivo_atual: Path | None = None


def arquivo_atual() -> Path | None:
    """O arquivo de log desta execução, ou `None` se o logging ainda não foi configurado.

    Existe para a interface poder abrir o log sem que `main` tenha de carregar o caminho
    por todas as camadas até o controller.
    """
    return _arquivo_atual


def definir_nivel(nivel: str) -> None:
    """Troca o nível dos logs da aplicação em runtime.

    Ajusta o logger `esquizocap` E o handler de arquivo: o handler tem nível próprio, e
    mexer só no logger deixaria os registros de DEBUG serem criados e descartados na
    escrita — o sintoma seria "liguei o DEBUG e o arquivo continua igual".

    Args:
        nivel: Um de `NIVEIS_DISPONIVEIS`. Um valor desconhecido é ignorado com aviso.
    """
    if nivel not in NIVEIS_DISPONIVEIS:
        logging.getLogger(__name__).warning(f'Nível de log desconhecido, ignorado: "{nivel}".')
        return

    logger_app = logging.getLogger('esquizocap')
    logger_app.setLevel(nivel)
    for handler in logger_app.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(nivel)
    logger_app.info(f'Nível de log alterado para {nivel}.')


def configurar_logging(pasta_logs: Path, nivel: str = NIVEL_PADRAO) -> Path:
    """Configura o logging da aplicação inteira. Chame uma vez, na inicialização.

    Args:
        pasta_logs: Onde gravar o arquivo. Criada se não existir.
        nivel: Nível dos logs da aplicação (o console fica em WARNING para não poluir).

    Returns:
        O caminho do arquivo de log desta execução.
    """
    global _arquivo_atual

    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_logs / f'esquizocap_{time.strftime("%Y-%m-%d_%H-%M-%S")}.log'
    _arquivo_atual = arquivo

    logging.config.dictConfig(
        {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {'padrao': {'format': FORMATO}},
            'handlers': {
                'arquivo': {
                    'class': 'logging.FileHandler',
                    'filename': str(arquivo),
                    'encoding': 'utf-8',
                    'formatter': 'padrao',
                    'level': nivel,
                },
                # O console fica só com o que exige atenção: durante a aquisição, o log de
                # INFO é volumoso e esconderia qualquer coisa realmente importante.
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'padrao',
                    'level': 'WARNING',
                },
            },
            'loggers': {
                'esquizocap': {'handlers': ['arquivo', 'console'], 'level': nivel, 'propagate': False},
            },
            'root': {'handlers': ['console'], 'level': 'WARNING'},
        }
    )

    logging.getLogger('esquizocap').info(f'Logging iniciado. Arquivo desta execução: {arquivo}')
    return arquivo
