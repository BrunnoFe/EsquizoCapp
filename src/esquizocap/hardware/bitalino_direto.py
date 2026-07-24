"""Leitor de EEG do Modo Direto: fala com o BITalino pela porta de acesso, sem OpenSignals.

Ao contrário do Modo OpenSignals, aqui a aplicação DIRIGE o dispositivo: escolhe a taxa
acordada, escolhe os canais e manda iniciar. Três consequências que valem entender antes de
mexer neste arquivo:

1. **Silêncio é falha, não ciclo vazio.** No Modo OpenSignals a aplicação assina um stream
   que outro programa publica, e um timeout significa "ele ainda não publicou". Aqui, depois
   do comando de início, o dispositivo emite na taxa acordada e ponto: silêncio prolongado
   quer dizer que algo quebrou. Por isso `ler_amostra` e `ler_bloco` NUNCA devolvem
   `(None, None)` — qualquer falha vira `ErroStreamPerdido`.

2. **O layout de saída imita o do OpenSignals**, e não o do protocolo. O firmware manda
   `[seq, dig0..dig3, A1..A6]`; o stream LSL publica `[nSeq, A1..A6]`. Quem consome indexa
   pelo NÚMERO do canal (`amostra[canal]`, canal de 1 a 6), então os quatro canais digitais
   saem fora e o número de sequência FICA, no índice 0. Recortar o cabeçalho inteiro poria
   A1 no índice 0 e faria o canal 1 ler A2 — sem erro nenhum, só cor errada na fita.

3. **Só o canal ativo é convertido para microvolts.** É o que mais se aproxima do
   OpenSignals, que converte apenas os canais com sensor declarado e entrega os demais em
   ADU cru. Os outros cinco canais saem em ADU, e isso é intencional — ver `docs/notas-futuras.md`.

O protocolo em si vive em `protocolo_bitalino`, todo em funções puras, para ser testável sem
dispositivo plugado.
"""

import logging
import re
import time

import serial
from serial.serialutil import SerialException

from esquizocap.hardware import protocolo_bitalino
from esquizocap.hardware.contratos import ErroConexaoBitalino, ErroStreamPerdido, LeitorBitalino

logger = logging.getLogger(__name__)

PAUSA_ENTRE_COMANDOS_SEGUNDOS: float = 0.1
"""O firmware não acompanha dois comandos colados. A API oficial usa a mesma pausa."""

CANAL_ATIVO_PADRAO: int = 1
"""Canal convertido enquanto a interface não informar outro."""

FOLGA_DO_BLOCO: float = 3.0
"""Quantas vezes a duração teórica o bloco pode levar antes de ser considerado perdido.

Folgado de propósito: o Bluetooth entrega em rajadas, e um teto apertado transformaria
jitter normal em falha. O que se quer pegar é a ordem de grandeza errada, não o atraso.
"""

PADRAO_PORTA_DE_ACESSO: re.Pattern[str] = re.compile(r'^(COM\d+|/dev/\S+)$', re.IGNORECASE)
"""Uma porta de acesso, não um MAC.

Validar antes de abrir importa porque o engano mais provável é passar o MAC do dispositivo
— que é o endereço do OUTRO modo. Sem esta guarda o erro viria do sistema operacional, numa
mensagem que não explica o que o operador fez de errado.
"""


