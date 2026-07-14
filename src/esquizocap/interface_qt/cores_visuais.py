"""Conversão de cor para a view: HSV na escala do firmware (0–255) para `QColor`/hex.

Fica separado de `dominio/cor.py` de propósito: aquele módulo converte HSV em RGB
para o protocolo serial do Arduino; este converte para `QColor`, para pintar a QML.
É a mesma origem conceitual (HSV na escala do firmware), com consumidores diferentes.
"""

from PySide6.QtGui import QColor


def limitar(valor: float, minimo: float, maximo: float) -> float:
    """Restringe `valor` ao intervalo fechado `[minimo, maximo]`."""
    return max(minimo, min(maximo, valor))


def hsv_para_qcolor(matiz: float, saturacao: float, brilho: float) -> QColor:
    """Converte HSV na escala do firmware/GUI (0–255) para um `QColor`.

    Qt espera o matiz em graus (0–359); saturação e brilho já usam 0–255, a mesma
    escala do firmware, então passam direto (só arredondados e limitados).
    """
    matiz_em_graus = int(round(limitar(matiz, 0, 255) / 255.0 * 359.0))
    return QColor.fromHsv(matiz_em_graus, int(limitar(saturacao, 0, 255)), int(limitar(brilho, 0, 255)))


def qcolor_para_hex(cor: QColor) -> str:
    """Formato `"#RRGGBB"` maiúsculo, para exibição na interface."""
    return cor.name().upper()
