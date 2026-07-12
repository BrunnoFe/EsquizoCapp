"""Formato das mensagens enviadas à engine visual do Godot.

Fica separado das implementações para que a real e a fake montem exatamente a mesma
mensagem — uma divergência de protocolo aparece nos dois modos, não só com o
binário do Godot na mão.
"""

import random

# Faixas dos parâmetros de shader. Eles NÃO derivam do sinal: são sorteados a cada
# envio só para dar variação visual. O comportamento vem do código original.
FAIXA_OCTAVES: tuple[int, int] = (100, 310)
FAIXA_ZOOM_FATOR: tuple[float, float] = (10.0, 18.5)
FAIXA_ZOOM_COEFICIENTE: tuple[float, float] = (1.2, 1.32)
FAIXA_BRILHO: tuple[int, int] = (1, 3)
FAIXA_POTENCIA: tuple[int, int] = (1, 3)
FAIXA_INTENSIDADE: tuple[float, float] = (0.0, 0.1)


def _decimal_com_virgula(valor: float, casas: int) -> str:
    """Formata um decimal com vírgula, e não ponto.

    O lado Godot espera o separador decimal no padrão brasileiro: mandar ponto faz
    o parser de lá falhar (ex.: '17,32' funciona, '17.32' não).
    """
    return str(round(valor, casas)).replace('.', ',')


def montar_mensagem_visual(rgb: tuple[int, int, int]) -> str:
    """Monta a mensagem de 9 campos que a engine espera, separados por hífen.

    O formato é `R-G-B-octaves-zoomfact-zoomcoef-brilho-power-intensity`,
    ex.: `110-0-120-196-17,32-1,266-1-2-0,038`.

    Args:
        rgb: Cor já convertida de HSV para RGB, cada canal de 0 a 255.

    Returns:
        A mensagem pronta para ir ao socket, ainda como texto (sem encoding).
    """
    campos: list[str] = [
        str(rgb[0]),
        str(rgb[1]),
        str(rgb[2]),
        str(random.randint(*FAIXA_OCTAVES)),
        _decimal_com_virgula(random.uniform(*FAIXA_ZOOM_FATOR), casas=3),
        _decimal_com_virgula(random.uniform(*FAIXA_ZOOM_COEFICIENTE), casas=3),
        str(random.randint(*FAIXA_BRILHO)),
        str(random.randint(*FAIXA_POTENCIA)),
        _decimal_com_virgula(random.uniform(*FAIXA_INTENSIDADE), casas=3),
    ]
    return '-'.join(campos)