class BitalinoDireto(LeitorBitalino):
    """Leitor do Modo Direto, sobre a porta de acesso (`COM7`) do BITalino.

    O OpenSignals precisa estar FECHADO: o dispositivo aceita um cliente por vez, e a porta
    fica presa a quem a abriu primeiro.
    """

    def __init__(self) -> None:
        self._porta: serial.Serial | None = None
        self._canais: list[int] = []
        self._taxa_amostragem_hz: int = 0
        self._canal_ativo: int = CANAL_ATIVO_PADRAO
        self._amostras_lidas: int = 0

    def conectar(self, endereco: str, taxa_amostragem_hz: int, canais: list[int]) -> None:
        """Abre a porta de acesso e inicia a aquisição no dispositivo.

        Args:
            endereco: Porta de acesso, no formato `COM7`.
            taxa_amostragem_hz: Taxa acordada. Só 1, 10, 100 ou 1000 Hz.
            canais: Canais analógicos a adquirir, de 1 a 6.

        Raises:
            ErroConexaoBitalino: Porta inválida, porta que não abre (dispositivo desligado,
                OpenSignals segurando a porta, pareamento caído) ou parâmetros de aquisição
                que o firmware não aceita.
        """
        if not PADRAO_PORTA_DE_ACESSO.match(endereco):
            raise ErroConexaoBitalino(
                f'Porta de acesso inválida: "{endereco}". No Modo Direto o endereço é uma porta '
                'serial, no formato "COM7" (Windows) ou "/dev/rfcomm0" — e NÃO o MAC do '
                'dispositivo, que só vale no Modo OpenSignals.'
            )

        # Os comandos são montados ANTES de abrir a porta: assim um parâmetro inválido falha
        # sem deixar uma porta aberta para trás.
        try:
            comando_taxa = protocolo_bitalino.comando_definir_taxa(taxa_hz=taxa_amostragem_hz)
            comando_inicio = protocolo_bitalino.comando_iniciar(canais=canais)
        except ValueError as erro:
            raise ErroConexaoBitalino(f'Parâmetros de aquisição inválidos: {erro}') from erro

        logger.info(
            f'Abrindo porta de acesso "{endereco}" a {taxa_amostragem_hz} Hz, canais {sorted(set(canais))} ...'
        )

        try:
            porta = serial.Serial(endereco, protocolo_bitalino.BAUDRATE)
        except (SerialException, ValueError) as erro:
            raise ErroConexaoBitalino(
                f'Não foi possível abrir a porta de acesso "{endereco}": {erro}. '
                'Verifique se o BITalino está ligado e pareado, se a porta é a de saída do par '
                'Bluetooth e se o OpenSignals está FECHADO — o dispositivo aceita um cliente por vez.'
            ) from erro

        self._porta = porta
        self._canais = sorted(set(canais))
        self._taxa_amostragem_hz = taxa_amostragem_hz
        self._amostras_lidas = 0

        try:
            self._enviar(comando_taxa)
            self._enviar(comando_inicio)
        except ErroStreamPerdido as erro:
            # A porta abriu mas o dispositivo não aceitou os comandos: fecha antes de subir,
            # senão ela fica presa até o processo morrer.
            self.encerrar_stream()
            raise ErroConexaoBitalino(f'A porta "{endereco}" abriu, mas o BITalino não respondeu: {erro}') from erro

        logger.info(f'BITalino "{endereco}" adquirindo a {taxa_amostragem_hz} Hz')

    def definir_canal_ativo(self, canal: int) -> None:
        """Define qual canal é convertido para microvolts. Não toca no dispositivo."""
        protocolo_bitalino.validar_canal(canal=canal)
        self._canal_ativo = canal

    def taxa_amostragem_nominal(self) -> int:
        """A taxa ACORDADA — aqui é uma lembrança, não uma pergunta: foi a aplicação que a
        escolheu e a mandou ao dispositivo.

        Raises:
            ErroConexaoBitalino: Se ainda não houve conexão. Devolver 0 seria pior: a
                análise espectral divide pela taxa, e um zero silencioso viraria divisão por
                zero ou uma banda sem sentido, longe daqui.
        """
        self._porta_aberta()
        return self._taxa_amostragem_hz

    def _porta_aberta(self) -> serial.Serial:
        """Devolve a porta, exigindo que `conectar` já tenha rodado.

        Raises:
            ErroConexaoBitalino: Se a porta não estiver aberta.
        """
        if self._porta is None:
            raise ErroConexaoBitalino(
                'Porta de acesso do BITalino não está aberta. Chame `conectar` antes de ler amostras.'
            )
        return self._porta

    def _enviar(self, comando: int) -> None:
        """Envia um comando de um byte ao firmware.

        Raises:
            ErroStreamPerdido: Se a escrita falhar (cabo arrancado, pareamento caído).
        """
        time.sleep(PAUSA_ENTRE_COMANDOS_SEGUNDOS)
        try:
            self._porta_aberta().write(bytes([comando]))
        except SerialException as erro:
            raise ErroStreamPerdido(f'Falha ao enviar o comando {comando:#04x} ao BITalino: {erro}') from erro

    def _ler_uma_linha(self, timeout: float) -> list[float]:
        """Lê um frame e devolve `[seq, A1..An]`, com o canal ativo já em microvolts.

        Raises:
            ErroStreamPerdido: Timeout, falha de transporte ou frame corrompido. As três
                significam a mesma coisa neste modo — a aquisição não está mais confiável —,
                e a mensagem distingue qual foi, para o log.
        """
        porta = self._porta_aberta()
        tamanho = protocolo_bitalino.tamanho_frame_bytes(quantidade_canais=len(self._canais))
        porta.timeout = timeout

        try:
            frame = porta.read(tamanho)
        except SerialException as erro:
            raise ErroStreamPerdido(f'Falha ao ler do BITalino: {erro}') from erro

        if len(frame) != tamanho:
            raise ErroStreamPerdido(
                f'O BITalino parou de enviar: esperados {tamanho} byte(s), chegaram {len(frame)} '
                f'em {timeout:.2f}s. Verifique a alimentação e o pareamento.'
            )

        if not protocolo_bitalino.crc_confere(frame=frame):
            # Sem retry automático de propósito: reconectar em silêncio esconderia um
            # dispositivo genuinamente ruim. A interface oferece reconectar.
            raise ErroStreamPerdido(
                'Frame do BITalino chegou corrompido (CRC não confere). Pode ser interferência '
                'no Bluetooth ou distância excessiva do dispositivo.'
            )

        leitura = protocolo_bitalino.decodificar_frame(frame=frame, quantidade_canais=len(self._canais))
        return protocolo_bitalino.montar_linha(
            leitura=leitura, canais=self._canais, canal_ativo=self._canal_ativo
        )

    def ler_amostra(self, timeout: float) -> tuple[list[float], float] | tuple[None, None]:
        """Lê uma amostra. NUNCA devolve `(None, None)`: ver o cabeçalho do módulo."""
        linha = self._ler_uma_linha(timeout=timeout)
        timestamp = self._proximo_timestamp()
        return linha, timestamp

    def ler_bloco(self, timeout: float, max_amostras: int) -> tuple[list[list[float]], list[float]]:
        """Lê um bloco inteiro. Devolve `max_amostras` linhas ou levanta.

        Um bloco parcial significaria que o dispositivo parou no meio, e neste modo isso é
        falha, não ciclo vazio.

        O `timeout` vale por amostra, MAS o bloco também tem um teto agregado, proporcional
        ao tempo que ele deveria levar na taxa acordada. Sem esse teto, um bloco grande numa
        taxa baixa bloquearia por minutos — 500 amostras a 1 Hz são mais de oito minutos — e
        a interface ficaria muda, sem erro e sem dado, que é exatamente o modo de falha que
        este leitor existe para evitar.

        Raises:
            ErroStreamPerdido: Se uma amostra falhar, ou se o bloco estourar o teto agregado.
        """
        duracao_esperada = max_amostras / self._taxa_amostragem_hz
        prazo_final = time.monotonic() + duracao_esperada * FOLGA_DO_BLOCO + timeout

        amostras: list[list[float]] = []
        timestamps: list[float] = []

        for _ in range(max_amostras):
            if time.monotonic() > prazo_final:
                raise ErroStreamPerdido(
                    f'A leitura do bloco estourou o prazo: {len(amostras)} de {max_amostras} amostras '
                    f'em mais de {duracao_esperada * FOLGA_DO_BLOCO + timeout:.1f}s, quando a {self._taxa_amostragem_hz} Hz '
                    f'deveria levar ~{duracao_esperada:.1f}s. O BITalino está entregando mais devagar que o combinado.'
                )

            amostras.append(self._ler_uma_linha(timeout=timeout))
            timestamps.append(self._proximo_timestamp())

        return amostras, timestamps

    def _proximo_timestamp(self) -> float:
        """Timestamp derivado da contagem de amostras e da taxa acordada.

        O dispositivo não carimba hora nos frames — quem carimbava era o LSL. Derivar da
        contagem mantém o espaçamento exatamente regular, que é o que a análise espectral
        assume ao usar a taxa nominal.
        """
        timestamp = self._amostras_lidas / self._taxa_amostragem_hz
        self._amostras_lidas += 1
        return timestamp

    def encerrar_stream(self) -> None:
        """Manda o dispositivo parar e fecha a porta. Idempotente.

        Mandar parar importa: um BITalino deixado adquirindo continua transmitindo e gasta
        bateria, e a próxima conexão encontra o buffer cheio de amostras velhas.
        """
        if self._porta is None:
            return

        porta, self._porta = self._porta, None

        try:
            porta.write(bytes([protocolo_bitalino.COMANDO_PARAR]))
        except SerialException as erro:
            # Não propaga: fechar a porta é mais importante que parar com elegância, e este
            # caminho roda dentro do `__exit__`, inclusive quando algo já falhou antes.
            logger.warning(f'Não foi possível mandar o BITalino parar antes de fechar a porta: {erro}')

        porta.close()
        logger.info(f'Porta de acesso do BITalino encerrada após {self._amostras_lidas} amostras')
