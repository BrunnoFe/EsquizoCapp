"""Faz uma exceção não tratada virar uma caixa na tela, em vez de sumir no console.

O modo de falha que isto ataca é o mais caro do projeto, e é silencioso. Sem esta rede, uma
exceção levantada fora de um `try` — um `ValueError` do protocolo do BITalino, por exemplo —
sobe até o Qt, que imprime o traceback no `stderr` e **segue rodando**. A janela continua
viva, a fita de LED continua acesa na última cor calculada, e nada na tela diz que o
programa parou de saber o que está fazendo. Numa instalação em exposição, isso é
indistinguível de escolha artística.

O que a rede NÃO cobre, e vale saber antes de confiar demais nela:

- Exceção dentro de um slot do Qt nem sempre chega ao `sys.excepthook` — dependendo da
  versão e do modo de compilação, o PySide as trata internamente.
- Exceção em thread criada por bibliotecas de terceiros que instalem o próprio hook.

Cobre o caminho principal e as threads criadas com `threading.Thread`, que é muito mais do
que existia antes — que era nada.
"""

from __future__ import annotations

import logging
import sys
import threading
from types import TracebackType

from esquizocap.aplicacao import catalogo_erros
from esquizocap.interface.controller import EsquizoController

logger = logging.getLogger(__name__)


def instalar(controlador: EsquizoController) -> None:
    """Passa a encaminhar exceções não tratadas para a caixa de mensagem do `controlador`.

    Chamado uma vez, no bootstrap, depois que o controller existe. Os hooks anteriores são
    chamados também, para não engolir o traceback que o Python já imprimiria — a caixa
    ACRESCENTA um aviso visível, não substitui o registro.
    """
    hook_anterior = sys.excepthook
    hook_de_thread_anterior = threading.excepthook

    def ao_escapar_uma_excecao(
        tipo: type[BaseException],
        erro: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        # KeyboardInterrupt é o usuário mandando parar, não um defeito: abrir uma caixa
        # sobre isso seria ruído, e ela nem seria vista, já que o app está fechando.
        if issubclass(tipo, KeyboardInterrupt):
            hook_anterior(tipo, erro, traceback)
            return

        logger.critical('Exceção não tratada chegou ao topo', exc_info=(tipo, erro, traceback))
        _avisar_na_tela(controlador, erro)
        hook_anterior(tipo, erro, traceback)

    def ao_escapar_numa_thread(argumentos: threading.ExceptHookArgs) -> None:
        if argumentos.exc_value is None or issubclass(argumentos.exc_type, SystemExit):
            hook_de_thread_anterior(argumentos)
            return

        logger.critical(
            f'Exceção não tratada na thread "{argumentos.thread.name if argumentos.thread else "?"}"',
            exc_info=(argumentos.exc_type, argumentos.exc_value, argumentos.exc_traceback),
        )
        _avisar_na_tela(controlador, argumentos.exc_value)
        hook_de_thread_anterior(argumentos)

    sys.excepthook = ao_escapar_uma_excecao
    threading.excepthook = ao_escapar_numa_thread
    logger.debug('Rede de segurança de exceções instalada.')


def _avisar_na_tela(controlador: EsquizoController, erro: BaseException) -> None:
    """Pede a caixa pelo SINAL, e não chamando `_reportar` direto.

    O hook roda na thread onde a exceção aconteceu, que pode não ser a da GUI. Emitir o
    sinal deixa o Qt enfileirar a chamada na thread do controller; escrever o estado daqui
    seria uma corrida silenciosa — exatamente o tipo de bug que este módulo existe para
    tornar visível.

    Um `except` amplo aqui é deliberado: se avisar na tela falhar, o traceback original
    ainda precisa chegar ao hook anterior. Falhar aqui não pode custar o registro do erro
    de verdade.
    """
    try:
        controlador.mensagemSolicitada.emit(catalogo_erros.falha_inesperada(erro))
    except Exception:  # noqa: BLE001
        logger.exception('A rede de segurança não conseguiu mostrar a caixa de erro')
