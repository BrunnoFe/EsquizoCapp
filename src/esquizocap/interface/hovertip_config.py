from idlelib.tooltip import Label, OnHoverTooltipBase


class Hovertip(OnHoverTooltipBase):
    "A tooltip that pops up when a mouse hovers over an anchor widget."
    def __init__(self, anchor_widget, text, hover_delay=1000,
                 foreground="#000000", background="#ffffe0", **kwargs):
        """Create a text tooltip with a mouse hover delay.

        anchor_widget: the widget next to which the tooltip will be shown
        hover_delay: time to delay before showing the tooltip, in milliseconds

        Note that a widget will only be shown when showtip() is called,
        e.g. after hovering over the anchor widget with the mouse for enough
        time.
        """
        super().__init__(anchor_widget, hover_delay=hover_delay)
        self.text = text
        self.foreground: str = foreground
        self.background: str = background
        self.customize = kwargs

    def showcontents(self) -> None:
        label = Label(self.tipwindow, text=self.text, justify='left',
                       relief='flat',  borderwidth=0, pady=5, padx=5,
                       foreground=self.foreground, background=self.background)
        label.pack()
        
def set_tooltips(widgets:tuple, tips:dict, bg: str, fg: str, delay: int = 1000) -> None:
    for wid, tip in zip(widgets, tips.values()):
        Hovertip(anchor_widget=wid, text=tip, hover_delay=delay, background=bg, foreground=fg)

#if __name__ == '__main__':
#    import json
#    wids = ('combox_theme', 'combobx_model', 'gravar_check')
#    with open('settings\\tips.json', mode='r', encoding='utf-8') as file:
#        tips = json.load(file)
#    set_tooltips(tips['tips'], wids)
