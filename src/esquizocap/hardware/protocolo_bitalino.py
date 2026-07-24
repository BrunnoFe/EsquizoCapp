"""Protocolo serial do BITalino (r)evolution: comandos, frames e conversão de unidade.

TUDO aqui é função pura sobre bytes e inteiros — nada abre porta, nada bloqueia, nada
depende de dispositivo plugado. É de propósito: este módulo concentra os dois erros mais
prováveis (e mais silenciosos) do Modo Direto, e precisa ser testável sem hardware.

Os dois erros são:

1. **Canal deslocado.** O firmware empacota os canais analógicos em bits, do fim do frame
   para o começo, e A1..A4 usam 10 bits enquanto A5..A6 usam 6. Errar o desempacotamento
   não levanta exceção nenhuma: entrega números plausíveis do canal errado.
2. **Unidade errada.** O dispositivo entrega ADU (inteiro do conversor A/D), não microvolts.
   O ADU é sempre positivo e centrado em meia escala; o EEG tem média zero e vive em ±39 µV.
   Entregar ADU ao domínio dá um sinal com offset gigante e amplitude ~12x maior — de novo,
   sem erro nenhum, só cor errada na fita.

Por que não a lib oficial `bitalino`: ela declara `PyBluez-bitalino` como dependência de
instalação, e o PyBluez não compila em Python moderno — `pip install -r requirements.txt`
quebraria para quem clonasse o repositório. O PyBluez só é usado na descoberta de
dispositivos, que não usamos (conectamos por porta de acesso), mas isso não ajuda: a
dependência é resolvida na instalação, não no uso. Além disso a lib levanta `Exception`
pelado, com a MESMA mensagem para timeout, queda de link e falha de CRC — envolvê-la exigiria
o `except Exception` amplo que as convenções do projeto proíbem.

Referência do empacotamento e dos comandos: documentação do BITalino (r)evolution e a API
oficial (BITalinoWorld/revolution-python-api), ambas GPL v3, como este projeto.
"""

from dataclasses import dataclass

from esquizocap.hardware.constantes import (
    CANAIS_BITALINO,
    RESOLUCAO_CANAIS_AUXILIARES,
    RESOLUCAO_CANAIS_PRINCIPAIS,
    ULTIMO_CANAL_PRINCIPAL,
    resolucao_bits,
    validar_canal,
)

__all__ = [
    'ADU_MAXIMO_CANAIS_AUXILIARES',
    'ADU_MAXIMO_CANAIS_PRINCIPAIS',
    'BAUDRATE',
    'CODIGOS_DE_TAXA',
    'COMANDO_PARAR',
    'DESLOCAMENTOS_DIGITAIS',
    'LeituraBruta',
    'comando_definir_taxa',
    'comando_iniciar',
    'converter_para_microvolts',
    'crc_confere',
    'decodificar_frame',
    'montar_linha',
    'resolucao_bits',
    'tamanho_frame_bytes',
    'validar_canal',
]
"""`resolucao_bits` e `validar_canal` são reexportados de `constantes`: são fatos do
DISPOSITIVO, não do protocolo, mas quem decodifica um frame precisa deles à mão."""

BAUDRATE: int = 115200
"""Velocidade da porta de acesso. Fixa no firmware, não negociável."""

CODIGOS_DE_TAXA: dict[int, int] = {1: 0b00, 10: 0b01, 100: 0b10, 1000: 0b11}
"""Taxa de amostragem em Hz -> código de 2 bits que o firmware espera."""

COMANDO_PARAR: int = 0
"""Devolve o dispositivo ao repouso, encerrando a aquisição."""

ADU_MAXIMO_CANAIS_PRINCIPAIS: int = 2**RESOLUCAO_CANAIS_PRINCIPAIS - 1
ADU_MAXIMO_CANAIS_AUXILIARES: int = 2**RESOLUCAO_CANAIS_AUXILIARES - 1

TENSAO_ALIMENTACAO_V: float = 3.3
GANHO_SENSOR_EEG: float = 41782.0
"""Ganho do sensor de EEG do BITalino (r)evolution, do datasheet. Resulta em ±39,49 µV."""

MICROVOLTS_POR_VOLT: float = 1e6

DESLOCAMENTOS_DIGITAIS: tuple[int, ...] = (7, 6, 5, 4)
"""Onde cada canal digital mora no penúltimo byte do frame.

O frame sempre carrega os quatro digitais, mesmo sem ninguém os usar — eles ocupam o nibble
alto e empurram os analógicos, então não dá para simplesmente ignorá-los na conta.
"""


