"""Constantes das bordas de hardware.

Isto NÃO é configuração: são fatos sobre os dispositivos e sobre o protocolo. Os modos de
luminosidade, por exemplo, são os índices que o firmware do Arduino espera — mudá-los sem
mudar o firmware quebra a fita de LED em silêncio. Deixá-los num JSON editável dava a
falsa impressão de que eram ajustáveis.
"""

ENCODING_SERIAL = 'utf-8'
"""Encoding do comando enviado ao Arduino."""

BAUDRATE_PADRAO = 9600
"""O firmware atual espera 9600. As outras velocidades existem, mas não foram testadas."""

BAUDRATES_SUPORTADOS: tuple[int, ...] = (9600,)
"""Velocidades oferecidas na interface.

Só a 9600 está aqui de propósito: o firmware não negocia baudrate, então oferecer as
outras seria oferecer um jeito de quebrar a comunicação.
"""

MODOS_LUMINOSIDADE: tuple[str, ...] = (
    'Um a um',
    'Todos',
    'Gradiente',
    'A partir do Centro',
)
"""Modos de animação da fita de LED, na ORDEM que o firmware espera.

O índice (base 1) é o que vai no comando serial: 'Um a um' é 1, 'Todos' é 2, e assim por
diante. Reordenar esta tupla muda o comportamento do LED sem nenhum erro do lado Python.
"""

CANAIS_BITALINO: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
"""Canais analógicos do BITalino. É a capacidade do dispositivo, não uma escolha."""

TAXAS_AMOSTRAGEM_SUPORTADAS: tuple[int, ...] = (1, 10, 100, 1000)
"""Taxas de amostragem que o BITalino aceita, em Hz. Fato do dispositivo, não uma escolha.

O firmware não interpola: pedir qualquer outro valor é erro, não arredondamento.
"""

TAXA_AMOSTRAGEM_PADRAO_HZ: int = 1000
"""Taxa acordada usada quando ninguém escolhe uma.

É a única que serve aos dois modos de predição: as bandas de EEG vão até Gamma (45 Hz), e
Nyquist exige amostrar acima de ~90 Hz para enxergá-la.
"""


def indice_do_modo(modo: str) -> int:
    """Traduz o nome do modo de luminosidade para o índice que o firmware espera.

    Raises:
        ValueError: Se o modo não existir.
    """
    return MODOS_LUMINOSIDADE.index(modo) + 1
