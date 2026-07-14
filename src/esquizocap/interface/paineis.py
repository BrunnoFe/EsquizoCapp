"""Construção dos painéis da janela principal: um frame por seção da tela.

Cada função `criar_painel_*` monta os widgets de UMA seção, já posicionados dentro do
próprio frame, e devolve um dataclass com o que a `JanelaPrincipal` precisa tocar depois
(variáveis e widgets específicos — nunca o layout interno do painel).

Nada aqui decide nada: são só construtores de widget. A lógica de habilitar/desabilitar,
travar durante a aquisição ou reagir a cliques vive em `JanelaPrincipal` e em
`arduino_gui`. É essa divisão que permite ler um painel sem precisar entender o fluxo de
estados da aplicação inteira.
"""

from __future__ import annotations

from dataclasses import dataclass

import ttkbootstrap as ttk
from ttkbootstrap.constants import NE

from esquizocap.dominio.ciclo_aquisicao import ModoAnalise
from esquizocap.hardware import constantes
from esquizocap.hardware.contratos import ControladorLedArduino
from esquizocap.interface import arduino_gui, textos


@dataclass
class PainelTitulo:
    frame: ttk.Frame
    imagem: ttk.PhotoImage
    """Referência mantida viva: sem isto o Tk coleta a imagem e o label fica em branco."""


def criar_painel_titulo(master: ttk.Frame, caminho_foto: str) -> PainelTitulo:
    frame = ttk.Frame(master=master, name='title_frame')
    imagem = ttk.PhotoImage(file=caminho_foto)
    ttk.Label(master=frame, padding=10, image=imagem).grid(sticky='n')
    return PainelTitulo(frame=frame, imagem=imagem)


@dataclass
class PainelModelo:
    frame: ttk.Frame
    combobox: ttk.Combobox
    gravar_button: ttk.Checkbutton
    modelo_var: ttk.StringVar
    gravar_var: ttk.BooleanVar


def criar_painel_modelo(master: ttk.Frame) -> PainelModelo:
    frame = ttk.Frame(master=master, name='model_frame')

    # A escolha é cosmética: hoje há um modelo só, e o caminho vem da configuração.
    # Ver interface/textos.py e PLANO_ACAO.md, item 1.10.
    modelo_var = ttk.StringVar(value='Selecione um modelo de machine learning ...')
    gravar_var = ttk.BooleanVar(value=False)

    label = ttk.Label(master=frame, text='Selecione um modelo:', justify='left', name='model_label')
    combobox = ttk.Combobox(
        master=frame, justify='center', width=100, textvariable=modelo_var,
        state='readonly', values=textos.MODELOS_DISPONIVEIS, name='model_box',
    )
    gravar_button = ttk.Checkbutton(
        master=frame, text='Gravar aquisição', bootstyle='round-toggle',
        variable=gravar_var, name='gravar_button', style='Roundtoggle',
    )

    for coluna, widget in enumerate((label, combobox, gravar_button)):
        widget.grid(column=coluna, row=0, padx=5, pady=5, sticky='n')

    return PainelModelo(
        frame=frame, combobox=combobox, gravar_button=gravar_button,
        modelo_var=modelo_var, gravar_var=gravar_var,
    )


@dataclass
class PainelArduino:
    frame: ttk.Frame
    button: ttk.Button
    ports_box: ttk.Combobox
    vel_box: ttk.Combobox
    lumin_box: ttk.Combobox
    porta_var: ttk.StringVar
    veloc_var: ttk.IntVar
    lumin_var: ttk.StringVar
    string_var: ttk.StringVar
    """Rótulo do botão: "Conectar" ou "Desconectar". O comando do botão é ligado por
    quem chama, DEPOIS da construção — precisa do painel inteiro para montar o
    `WidgetsArduino` que `arduino_gui.alternar_conexao` espera."""


def criar_painel_arduino(master: ttk.Frame, arduino: ControladorLedArduino) -> PainelArduino:
    frame = ttk.Frame(master=master, name='arduino_frame')

    porta_var = ttk.StringVar(value='Selecione a porta do Arduino')
    veloc_var = ttk.IntVar(value=constantes.BAUDRATE_PADRAO)
    lumin_var = ttk.StringVar(value='Selecione um modo de luminosidade')
    string_var = ttk.StringVar(value='Conectar')

    label = ttk.Label(master=frame, text='Arduino: ', name='arduino_label')
    ports_box = ttk.Combobox(
        master=frame, textvariable=porta_var, width=40, justify='center',
        state='readonly', name='ard_port_box',
    )
    ports_box.configure(
        postcommand=lambda: arduino_gui.listar_portas(controlador=arduino, caixa=ports_box)
    )
    vel_box = ttk.Combobox(
        master=frame, values=constantes.BAUDRATES_SUPORTADOS, textvariable=veloc_var,
        width=40, height=15, justify='center', state='readonly', name='ard_vel_box',
    )
    lumin_box = ttk.Combobox(
        master=frame, values=constantes.MODOS_LUMINOSIDADE, textvariable=lumin_var,
        width=40, justify='center', state='readonly', name='ard_lumi_box',
    )
    button = ttk.Button(master=frame, textvariable=string_var)

    for coluna, widget in enumerate((label, ports_box, vel_box, lumin_box, button)):
        widget.grid(column=coluna, row=0, padx=5, pady=5, sticky='n')

    return PainelArduino(
        frame=frame, button=button, ports_box=ports_box, vel_box=vel_box, lumin_box=lumin_box,
        porta_var=porta_var, veloc_var=veloc_var, lumin_var=lumin_var, string_var=string_var,
    )


