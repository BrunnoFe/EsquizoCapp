"""Implementação real da engine visual — ARQUIVADO. Ver o README desta pasta.

Lançava o executável do Godot e falava com ele por socket TCP. Nada mais importa este
módulo: a integração foi desligada, pendente de reescrita.
"""

from esquizocap.hardware._engine_legado import server
from esquizocap.hardware._engine_legado.engine_protocolo import montar_mensagem_visual
from esquizocap.hardware._engine_legado.interfaces_engine import ErroEngineDesconectada
from esquizocap.infraestrutura.guitools import ENCODING_FORMAT, SetLogger, kill_process, runProcess

engineRealLogger: SetLogger = SetLogger(namelogger='engineReal', logfilepath=r'logs\EsquizoCapLogs.log')


class EngineGodot:
    """Engine real: o executável exportado do Godot, falando por socket TCP.

    O código-fonte do Godot não está no repositório, então o lado de lá é uma caixa
    preta. Dois comportamentos herdados que NÃO podem mudar sem entender esse lado:

    - o servidor faz bind na IP da LAN (não em 127.0.0.1) e AUTO-INCREMENTA a porta
      se a 5050 estiver ocupada. O binário do Godot provavelmente espera 5050 fixo,
      então um incremento quebra a conexão em silêncio;
    - `aguardar_conexao` bloqueia sem timeout na thread da GUI.
    """

    def __init__(self, nome_executavel: str, caminho_executavel: str) -> None:
        self._nome_executavel: str = nome_executavel
        self._caminho_executavel: str = caminho_executavel
        # O bind acontece já na construção porque a GUI mostra o endereço no rótulo
        # de status antes mesmo de a engine subir.
        self._servidor: server.Server = server.Server()

    @property
    def endereco(self) -> tuple[str, int]:
        return self._servidor.serverIp, self._servidor.port

    def iniciar(self) -> None:
        runProcess(executablename=self._nome_executavel, path=self._caminho_executavel, forceclose=True)

    def aguardar_conexao(self) -> None:
        engineRealLogger.logger.info(f'Aguardando a engine conectar em {self._servidor.serverIp}:{self._servidor.port} ...')
        self._servidor.start_listen()

    def enviar_cor(self, rgb: tuple[int, int, int]) -> None:
        mensagem: str = montar_mensagem_visual(rgb)
        try:
            self._servidor.connection.send(mensagem.encode(ENCODING_FORMAT))
        except ConnectionResetError as erro:
            raise ErroEngineDesconectada(
                f'A engine visual fechou a conexão ao receber "{mensagem}": {erro}'
            ) from erro

    def encerrar(self) -> None:
        kill_process(self._nome_executavel)
