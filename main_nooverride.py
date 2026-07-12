import ttkbootstrap as ttk
from tkinter.font import Font

from tools import arduino, guitools, server

ZERO = 0
CHUNK_SIZE = 500
METER_MAX = 255
METER_THICKNESS = 15
METERS_TEXT_FONT = '-size 35 -weight bold'
METERS_SUBTEXT_FONT = '-size 20 -weight bold'

mainLogger: guitools.SetLogger = guitools.SetLogger(logfilepath=r'logs\EsquizoCapLogs.log', namelogger='mainGUI')

class EsquizoCap:
    def __init__(self, title: str = 'EsquizoCap', themename: str = 'solar', size: tuple = None, resizable: tuple = (True, True), scaling: float = 1.0) -> None:
        
        self.app_basepath: str = guitools.os.getcwd()
        self.fileconfigs: dict | None = guitools.loadconfigs(self.app_basepath)
        self.gravacao_basepath = guitools.create_folder(self.app_basepath)
        self.realTimeRender: str | None = guitools.findFilePath(filename=self.fileconfigs['executables']['Render'], jsonconfig=self.fileconfigs, basepath=self.app_basepath)
        self.openSigPath: str | None = guitools.findFilePath(filename=self.fileconfigs['executables']['OpenSignals'], jsonconfig=self.fileconfigs)
        
        self.__set_mainwindow(title=title, themename=themename, size=size, resizable=resizable, scaling=scaling)
        
        self.__load_images(self.fileconfigs)
        
        self.__set_property(themename=themename)
        self.__set_frames()
        self.__set_grids(itens_to_grid=(self.title_frame, self.model_frame, self.arduino_frame, self.bitalino_frame, self.analysis_frame, self.status_frame, 
                                       self.start_frame, self.notebook, self.tail_frame), columnspan=len(self.fileconfigs['nofcolumns']), frame_grid=True)
        self.__set_vars()
        
        #self.__set_menus()
        self.__setTitlePhoto()
        self.__setwidgets(widgets=(self.__setmodel_widgets, self.__setarduino_widgets, self.__setbitalino_widgets, self.__setanalysis_widgets,
                                   self.__setStatusStart_widgets, self.__setmetersamp_widgets,self.__setmetersfreq_widgets, self.__setcolor_widgets))
        
        self.theme_box = ttk.Combobox(master=self.main_window, justify='center', values=self.fileconfigs['themes'], textvariable=self.theme_var, state='readonly', height=20, name='theme_box')
        self.theme_box.grid(columnspan=len(self.fileconfigs['nofcolumns']), row=self.fileconfigs['nofrows'][-1], sticky=ttk.NE, padx=10, pady=10)
        self.theme_box.bind('<<ComboboxSelected>>', lambda _: self.set_theme(self.theme_var.get()))

        #self.main_window.configure(background='white')
        
        self.__set_grids(itens_to_grid=((self.model_label, self.model_box, self.gravar_button),
                                        (self.arduino_label, self.arduino_ports_box, self.arduino_vel_box, self.arduino_lumin_box, self.arduino_button),
                                        (self.bitalino_label, self.bitalino_canais_box, self.bitalino_mac_box),
                                        (self.amp_hue_meter, self.amp_saturation_meter, self.amp_value_meter, self.amp_sampling_meter),
                                        (self.freq_hue_meter, self.freq_saturation_meter, self.freq_value_meter, self.freq_sampling_meter)))

        self.__set_grids(itens_to_grid=(self.status_update_label, self.start_button), 
                         columnspan=len(self.fileconfigs['nofcolumns']))

        self.notebook.add(child=self.amp_meters_frame, text='Amplitude', sticky=ttk.N, state='normal')
        self.notebook.add(child=self.freq_meters_frame, text='Frequência', sticky=ttk.N, state='normal')

        self.mutable_wids = (self.model_box, self.gravar_button, self.arduino_button, self.arduino_ports_box, 
                             self.arduino_vel_box, self.arduino_lumin_box, self.bitalino_canais_box, self.bitalino_mac_box) # type: ignore
        
        self.server_connection:server.Server = server.Server()
        
        self.__setgerenal_status_widgets()
        
        self.set_theme(theme_selected=themename)
         
    def __load_images(self, configsfile) -> None:
        self.title_photo: ttk.PhotoImage = ttk.PhotoImage(file=r'images\esquizo.png')
        self.red_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=r'images\red_circle.png').subsample(4,4)
        self.green_circle_img: ttk.PhotoImage = ttk.PhotoImage(file=r'images\green_circle.png').subsample(4,4)

    def get_win_size(self) -> None:
        self.main_window.update()
        self.window_width: int = self.main_window.winfo_width()
        self.window_height: int = self.main_window.winfo_height()
        
    def __set_property(self, themename: str) -> None:
        mainLogger.logger.info('Configurando propriedades ...')
        self.arduino = arduino.serial.Serial()
        self.selected_lumi_mode: int = ZERO
        self.bitalino_srate: int = 100
        self.sampling_rate: int = 10
        self.freq_runs: int = ZERO
        self.amp_runs: int = ZERO
        self.freq_resulta_faixa: str = None
        self.aquisicao: bool = False
        self.style: ttk.Style = ttk.Style(theme=themename)

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
        self.style.configure('.', font=self.font)
        mainLogger.logger.info(f'Tema alterado. Novo = {theme_selected}')

    def __set_grids(self, itens_to_grid: tuple[tuple], row: int = ZERO, columnspan: int | None = None, padx: int = 10, pady: int = 10, sticky: str = ttk.N, frame_grid: bool = False):
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

    def __set_mainwindow(self, title, themename, size, resizable, scaling) -> None:
        mainLogger.logger.info('Criando janela principal ...')
        self.main_window = ttk.Window(title=title, themename=themename, size=size, resizable=resizable, scaling=scaling, iconphoto=r'images\esquizo_ico.png', minsize=(1366,912))
        self.main_window.grid_columnconfigure(index=self.fileconfigs['nofcolumns'], weight=1)
        self.main_window.grid_rowconfigure(index=self.fileconfigs['nofrows'], weight=1)
        self.get_win_size()
        self.font = Font(family = "Helvetica", size = 15, weight='normal', slant='roman')
        self.main_window.option_add("*TCombobox*Listbox.font", self.font)
        self.main_window.option_add("*TCombobox.font", self.font)

    def __set_menus(self) -> None:
        mainLogger.logger.info('Criando os menus ...')
        self.main_menu = ttk.Menu(master=self.main_window, type='menubar', name='main_menu', border=0, borderwidth=0, bd=0, activeborderwidth=0, relief='raised', font=self.font)
        self.menu_gravacao = ttk.Menu(master=self.main_menu, tearoff=False, name='menu_gravação', border=0, borderwidth=0, bd=0, activeborderwidth=0, relief='raised', font=self.font)
        self.menu_configs = ttk.Menu(master=self.main_menu, tearoff=False, name='menu_configs',border=0, borderwidth=0, bd=0, activeborderwidth=0, relief='raised', font=self.font)
        self.menu_gravacao.add_command(label='Salvar dados em ...', command=self.__gravacao_basepath)
        self.menu_configs.add_command(label='Preferências', command=lambda: print('a'))
        self.main_menu.add_cascade(label='Gravação', menu=self.menu_gravacao)
        self.main_menu.add_cascade(label='Configurações', menu=self.menu_configs, hidemargin=True, underline=0, columnbreak=0)
        self.main_window.configure(menu=self.main_menu)

    def __setTitlePhoto(self) -> None:
        self.title_label = ttk.Label(master=self.title_frame, padding=10, image=self.title_photo)
        self.title_label.grid(columnspan=len(self.fileconfigs['nofcolumns']), sticky=ttk.N)
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
        self.theme_var = ttk.StringVar(value=self.main_window.style.theme_use())
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
        self.model_box.bind('<<ComboboxSelected>>', self.set_model_path) 
        self.gravar_button = ttk.Checkbutton(master=self.model_frame, text='Gravar aquisição', bootstyle='round-toggle', variable=self.gravar_var, name='gravar_button', style='Roundtoggle')

    def __setarduino_widgets(self)-> None:
        mainLogger.logger.info('Setting ARDUINO widgets')
        self.arduino_label = ttk.Label(master=self.arduino_frame, text='Arduino: ', name='arduino_label')
        self.arduino_ports_box = ttk.Combobox(master=self.arduino_frame, textvariable=self.arduino_porta_var, width=40, justify='center', postcommand= lambda: arduino.listar_portas(list=self.arduino_ports_box), state='readonly', name='ard_port_box')
        self.arduino_vel_box = ttk.Combobox(master=self.arduino_frame, values=self.fileconfigs['velocidade_pre'], textvariable=self.arduino_veloc_var, width=40, height=15, justify='center', state='readonly', name='ard_vel_box')
        self.arduino_lumin_box = ttk.Combobox(master=self.arduino_frame, values=self.fileconfigs['modos'], textvariable=self.arduino_lumin_var, width=40, justify='center', state='readonly', name='ard_lumi_box')  
        self.arduino_button = ttk.Button(master=self.arduino_frame, textvariable=self.arduino_string_var, command= lambda: arduino.connect(arduino=self.arduino, port=self.arduino_porta_var.get(), baudrate=self.arduino_veloc_var.get(), 
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
        self.analysis_box.grid(column=0, row=0, padx=10, pady=10, sticky=ttk.N)
        
    def __setStatusStart_widgets(self) -> None:
        mainLogger.logger.info('Setting START STATUS widgets')
        self.status_update_label = ttk.Label(master=self.status_frame, textvariable=self.status_update_var, justify='center')
        self.start_button = ttk.Button(master=self.start_frame, text='Começar aquisição', width=30, command=self.__start)
        
    def __setmetersamp_widgets(self) -> None:
        mainLogger.logger.info('Setting AMP METERS widgets')
        self.amp_hue_meter = ttk.Meter(master=self.amp_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                       showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_saturation_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                              showtext=True, subtext='Saturação', stepsize=2, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_value_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                         showtext=True, subtext='Brilho', stepsize=2, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.amp_sampling_meter = ttk.Meter(master=self.amp_meters_frame, interactive=True,  metertype='semi', amountused=900, amounttotal=1000, showtext=True, subtext='Amostragem', textright='ms', meterthickness=METER_THICKNESS,
                                              textleft='1x', stepsize=10, stripethickness=2, amountmin=100, arcrange=180, arcoffset=180, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
    
    def __setmetersfreq_widgets(self) -> None:
        mainLogger.logger.info('Setting FREQ METERS widgets')
        self.freq_hue_meter = ttk.Meter(master=self.freq_meters_frame, interactive=False, metertype='semi', amountused=ZERO, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                        showtext=True, subtext='Hue', stepsize=1, wedgesize=3, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_saturation_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=METER_MAX, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                               showtext=True, subtext='Saturação', stepsize=2, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_value_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=120, amounttotal=METER_MAX, meterthickness=METER_THICKNESS,
                                          showtext=True, subtext='Brilho', stepsize=2, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
        self.freq_sampling_meter = ttk.Meter(master=self.freq_meters_frame, interactive=True,  metertype='semi', amountused=3000, amounttotal=5000, showtext=True, subtext='Tamanho da Amostra', textright='ms', meterthickness=METER_THICKNESS,
                                             stepsize=CHUNK_SIZE, stripethickness=2, amountmin=1000, arcrange=180, arcoffset=180, metersize=300, textfont=METERS_TEXT_FONT, subtextfont=METERS_SUBTEXT_FONT)
    
    def __setcolor_widgets(self) -> None:
        mainLogger.logger.info('Setting COLOR UPDATE widgets')
        self.color_label = ttk.Label(master=self.tail_frame, textvariable=self.color_label_var, foreground='white', justify='center')
        self.color_label.grid(column=3, row=0, sticky=ttk.N, padx=10, pady=10)

    def __setgerenal_status_widgets(self) -> None:
        self.arduino_statuslabel = ttk.Label(master=self.general_status_frame, text='Arduino status:', image=self.red_circle_img, compound='right', justify='right')
        self.server_status = ttk.Label(master=self.general_status_frame, text=f'|  Server at {self.server_connection.serverIp}:{self.server_connection.port} status:', 
                                       justify='center', image=self.red_circle_img, compound='right')
        self.general_status_frame.grid(column=0, row=self.fileconfigs['nofrows'][-1], sticky='sw')
        self.arduino_statuslabel.grid(column=0, row=0, padx=2, pady=2)
        self.server_status.grid(column=1, row=0, padx=2, pady=2)
        
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
            self.after_action: str = self.main_window.after(ms=self.sampling_rate, func=self.__pullSamples)
            
            if self.gravar_var.get() is True:
                self.status_update_var.set(value='Executando e gravando a aquisição de dados')
            else:
                self.status_update_var.set(value='Executando aquisição de dados')
                       
    def __start(self) -> None:
        
        if self.aquisicao is False:
            
            if self.model_pathstring_var.get() in self.fileconfigs['models']: # verifica se é igual a algumo modelo do arquivo json (ex: Preditor HSV para Amplitude e Frequencia)
                mainLogger.logger.info(f'Carregando modelo "{self.model_path}" ... ')
                self.model = guitools.load_model(model_path=self.model_path) #model_path = string do arquivo json contendo o caminho (ex: json['models_path]["amp"]:"models/BestModel_HSV_v1.pickle")
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

            self.bitalino: guitools.StreamInlet | str = guitools.bitalino_connect(mac_addr=self.bitalino_macaddr_var.get())

            if isinstance(self.bitalino, str):
                mainLogger.logger.error(f'ERRO no Bitalino: {self.bitalino}')
                return guitools.Messagebox.show_error(title='Bitalino error!', message=f'{self.bitalino}')
            
            self.bitalino_srate = int(self.bitalino.info().nominal_srate())
            mainLogger.logger.info(f'Sampling rate do BITALINO = {self.bitalino_srate}')
            self.selected_lumi_mode = self.get_lumi_mode() 
            
            self.amp_array = guitools.numpy.array([]) #array para registrar o tempo de cada amostra de dado do eletrodo
            self.freq_results = guitools.numpy.array([]) 
            self.freq_samples = guitools.numpy.array([])
            self.freq_timestamp = guitools.numpy.array([])
            self.freq_timesamples = guitools.numpy.array([])

            self.start_button.configure(command=self.__queryStop)
            self.start_button['text'] = 'Parar aquisição'

            guitools.runProcess(executablename=self.fileconfigs['executables']['Render'], path=self.realTimeRender, forceclose=True)
            self.server_connection.start_listen()
            self.server_status.configure(image=self.green_circle_img)
            
            self.change_state(mutables=self.mutable_wids, to='disabled')
            self.freq_sampling_meter.configure(interactive=False)
            
            mainLogger.logger.info('Começando aquisição de dados ...')
            self.aquisicao = True
            self.__pullSamples()
        
    def __pullSamples(self) -> None:
        
        if self.gravar_var.get() is True:
            self.status_update_var.set(value='Executando e gravando a aquisição de dados')
        else:
            self.status_update_var.set(value='Executando aquisição de dados')
        
        try:
            if self.analysis_var.get() == 'Amplitude':
                
                eeg_data, timestamp = self.bitalino.pull_sample(timeout=1)
                
                self.notebook.select(self.amp_meters_frame)
                
                self.sampling_rate = self.amp_sampling_meter.amountusedvar.get()
                
                dado_eeg = guitools.numpy.float32(eeg_data[self.bitalino_canal_int])
                
                hsv_prediction, self.freq_resulta_faixa = self.do_prediction_and_send_data(eegdata_or_freq=dado_eeg)
                
                if self.gravar_var.get() is True:
                    self.amp_runs += 1
                    self.amp_array = guitools.numpy.append(self.amp_array, [timestamp, dado_eeg, hsv_prediction])
                
            else:
                self.notebook.select(self.freq_meters_frame)
                self.sampling_rate = CHUNK_SIZE

                eeg_data, timestamp = self.bitalino.pull_chunk(timeout=1, max_samples=CHUNK_SIZE)

                eeg_data = guitools.numpy.array(eeg_data)[:,1].astype(dtype='float32') #chuk samples shape =  (500,) size =  500
                timestamp = guitools.numpy.array(timestamp, dtype='float32')              
                
                self.freq_samples = guitools.numpy.append(self.freq_samples, eeg_data)
                self.freq_timestamp = guitools.numpy.append(self.freq_timestamp, timestamp)
                
                if self.freq_samples.size >= self.freq_sampling_meter.amountusedvar.get(): #precision = 2000 == size of array 2000
                    frequency_analysis = guitools.frequency_analysis(eeg_data=self.freq_samples, precision=self.freq_sampling_meter.amountusedvar.get())
                   
                    hsv_prediction, self.freq_resulta_faixa = self.do_prediction_and_send_data(eegdata_or_freq=frequency_analysis['frequency'], faixa=frequency_analysis['faixa']) 
            
                    if self.gravar_var.get() is True:                            
                        self.freq_runs += 1
                        self.freq_results = guitools.numpy.append(self.freq_results, [self.freq_runs, self.freq_timestamp[-1], frequency_analysis['frequency'],
                                                                                      frequency_analysis['power'], hsv_prediction, frequency_analysis['faixa']])
                        self.freq_timesamples = guitools.numpy.append(self.freq_timesamples, (self.freq_samples, self.freq_timestamp))
                    
                    self.freq_samples  = guitools.numpy.array([])
                    self.freq_timestamp = guitools.numpy.array([])
                        
                self.color_label_var.set(value=f'Analisando amostras = {self.freq_samples.size}/{self.freq_sampling_meter.amountusedvar.get()}{" | " + self.freq_resulta_faixa if self.freq_resulta_faixa is not None else ""}')                    
                
        except (TypeError, UnboundLocalError) as error:
            mainLogger.logger.exception(error)

    def do_prediction_and_send_data(self, eegdata_or_freq: float, faixa: str | None = None) -> tuple[str, str] | tuple[str, None] :
      
        hsv_prediction: str = f'{self.model.predict([[eegdata_or_freq]])[0]}'

        if self.analysis_var.get() == 'Amplitude':
            self.color_label_var.set(value=f'Amplitude = {eegdata_or_freq:0.2f}uV')
            self.amp_hue_meter.amountusedvar.set(int(hsv_prediction))
            saturacao = self.amp_saturation_meter.amountusedvar.get()
            brilho = self.amp_value_meter.amountusedvar.get()
            resultado = None
            print(f'H = {hsv_prediction}| Dados do canal ativo: {eegdata_or_freq:0.2f}uV | ({self.selected_lumi_mode}, {hsv_prediction}, {saturacao}, {brilho})')

        else:
            resultado: str = f'Frequência = {eegdata_or_freq:0.2f}Hz | {faixa}'
            self.freq_hue_meter.amountusedvar.set(int(hsv_prediction))
            saturacao: int = self.freq_saturation_meter.amountusedvar.get()
            brilho: int = self.freq_value_meter.amountusedvar.get()
            print(f'Predição = {hsv_prediction}| H = {hsv_prediction}, S = {saturacao}, V = {brilho}')

        self.arduino.write(f"({self.selected_lumi_mode},{hsv_prediction},{saturacao},{brilho})\n".encode(guitools.ENCODING_FORMAT))

        hex_color, rgb_color = guitools.hsv_rgb_hex(int(hsv_prediction), saturacao, brilho)
        
        try:
            self.server_connection.connection.send(','.join(f'{color}' for color in rgb_color).encode(guitools.ENCODING_FORMAT)) #send example = 125,100,0
        except ConnectionResetError as error:
            self.main_window.after_cancel(self.after_action)
            self.aquisicao = False
            mainLogger.logger.error(error)
            guitools.Messagebox.show_error(f'Renderização fechada. Parando a execução da aquisição. {error}')
            self.__stop() #parar a aquisição? ou continuar normalmente? 
        
        self.color_label.configure(background=hex_color)

        return hsv_prediction, resultado

    def __queryStop(self) -> None:
        self.aquisicao = False
        mainLogger.logger.info(f'Usuário selecionou "Parar aquisição".')
        resp: None | str = guitools.Messagebox.yesno(message='Deseja parar a aquisição?', alert=True)

        if resp == 'Yes':
            self.__stop()
        else:
            self.aquisicao = True
            return mainLogger.logger.info('Usuário escolheu voltar para a aquisição')
    
    def __stop(self) -> None:
        mainLogger.logger.info('Parando a aquisição ...')
        self.bitalino.close_stream()
        self.arduino.close()
        mainLogger.logger.info('Arduino e Bitalino desconectados')

        if self.freq_runs != ZERO:
            guitools.salvar_dados(registros={'freq_time_samples':self.freq_timesamples, 'freq_results':self.freq_results},
                                  basepath=self.gravacao_basepath, nrows=self.freq_runs, 
                                  ncolumns=self.freq_sampling_meter.amountusedvar.get())

        if self.amp_runs != ZERO:
            guitools.salvar_dados(registros={'amp':self.amp_array}, basepath=self.gravacao_basepath, nrows=self.amp_runs)

        self.arduino_string_var.set('Conectar')
        self.arduino_statuslabel.configure(image=self.red_circle_img)
        self.server_status.configure(image=self.red_circle_img)
        self.start_button['text'] = 'Começar aquisição'
        self.start_button.configure(command=self.__start)
        self.freq_sampling_meter.configure(interactive=True)

        self.amp_runs = ZERO
        self.freq_runs = ZERO

        self.change_state(mutables=self.mutable_wids, to='enabled')

if __name__ == '__main__':
    app = EsquizoCap(size=(1680,1000))
    app.main_window.after(ms=10, func=app.do_check)
    app.main_window.mainloop()