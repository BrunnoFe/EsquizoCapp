"""Implementação fake da engine visual — ARQUIVADO. Ver o README desta pasta.

Fingia ser a engine do Godot, sem processo nem socket. Nada mais importa este módulo.
"""

import logging

from esquizocap.hardware._engine_legado.engine_protocolo import montar_mensagem_visual

ENDERECO_SIMULADO: tuple[str, int] = ('127.0.0.1', 5050)

logger = logging.getLogger(__name__)


class EngineSimulada:
    """Finge ser a engine do Godot, registrando em log o que seria enviado.

    Diferença importante para a real: `aguardar_conexao` retorna imediatamente, em
    vez de bloquear num `accept()`. Sem isso a GUI congelaria esperando um Godot que
    nunca vai conectar, e a aquisição não poderia ser exercitada sem o binário.

    A mensagem é montada pelo mesmo código da engine real
    (`engine_protocolo.montar_mensagem_visual`), então o formato não diverge.
    """

    def __init__(self) -> None:
        self.ultima_mensagem: str | None = None
        self.mensagens_enviadas: int = 0

    @property
    def endereco(self) -> tuple[str, int]:
        return ENDERECO_SIMULADO

    def iniciar(self) -> None:
        logger.info('[FAKE] Engine simulada "iniciada" (nenhum processo do Godot foi lançado)')

    def aguardar_conexao(self) -> None:
        logger.info('[FAKE] Engine simulada conectada de imediato (sem accept() bloqueante)')

    def enviar_cor(self, rgb: tuple[int, int, int]) -> None:
        self.ultima_mensagem = montar_mensagem_visual(rgb)
        self.mensagens_enviadas += 1
        logger.debug(f'[FAKE] Mensagem que iria para o Godot = {self.ultima_mensagem!r}')

    def encerrar(self) -> None:
        logger.info(
            f'[FAKE] Engine simulada encerrada após {self.mensagens_enviadas} mensagens'
        )
