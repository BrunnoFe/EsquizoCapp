import inspect

from ttkbootstrap.constants import NE, SE, N

from esquizocap import hardware
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ModoAnalise, ResultadoCiclo
from esquizocap.dominio.predicao import carregar_modelo
from esquizocap.infraestrutura import guitools
from esquizocap.interface import arduino_gui, hovertip_config, loading_screen
from esquizocap.interface.custom_gui import CreateCustomGui, ttk

ZERO = 0
CHUNK_SIZE = 500
METER_MAX = 255
METER_THICKNESS = 12
METERS_SIZE = 200
METERS_TEXT_FONT = '-size 20 -weight bold'
METERS_SUBTEXT_FONT = '-size 12 -weight bold'

mainLogger: guitools.SetLogger = guitools.SetLogger(logfilepath=r'logs\EsquizoCapLogs.log', namelogger='mainGUI')

class EsquizoCap:
    def __init__(self, themename: str = 'solar', width: int = 1680, heigth: int = 1000) -> None:      
        self.app_basepath: guitools.Path = guitools.Path.cwd()
        self.fileconfigs: dict | None = guitools.loadconfigs(self.app_basepath)
        self.gravacao_basepath = guitools.create_folder(self.app_basepath)

        self.realTimeRender: str | None = guitools.findFilePath(filename=self.fileconfigs['executables']['Render'], jsonconfig=self.fileconfigs, basepath=self.app_basepath)
        self.openSigPath: str | None = guitools.findFilePath(filename=self.fileconfigs['executables']['OpenSignals'], jsonconfig=self.fileconfigs)

        self.custom_gui: CreateCustomGui = CreateCustomGui(iconpath=self.fileconfigs['icon'], themename=themename, width=width, heigth=heigth)
        self.root: ttk.Window = self.custom_gui.root
        self.main_window: ttk.Frame = self.custom_gui.main_window
       
        self.__load_images()
        self.__set_property(themename=themename)
        self.__set_frames()
        self.__set_grids(itens_to_grid=(self.title_frame, self.model_frame, self.arduino_frame, self.bitalino_frame, self.analysis_frame, self.status_frame, 
                                       self.start_frame, self.notebook, self.tail_frame), columnspan=len(self.fileconfigs['nofcolumns']), frame_grid=True)
        self.__set_vars()
        self.__setTitlePhoto()
        self.__setwidgets(widgets=(self.__setmodel_widgets, self.__setarduino_widgets, self.__setbitalino_widgets, self.__setanalysis_widgets,
                                   self.__setStatusStart_widgets, self.__setmetersamp_widgets,self.__setmetersfreq_widgets, self.__setcolor_widgets))
        
        self.theme_box = ttk.Combobox(master=self.custom_gui.title_bar, justify='center', values=self.fileconfigs['themes'], textvariable=self.theme_var, state='readonly', height=20, name='theme_box')
        self.theme_box.grid(column=2, row=0, sticky=NE, padx=15)
        self.theme_box.bind('<<ComboboxSelected>>', lambda _: self.set_theme(self.theme_var.get()))
        
        self.__set_grids(itens_to_grid=((self.model_label, self.model_box, self.gravar_button),
                                        (self.arduino_label, self.arduino_ports_box, self.arduino_vel_box, self.arduino_lumin_box, self.arduino_button),
                                        (self.bitalino_label, self.bitalino_canais_box, self.bitalino_mac_box),
                                        (self.amp_hue_meter, self.amp_saturation_meter, self.amp_value_meter, self.amp_sampling_meter),
                                        (self.freq_hue_meter, self.freq_saturation_meter, self.freq_value_meter, self.freq_sampling_meter)))

        self.__set_grids(itens_to_grid=(self.status_update_label, self.start_button), 
                         columnspan=len(self.fileconfigs['nofcolumns']))

        self.notebook.add(child=self.amp_meters_frame, text='Amplitude', sticky=N, state='normal')
        self.notebook.add(child=self.freq_meters_frame, text='Frequência', sticky=N, state='normal')

        self.mutable_wids = (self.model_box, self.gravar_button, self.arduino_button, self.arduino_ports_box,
                             self.arduino_vel_box, self.arduino_lumin_box, self.bitalino_canais_box, self.bitalino_mac_box)
        
        # A integração com a engine visual foi desligada; ver src/esquizocap/hardware/_engine_legado/.
        
        self.__setgerenal_status_widgets()
        self.__sethovertips(classes=(ttk.Button, ttk.Combobox, ttk.Checkbutton, ttk.Meter))
        
        self.set_theme(theme_selected=themename)

        ttk.Sizegrip(master=self.main_window).grid(column=self.fileconfigs['nofcolumns'][-1], row=self.fileconfigs['nofrows'][-1], sticky=SE)
        
        self.root.after(100, self.custom_gui.set_appwindow) # to see the icon on the task bar
        self.root.bind("<FocusIn>", self.custom_gui.deminimize) # to view the window by clicking on the window icon on the taskbar
    
    def __load_images(self) -> None:
        self.title_photo: ttk.PhotoImage = ttk.PhotoImage(file=self.fileconfigs['title_photo'])
        self.red_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=self.fileconfigs['red_circle']).subsample(5,5)
        self.green_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=self.fileconfigs['green_circle']).subsample(5,5)
    
    def __sethovertips(self, classes: tuple, delay: int = 1000) -> None:
        properties: list[str] = [m for (m, v) in inspect.getmembers(self) if isinstance(v, classes)]
        properties.sort(key=str.lower)
        tip_widgets: list = []
        for widget in properties:
            tip_widgets.append(getattr(self, widget))
        tips_dict: dict = dict(sorted(self.fileconfigs['tips'].items()))
        hovertip_config.set_tooltips(widgets=tip_widgets, tips=tips_dict, bg='#bc951a', fg='white', delay=delay)
        
    def __set_property(self, themename: str) -> None:
        mainLogger.logger.info('Configurando propriedades ...')
        self.arduino: hardware.ControladorLedArduino = hardware.criar_arduino()
        self.bitalino: hardware.LeitorBitalino = hardware.criar_bitalino()
        self.selected_lumi_mode: int = ZERO
        self.bitalino_srate: int = 100
        self.sampling_rate: int = 10
        self.freq_runs: int = ZERO
        self.amp_runs: int = ZERO
        self.freq_resulta_faixa: str = None
        self.aquisicao: bool = False
        self.style: ttk.Style = ttk.Style(theme=themename)
        self.after_action: list = []

    def set_model_path(self) -> None:
        self.model_pathstring_var.set(self.fileconfigs['models'][0]) ## retirar dps ... provavelmente pq posso colocar essa string diretamente no widget
        self.model_path: str = self.fileconfigs['models_path']['amp']
        mainLogger.logger.info(f'Modelo de machine learning escolhido = {self.model_path}')

    def __gravacao_basepath(self) -> None:
        self.gravacao_basepath: str = guitools.askdirectory(title='Selecione a pasta para salvar os dados da aquisição e predição: ')
        mainLogger.logger.info(f'Pasta de salvamento dos arquivos das gravaçãoes alterado. Novo = {self.gravacao_basepath}')

    def set_theme(self, theme_selected) -> None:
        self.style.theme_use(themename=theme_selected)
        self.style.configure('TCombobox', arrowsize = 20) #"Helvetica", size = 15
        self.style.configure('TSizegrip', size=50)
        self.style.configure('.', font=self.custom_gui.font)
        mainLogger.logger.info(f'Tema alterado. Novo = {theme_selected}')

    def __set_grids(self, itens_to_grid: tuple[tuple], row: int = ZERO, columnspan: int | None = None, padx: int = 5, pady: int = 5, sticky: str = N, frame_grid: bool = False):
        if columnspan is None:
            mainLogger.logger.info('Configurando os grids dos widgets ...')
            for iterable in itens_to_grid:
                for column, item in enumerate(iterable=iterable, start=ZERO):
                    mainLogger.logger.info(f'Widget: configurando item {item} na coluna {column} e linha {row}, fixado em "{sticky}"')
                    item.grid(column=column, row=row, padx=padx, pady=pady, sticky=sticky)
        else:
            if frame_grid is False:
                mainLogger.logger.info('Configurando grids com columnspan ...')
                for column, item in enumerate(iterable=itens_to_grid, start=ZERO):
                    mainLogger.logger.info(f'Widget: configurando item {item} com columnspan = {columnspan} na linha "{row}", fixado em "{sticky}"')
                    item.grid(columnspan=columnspan, row=row, padx=padx, pady=pady, sticky=sticky) # type: ignore
            else:
                mainLogger.logger.info('Configurando Frame grids ...')
                for row_index, frame in enumerate(iterable=itens_to_grid, start=ZERO):
                    mainLogger.logger.info(f'Frame: configurando frame {frame} com columnspan = {columnspan} na linha {row_index}, fixado em "{sticky}"')
                    frame.grid(columnspan=columnspan, row=row_index, sticky=sticky, padx=pady, pady=padx)

    def change_state(self, mutables: tuple, to: str = 'disabled') -> None:
        for mutable in mutables:
            if isinstance(mutable, ttk.Button):
                mainLogger.logger.info(f'Alterando o estado do Botão "{mutable}" para {to}')
                mutable['state'] = to
            elif isinstance(mutable, ttk.Combobox):
                if to == 'disabled':
                    mainLogger.logger.info(f'Alterando o estado do Combobox "{mutable}" para {to}')
                    mutable['state'] = to
                else:
                    mainLogger.logger.info(f'Alterando o estado do Combobox "{mutable}" para "readonly"')
                    mutable['state'] = 'readonly'

    def get_lumi_mode(self) -> int:
        for int_modo, str_modo in enumerate(self.fileconfigs['modos'], start=1):
            if str_modo == self.arduino_lumin_var.get():
                mainLogger.logger.info(f'Modo de iluminação escolhido = {int_modo}')
                return int_modo        

    def __setTitlePhoto(self) -> None:
        self.title_label = ttk.Label(master=self.title_frame, padding=10, image=self.title_photo)
        self.title_label.grid(columnspan=len(self.fileconfigs['nofcolumns']), sticky=N)
        mainLogger.logger.info(f'Configurando a foto da janela principal. Foto escolhida = {self.title_photo}')

    def __setwidgets(self, widgets) -> None:
        mainLogger.logger.info('Configurando todos os widgets ...')
        for func in widgets:
            func()

    def __set_vars(self) -> None:
        mainLogger.logger.info('Criando todas as variáveis ...')
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
        
    def __set_frames(self) -> None:
        mainLogger.logger.info('Setting FRAMES ...')
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
        mainLogger.logger.info('Setting MODEL widgets')
        self.model_label = ttk.Label(master=self.model_frame, text='Selecione um modelo:', justify='left', name='model_label')     
        self.model_box = ttk.Combobox(master=self.model_frame, justify='center', width=100, textvariable=self.model_pathstring_var, state='readonly', values=self.fileconfigs['models'], name='model_box')
        self.model_box.bind('<<ComboboxSelected>>', lambda _: self.set_model_path()) 
        self.gravar_button = ttk.Checkbutton(master=self.model_frame, text='Gravar aquisição', bootstyle='round-toggle', variable=self.gravar_var, name='gravar_button', style='Roundtoggle')

    def __setarduino_widgets(self)-> None:
        mainLogger.logger.info('Setting ARDUINO widgets')
        self.arduino_label = ttk.Label(master=self.arduino_frame, text='Arduino: ', name='arduino_label')
        self.arduino_ports_box = ttk.Combobox(master=self.arduino_frame, textvariable=self.arduino_porta_var, width=40, justify='center', postcommand= lambda: arduino_gui.listar_portas(controlador=self.arduino, list=self.arduino_ports_box), state='readonly', name='ard_port_box')
        self.arduino_vel_box = ttk.Combobox(master=self.arduino_frame, values=self.fileconfigs['velocidade_pre'], textvariable=self.arduino_veloc_var, width=40, height=15, justify='center', state='readonly', name='ard_vel_box')
        self.arduino_lumin_box = ttk.Combobox(master=self.arduino_frame, values=self.fileconfigs['modos'], textvariable=self.arduino_lumin_var, width=40, justify='center', state='readonly', name='ard_lumi_box')  
        self.arduino_button = ttk.Button(master=self.arduino_frame, textvariable=self.arduino_string_var, command= lambda: arduino_gui.connect(arduino=self.arduino, port=self.arduino_porta_var.get(), baudrate=self.arduino_veloc_var.get(), 
                                                                                                                                       modo=self.arduino_lumin_var.get(), configsfile=self.fileconfigs, 
                                                                                                                                       string=self.arduino_string_var, botao=self.arduino_button, selfmode=self.selected_lumi_mode,
                                                                                                                                       boxes=(self.arduino_ports_box, self.arduino_vel_box, self.arduino_lumin_box),
                                                                                                                                       status={'labelimg':self.arduino_statuslabel, 'red':self.red_circle_img, 'green':self.green_circle_img}))
    def __setbitalino_widgets(self)-> None:
        mainLogger.logger.info('Setting BITALINO widgets')
        self.bitalino_label = ttk.Label(master=self.bitalino_frame, text='Bitalino: ', name='bit_label')
        self.bitalino_canais_box = ttk.Combobox(master=self.bitalino_frame, textvariable=self.bitalino_canal_var, width=40, justify='center', state='readonly', name='bit_canais_box', 
                                                postcommand= lambda: guitools.canais_bitalino(canais=self.fileconfigs['canais_bitalino'], box=self.bitalino_canais_box))
        self.bitalino_mac_box = ttk.Combobox(master=self.bitalino_frame, values=self.fileconfigs['mac_addr'], textvariable=self.bitalino_macaddr_var, width=40, justify='center', state='readonly', name='bit_mac_box')
        
    def __setanalysis_widgets(self) -> None:
        mainLogger.logger.info('Setting ANALYSIS widgets')
        self.analysis_label_frame = ttk.LabelFrame(master=self.analysis_frame, labelanchor='n', text='Escolha o modo de analise')
        self.analysis_label_frame.grid(columnspan=len(self.fileconfigs['nofcolumns']), column=0, row=0, padx=10, pady=10)
        self.analysis_box = ttk.Combobox(master=self.analysis_label_frame, justify='center', values=['Frequência', 'Amplitude'], textvariable=self.analysis_var, state='readonly')
        self.analysis_box.grid(column=0, row=0, padx=10, pady=10, sticky=N)
        
    def __setStatusStart_widgets(self) -> None:
        mainLogger.logger.info('Setting START STATUS widgets')
        self.status_update_label = ttk.Label(master=self.status_frame, textvariable=self.status_update_var, justify='center')
        self.start_button = ttk.Button(master=self.start_frame, text='Começar aquisição', width=30, command=self.__start)
        
    def __setmetersamp_widgets(self) -> None:
        mainLogger.logger.info('Setting AMP METERS widgets')
        self.amp_hue_meter = ttk.Meter(master=self.amp_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                       showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_saturation_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                              showtext=True, subtext='Saturação', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_value_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                         showtext=True, subtext='Brilho', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_sampling_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=900, amounttotal=1000, showtext=True, subtext='Amostragem', textright='ms', meterthickness=METER_THICKNESS,
                                              textleft='1x', stepsize=10, stripethickness=2, amountmin=100, arcrange=180, arcoffset=180, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
    
    def __setmetersfreq_widgets(self) -> None:
        mainLogger.logger.info('Setting FREQ METERS widgets')
        self.freq_hue_meter = ttk.Meter(master=self.freq_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                        showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_saturation_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                               showtext=True, subtext='Saturação', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_value_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                          showtext=True, subtext='Brilho', stepsize=2, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_sampling_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=3000, amounttotal=5000, showtext=True, subtext='Tamanho da Amostra', textright='ms', meterthickness=METER_THICKNESS,
                                             stepsize=CHUNK_SIZE, stripethickness=2, amountmin=1000, arcrange=180, arcoffset=180, metersize=METERS_SIZE, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
    
    def __setcolor_widgets(self) -> None:
        mainLogger.logger.info('Setting COLOR UPDATE widgets')
        self.color_label = ttk.Label(master=self.tail_frame, textvariable=self.color_label_var, foreground='white', justify='center')
        self.color_label.grid(column=3, row=0, sticky=N, padx=10, pady=10)

    def __setgerenal_status_widgets(self) -> None:
        self.arduino_statuslabel = ttk.Label(master=self.general_status_frame, text='Arduino status:', image=self.red_circle_img, compound='right', justify='right')
        self.general_status_frame.grid(column=0, row=self.fileconfigs['nofrows'][-1], sticky='sw')
        self.arduino_statuslabel.grid(column=0, row=0, padx=2, pady=2)
        
    def do_check(self) -> None:
        
        self.main_window.after(ms=self.sampling_rate, func=self.do_check)
        
        if self.aquisicao is False:
                
            if self.model_pathstring_var.get() not in self.fileconfigs['models']:
                return self.status_update_var.set(value='Selecione o modelo de machine learning')
                
            if 'COM' not in self.arduino_porta_var.get() or self.arduino_lumin_var.get() not in self.fileconfigs['modos']:
                return self.status_update_var.set(value='Configure o Arduino')
            
            if 'COM' in self.arduino_porta_var.get() and self.arduino_lumin_var.get() in self.fileconfigs['modos'] and self.arduino_string_var.get() == 'Conectar':
                return self.status_update_var.set(value='Arduino configurado! Pressione "Conectar"')
            
            if self.bitalino_canal_var.get() =='Selecione o canal ativo do Bitalino' or self.bitalino_macaddr_var.get() not in self.fileconfigs['mac_addr']:
                return self.status_update_var.set(value='Configure o Bitalino')
                
            if self.arduino_string_var.get() == 'Desconectar' and self.model_pathstring_var.get() in self.fileconfigs['models'] and self.bitalino_canal_var.get() != 'Selecione o canal ativo do Bitalino' and self.bitalino_macaddr_var.get() in self.fileconfigs['mac_addr']:
                return self.status_update_var.set(value='Pressione "Começar aquisição"')
            
            else:
                return self.status_update_var.set(value='Selecione todas as opções acima')
                                      
        else:
            if self.after_action.__len__() > 1:
                self.after_action.remove(self.after_action[0])
                
            self.after_action.append(self.main_window.after(ms=self.sampling_rate, func=self.__pullSamples))
            
            if self.gravar_var.get() is True:
                self.status_update_var.set(value='Executando e gravando a aquisição de dados')
            else:
                self.status_update_var.set(value='Executando aquisição de dados')
                       
    def __start(self) -> None:
        
        if self.aquisicao is False:
            
            if self.model_pathstring_var.get() in self.fileconfigs['models']: # verifica se é igual a algumo modelo do arquivo json (ex: Preditor HSV para Amplitude e Frequencia)
                mainLogger.logger.info(f'Carregando modelo "{self.model_path}" ... ')
                self.model = carregar_modelo(caminho_modelo=self.model_path)
            else:
                mainLogger.logger.error('Usuário não escolheu um modelo para realizar as predições')
                return guitools.Messagebox.show_error(title='Error!', message='Escolha um modelo para realizar as predições.')

            if self.arduino_string_var.get() != 'Desconectar':
                mainLogger.logger.warning('Usuário não conectou o arduino antes de começar a aquisição')
                return guitools.Messagebox.show_warning(title='Aviso!', message='Conecte o arduino antes de iniciar a aquisição.')

            try:
                self.bitalino_canal_int = int(self.bitalino_canal_var.get())
                mainLogger.logger.info(f'Canal do BITALINO escolhido para aquisição = A{self.bitalino_canal_int}')
            except ValueError:
                mainLogger.logger.warning('Usuário não escolheu um canal ativo do BITALINO para aquisição')
                return guitools.Messagebox.show_warning(message='Selecione o canal ativo do Bitalino antes de começar a aquisição.')

            try:
                self.bitalino.conectar(mac_addr=self.bitalino_macaddr_var.get())
            except hardware.ErroConexaoBitalino as erro:
                mainLogger.logger.error(f'ERRO no Bitalino: {erro}')
                return guitools.Messagebox.show_error(title='Bitalino error!', message=f'{erro}')

            self.bitalino_srate = self.bitalino.taxa_amostragem_nominal()
            mainLogger.logger.info(f'Sampling rate do BITALINO = {self.bitalino_srate}')
            self.selected_lumi_mode = self.get_lumi_mode()

            # O núcleo é montado aqui, e não no __init__, porque só agora existem todas as
            # escolhas do usuário: modelo, canal, modo de análise e tamanho da janela.
            self.ciclo = CicloAquisicao(
                leitor=self.bitalino,
                arduino=self.arduino,
                modelo=self.model,
                modo_analise=ModoAnalise(self.analysis_var.get()),
                canal_bitalino=self.bitalino_canal_int,
                modo_luminosidade=self.selected_lumi_mode,
                tamanho_amostra_frequencia=self.freq_sampling_meter.amountusedvar.get(),
            )

            self.amp_array = guitools.numpy.array([]) #array para registrar o tempo de cada amostra de dado do eletrodo
            self.freq_results = guitools.numpy.array([])
            self.freq_timesamples = guitools.numpy.array([])

            self.start_button.configure(command=self.__queryStop)
            self.start_button['text'] = 'Parar aquisição'

            self.change_state(mutables=self.mutable_wids, to='disabled')
            self.freq_sampling_meter.configure(interactive=False)
            
            mainLogger.logger.info('Começando aquisição de dados ...')
            self.aquisicao = True
            self.__pullSamples()
        
    def __pullSamples(self) -> None:
        """Roda um ciclo do núcleo e reflete o resultado na interface.

        A GUI não faz mais aquisição nem predição: ela só escolhe os parâmetros que o
        usuário controla (saturação, brilho), pede um ciclo ao `CicloAquisicao` e pinta
        o `ResultadoCiclo` que voltar.
        """
        try:
            if self.analysis_var.get() == 'Amplitude':
                self.notebook.select(self.amp_meters_frame)
                self.sampling_rate = self.amp_sampling_meter.amountusedvar.get()
                saturacao = self.amp_saturation_meter.amountusedvar.get()
                brilho = self.amp_value_meter.amountusedvar.get()
            else:
                self.notebook.select(self.freq_meters_frame)
                self.sampling_rate = CHUNK_SIZE
                saturacao = self.freq_saturation_meter.amountusedvar.get()
                brilho = self.freq_value_meter.amountusedvar.get()

            resultado = self.ciclo.processar_amostra(saturacao=saturacao, brilho=brilho)

            # No modo Frequência, um ciclo pode não produzir resultado: os blocos ainda
            # estão sendo acumulados até fechar a janela de análise.
            if resultado is not None:
                self.__pintar_resultado(resultado)

                if self.gravar_var.get() is True:
                    self.__registrar_resultado(resultado)

            if self.analysis_var.get() != 'Amplitude':
                self.color_label_var.set(
                    value=f'Analisando amostras = {self.ciclo.amostras_acumuladas}/{self.ciclo.tamanho_amostra_frequencia}'
                          f'{" | " + self.freq_resulta_faixa if self.freq_resulta_faixa is not None else ""}'
                )

        except (IndexError, hardware.ErroStreamPerdido, hardware.ErroConexaoBitalino) as error:
            mainLogger.logger.exception(error)
            self.aquisicao = False
            msg: str = (f'{type(error).__name__} detectado. OpenSignals ou BITalino pode não estar '
                        'funcionando corretamente. Verifique a conexão.')
            mainLogger.logger.error(msg)
            guitools.Messagebox.show_error(msg)
            self.__stop()

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

    def __registrar_resultado(self, resultado: ResultadoCiclo) -> None:
        """Acumula o resultado para a exportação em Excel feita no `__stop`."""
        if resultado.janela is None:
            self.amp_runs += 1
            self.amp_array = guitools.numpy.append(
                self.amp_array, [resultado.timestamp, resultado.metrica_bruta, resultado.hue]
            )
            return

        self.freq_runs += 1
        self.freq_results = guitools.numpy.append(
            self.freq_results,
            [self.freq_runs, resultado.timestamp, resultado.metrica_bruta,
             resultado.potencia, resultado.hue, resultado.faixa_frequencia],
        )
        self.freq_timesamples = guitools.numpy.append(
            self.freq_timesamples, (resultado.janela.amostras, resultado.janela.timestamps)
        )

    def __cancel_actions(self, action_list: list) -> None:
        if action_list.__len__() > 0: 
            for index, _ in enumerate(action_list):
                self.main_window.after_cancel(action_list[index])
            return mainLogger.logger.info(f'Lista com {action_list.__len__()} ações. Todas foram canceladas.')
        return mainLogger.logger.warning(f'Lista de ações vazia. Nenhuma ação foi cancelada. Lista = {action_list}')

    def __queryStop(self) -> None:
        self.aquisicao = False
        self.__cancel_actions(self.after_action)
        mainLogger.logger.info(f'Usuário selecionou "Parar aquisição".')
        resp: None | str = guitools.Messagebox.yesno(message='Deseja parar a aquisição?', alert=True)

        if resp == 'Yes':
            self.__stop()
        else:
            self.aquisicao = True
            return mainLogger.logger.info('Usuário escolheu voltar para a aquisição')
    
    def __stop(self) -> None:
        mainLogger.logger.info('Parando a aquisição ...')
        self.__cancel_actions(self.after_action)
        self.bitalino.encerrar_stream()
        self.arduino.desconectar()
        mainLogger.logger.info('Arduino e Bitalino desconectados.')

        if self.freq_runs != ZERO:
            guitools.salvar_dados(registros={'freq_time_samples':self.freq_timesamples, 'freq_results':self.freq_results},
                                  basepath=self.gravacao_basepath, nrows=self.freq_runs, 
                                  ncolumns=self.freq_sampling_meter.amountusedvar.get())

        if self.amp_runs != ZERO:
            guitools.salvar_dados(registros={'amp':self.amp_array}, basepath=self.gravacao_basepath, nrows=self.amp_runs)

        self.arduino_string_var.set('Conectar')
        self.arduino_statuslabel.configure(image=self.red_circle_img)
        self.start_button['text'] = 'Começar aquisição'
        self.start_button.configure(command=self.__start)
        self.freq_sampling_meter.configure(interactive=True)

        self.amp_runs = ZERO
        self.freq_runs = ZERO

        self.change_state(mutables=self.mutable_wids, to='enabled')

if __name__ == '__main__':
    loading_screen_ = loading_screen.LoadingScreen()
    loading_screen_.execute(folderpath=r'images\\gif', duration=4500)
    
    app = EsquizoCap()
    app.main_window.after(ms=10, func=app.do_check)
    app.main_window.mainloop()