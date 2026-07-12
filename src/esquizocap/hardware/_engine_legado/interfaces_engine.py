"""Contrato da engine visual — ARQUIVADO.

Vivia em `tools/hardware/interfaces.py` até a integração com a engine ser desligada.
Mantido aqui para que o pacote arquivado continue coerente e revivível. Ver o README
desta pasta.
"""

from typing import Protocol, runtime_checkable


class ErroEngineDesconectada(Exception):
    """A engine visual fechou a conexão (na prática, a janela do Godot foi fechada).

    Traduzia o `ConnectionResetError` do socket.
    """


@runtime_checkable
class EngineVisual(Protocol):
    """Contrato da engine de shaders reativos (Godot).

    A engine era um processo separado que conectava de volta como CLIENTE: a aplicação
    é que abria o servidor. Por isso o ciclo era `iniciar` (lança o processo) e só
    então `aguardar_conexao`.
    """

    @property
    def endereco(self) -> tuple[str, int]:
        """Endereço em que a engine era esperada, como `(ip, porta)`."""
        ...

    def iniciar(self) -> None:
        """Lança o processo da engine, reiniciando-o se já estiver rodando."""
        ...

    def aguardar_conexao(self) -> None:
        """Bloqueia até a engine conectar de volta.

        ATENÇÃO: na implementação real isso era um `accept()` bloqueante e SEM timeout,
        chamado na thread da GUI — a interface congelava até o Godot conectar.
        """
        ...

    def enviar_cor(self, rgb: tuple[int, int, int]) -> None:
        """Envia uma cor para a engine, junto dos parâmetros de shader.

        Raises:
            ErroEngineDesconectada: Se a engine tiver fechado a conexão.
        """
        ...

    def encerrar(self) -> None:
        """Encerra o processo da engine."""
        ...
