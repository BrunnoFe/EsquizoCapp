"""Textos e temas da interface.

Isto é conteúdo de UI, não configuração: as tooltips explicam a interface para quem a
está usando, e mudam junto com ela. Ficavam no `configs.json`, misturadas com endereços
MAC e caminhos de executável.
"""

TEMAS: tuple[str, ...] = (
    'cyborg',
    'solar',
    'vapor',
    'journal',
    'pulse',
    'litera',
    'sandstone',
    'lumen',
    'simplex',
    'cosmo',
    'minty',
    'flatly',
)
"""Temas do ttkbootstrap oferecidos na interface."""

MODELOS_DISPONIVEIS: tuple[str, ...] = ('Preditor HSV baseado em Amplitude',)
"""Nomes dos modelos oferecidos no combobox.

Hoje há um só, e a escolha não muda nada: o caminho do modelo vem da configuração. Ver
PLANO_ACAO.md, item 1.10.
"""

TOOLTIPS: dict[str, str] = {
    'amp_hue_meter': 'Valor do HUE no padrão de cores HSV determinado pelo modelo',
    'amp_sampling_meter': 'Uma amostra de dados será capturada a cada milissegundos',
    'amp_saturation_meter': 'Valor da Saturação da cor no padrão de cores HSV',
    'amp_value_meter': 'Brilho da cor no padrão HSV',
    'freq_hue_meter': 'Valor do HUE no padrão de cores HSV determinado pelo modelo',
    'freq_sampling_meter': (
        'Quantidade de amostras acumuladas antes de cada análise de frequência '
        '(a taxa de amostragem vem do próprio dispositivo)'
    ),
    'freq_saturation_meter': 'Valor da Saturação da cor no padrão de cores HSV',
    'freq_value_meter': 'Brilho da cor no padrão HSV',
    'theme_box': 'Modifique as cores do aplicativo selecionando algum dos temas disponíveis neste menu',
    'model_box': 'Modelos de machine learning disponíveis para a predição das cores',
    'gravar_button': 'Marque esta opção para gravar a aquisição de dados',
    'arduino_ports_box': (
        "Selecione a porta USB (ex: 'COM5 CH340') ou link por Bluetooth em que o Arduino está conectado"
    ),
    'arduino_vel_box': 'Velocidade de comunicação da porta serial',
    'arduino_lumin_box': (
        "'Um a um': um led muda de cor a cada 5ms até que toda fita esteja completa\n"
        "'Todos': todos os LEDs mudam de cor ao mesmo tempo\n"
        "'Gradiente': todos os LEDs mudam de cor de forma gradual entre a cor antiga e a nova\n"
        "'A partir do centro': os LEDs mudam de cor a partir do centro da fita para as extremidades"
    ),
    'arduino_button': 'Pressione para conectar o arduino',
    'bitalino_canais_box': 'Selecione o canal do Bitalino que será utilizado durante a aquisição',
    'bitalino_mac_box': (
        'Código de identificação do dispositivo utilizado.\n'
        'O endereço MAC do Bitalino pode ser encontrado no aplicativo do OpenSignals '
        '(exemplo: 20:17:09:18:60:29)'
    ),
    'analysis_box': (
        'Amplitude: o modelo irá predizer a cor com base na amplitude do sinal EEG\n'
        'Frequência: com base na frequência dominante de um período analisado, o modelo irá '
        'predizer a cor correspondente'
    ),
    'start_button': 'Clique para começar a aquisição dos dados',
}
