"""Contratos das bordas de hardware do EsquizoCap.

Cada classe base aqui captura apenas o que o resto do sistema realmente consome do
componente — nem mais, nem menos. Assim é possível trocar o hardware real por um
simulador sem que a GUI ou a lógica de negócio percebam a diferença.

São `abc.ABC`, e não `Protocol`: a herança é explícita, e uma implementação a que
falte qualquer método do contrato falha já na instanciação, em vez de só estourar
quando o método faltante for chamado — o que, numa borda de hardware, aconteceria
no meio de uma aquisição.
"""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self


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


class ControladorLedArduino(ABC):
    """Contrato do Arduino que comanda a fita de LED.

    O protocolo serial em si (formato do comando, encoding) é responsabilidade da
    implementação, não de quem chama: quem consome esta interface pensa em
    "enviar uma cor", não em bytes.

    É um context manager: dentro de um `with`, a porta é fechada ao sair do bloco,
    inclusive se uma exceção interromper o corpo. Uma porta serial é um recurso do
    SO — deixá-la aberta impede o próximo processo (ou a próxima execução) de abrir.
    """

    @property
    @abstractmethod
    def esta_conectado(self) -> bool:
        """Indica se a porta serial está aberta no momento."""

    @abstractmethod
    def listar_portas(self) -> list[str]:
        """Lista as portas seriais disponíveis, no formato "COM5 - descrição".

        A GUI depende de a string conter "COM" para liberar o botão de conexão,
        e `conectar` corta a descrição no primeiro " - ".
        """

    @abstractmethod
    def conectar(self, porta: str, baudrate: int) -> None:
        """Abre a conexão serial com o Arduino.

        Args:
            porta: Porta escolhida na GUI, possivelmente com descrição ("COM5 - CH340").
            baudrate: Velocidade da porta serial (o firmware atual espera 9600).

        Raises:
            ErroConexaoArduino: Se a porta não puder ser aberta.
        """

    @abstractmethod
    def desconectar(self) -> None:
        """Fecha a conexão serial.

        DEVE ser idempotente: chamar duas vezes, ou sem nunca ter conectado, não pode
        levantar exceção. O `__exit__` depende disso — ele fecha a porta mesmo quando o
        corpo do `with` falhou antes de conectar.
        """

    @abstractmethod
    def enviar_comando_cor(self, modo: int, hue: int, saturacao: int, brilho: int) -> None:
        """Envia uma cor HSV e o modo de animação para a fita de LED.

        Args:
            modo: Modo de luminosidade, de 1 a 4 (Um a um, Todos, Gradiente, A partir do Centro).
            hue: Matiz previsto pelo modelo, de 0 a 255.
            saturacao: Saturação, de 0 a 255 (vem do medidor da GUI, não do modelo).
            brilho: Brilho, de 0 a 255 (vem do medidor da GUI, não do modelo).
        """

    def __enter__(self) -> Self:
        """Entra no bloco `with`.

        NÃO conecta: porta e baudrate são escolhas de quem chama, e conectar aqui
        exigiria passá-las ao construtor. O `with` cuida só do fechamento.
        """
        return self

    def __exit__(
        self,
        tipo_excecao: type[BaseException] | None,
        excecao: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Fecha a porta ao sair do bloco, mesmo se o corpo levantou exceção.

        Retorna None (falsy), ou seja, NÃO suprime a exceção: ela continua subindo.
        """
        self.desconectar()


class LeitorBitalino(ABC):
    """Contrato da fonte de sinal EEG.

    O BITalino nunca é acessado direto: o OpenSignals publica um stream via Lab
    Streaming Layer e é dele que se lê. Quem consome esta interface não precisa
    saber disso — só pede amostras.

    É um context manager: dentro de um `with`, o stream é encerrado ao sair do bloco,
    inclusive se uma exceção interromper o corpo. O inlet do LSL segura um socket;
    abandoná-lo aberto deixa a conexão pendurada até o processo morrer.
    """

    @abstractmethod
    def conectar(self, mac_addr: str) -> None:
        """Abre o stream de EEG do dispositivo com o MAC informado.

        Args:
            mac_addr: Endereço MAC do BITalino, que é também o `type` do stream LSL.

        Raises:
            ErroConexaoBitalino: MAC inválido, ou stream não encontrado (OpenSignals
                fechado ou sem o compartilhamento LSL ativo).
        """

    @abstractmethod
    def taxa_amostragem_nominal(self) -> int:
        """Taxa de amostragem declarada pelo stream, em Hz."""

    @abstractmethod
    def ler_amostra(self, timeout: float) -> tuple[list[float], float]:
        """Lê uma única amostra (um valor por canal) e seu timestamp.

        Usado no modo Amplitude, em que cada amostra vira uma predição de cor.

        Returns:
            Uma tupla `(canais, timestamp)`, onde `canais` tem um valor por canal do
            dispositivo — a aquisição indexa esse vetor pelo canal escolhido na GUI.

        Raises:
            ErroStreamPerdido: Se o stream cair durante a leitura.
        """

    @abstractmethod
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

    @abstractmethod
    def encerrar_stream(self) -> None:
        """Fecha o stream.

        DEVE ser idempotente: chamar duas vezes, ou sem nunca ter conectado, não pode
        levantar exceção. O `__exit__` depende disso — ele encerra o stream mesmo
        quando o corpo do `with` falhou antes de conectar.
        """

    def __enter__(self) -> Self:
        """Entra no bloco `with`.

        NÃO conecta: o MAC é escolha de quem chama. O `with` cuida só do fechamento.
        """
        return self

    def __exit__(
        self,
        tipo_excecao: type[BaseException] | None,
        excecao: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Encerra o stream ao sair do bloco, mesmo se o corpo levantou exceção.

        Retorna None (falsy), ou seja, NÃO suprime a exceção: ela continua subindo.
        """
        self.encerrar_stream()