@dataclass(frozen=True)
class LeituraBruta:
    """Um frame já desempacotado, ainda em ADU.

    A conversão para unidade física NÃO acontece aqui de propósito: ela depende de qual
    sensor está plugado em qual canal, e isso é decisão de quem consome, não do protocolo.
    """

    sequencia: int
    """Contador do firmware, de 0 a 15. Serve para detectar amostra perdida."""

    digitais: list[int]
    """Os quatro canais digitais, cada um 0 ou 1."""

    analogicos: list[int]
    """Um valor em ADU por canal analógico pedido, na ordem dos canais."""


def comando_definir_taxa(taxa_hz: int) -> int:
    """Monta o comando que fixa a taxa de amostragem.

    O código da taxa ocupa os dois bits mais altos; os bits `11` no fim identificam o
    comando.

    Raises:
        ValueError: Se a taxa não for uma das quatro suportadas. O firmware não interpola —
            pedir 500 Hz é erro, não arredondamento.
    """
    if taxa_hz not in CODIGOS_DE_TAXA:
        raise ValueError(
            f'Taxa de amostragem não suportada pelo BITalino: {taxa_hz} Hz. As aceitas são {sorted(CODIGOS_DE_TAXA)}.'
        )

    return (CODIGOS_DE_TAXA[taxa_hz] << 6) | 0b11


def comando_iniciar(canais: list[int]) -> int:
    """Monta o comando que inicia a aquisição nos canais informados.

    Cada canal liga um bit: o canal N (1 a 6) ocupa o bit (N + 1). O bit 0, sempre ligado,
    identifica o comando.

    Args:
        canais: Canais analógicos, de 1 a 6. Ordem e repetições são irrelevantes.

    Raises:
        ValueError: Se a lista estiver vazia ou contiver canal fora de 1 a 6.
    """
    canais_unicos = sorted(set(canais))

    if not canais_unicos:
        raise ValueError('Nenhum canal informado: a aquisição precisa de ao menos um canal.')

    fora_da_faixa = [canal for canal in canais_unicos if canal not in CANAIS_BITALINO]
    if fora_da_faixa:
        raise ValueError(
            f'Canal inexistente no BITalino: {fora_da_faixa}. Os canais válidos são {list(CANAIS_BITALINO)}.'
        )

    comando = 0b1
    for canal in canais_unicos:
        comando |= 1 << (canal + 1)

    return comando


