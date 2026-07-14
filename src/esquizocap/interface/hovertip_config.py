"""Tooltips que aparecem ao pousar o mouse sobre um widget."""

import logging
from collections.abc import Mapping
from idlelib.tooltip import Label, OnHoverTooltipBase
from tkinter import Widget

logger = logging.getLogger(__name__)


class Hovertip(OnHoverTooltipBase):
    """Tooltip com atraso, exibida enquanto o mouse estiver sobre o widget âncora."""

    def __init__(
        self,
        anchor_widget: Widget,
        text: str,
        hover_delay: int = 1000,
        foreground: str = '#000000',
        background: str = '#ffffe0',
    ) -> None:
        super().__init__(anchor_widget, hover_delay=hover_delay)
        self.text = text
        self.foreground: str = foreground
        self.background: str = background

    def showcontents(self) -> None:
        label = Label(
            self.tipwindow,
            text=self.text,
            justify='left',
            relief='flat',
            borderwidth=0,
            pady=5,
            padx=5,
            foreground=self.foreground,
            background=self.background,
        )
        label.pack()


def aplicar_tooltips(
    widgets: Mapping[str, Widget],
    textos: Mapping[str, str],
    fundo: str,
    frente: str,
    atraso_ms: int = 1000,
) -> None:
    """Liga cada widget ao seu texto de tooltip, casando os dois PELO NOME.

    A versão anterior emparelhava as duas coleções com um `zip` sobre listas ordenadas
    alfabeticamente: bastava acrescentar um widget no meio do alfabeto para que todas as
    tooltips seguintes passassem a descrever o widget errado, sem erro nenhum. Aqui um
    nome sem par é registrado no log, não silenciosamente deslocado.

    Args:
        widgets: Nome do widget -> widget.
        textos: Nome do widget -> texto da tooltip.
    """
    for nome, texto in textos.items():
        widget = widgets.get(nome)

        if widget is None:
            logger.warning(f'Tooltip definida para "{nome}", mas esse widget não existe na janela.')
            continue

        Hovertip(
            anchor_widget=widget,
            text=texto,
            hover_delay=atraso_ms,
            background=fundo,
            foreground=frente,
        )

    sem_tooltip = sorted(set(widgets) - set(textos))
    if sem_tooltip:
        logger.info(f'Widgets sem tooltip: {sem_tooltip}')
