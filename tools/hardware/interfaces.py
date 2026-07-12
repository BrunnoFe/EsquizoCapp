"""Contratos das bordas de hardware do EsquizoCap.

Cada Protocol aqui captura apenas o que o resto do sistema realmente consome do
componente — nem mais, nem menos. Assim é possível trocar o hardware real por um
simulador sem que a GUI ou a lógica de negócio percebam a diferença.
"""

from typing import Protocol, runtime_checkable


class ErroConexaoArduino(Exception):
    """Falha ao abrir ou manter a conexão serial com o Arduino.

    Existe para que as implementações não vazem exceções específicas do pyserial
    (`serial.SerialException`) para quem consome a interface.
    """


class ErroConexaoBitalino(Exception):
    """Falha ao resolver ou abrir o stream de EEG do BITalino.

    Cobre tanto MAC inválido quanto stream não encontrado — na prática, o
    OpenSignals fechado ou sem o compartilhamento "Lab Streaming Layer" ativo.
    """


class ErroStreamPerdido(Exception):
    """O stream de EEG caiu no meio da aquisição.

    Traduz o `pylsl.LostError` para que a lógica de aquisição não precise
    conhecer o pylsl. A aquisição trata isso parando a captura, não como fatal.
    """


class ErroEngineDesconectada(Exception):
    """A engine visual fechou a conexão (na prática, a janela do Godot foi fechada).

    Traduz o `ConnectionResetError` do socket. A aquisição trata isso parando a
    captura.
    """


@runtime_checkable
class ControladorLedArduino(Protocol):
    """Contrato do Arduino que comanda a fita de LED.

    O protocolo serial em si (formato do comando, encoding) é responsabilidade da
    implementação, não de quem chama: quem consome esta interface pensa em
    "enviar uma cor", não em bytes.
    """

    @property
    def esta_conectado(self) -> bool:
        """Indica se a porta serial está aberta no momento."""
        ...

    def listar_portas(self) -> list[str]:
        """Lista as portas seriais disponíveis, no formato "COM5 - descrição".

        A GUI depende de a string conter "COM" para liberar o botão de conexão,
        e `conectar` corta a descrição no primeiro " - ".
        """
        ...

    def conectar(self, porta: str, baudrate: int) -> None:
        """Abre a conexão serial com o Arduino.

        Args:
            porta: Porta escolhida na GUI, possivelmente com descrição ("COM5 - CH340").
            baudrate: Velocidade da porta serial (o firmware atual espera 9600).

        Raises:
            ErroConexaoArduino: Se a porta não puder ser aberta.
        """
        ...

    def desconectar(self) -> None:
        """Fecha a conexão serial. Não deve falhar se já estiver fechada."""
        ...

    def enviar_comando_cor(self, modo: int, hue: int, saturacao: int, brilho: int) -> None:
        """Envia uma cor HSV e o modo de animação para a fita de LED.

        Args:
            modo: Modo de luminosidade, de 1 a 4 (Um a um, Todos, Gradiente, A partir do Centro).
            hue: Matiz previsto pelo modelo, de 0 a 255.
            saturacao: Saturação, de 0 a 255 (vem do medidor da GUI, não do modelo).
            brilho: Brilho, de 0 a 255 (vem do medidor da GUI, não do modelo).
        """
        ...


@runtime_checkable
class LeitorBitalino(Protocol):
    """Contrato da fonte de sinal EEG.

    O BITalino nunca é acessado direto: o OpenSignals publica um stream via Lab
    Streaming Layer e é dele que se lê. Quem consome esta interface não precisa
    saber disso — só pede amostras.
    """

    def conectar(self, mac_addr: str) -> None:
        """Abre o stream de EEG do dispositivo com o MAC informado.

        Args:
            mac_addr: Endereço MAC do BITalino, que é também o `type` do stream LSL.

        Raises:
            ErroConexaoBitalino: MAC inválido, ou stream não encontrado (OpenSignals
                fechado ou sem o compartilhamento LSL ativo).
        """
        ...

    def taxa_amostragem_nominal(self) -> int:
        """Taxa de amostragem declarada pelo stream, em Hz."""
        ...

    def ler_amostra(self, timeout: float) -> tuple[list[float], float]:
        """Lê uma única amostra (um valor por canal) e seu timestamp.

        Usado no modo Amplitude, em que cada amostra vira uma predição de cor.

        Returns:
            Uma tupla `(canais, timestamp)`, onde `canais` tem um valor por canal do
            dispositivo — a aquisição indexa esse vetor pelo canal escolhido na GUI.

        Raises:
            ErroStreamPerdido: Se o stream cair durante a leitura.
        """
        ...

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        """Lê um bloco de amostras de uma vez, com os timestamps correspondentes.

        Usado no modo Frequência, que acumula blocos até ter amostras suficientes
        para a análise espectral.

        Returns:
            Uma tupla `(amostras, timestamps)`, onde `amostras` é uma lista de linhas
            e cada linha tem um valor por canal.

        Raises:
            ErroStreamPerdido: Se o stream cair durante a leitura.
        """
        ...

    def encerrar_stream(self) -> None:
        """Fecha o stream. Não deve falhar se já estiver fechado."""
        ...


@runtime_checkable
class EngineVisual(Protocol):
    """Contrato da engine de shaders reativos (Godot).

    A engine é um processo separado que conecta de volta como CLIENTE: a aplicação
    é quem abre o servidor. Por isso o ciclo é `iniciar` (lança o processo) e só
    então `aguardar_conexao`.
    """

    @property
    def endereco(self) -> tuple[str, int]:
        """Endereço em que a engine é esperada, como `(ip, porta)`.

        Precisa existir antes de a engine subir: a GUI mostra esse endereço no
        rótulo de status assim que a janela abre.
        """
        ...

    def iniciar(self) -> None:
        """Lança o processo da engine, reiniciando-o se já estiver rodando."""
        ...

    def aguardar_conexao(self) -> None:
        """Bloqueia até a engine conectar de volta.

        ATENÇÃO: na implementação real isso é um `accept()` bloqueante e SEM timeout,
        chamado na thread da GUI — a interface congela até o Godot conectar. É o
        comportamento original e a ordem (`iniciar` e depois `aguardar_conexao`) não
        pode ser invertida.
        """
        ...

    def enviar_cor(self, rgb: tuple[int, int, int]) -> None:
        """Envia uma cor para a engine, junto dos parâmetros de shader.

        Args:
            rgb: Cor já convertida de HSV para RGB, cada canal de 0 a 255.

        Raises:
            ErroEngineDesconectada: Se a engine tiver fechado a conexão.
        """
        ...

    def encerrar(self) -> None:
        """Encerra o processo da engine. Não deve falhar se ele já estiver fechado."""
        ...
