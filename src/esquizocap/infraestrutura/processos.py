"""Lançamento e encerramento de processos externos.

Hoje isto só é usado pela integração arquivada com a engine do Godot
(`hardware/_engine_legado/`). Nada no caminho ativo lança processos: o OpenSignals é
aberto manualmente pelo usuário.

Windows-only: o encerramento usa `taskkill`.
"""

import logging
import subprocess

import psutil

logger = logging.getLogger(__name__)


class ErroDeProcesso(Exception):
    """Não foi possível iniciar o processo externo."""


def esta_rodando(nome_executavel: str) -> bool:
    """Indica se já existe um processo com esse nome."""
    return any(processo.name() == nome_executavel for processo in psutil.process_iter())


def encerrar(nome_executavel: str) -> None:
    """Encerra o processo, se ele estiver rodando. Idempotente."""
    if not esta_rodando(nome_executavel):
        logger.info(f'"{nome_executavel}" não está sendo executado')
        return

    subprocess.run(['taskkill', '/f', '/im', nome_executavel], check=False, capture_output=True)
    logger.info(f'"{nome_executavel}" encerrado')


def iniciar(nome_executavel: str, caminho: str, reiniciar: bool = False) -> None:
    """Inicia um executável.

    Args:
        nome_executavel: Nome do processo, usado para saber se já está rodando.
        caminho: Caminho completo do executável.
        reiniciar: Se True, encerra uma instância existente antes de iniciar.

    Raises:
        ErroDeProcesso: Se o executável não puder ser iniciado.
    """
    if esta_rodando(nome_executavel):
        if not reiniciar:
            logger.info(f'"{nome_executavel}" já está rodando')
            return
        encerrar(nome_executavel)

    try:
        subprocess.Popen([caminho], shell=False)
    except OSError as erro:
        raise ErroDeProcesso(f'Não foi possível iniciar "{nome_executavel}" em "{caminho}": {erro}') from erro

    logger.info(f'"{nome_executavel}" iniciado')
