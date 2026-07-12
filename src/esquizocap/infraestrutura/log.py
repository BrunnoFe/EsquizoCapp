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


def configurar_logging(pasta_logs: Path, nivel: str = NIVEL_PADRAO) -> Path:
    """Configura o logging da aplicação inteira. Chame uma vez, na inicialização.

    Args:
        pasta_logs: Onde gravar o arquivo. Criada se não existir.
        nivel: Nível dos logs da aplicação (o console fica em WARNING para não poluir).

    Returns:
        O caminho do arquivo de log desta execução.
    """
    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_logs / f'esquizocap_{time.strftime("%Y-%m-%d_%H-%M-%S")}.log'

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
