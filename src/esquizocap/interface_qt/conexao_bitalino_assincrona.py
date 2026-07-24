"""Conexão do BITalino fora da GUI thread.

`LeitorBitalino.conectar` bloqueia nos dois modos de aquisição — resolvendo o stream LSL
no Modo OpenSignals, abrindo a porta serial no Modo Direto — e pode levar segundos. A GUI
não pode travar durante esse tempo, por isso a chamada real roda numa `threading.Thread`
auxiliar.
"""

import logging
import threading
from collections.abc import Callable

from esquizocap.hardware.contratos import ErroConexaoBitalino, LeitorBitalino

logger = logging.getLogger(__name__)


class ConectorBitalinoAssincrono:
    """Dispara `leitor.conectar(...)` numa thread auxiliar e entrega o resultado
    através de um callback.

    O callback é chamado a partir da THREAD AUXILIAR, nunca da GUI thread. Quem usa
    esta classe numa interface Qt deve entregar um callback thread-safe — no
    `EsquizoController`, isso é feito emitindo um `Signal` Qt de dentro do callback,
    já que sinais Qt cruzam de thread automaticamente (viram `Qt.QueuedConnection`).
    """

    def __init__(self, leitor: LeitorBitalino) -> None:
        self._leitor = leitor

    def conectar(
        self,
        endereco: str,
        taxa_amostragem_hz: int,
        canais: list[int],
        ao_concluir: Callable[[bool, str], None],
    ) -> None:
        """Inicia a conexão numa thread auxiliar e retorna imediatamente.

        Args:
            endereco: Onde encontrar o dispositivo — MAC do dispositivo no Modo
                OpenSignals, porta de acesso no Modo Direto.
            taxa_amostragem_hz: Taxa acordada para a aquisição.
            canais: Canais analógicos a adquirir.
            ao_concluir: Chamado, na thread auxiliar, com `(sucesso, mensagem_erro)`
                — mensagem vazia em caso de sucesso.
        """

        def alvo_da_thread() -> None:
            try:
                self._leitor.conectar(endereco=endereco, taxa_amostragem_hz=taxa_amostragem_hz, canais=canais)
            except ErroConexaoBitalino as erro:
                ao_concluir(False, str(erro))
            else:
                ao_concluir(True, "")

        threading.Thread(target=alvo_da_thread, name="conectar-bitalino", daemon=True).start()