def tamanho_frame_bytes(quantidade_canais: int) -> int:
    """Quantos bytes o firmware envia por amostra, para essa quantidade de canais.

    NÃO é linear: os quatro primeiros canais custam 10 bits cada e os dois últimos custam 6.
    Somam-se ainda 4 bits de sequência, 4 de digitais e 4 de CRC. Errar esta conta
    dessincroniza a leitura de forma permanente — todo frame seguinte sai deslocado.
    """
    if quantidade_canais <= ULTIMO_CANAL_PRINCIPAL:
        bits = 12 + RESOLUCAO_CANAIS_PRINCIPAIS * quantidade_canais
    else:
        bits = 52 + RESOLUCAO_CANAIS_AUXILIARES * (quantidade_canais - ULTIMO_CANAL_PRINCIPAL)

    return -(-bits // 8)  # divisão inteira arredondando para cima


def _crc4(frame: bytes) -> int:
    """Calcula o CRC-4 do frame, com o nibble do CRC zerado antes da conta.

    O firmware transmite o CRC no nibble baixo do último byte, e o calcula sobre o frame com
    esse nibble em zero — por isso ele é mascarado aqui antes do laço.
    """
    bytes_sem_crc = bytearray(frame)
    bytes_sem_crc[-1] &= 0xF0

    resto = 0
    for byte in bytes_sem_crc:
        for deslocamento in range(7, -1, -1):
            resto <<= 1
            if resto & 0x10:
                resto ^= 0b11
            resto ^= (byte >> deslocamento) & 0b1

    return resto & 0x0F


def crc_confere(frame: bytes) -> bool:
    """Indica se o frame chegou íntegro.

    Bluetooth entrega pacote corrompido de vez em quando. Sem esta checagem, o byte trocado
    vira uma amostra plausível e o erro segue adiante sem deixar rastro.
    """
    crc_recebido = frame[-1] & 0x0F
    return crc_recebido == _crc4(frame)


def decodificar_frame(frame: bytes, quantidade_canais: int) -> LeituraBruta:
    """Desempacota um frame em sequência, digitais e canais analógicos, tudo em ADU.

    O firmware empacota do FIM do frame para o começo, e as fronteiras dos canais não caem
    em múltiplos de 8 bits — daí a aritmética de máscaras e deslocamentos abaixo, canal a
    canal. Está escrita de forma explícita, e não num laço genérico, porque cada canal tem
    um recorte diferente e um laço esconderia justamente onde um erro entraria.

    NÃO valida o CRC: use `crc_confere` antes. São separados para que quem chama decida o
    que fazer com um frame corrompido.

    Raises:
        ValueError: Se o frame não tiver o tamanho esperado para essa quantidade de canais.
            Um frame curto significa leitura dessincronizada, e decodificá-lo produziria
            amostras plausíveis e erradas.
    """
    tamanho_esperado = tamanho_frame_bytes(quantidade_canais=quantidade_canais)
    if len(frame) != tamanho_esperado:
        raise ValueError(
            f'Tamanho de frame inesperado: {len(frame)} byte(s) para {quantidade_canais} canal(is), '
            f'quando o esperado eram {tamanho_esperado}. A leitura provavelmente dessincronizou.'
        )

    sequencia = frame[-1] >> 4
    digitais = [(frame[-2] >> deslocamento) & 0b1 for deslocamento in DESLOCAMENTOS_DIGITAIS]

    analogicos: list[int] = []
    if quantidade_canais > 0:
        analogicos.append(((frame[-2] & 0x0F) << 6) | (frame[-3] >> 2))
    if quantidade_canais > 1:
        analogicos.append(((frame[-3] & 0x03) << 8) | frame[-4])
    if quantidade_canais > 2:
        analogicos.append((frame[-5] << 2) | (frame[-6] >> 6))
    if quantidade_canais > 3:
        analogicos.append(((frame[-6] & 0x3F) << 4) | (frame[-7] >> 4))
    if quantidade_canais > 4:
        analogicos.append(((frame[-7] & 0x0F) << 2) | (frame[-8] >> 6))
    if quantidade_canais > 5:
        analogicos.append(frame[-8] & 0x3F)

    return LeituraBruta(sequencia=sequencia, digitais=digitais, analogicos=analogicos)


def montar_linha(leitura: LeituraBruta, canais: list[int], canal_ativo: int) -> list[float]:
    """Monta a linha no layout que o resto do sistema espera: `[sequência, A1..An]`.

    Este é o ponto onde o Modo Direto se disfarça de Modo OpenSignals, e o mais fácil de
    errar de forma invisível. Duas regras, e as duas doem se quebradas:

    1. **O número de sequência FICA, no índice 0**, e os quatro canais digitais saem fora.
       Não é enfeite: quem consome indexa pelo NÚMERO do canal (`amostra[canal]`, de 1 a 6),
       exatamente como faz com o stream do OpenSignals, que publica `[nSeq, A1..A6]`.
       Recortar o cabeçalho inteiro poria A1 no índice 0 e faria o canal 1 ler A2.

    2. **Só o canal ativo vira microvolts.** Os demais saem em ADU, porque converter um
       canal sem saber qual sensor está nele produz um número que não significa nada. É o
       mesmo comportamento do OpenSignals, que só converte canal com sensor declarado.

    Args:
        leitura: Frame já desempacotado, em ADU.
        canais: Canais adquiridos, na mesma ordem de `leitura.analogicos`.
        canal_ativo: O canal que o sistema está consumindo, e o único convertido.

    Raises:
        ValueError: Se a quantidade de canais não bater com a de valores lidos — sinal de
            que a leitura dessincronizou ou de que os canais mudaram sem reiniciar.
    """
    if len(canais) != len(leitura.analogicos):
        raise ValueError(
            f'Canais e valores lidos não batem: {len(canais)} canal(is) declarado(s) para '
            f'{len(leitura.analogicos)} valor(es) no frame.'
        )

    linha: list[float] = [float(leitura.sequencia)]

    for canal, adu in zip(canais, leitura.analogicos, strict=True):
        if canal == canal_ativo:
            linha.append(converter_para_microvolts(adu=adu, canal=canal))
        else:
            linha.append(float(adu))

    return linha


def converter_para_microvolts(adu: int, canal: int) -> float:
    """Converte um valor em ADU para microvolts, assumindo o sensor de EEG.

    Função de transferência do datasheet:
        `EEG(µV) = ((ADU / 2^n) - 0.5) * VCC / ganho * 1e6`

    O `- 0.5` é o que move o sinal de "sempre positivo, centrado em meia escala" para "média
    zero", que é como o EEG realmente se comporta e como o resto do sistema o espera.

    O expoente `n` vem da resolução do CANAL, não é fixo: usar 10 bits em A5/A6 (que são de
    6) comprimiria o sinal a um dezesseis avos da faixa — sem erro, só errado.

    ATENÇÃO: assume EEG. Aplicar isto a um canal com outro sensor (EDA, ECG, ...) devolve um
    número em microvolts que não significa nada, porque cada sensor tem ganho próprio, e o
    EDA nem sequer mede tensão. Ver `docs/notas-futuras.md`.

    Raises:
        ValueError: Se o canal estiver fora de 1 a 6.
    """
    niveis: int = 1 << resolucao_bits(canal=canal)
    tensao_volts: float = (adu / niveis - 0.5) * TENSAO_ALIMENTACAO_V / GANHO_SENSOR_EEG

    return tensao_volts * MICROVOLTS_POR_VOLT
