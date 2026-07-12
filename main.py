import inspect
import logging
from pathlib import Path

from ttkbootstrap.constants import NE, SE, N
from ttkbootstrap.dialogs import Messagebox, Querybox

from esquizocap import hardware
from esquizocap.aplicacao import EventoErro, EventoParado, EventoResultado, ServicoAquisicao
from esquizocap.dominio.ciclo_aquisicao import (
    CicloAquisicao,
    ControlesUsuario,
    ModoAnalise,
    ResultadoCiclo,
)
from esquizocap.dominio.predicao import carregar_modelo
from esquizocap.hardware import constantes
from esquizocap.infraestrutura import config, log, persistencia, recursos
from esquizocap.interface import arduino_gui, hovertip_config, loading_screen, textos
from esquizocap.interface.custom_gui import CreateCustomGui, ttk
from esquizocap.interface.estado import (
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    mensagem_de_aquisicao,
)

ZERO = 0
CHUNK_SIZE = 500
METER_MAX = 255
METER_THICKNESS = 12
METERS_SIZE = 200
METERS_TEXT_FONT = '-size 20 -weight bold'
METERS_SUBTEXT_FONT = '-size 12 -weight bold'

# De quanto em quanto tempo a GUI drena a fila da thread de aquisição. É só o ritmo do
# DESENHO — a aquisição roda no ritmo do BITalino, independentemente disto. 33 ms dá
# ~30 quadros por segundo, que é mais do que suficiente para acompanhar uma cor mudando.
INTERVALO_DRENAGEM_MS = 33

# Índices do grid da janela principal. Isto é layout de interface, e vivia no
# `configs.json` como se fosse configuração do usuário.
COLUNAS_GRID = (0, 1, 2, 3, 4)
LINHAS_GRID = (0, 1, 2, 3, 4, 5, 6, 7, 8)

logger = logging.getLogger(__name__)