@dataclass
class PainelStatusArduino:
    frame: ttk.Frame
    label: ttk.Label


def criar_painel_status_arduino(master: ttk.Frame, imagem_desconectado: ttk.PhotoImage) -> PainelStatusArduino:
    frame = ttk.Frame(master=master, name='general_status_frame')
    label = ttk.Label(
        master=frame, text='Arduino status:', image=imagem_desconectado, compound='right', justify='right',
    )
    label.grid(column=0, row=0, padx=2, pady=2)
    return PainelStatusArduino(frame=frame, label=label)


@dataclass
class PainelBitalino:
    frame: ttk.Frame
    canais_box: ttk.Combobox
    mac_box: ttk.Combobox
    canal_var: ttk.StringVar
    mac_var: ttk.StringVar


def criar_painel_bitalino(master: ttk.Frame, macs_conhecidos: tuple[str, ...]) -> PainelBitalino:
    frame = ttk.Frame(master=master, name='bitalino_frame')

    canal_var = ttk.StringVar(value='Selecione o canal ativo do Bitalino')
    mac_var = ttk.StringVar(value='Selecione o endereço MAC do Bitalino')

    label = ttk.Label(master=frame, text='Bitalino: ', name='bit_label')
    canais_box = ttk.Combobox(
        master=frame, textvariable=canal_var, values=constantes.CANAIS_BITALINO,
        width=40, justify='center', state='readonly', name='bit_canais_box',
    )
    mac_box = ttk.Combobox(
        master=frame, values=macs_conhecidos, textvariable=mac_var,
        width=40, justify='center', state='readonly', name='bit_mac_box',
    )

    for coluna, widget in enumerate((label, canais_box, mac_box)):
        widget.grid(column=coluna, row=0, padx=5, pady=5, sticky='n')

    return PainelBitalino(frame=frame, canais_box=canais_box, mac_box=mac_box, canal_var=canal_var, mac_var=mac_var)


@dataclass
class PainelAnalise:
    frame: ttk.Frame
    combobox: ttk.Combobox
    analise_var: ttk.StringVar


def criar_painel_analise(master: ttk.Frame) -> PainelAnalise:
    frame = ttk.Frame(master=master, name='analysis_frame')
    analise_var = ttk.StringVar(value=ModoAnalise.FREQUENCIA.value)

    label_frame = ttk.LabelFrame(master=frame, labelanchor='n', text='Escolha o modo de analise')
    label_frame.grid(column=0, row=0, padx=10, pady=10, sticky='n')

    combobox = ttk.Combobox(
        master=label_frame, justify='center', values=[modo.value for modo in ModoAnalise],
        textvariable=analise_var, state='readonly',
    )
    combobox.grid(column=0, row=0, padx=10, pady=10, sticky='n')

    return PainelAnalise(frame=frame, combobox=combobox, analise_var=analise_var)


@dataclass
class PainelStatusInicio:
    frame: ttk.Frame
    status_label: ttk.Label
    start_button: ttk.Button
    status_var: ttk.StringVar


def criar_painel_status_inicio(master_status: ttk.Frame, master_start: ttk.Frame) -> PainelStatusInicio:
    status_var = ttk.StringVar(value='Selecione todas as opções disponíveis acima')

    status_label = ttk.Label(master=master_status, textvariable=status_var, justify='center')
    status_label.grid(row=0, padx=5, pady=5, sticky='n')

    start_button = ttk.Button(master=master_start, text='Começar aquisição', width=30)
    start_button.grid(row=0, padx=5, pady=5, sticky='n')

    return PainelStatusInicio(
        frame=master_status, status_label=status_label, start_button=start_button, status_var=status_var,
    )


@dataclass
class PainelCor:
    frame: ttk.Frame
    label: ttk.Label
    cor_var: ttk.StringVar


def criar_painel_cor(master: ttk.Frame, texto_inicial: str) -> PainelCor:
    frame = ttk.Frame(master=master, name='tail_frame')
    cor_var = ttk.StringVar(value=texto_inicial)
    label = ttk.Label(master=frame, textvariable=cor_var, foreground='white', justify='center')
    label.grid(column=3, row=0, sticky='n', padx=10, pady=10)
    return PainelCor(frame=frame, label=label, cor_var=cor_var)


def criar_seletor_tema(master: ttk.Frame, tema_atual: str) -> tuple[ttk.Combobox, ttk.StringVar]:
    """A combobox de tema, no canto da barra de título."""
    tema_var = ttk.StringVar(value=tema_atual)
    combobox = ttk.Combobox(
        master=master, justify='center', values=textos.TEMAS, textvariable=tema_var,
        state='readonly', height=20, name='theme_box',
    )
    combobox.grid(column=2, row=0, sticky=NE, padx=15)
    return combobox, tema_var
