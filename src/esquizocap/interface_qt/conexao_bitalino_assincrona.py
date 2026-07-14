"""Conexão do BITalino fora da GUI thread.

`LeitorBitalino.conectar` bloqueia por causa da resolução do stream LSL (pode levar
segundos), e a GUI não pode travar durante esse tempo — por isso a chamada real roda
numa `threading.Thread` auxiliar.
"""

import logging
import threading
from collections.abc import Callable

from esquizocap.hardware.contratos import ErroConexaoBitalino, LeitorBitalino

logger = logging.getLogger(__name__)


class ConectorBitalinoAssincrono:
    """Dispara `leitor.conectar(mac_addr=...)` numa thread auxiliar e entrega o
    resultado através de um callback.

    O callback é chamado a partir da THREAD AUXILIAR, nunca da GUI thread. Quem usa
    esta classe numa interface Qt deve entregar um callback thread-safe — no
    `EsquizoController`, isso é feito emitindo um `Signal` Qt de dentro do callback,
    já que sinais Qt cruzam de thread automaticamente (viram `Qt.QueuedConnection`).
    """

    def __init__(self, leitor: LeitorBitalino) -> None:
        self._leitor = leitor

    def conectar(self, mac_addr: str, ao_concluir: Callable[[bool, str], None]) -> None:
        """Inicia a conexão numa thread auxiliar e retorna imediatamente.

        Args:
            mac_addr: MAC do stream LSL a resolver, igual ao configurado no
                OpenSignals.
            ao_concluir: Chamado, na thread auxiliar, com `(sucesso, mensagem_erro)`
                — mensagem vazia em caso de sucesso.
        """

        def alvo_da_thread() -> None:
            try:
                self._leitor.conectar(mac_addr=mac_addr)
            except ErroConexaoBitalino as erro:
                ao_concluir(False, str(erro))
            else:
                ao_concluir(True, "")

        threading.Thread(target=alvo_da_thread, name="conectar-bitalino", daemon=True).start()