class EsquizoCap:
    def __init__(self, configuracao: config.Configuracao, width: int = 1680, heigth: int = 1000) -> None:
        self.config = configuracao
        themename = configuracao.tema
        self.gravacao_basepath: Path = configuracao.pasta_gravacoes

        self.custom_gui: CreateCustomGui = CreateCustomGui(iconpath=str(recursos.ICONE), themename=themename, width=width, heigth=heigth)
        self.root: ttk.Window = self.custom_gui.root
        self.main_window: ttk.Frame = self.custom_gui.main_window
       
        self.__load_images()
        self.__set_property(themename=themename)
        self.__set_frames()
        self.__set_grids(itens_to_grid=(self.title_frame, self.model_frame, self.arduino_frame, self.bitalino_frame, self.analysis_frame, self.status_frame, 
                                       self.start_frame, self.notebook, self.tail_frame), columnspan=len(COLUNAS_GRID), frame_grid=True)
        self.__set_vars()
        self.__setTitlePhoto()
        self.__setwidgets(widgets=(self.__setmodel_widgets, self.__setarduino_widgets, self.__setbitalino_widgets, self.__setanalysis_widgets,
                                   self.__setStatusStart_widgets, self.__setmetersamp_widgets,self.__setmetersfreq_widgets, self.__setcolor_widgets))
        
        self.theme_box = ttk.Combobox(master=self.custom_gui.title_bar, justify='center', values=textos.TEMAS, textvariable=self.theme_var, state='readonly', height=20, name='theme_box')
        self.theme_box.grid(column=2, row=0, sticky=NE, padx=15)
        self.theme_box.bind('<<ComboboxSelected>>', lambda _: self.set_theme(self.theme_var.get()))
        
        self.__set_grids(itens_to_grid=((self.model_label, self.model_box, self.gravar_button),
                                        (self.arduino_label, self.arduino_ports_box, self.arduino_vel_box, self.arduino_lumin_box, self.arduino_button),
                                        (self.bitalino_label, self.bitalino_canais_box, self.bitalino_mac_box),
                                        (self.amp_hue_meter, self.amp_saturation_meter, self.amp_value_meter, self.amp_sampling_meter),
                                        (self.freq_hue_meter, self.freq_saturation_meter, self.freq_value_meter, self.freq_sampling_meter)))

        self.__set_grids(itens_to_grid=(self.status_update_label, self.start_button), 
                         columnspan=len(COLUNAS_GRID))

        self.notebook.add(child=self.amp_meters_frame, text='Amplitude', sticky=N, state='normal')
        self.notebook.add(child=self.freq_meters_frame, text='Frequência', sticky=N, state='normal')

        self.mutable_wids = (self.model_box, self.gravar_button, self.arduino_button, self.arduino_ports_box,
                             self.arduino_vel_box, self.arduino_lumin_box, self.bitalino_canais_box, self.bitalino_mac_box)
        
        # A integração com a engine visual foi desligada; ver src/esquizocap/hardware/_engine_legado/.
        
        self.__setgerenal_status_widgets()
        self.__sethovertips(classes=(ttk.Button, ttk.Combobox, ttk.Checkbutton, ttk.Meter))
        
        self.set_theme(theme_selected=themename)

        ttk.Sizegrip(master=self.main_window).grid(column=COLUNAS_GRID[-1], row=LINHAS_GRID[-1], sticky=SE)
        
        self.root.after(100, self.custom_gui.set_appwindow) # to see the icon on the task bar
        self.root.bind("<FocusIn>", self.custom_gui.deminimize) # to view the window by clicking on the window icon on the taskbar

        # Os DOIS caminhos de saída precisam desligar o hardware. O "×" é um botão nosso
        # (a janela não tem barra de título nativa), então o protocolo WM_DELETE_WINDOW
        # sozinho não o cobriria — ele só pega o Alt+F4.
        self.custom_gui.close_button.configure(command=self.ao_fechar)
        self.root.protocol('WM_DELETE_WINDOW', self.ao_fechar)

        # Estado inicial: ninguém escolheu nada ainda. Isto trava o botão "Começar" e
        # escreve a primeira mensagem de status — o que o `do_check` fazia no 1º tique.
        self.__ao_mudar_selecao()
    
    def __load_images(self) -> None:
        self.title_photo: ttk.PhotoImage = ttk.PhotoImage(file=str(recursos.FOTO_TITULO))
        self.red_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=str(recursos.CIRCULO_VERMELHO)).subsample(5,5)
        self.green_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=str(recursos.CIRCULO_VERDE)).subsample(5,5)
    
    def __sethovertips(self, classes: tuple, delay: int = 1000) -> None:
        properties: list[str] = [m for (m, v) in inspect.getmembers(self) if isinstance(v, classes)]
        properties.sort(key=str.lower)
        tip_widgets: list = []
        for widget in properties:
            tip_widgets.append(getattr(self, widget))
        tips_dict: dict = dict(sorted(textos.TOOLTIPS.items()))
        hovertip_config.set_tooltips(widgets=tip_widgets, tips=tips_dict, bg='#bc951a', fg='white', delay=delay)
        
    def __set_property(self, themename: str) -> None:
        logger.info('Configurando propriedades ...')
        self.arduino: hardware.ControladorLedArduino = hardware.criar_arduino()
        self.bitalino: hardware.LeitorBitalino = hardware.criar_bitalino()
        self.selected_lumi_mode: int = ZERO
        self.bitalino_srate: int = 100
        self.freq_resulta_faixa: str | None = None
        self.style: ttk.Style = ttk.Style(theme=themename)

        # O estado é EXPLÍCITO agora. Antes era inferido comparando strings de StringVar,
        # num `after(10 ms)` que rodava para sempre só para escolher a frase do status.
        self.estado: EstadoApp = EstadoApp.CONFIGURANDO

        # A aquisição não roda mais nesta thread. O serviço só existe entre o "Começar" e
        # o "Parar"; fora disso é None, e isso é o que significa "não estamos adquirindo".
        self.servico: ServicoAquisicao | None = None
        self._agendamento_drenagem: str | None = None

    def set_model_path(self) -> None:
        self.model_pathstring_var.set(textos.MODELOS_DISPONIVEIS[0]) ## retirar dps ... provavelmente pq posso colocar essa string diretamente no widget
        self.model_path: str = self.config.caminho_modelo
        logger.info(f'Modelo de machine learning escolhido = {self.model_path}')

    def set_theme(self, theme_selected) -> None:
        self.style.theme_use(themename=theme_selected)
        self.style.configure('TCombobox', arrowsize = 20) #"Helvetica", size = 15
        self.style.configure('TSizegrip', size=50)
        self.style.configure('.', font=self.custom_gui.font)
        logger.info(f'Tema alterado. Novo = {theme_selected}')

    def __set_grids(self, itens_to_grid: tuple[tuple], row: int = ZERO, columnspan: int | None = None, padx: int = 5, pady: int = 5, sticky: str = N, frame_grid: bool = False):
        if columnspan is None:
            logger.info('Configurando os grids dos widgets ...')
            for iterable in itens_to_grid:
                for column, item in enumerate(iterable=iterable, start=ZERO):
                    logger.info(f'Widget: configurando item {item} na coluna {column} e linha {row}, fixado em "{sticky}"')
                    item.grid(column=column, row=row, padx=padx, pady=pady, sticky=sticky)
        else:
            if frame_grid is False:
                logger.info('Configurando grids com columnspan ...')
                for column, item in enumerate(iterable=itens_to_grid, start=ZERO):
                    logger.info(f'Widget: configurando item {item} com columnspan = {columnspan} na linha "{row}", fixado em "{sticky}"')
                    item.grid(columnspan=columnspan, row=row, padx=padx, pady=pady, sticky=sticky) # type: ignore
            else:
                logger.info('Configurando Frame grids ...')
                for row_index, frame in enumerate(iterable=itens_to_grid, start=ZERO):
                    logger.info(f'Frame: configurando frame {frame} com columnspan = {columnspan} na linha {row_index}, fixado em "{sticky}"')
                    frame.grid(columnspan=columnspan, row=row_index, sticky=sticky, padx=pady, pady=padx)

    def change_state(self, mutables: tuple, to: str = 'disabled') -> None:
        for mutable in mutables:
            if isinstance(mutable, ttk.Button):
                logger.info(f'Alterando o estado do Botão "{mutable}" para {to}')
                mutable['state'] = to
            elif isinstance(mutable, ttk.Combobox):
                if to == 'disabled':
                    logger.info(f'Alterando o estado do Combobox "{mutable}" para {to}')
                    mutable['state'] = to
                else:
                    logger.info(f'Alterando o estado do Combobox "{mutable}" para "readonly"')
                    mutable['state'] = 'readonly'

    def get_lumi_mode(self) -> int:
        indice = constantes.indice_do_modo(self.arduino_lumin_var.get())
        logger.info(f'Modo de iluminação escolhido = {indice}')
        return indice

    def __setTitlePhoto(self) -> None:
        self.title_label = ttk.Label(master=self.title_frame, padding=10, image=self.title_photo)
        self.title_label.grid(columnspan=len(COLUNAS_GRID), sticky=N)
        logger.info(f'Configurando a foto da janela principal. Foto escolhida = {self.title_photo}')

    def __setwidgets(self, widgets) -> None:
        logger.info('Configurando todos os widgets ...')
        for func in widgets:
            func()

    def __set_vars(self) -> None:
        logger.info('Criando todas as variáveis ...')
        self.gravar_var = ttk.BooleanVar(value=False)
        self.model_pathstring_var = ttk.StringVar(value='Selecione um modelo de machine learning ...')
        self.arduino_lumin_var = ttk.StringVar(value='Selecione um modo de luminosidade')
        self.arduino_porta_var = ttk.StringVar(value='Selecione a porta do Arduino')
        self.arduino_string_var = ttk.StringVar(value='Conectar')
        self.arduino_veloc_var = ttk.IntVar(value=9600)
        self.bitalino_macaddr_var = ttk.StringVar(value='Selecione o endereço MAC do Bitalino')
        self.bitalino_canal_var = ttk.StringVar(value='Selecione o canal ativo do Bitalino')
        self.analysis_var = ttk.StringVar(value='Frequência')
        self.status_update_var = ttk.StringVar(value='Selecione todas as opções disponíveis acima')
        self.theme_var = ttk.StringVar(value=self.root.style.theme_use())
        self.color_label_var = ttk.StringVar(value='Aguardando início da aquisição')

        # Reagir a mudanças, em vez de varrê-las 100 vezes por segundo. O `trace_add`
        # dispara exatamente quando o usuário mexe em alguma coisa — que é o único
        # momento em que a prontidão pode ter mudado.
        for variavel in (
            self.model_pathstring_var,
            self.arduino_lumin_var,
            self.arduino_porta_var,
            self.arduino_string_var,
            self.bitalino_macaddr_var,
            self.bitalino_canal_var,
            self.gravar_var,
        ):
            variavel.trace_add('write', self.__ao_mudar_selecao)

    def __ao_mudar_selecao(self, *_args: object) -> None:
        """Uma escolha do usuário mudou: reavalia o estado e atualiza o status.

        Recebe `*_args` porque o Tk passa (nome, índice, operação) para o callback de
        trace, e nada disso interessa aqui — a regra olha o retrato inteiro da seleção.
        """
        if self.estado in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO):
            # Durante a aquisição os widgets estão travados; o status pertence à thread.
            return

        selecao = SelecaoUsuario(
            modelo=self.model_pathstring_var.get(),
            porta_arduino=self.arduino_porta_var.get(),
            modo_luminosidade=self.arduino_lumin_var.get(),
            arduino_conectado=self.arduino.esta_conectado,
            canal_bitalino=self.bitalino_canal_var.get(),
            mac_bitalino=self.bitalino_macaddr_var.get(),
        )

        self.estado, mensagem = avaliar_prontidao(
            selecao=selecao, macs_validos=self.config.macs_bitalino
        )
        self.status_update_var.set(value=mensagem)
        self.start_button['state'] = 'normal' if self.estado is EstadoApp.PRONTO else 'disabled'

    def __controles_atuais(self) -> ControlesUsuario:
        """Lê os medidores e monta o objeto que a thread de aquisição vai consumir.

        SÓ pode ser chamado da thread da GUI: `amountusedvar.get()` é uma chamada ao Tk.
        A thread de aquisição nunca faz isso — ela recebe o resultado já pronto.
        """
        if self.analysis_var.get() == 'Amplitude':
            return ControlesUsuario(
                saturacao=self.amp_saturation_meter.amountusedvar.get(),
                brilho=self.amp_value_meter.amountusedvar.get(),
                # O medidor está em milissegundos; o domínio raciocina em segundos.
                intervalo_predicao_segundos=self.amp_sampling_meter.amountusedvar.get() / 1000,
            )

        # No modo Frequência a cadência já vem do tamanho da janela: não há intervalo.
        return ControlesUsuario(
            saturacao=self.freq_saturation_meter.amountusedvar.get(),
            brilho=self.freq_value_meter.amountusedvar.get(),
        )

    def __ao_mudar_medidor(self, *_args: object) -> None:
        """O usuário mexeu num medidor: repassa os novos controles à thread de aquisição.

        É este empurrão que substitui a thread ir "buscar" o valor no widget — o que
        seria tocar em Tkinter de fora da thread da interface, e é comportamento
        indefinido.
        """
        if self.servico is not None:
            self.servico.atualizar_controles(self.__controles_atuais())

    def __set_frames(self) -> None:
        logger.info('Setting FRAMES ...')
        self.title_frame = ttk.Frame(master=self.main_window, name='title_frame')   #row 0
        self.model_frame = ttk.Frame(master=self.main_window, name='model_frame')   #row 1
        self.arduino_frame = ttk.Frame(master=self.main_window, name='arduino_frame') #row 2
        self.bitalino_frame = ttk.Frame(master=self.main_window, name='bitalino_frame')#row 3
        self.analysis_frame = ttk.Frame(master=self.main_window, name='analysis_frame')#row 4
        self.status_frame = ttk.Frame(master=self.main_window, name='status_frame')  #row 5
        self.start_frame = ttk.Frame(master=self.main_window, name='start_frame')   #row 6
        self.notebook = ttk.Notebook(master=self.main_window, name='notebook_frame')   #row 7
        self.amp_meters_frame = ttk.Frame(master=self.notebook, name='amp_meters_frame') #row 7
        self.freq_meters_frame = ttk.Frame(master=self.notebook, name='freq_meters_frame')#row 7  
        self.tail_frame = ttk.Frame(master=self.main_window, name='tail_frame')    #row 8
        self.general_status_frame = ttk.Frame(master=self.main_window, name='general_status_frame') # row 8
    
    def __setmodel_widgets(self)-> None:
        logger.info('Setting MODEL widgets')
        self.model_label = ttk.Label(master=self.model_frame, text='Selecione um modelo:', justify='left', name='model_label')     
        self.model_box = ttk.Combobox(master=self.model_frame, justify='center', width=100, textvariable=self.model_pathstring_var, state='readonly', values=textos.MODELOS_DISPONIVEIS, name='model_box')
        self.model_box.bind('<<ComboboxSelected>>', lambda _: self.set_model_path()) 
        self.gravar_button = ttk.Checkbutton(master=self.model_frame, text='Gravar aquisição', bootstyle='round-toggle', variable=self.gravar_var, name='gravar_button', style='Roundtoggle')

    def __setarduino_widgets(self)-> None:
        logger.info('Setting ARDUINO widgets')
        self.arduino_label = ttk.Label(master=self.arduino_frame, text='Arduino: ', name='arduino_label')
        self.arduino_ports_box = ttk.Combobox(master=self.arduino_frame, textvariable=self.arduino_porta_var, width=40, justify='center', postcommand= lambda: arduino_gui.listar_portas(controlador=self.arduino, list=self.arduino_ports_box), state='readonly', name='ard_port_box')
        self.arduino_vel_box = ttk.Combobox(master=self.arduino_frame, values=constantes.BAUDRATES_SUPORTADOS, textvariable=self.arduino_veloc_var, width=40, height=15, justify='center', state='readonly', name='ard_vel_box')
        self.arduino_lumin_box = ttk.Combobox(master=self.arduino_frame, values=constantes.MODOS_LUMINOSIDADE, textvariable=self.arduino_lumin_var, width=40, justify='center', state='readonly', name='ard_lumi_box')  
        self.arduino_button = ttk.Button(master=self.arduino_frame, textvariable=self.arduino_string_var, command= lambda: arduino_gui.connect(arduino=self.arduino, port=self.arduino_porta_var.get(), baudrate=self.arduino_veloc_var.get(), 
                                                                                                                                       modo=self.arduino_lumin_var.get(),
                                                                                                                                       string=self.arduino_string_var, botao=self.arduino_button,
                                                                                                                                       boxes=(self.arduino_ports_box, self.arduino_vel_box, self.arduino_lumin_box),
                                                                                                                                       status={'labelimg':self.arduino_statuslabel, 'red':self.red_circle_img, 'green':self.green_circle_img}))
    def __setbitalino_widgets(self)-> None:
        logger.info('Setting BITALINO widgets')
        self.bitalino_label = ttk.Label(master=self.bitalino_frame, text='Bitalino: ', name='bit_label')
        self.bitalino_canais_box = ttk.Combobox(master=self.bitalino_frame, textvariable=self.bitalino_canal_var, width=40, justify='center', state='readonly', name='bit_canais_box', 
                                                values=constantes.CANAIS_BITALINO)
        self.bitalino_mac_box = ttk.Combobox(master=self.bitalino_frame, values=self.config.macs_bitalino, textvariable=self.bitalino_macaddr_var, width=40, justify='center', state='readonly', name='bit_mac_box')
        
    def __setanalysis_widgets(self) -> None:
        logger.info('Setting ANALYSIS widgets')
        self.analysis_label_frame = ttk.LabelFrame(master=self.analysis_frame, labelanchor='n', text='Escolha o modo de analise')
        self.analysis_label_frame.grid(columnspan=len(COLUNAS_GRID), column=0, row=0, padx=10, pady=10)
        self.analysis_box = ttk.Combobox(master=self.analysis_label_frame, justify='center', values=['Frequência', 'Amplitude'], textvariable=self.analysis_var, state='readonly')
        self.analysis_box.grid(column=0, row=0, padx=10, pady=10, sticky=N)
        
    def __setStatusStart_widgets(self) -> None:
        logger.info('Setting START STATUS widgets')
        self.status_update_label = ttk.Label(master=self.status_frame, textvariable=self.status_update_var, justify='center')
        self.start_button = ttk.Button(master=self.start_frame, text='Começar aquisição', width=30, command=self.__start)
        
    def __setmetersamp_widgets(self) -> None:
        logger.info('Setting AMP METERS widgets')
        self.amp_hue_meter = ttk.Meter(master=self.amp_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                       showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_saturation_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                              showtext=True, subtext='Saturação', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_value_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                         showtext=True, subtext='Brilho', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_sampling_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=900, amounttotal=1000, showtext=True, subtext='Amostragem', textright='ms', meterthickness=METER_THICKNESS,
                                              textleft='1x', stepsize=10, stripethickness=2, amountmin=100, arcrange=180, arcoffset=180, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)

        for medidor in (self.amp_saturation_meter, self.amp_value_meter, self.amp_sampling_meter):
            medidor.amountusedvar.trace_add('write', self.__ao_mudar_medidor)


    def __setmetersfreq_widgets(self) -> None:
        logger.info('Setting FREQ METERS widgets')
        self.freq_hue_meter = ttk.Meter(master=self.freq_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                        showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_saturation_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                               showtext=True, subtext='Saturação', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_value_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                          showtext=True, subtext='Brilho', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_sampling_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=3000, amounttotal=5000, showtext=True, subtext='Tamanho da Amostra', textright='ms', meterthickness=METER_THICKNESS,
                                             stepsize=CHUNK_SIZE, stripethickness=2, amountmin=1000, arcrange=180, arcoffset=180, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)

        # O "Tamanho da Amostra" NÃO entra aqui: ele define a janela de análise, que é
        # fixada na construção do ciclo e travada durante a aquisição.
        for medidor in (self.freq_saturation_meter, self.freq_value_meter):
            medidor.amountusedvar.trace_add('write', self.__ao_mudar_medidor)


    def __setcolor_widgets(self) -> None:
        logger.info('Setting COLOR UPDATE widgets')
        self.color_label = ttk.Label(master=self.tail_frame, textvariable=self.color_label_var, foreground='white', justify='center')
        self.color_label.grid(column=3, row=0, sticky=N, padx=10, pady=10)

    def __setgerenal_status_widgets(self) -> None:
        self.arduino_statuslabel = ttk.Label(master=self.general_status_frame, text='Arduino status:', image=self.red_circle_img, compound='right', justify='right')
        self.general_status_frame.grid(column=0, row=LINHAS_GRID[-1], sticky='sw')
        self.arduino_statuslabel.grid(column=0, row=0, padx=2, pady=2)
        
    def __start(self) -> None:
        """Conecta o BITalino, monta o núcleo e entrega a aquisição a uma thread.

        A partir daqui a GUI não lê mais o EEG: ela só drena a fila do serviço e pinta.
        """
        if self.estado is not EstadoApp.PRONTO:
            logger.warning(f'"Começar aquisição" pressionado no estado {self.estado.name}; ignorando.')
            return

        logger.info(f'Carregando modelo "{self.model_path}" ... ')
        self.model = carregar_modelo(caminho_modelo=self.model_path)

        self.bitalino_canal_int = int(self.bitalino_canal_var.get())
        logger.info(f'Canal do BITALINO escolhido para aquisição = A{self.bitalino_canal_int}')

        try:
            self.bitalino.conectar(mac_addr=self.bitalino_macaddr_var.get())
        except hardware.ErroConexaoBitalino as erro:
            logger.error(f'ERRO no Bitalino: {erro}')
            return Messagebox.show_error(title='Bitalino error!', message=f'{erro}')

        self.bitalino_srate = self.bitalino.taxa_amostragem_nominal()
        logger.info(f'Sampling rate do BITALINO = {self.bitalino_srate}')
        self.selected_lumi_mode = self.get_lumi_mode()

        modo = ModoAnalise(self.analysis_var.get())
        self.notebook.select(
            self.amp_meters_frame if modo is ModoAnalise.AMPLITUDE else self.freq_meters_frame
        )

        # O núcleo é montado aqui, e não no __init__, porque só agora existem todas as
        # escolhas do usuário: modelo, canal, modo de análise e tamanho da janela.
        self.ciclo = CicloAquisicao(
            leitor=self.bitalino,
            arduino=self.arduino,
            modelo=self.model,
            modo_analise=modo,
            canal_bitalino=self.bitalino_canal_int,
            modo_luminosidade=self.selected_lumi_mode,
            tamanho_amostra_frequencia=self.freq_sampling_meter.amountusedvar.get(),
        )

        # A gravação passou a viver DENTRO do serviço. É o que permite a fila de desenho
        # descartar resultados quando a interface não acompanha, sem perder dado gravado.
        self.servico = ServicoAquisicao(ciclo=self.ciclo, gravar=self.gravar_var.get())
        self.servico.atualizar_controles(self.__controles_atuais())

        self.freq_resulta_faixa = None
        self.estado = EstadoApp.ADQUIRINDO

        self.start_button.configure(command=self.__queryStop)
        self.start_button['text'] = 'Parar aquisição'
        self.change_state(mutables=self.mutable_wids, to='disabled')
        self.freq_sampling_meter.configure(interactive=False)
        self.status_update_var.set(value=mensagem_de_aquisicao(gravando=self.gravar_var.get()))

        logger.info('Começando aquisição de dados ...')
        self.servico.iniciar()
        self.__drenar_eventos()

    def __drenar_eventos(self) -> None:
        """Consome o que a thread de aquisição publicou e reflete na tela.

        Roda na thread da GUI, a cada `INTERVALO_DRENAGEM_MS`. Nunca bloqueia: se a fila
        estiver vazia, sai na hora e a janela segue respondendo. É o único ponto em que
        um resultado da aquisição toca em widget.
        """
        if self.servico is None:
            return

        for evento in self.servico.drenar():
            match evento:
                case EventoResultado():
                    self.__pintar_resultado(evento.resultado)

                case EventoErro():
                    logger.error(f'A thread de aquisição reportou: {evento.erro}')
                    Messagebox.show_error(title='Erro na aquisição!', message=evento.mensagem_usuario)

                case EventoParado():
                    logger.info(f'Aquisição encerrada. {evento.total_gravado} resultados gravados.')
                    self.__finalizar_aquisicao()
                    return

        self.__pintar_progresso()
        self._agendamento_drenagem = self.main_window.after(
            ms=INTERVALO_DRENAGEM_MS, func=self.__drenar_eventos
        )

    def __pintar_progresso(self) -> None:
        """Mostra o quanto falta para fechar a próxima janela de análise (modo Frequência)."""
        if self.servico is None or self.ciclo.modo_analise is ModoAnalise.AMPLITUDE:
            return

        faixa = f' | {self.freq_resulta_faixa}' if self.freq_resulta_faixa is not None else ''
        self.color_label_var.set(
            value=f'Analisando amostras = {self.servico.progresso_janela}'
                  f'/{self.ciclo.tamanho_amostra_frequencia}{faixa}'
        )

    def __pintar_resultado(self, resultado: ResultadoCiclo) -> None:
        """Reflete um `ResultadoCiclo` nos widgets. Nenhuma lógica de negócio aqui."""
        if resultado.faixa_frequencia is None:
            self.amp_hue_meter.amountusedvar.set(resultado.hue)
            self.color_label_var.set(value=f'Amplitude = {resultado.metrica_bruta:0.2f}uV')
        else:
            self.freq_hue_meter.amountusedvar.set(resultado.hue)
            self.freq_resulta_faixa = (f'Frequência = {resultado.metrica_bruta:0.2f}Hz '
                                       f'| {resultado.faixa_frequencia}')

        self.color_label.configure(background=resultado.cor_hex)

    def __salvar_gravacao(self, resultados: list[ResultadoCiclo]) -> None:
        """Pergunta o nome ao usuário e manda gravar.

        Quem pergunta é a interface. A `persistencia` só recebe o caminho pronto — antes,
        ela abria um diálogo no meio da função de dados.
        """
        modo: str = self.analysis_var.get()
        nome_escolhido = Querybox.get_string(
            prompt=f'Dê um nome para o arquivo EXCEL com os dados de {modo}:',
            initialvalue=persistencia.nome_sugerido(modo),
        )

        if not nome_escolhido:
            logger.warning('Usuário cancelou o salvamento. A gravação foi descartada.')
            return

        destino = Path(self.gravacao_basepath) / f'{nome_escolhido}.xlsx'

        try:
            persistencia.salvar_gravacao(resultados=resultados, destino=destino)
        except persistencia.ErroDeGravacao as erro:
            logger.error(str(erro))
            Messagebox.show_error(title='Erro no salvamento de dados!', message=str(erro))

    def __queryStop(self) -> None:
        """Confirma com o usuário e pede a parada. NÃO espera aqui.

        A thread pode levar até ~1 s para perceber o pedido, se estiver no meio de uma
        leitura bloqueante. Quem conclui o encerramento é o `EventoParado`, quando ele
        chegar pela fila — daí o estado PARANDO no meio do caminho, que impede um segundo
        clique de pedir a parada de novo.
        """
        if self.estado is not EstadoApp.ADQUIRINDO:
            return

        logger.info('Usuário selecionou "Parar aquisição".')

        if Messagebox.yesno(message='Deseja parar a aquisição?', alert=True) != 'Yes':
            logger.info('Usuário escolheu voltar para a aquisição')
            return

        self.estado = EstadoApp.PARANDO
        self.status_update_var.set(value='Parando a aquisição ...')
        self.start_button['state'] = 'disabled'

        if self.servico is not None:
            self.servico.parar()

    def __finalizar_aquisicao(self) -> None:
        """Fecha o hardware, oferece a gravação e devolve a interface ao estado ocioso.

        Chamado ao receber o `EventoParado` — que a thread SEMPRE publica, tanto na parada
        normal quanto depois de um erro. É por isso que uma falha do BITalino no meio da
        aquisição também passa por aqui: não existe caminho de saída que esqueça de fechar
        a porta serial.
        """
        if self.servico is None:
            return

        # A thread já terminou (o EventoParado é a última coisa que ela publica), mas o
        # `parar()` também cobre o caso do erro, em que ninguém pediu a parada.
        self.servico.parar()
        resultados = self.servico.gravacao
        self.servico = None
        self._agendamento_drenagem = None

        self.bitalino.encerrar_stream()
        self.arduino.desconectar()
        logger.info('Arduino e Bitalino desconectados.')

        if resultados:
            self.__salvar_gravacao(resultados=resultados)

        self.arduino_string_var.set('Conectar')
        self.arduino_statuslabel.configure(image=self.red_circle_img)
        self.start_button['text'] = 'Começar aquisição'
        self.start_button.configure(command=self.__start)
        self.start_button['state'] = 'normal'
        self.freq_sampling_meter.configure(interactive=True)
        self.color_label_var.set(value='Aguardando início da aquisição')

        self.change_state(mutables=self.mutable_wids, to='enabled')

        self.estado = EstadoApp.CONFIGURANDO
        self.__ao_mudar_selecao()

    def ao_fechar(self) -> None:
        """Desligamento ordenado: para a thread e fecha o hardware ANTES de destruir a janela.

        Antes, o "×" chamava `root.destroy()` direto: a porta serial e o stream do LSL
        ficavam abertos até o processo morrer, e a próxima execução podia não conseguir
        abrir a porta. Aqui a saída passa pelos mesmos context managers de sempre.
        """
        logger.info('Fechando o EsquizoCap ...')

        if self.servico is not None:
            self.servico.parar()
            self.servico = None

        # Idempotentes por contrato: chamar sem nunca ter conectado é seguro.
        self.bitalino.encerrar_stream()
        self.arduino.desconectar()

        self.root.destroy()


def main() -> None:
    """Ponto de entrada: prepara o ambiente e sobe a interface.

    A ordem importa. Logging e configuração são preparados ANTES de a GUI existir, para
    que uma configuração inválida ou um asset faltando falhem com uma mensagem clara em
    vez de virarem um erro obscuro do Tkinter no meio da montagem da janela.
    """
    log.configurar_logging(pasta_logs=recursos.PASTA_LOGS)

    try:
        recursos.validar()
        configuracao = config.carregar()
    except (recursos.ErroDeRecurso, config.ErroDeConfiguracao) as erro:
        logger.critical(str(erro))
        raise SystemExit(f'EsquizoCap não pôde iniciar:\n\n{erro}') from erro

    loading_screen.LoadingScreen().execute(
        folderpath=str(recursos.PASTA_GIF_CARREGAMENTO), duration=4500
    )

    # Sem `after(do_check)`: o estado da interface reage a mudanças (trace nas variáveis
    # do Tk), em vez de ser varrido 100 vezes por segundo.
    app = EsquizoCap(configuracao=configuracao)
    app.main_window.mainloop()


if __name__ == '__main__':
    main()