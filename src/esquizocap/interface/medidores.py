"""Os medidores de Hue/Saturação/Brilho/Amostragem, para os dois modos de análise.

Existe um `PainelMedidores` por modo (Amplitude e Frequência) porque as faixas, o passo e
o significado do quarto medidor mudam entre os dois — mas os dois expõem a MESMA forma
(`controles_usuario`, `observar_mudancas`), que é o que permite a `JanelaPrincipal` tratar
"o painel do modo ativo" sem um `if` espalhado pelo resto da classe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import ttkbootstrap as ttk

from esquizocap.dominio.ciclo_aquisicao import ControlesUsuario
from esquizocap.interface import layout


@dataclass
class PainelMedidores:
    """Os quatro medidores semicirculares de um modo de análise, já no seu próprio frame."""

    frame: ttk.Frame
    hue_meter: ttk.Meter
    saturation_meter: ttk.Meter
    value_meter: ttk.Meter
    sampling_meter: ttk.Meter

    quarto_medidor_e_intervalo: bool
    """True no modo Amplitude (o quarto medidor é o intervalo entre predições, em ms) e
    False no modo Frequência (lá é o tamanho da janela de análise, em amostras — que não
    entra em `ControlesUsuario`: é fixado na construção do `CicloAquisicao`)."""

    def controles_usuario(self) -> ControlesUsuario:
        """Lê os três (ou quatro) medidores e monta o que a thread de aquisição consome.

        SÓ pode ser chamado da thread da GUI: `amountusedvar.get()` é uma chamada ao Tk.
        """
        if self.quarto_medidor_e_intervalo:
            return ControlesUsuario(
                saturacao=self.saturation_meter.amountusedvar.get(),
                brilho=self.value_meter.amountusedvar.get(),
                # O medidor está em milissegundos; o domínio raciocina em segundos.
                intervalo_predicao_segundos=self.sampling_meter.amountusedvar.get() / 1000,
            )
        return ControlesUsuario(
            saturacao=self.saturation_meter.amountusedvar.get(),
            brilho=self.value_meter.amountusedvar.get(),
        )

    def observar_mudancas(self, callback: Callable[..., None]) -> None:
        """Chama `callback` sempre que um medidor que a thread consome mudar.

        O medidor de Hue nunca entra: ele é OUTPUT (o que a predição pintou), não input do
        usuário. No modo Frequência o medidor de amostragem também fica de fora — ele
        define o tamanho da janela, travado durante toda a aquisição.
        """
        medidores = (self.saturation_meter, self.value_meter)
        if self.quarto_medidor_e_intervalo:
            medidores = (*medidores, self.sampling_meter)

        for medidor in medidores:
            medidor.amountusedvar.trace_add('write', callback)

    def travar_amostragem(self, travar: bool) -> None:
        """Trava o medidor de amostragem/janela. Só tem efeito visível no modo Frequência.

        No modo Amplitude o medidor correspondente é o intervalo de predição, que o
        usuário pode seguir ajustando ao vivo — por isso ele nunca é travado por aqui.
        """
        if self.quarto_medidor_e_intervalo:
            return
        self.sampling_meter.configure(interactive=not travar)


def criar_medidores_amplitude(master: ttk.Frame) -> PainelMedidores:
    """Monta o painel de medidores do modo Amplitude."""
    frame = ttk.Frame(master=master, name='amp_meters_frame')

    hue_meter = ttk.Meter(
        master=frame, interactive=False, amountused=0, amounttotal=layout.VALOR_MAXIMO_HSV,
        subtext='Hue', stepsize=1, wedgesize=3, **layout.OPCOES_MEDIDOR,
    )
    saturation_meter = ttk.Meter(
        master=frame, interactive=True, amountused=layout.VALOR_MAXIMO_HSV,
        amounttotal=layout.VALOR_MAXIMO_HSV, subtext='Saturação', stepsize=2, **layout.OPCOES_MEDIDOR,
    )
    value_meter = ttk.Meter(
        master=frame, interactive=True, amountused=120, amounttotal=layout.VALOR_MAXIMO_HSV,
        subtext='Brilho', stepsize=2, **layout.OPCOES_MEDIDOR,
    )
    sampling_meter = ttk.Meter(
        master=frame, interactive=True, amountused=900, amounttotal=1000, amountmin=100,
        subtext='Amostragem', textright='ms', textleft='1x', stepsize=10, stripethickness=2,
        arcrange=180, arcoffset=180, **layout.OPCOES_MEDIDOR,
    )

    for coluna, medidor in enumerate((hue_meter, saturation_meter, value_meter, sampling_meter)):
        medidor.grid(column=coluna, row=0, padx=5, pady=5)

    return PainelMedidores(
        frame=frame,
        hue_meter=hue_meter,
        saturation_meter=saturation_meter,
        value_meter=value_meter,
        sampling_meter=sampling_meter,
        quarto_medidor_e_intervalo=True,
    )


def criar_medidores_frequencia(master: ttk.Frame) -> PainelMedidores:
    """Monta o painel de medidores do modo Frequência."""
    frame = ttk.Frame(master=master, name='freq_meters_frame')

    hue_meter = ttk.Meter(
        master=frame, interactive=False, amountused=0, amounttotal=layout.VALOR_MAXIMO_HSV,
        subtext='Hue', stepsize=1, wedgesize=3, **layout.OPCOES_MEDIDOR,
    )
    saturation_meter = ttk.Meter(
        master=frame, interactive=True, amountused=layout.VALOR_MAXIMO_HSV,
        amounttotal=layout.VALOR_MAXIMO_HSV, subtext='Saturação', stepsize=2, **layout.OPCOES_MEDIDOR,
    )
    value_meter = ttk.Meter(
        master=frame, interactive=True, amountused=120, amounttotal=layout.VALOR_MAXIMO_HSV,
        subtext='Brilho', stepsize=2, **layout.OPCOES_MEDIDOR,
    )
    sampling_meter = ttk.Meter(
        master=frame, interactive=True, amountused=3000, amounttotal=5000, amountmin=1000,
        subtext='Tamanho da Amostra', textright='ms', stepsize=layout.PASSO_AMOSTRA_FREQUENCIA,
        stripethickness=2, arcrange=180, arcoffset=180, **layout.OPCOES_MEDIDOR,
    )

    for coluna, medidor in enumerate((hue_meter, saturation_meter, value_meter, sampling_meter)):
        medidor.grid(column=coluna, row=0, padx=5, pady=5)

    return PainelMedidores(
        frame=frame,
        hue_meter=hue_meter,
        saturation_meter=saturation_meter,
        value_meter=value_meter,
        sampling_meter=sampling_meter,
        quarto_medidor_e_intervalo=False,
    )
