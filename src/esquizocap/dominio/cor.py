"""Conversão de cor entre os espaços usados pelo sistema."""

import colorsys

VALOR_MAXIMO_CANAL: int = 255


def hsv_para_rgb_hex(hue: int, saturacao: int, brilho: int) -> tuple[str, tuple[int, int, int]]:
    """Converte uma cor HSV para hexadecimal e RGB.

    O sistema trabalha com HSV em escala 0–255 (e não com o 0–1 do `colorsys`, nem
    com o 0–360 do matiz), porque é isso que o modelo prevê e o que o firmware do
    Arduino espera.

    Args:
        hue: Matiz, de 0 a 255.
        saturacao: Saturação, de 0 a 255.
        brilho: Brilho, de 0 a 255.

    Returns:
        Uma tupla `(hex, rgb)`, com a cor em `#RRGGBB` e nos três canais de 0 a 255.
    """
    hue_normalizado: float = hue / VALOR_MAXIMO_CANAL
    saturacao_normalizada: float = saturacao / VALOR_MAXIMO_CANAL
    brilho_normalizado: float = brilho / VALOR_MAXIMO_CANAL

    # Desempacotado em três, e não montado por compreensão: só assim o tipo fica
    # `tuple[int, int, int]` de fato, e não `tuple[int, ...]` de tamanho desconhecido.
    vermelho, verde, azul = colorsys.hsv_to_rgb(
        hue_normalizado, saturacao_normalizada, brilho_normalizado
    )

    rgb: tuple[int, int, int] = (
        int(vermelho * VALOR_MAXIMO_CANAL),
        int(verde * VALOR_MAXIMO_CANAL),
        int(azul * VALOR_MAXIMO_CANAL),
    )

    return f'#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}', rgb
