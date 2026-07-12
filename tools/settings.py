import json

settings: dict = {
  "icon":"images\\esquizo_ico.ico",
  "title_photo":"images\\esquizo.png",
  "green_circle":"images\\green_circle.png",
  "red_circle":"images\\red_circle.png",
  "velocidades": [
    300,
    600,
    1200,
    2400,
    4800,
    9600,
    14400,
    19200,
    28800,
    31250,
    38400,
    57600,
    115200
  ],
  "velocidade_pre": [
    9600
  ],
  "modos": [
    "Um a um",
    "Todos",
    "Gradiente",
    "A partir do Centro"
  ],
  "canais_bitalino": [
    1,
    2,
    3,
    4,
    5,
    6
  ],
  "mac_addr": [
    "20:17:09:18:60:29",
    "12:25:33:81:92:44"
  ],
  "nofrows": [
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8
  ],
  "nofcolumns": [
    0,
    1,
    2,
    3,
    4
  ],
  "analysis_mode": [
    "Frequ\u00eancia",
    "Amplitude"
  ],
  "themes": [
    "cyborg",
    "solar",
    "vapor",
    "journal",
    "pulse",
    "litera",
    "sandstone",
    "lumen",
    "simplex",
    "cosmo",
    "minty",
    "flatly"
  ],
  "models_path": {
    "amp": "models\\BestModel_HSV_v1.pickle",
    "freq": "models\\BestModel_HSV_v1.pickle"
  },
  "models": [
    "Preditor HSV baseado em Amplitude"
  ],
  "executables": {
    "OpenSignals": "OpenSignals.exe",
    "Render": "Learning_Shaders.exe"
  },
  "OpenSignals.exe": "C:\\Plux\\OpenSignals (r)evolution\\OpenSignals.exe",
  "Learning_Shaders.exe": "C:\\Users\\Algu\u00e9m\\Documents\\0_EsquizoCap\\engine\\Learning_Shaders.exe",
  "tips":{
    "amp_hue_meter" : "Valor do HUE no padrão de cores HSV determinado pelo modelo",
    "amp_sampling_meter" : "Uma amostra de dados será capturada a cada milissegundos",
    "amp_saturation_meter" : "Valor da Saturação da cor no padrão de cores HSV",
    "amp_value_meter" : "Brilho da cor no padrão HSV",
    "freq_hue_meter" : "Valor do HUE no padrão de cores HSV determinado pelo modelo",
    "freq_sampling_meter" : "Quantidade de dados que serão capturados em segundos (ex: 5000 ms são 5 segundos de dados para analise de frequência)",
    "freq_saturation_meter" : "Valor da Saturação da cor no padrão de cores HSV",
    "freq_value_meter" : "Brilho da cor no padrão HSV",
    "theme_box":"Modifique as cores do aplicativo selecionando algum dos temas disponíveis neste menu",
    "model_box":"Modelos de machine learning disponíveis para a predição das cores",
    "gravar_button":"Marque esta opção para gravar a aquisição de dados",
    "arduino_ports_box":"Selecione a porta USB (ex: 'COM5 CH340') ou link por Bluetooth o Arduino esta conectado",
    "arduino_vel_box":"Velocidade de comunicação da porta serial",
    "arduino_lumin_box":"'Um a um': um led muda de cor a cada 5ms até que toda fita esteja completa\n'Todos': todos os LEDs mudam de cor ao mesmo tempo\n'Gradiente': todos os LEDs mudam de cor de forma gradual entre a cor antiga e a nova\n'A partir do centro': os LEDs mudam de cor a paritr do centro da fita para a extremidades",
    "arduino_button":"Pressione para conectar o arduino",
    "bitalino_canais_box":"Selecione os canais Bitalino que serão utilizados durante a aquisição",
    "bitalino_mac_box":"Código de identificação do dispositivo utilizado.\nO endereço MAC do Bitalino pode ser encontrado no aplicativo do OpenSignals (exemplo: 20:17:09:18:60:29)",
    "analysis_box":"Amplitude: o modelo irá predizer a cor com base nas diferenças entre picos e vales dos sinais EEG analisados\nFrequência: com base na frequência dominante de um período analisado, o modelo irá predizer a cor correspondente",
    "start_button":"Clique para começar a aquisição dos dados"
  }
}

def create_settings_file() -> None:
    
    json_object: str = json.dumps(settings, indent=4)
    
    with open(r"settings\configs.json", "x", encoding='utf-8') as outfile:
      outfile.write(json_object)

if __name__ == '__main__':
    create_settings_file()