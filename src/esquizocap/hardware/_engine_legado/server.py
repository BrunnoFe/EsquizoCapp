"""Servidor TCP da engine visual — ARQUIVADO. Ver o README desta pasta.

Vivia em `tools/server.py`. A aplicação era o SERVIDOR e o Godot conectava como
cliente. Nada mais importa este módulo.
"""

import socket

from esquizocap.infraestrutura import guitools

server_logger: guitools.SetLogger = guitools.SetLogger(logfilepath=r'logs\EsquizoCapLogs.log', namelogger='serverLogger')

class Server:
    def __init__(self, port:int = 5050) -> None:
        self.serverIp: str = socket.gethostbyname(socket.gethostname()) #HELICOPTER ip addr local
        self.port: int = port
        self.addr: tuple = (self.serverIp, self.port)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        port_not_found = True
        
        while port_not_found:
            try:
                self.server.bind(self.addr)
                server_logger.logger.warning(f'Porta encontrada! Port = {self.port}')
                port_not_found = False
            except OSError as error:
                server_logger.logger.warning(f'Erro: {error}. Porta padrão "{self.port}" ocupada. Buscando nova porta.')
                self.port += 1
                self.addr = (self.serverIp , self.port)
            
        server_logger.logger.info(msg=f'Server bind to address: {self.serverIp}:{self.port}')
        self.connection:socket.socket = None
        
    def start_listen(self) -> None:   
        self.server.listen()
        server_logger.logger.info(msg='Aguardando conexão ...')
        self.connection, address = self.server.accept()
        server_logger.logger.info(msg=f'IP={':'.join(str(item) for item in address)} connected!')
        
    def send_message(self, message:str) -> None: 
        if message != "" or message is not None:
            message_enc: bytes = message.encode(guitools.ENCODING_FORMAT)
            self.connection.send(message_enc)
            server_logger.logger.info(f'Sended message = {message}')
        else:
            server_logger.logger.warning(f'Invalid message format! Message = {message}')
    
    def close_connection(self) -> None:
        server_logger.logger.info(msg='Conexão encerrada!')
        self.connection.close()
        