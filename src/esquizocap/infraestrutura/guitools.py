import json
import logging
import os
import subprocess
import time
from pathlib import Path
from tkinter.filedialog import askdirectory

import numpy
import pandas as pd
import psutil
from ttkbootstrap.dialogs import Messagebox, Querybox

from esquizocap.infraestrutura import settings

ENCODING_FORMAT = 'utf-8'
DEPENDENCIES: list[str] = ['engine', 'images', 'logs', 'models', 'settings']

for directory in DEPENDENCIES:
    dir_path: Path = Path.cwd().joinpath(directory)
    print(dir_path)
    if dir_path.exists() is False:
        dir_path.mkdir(parents=True, exist_ok=True)

class SetLogger():
    def __init__(self, namelogger: str, logfilepath: str, level: str | None = 'DEBUG') -> None:
        """_summary_

        Args:
            logfilepath (str): _description_
            level (str | None, optional): _description_. Defaults to 'DEBUG'.
        """
        if level.upper() not in logging._nameToLevel:
            level = 'DEBUG'
            
        self.logger: logging.Logger = logging.getLogger(namelogger)
        self.logger.setLevel(logging._nameToLevel[level.upper()])
        
        self.logfilepath: str = rf'{logfilepath.split(".")[0]}_{time.strftime(r"%d_%m_%Y_%H_%M_%S", time.localtime())}.log'

        self.logFormat = logging.Formatter(fmt='%(asctime)s:%(filename)s: %(name)s: %(levelname)s: %(funcName)s -> %(message)s')

        self.logFileHandler = logging.FileHandler(self.logfilepath, encoding=ENCODING_FORMAT)
        self.logFileHandler.setFormatter(self.logFormat)

        self.logStremHandler = logging.StreamHandler()
        self.logStremHandler.setFormatter(self.logFormat)

        self.logger.addHandler(self.logFileHandler)
        self.logger.addHandler(self.logStremHandler)
        
        self.logger.info(f'Logger "{namelogger}" iniciado')
        
guilogger: SetLogger = SetLogger(logfilepath=r'logs\EsquizoCapLogs.log', namelogger='guitoolsLogger')

def create_folder(appbasepath: str | Path) -> str:
    """_summary_

    Args:
        appbasepath (str): _description_

    Returns:
        str: _description_
    """
    data_path: Path = Path.home()/'Documents'/'EsquizoCap'/'Data'
    
    if data_path.exists() is False:
        guilogger.logger.warning(msg=f'Caminho "{data_path}" não encontrado. Criando pastas necessárias ...')
        data_path.mkdir(parents=True, exist_ok=True)
        
    guilogger.logger.info(msg=f'App path = {appbasepath}, data files path = {data_path}')
    return data_path

def loadconfigs(apppath: str | Path) -> dict | None:
    """_summary_

    Args:
        apppath (str): _description_

    Returns:
        dict | None: _description_
    """
    settingsJsonFilePath: Path = apppath.joinpath(r'settings\configs.json')
    guilogger.logger.info(msg=f'File settings path = {settingsJsonFilePath}')
    if settingsJsonFilePath.exists():
        try:
            with open(settingsJsonFilePath, 'r', encoding=ENCODING_FORMAT) as json_open:
                guilogger.logger.info('Arquivo de configurações carregado com sucesso!')
                return json.load(json_open)
        except (json.JSONDecodeError, TypeError, OSError, FileNotFoundError) as error:
            msg: str = f'O seguinte problema com o arquivo de configurações foi encontrado: {error}'
            guilogger.logger.error(msg)
            return Messagebox.show_error(message=msg)
    else:
        msg: str = 'Arquivo de configurações não encontrado! Recriando arquivo ...'
        guilogger.logger.error(msg)
        settings.create_settings_file()
        with open(settingsJsonFilePath, 'r', encoding=ENCODING_FORMAT) as json_open:
            guilogger.logger.info('Arquivo de configurações carregado com sucesso!')
            return json.load(json_open)

def findFilePath(filename: str, jsonconfig: dict = None, basepath: str = r'C:\\') -> str | None:
    """Encontra o caminho de um arquivo.\n
    Essa função busca, a partir de uma pasta base do sistema, um arquivo especificado pelo usuário.

    Args:
        name (str): Nome do arquivo executável, exemplo: 'OpenSignals.exe'.
        path (str): Diretório base para começar a busca, exemplo: 'C:\\'

    Returns:
        None caso o arquivo não seja encontrado ou a string contendo o caminho.
    """

    jsonconfig = {} if jsonconfig is None else jsonconfig

    if filename in jsonconfig:
        if os.path.exists(jsonconfig[filename]):
            guilogger.logger.info(f'Executável "{filename}" encontrado em: "{jsonconfig[filename]}"')
            return jsonconfig[filename]
        else:
            guilogger.logger.error(f'"{filename}" não encontrado no computador a partir do caminho salvo anteriormente. Buscando caminho do arquivo...')
            return __find(filename, jsonconfig, basepath)
    else:
        guilogger.logger.error(f'"{filename}" não encotrado no arquivo de configurações. Buscando e armazenando o caminho do arquivo...')
        return __find(filename, jsonconfig, basepath)
    
def __find(filename: str, jsonconfig: dict = None, basepath: str = r'C:\\') -> str | None:
    for root, _, files in os.walk(basepath):
        if filename in files:
            guilogger.logger.info(f'Executável "{filename}" encontrado em: "{root}"')
            jsonconfig[filename] = os.path.join(root, filename)
            with open(r'settings\configs.json', mode='w', encoding=ENCODING_FORMAT) as file:
                json.dump(jsonconfig, file, indent=2)
                guilogger.logger.info(f'"{jsonconfig[filename]}" adicionado ao arquivo "{file.name}" na chave "{filename}"')
            return os.path.join(root, filename)
    
    msg: str = f'Executável {filename} não encontrado no computador!'
    guilogger.logger.error(msg)
    return Messagebox.show_error(msg)

def __verify_files():
    pass

def runProcess(executablename: str, path: str, forceclose: bool = False) -> None:
    """Inicializa um processo ou executável.

    Args:
        executableName (str): Nome do arquivo executável que será inicializado
        path (str): Caminho do arquivo executável
        forceclose (bool, optional): True se deseja que o processo seja reinicializado. Defaults to False.

    Returns:
        _type_: _description_
    """
    process_isrunning = False

    for process in psutil.process_iter():
        if process.name() == executablename:
            guilogger.logger.info(f'{executablename} already running')
            process_isrunning = True
            if forceclose == True:
                kill_process(executablename)
                guilogger.logger.info(f'Processo "{executablename}" encerrado!')
                process_isrunning = False

    if process_isrunning is False:         
        try:
            subprocess.Popen([path], shell=False)
            return guilogger.logger.info(f"{executablename} is now running.")
        except OSError as e:
            msg: str = f'Não foi possível inicializar "{executablename}". Erro = {e}'
            guilogger.logger.error(msg, exc_info=True)
            return Messagebox.show_error(msg)

def kill_process(executablename): #TODO: melhorar essa função! ele é repetida com a de runProcess
    for process in psutil.process_iter():
        if process.name() == executablename:
            os.system(f'taskkill /f /im  {executablename}')
            return guilogger.logger.info(f'"{executablename}" encerrado!')
        
    return guilogger.logger.info(f'"{executablename}" não está sendo executado')

def canais_bitalino(**kwargs) -> None:
    if isinstance(kwargs['canais'], list):
        kwargs['box']['values'] = kwargs['canais']

def salvar_dados(registros: dict, basepath: str = None, nrows: int = None, ncolumns: int = None) -> None:
    guilogger.logger.info('Salvando dados da aquisição')
    guilogger.logger.debug(f'Base path de salvamento dos dados = {basepath}')

    if 'freq_time_samples' in registros: 
        
        tipo = 'Frequência'
        guilogger.logger.info('Salvando os dados de Frequência')

        time_samples = registros['freq_time_samples'].reshape(nrows*2, ncolumns)
        time_samples = pd.DataFrame(time_samples, dtype='float32')

        resultados = registros['freq_results'].reshape(nrows, 6)
        resultados = pd.DataFrame(resultados)
        resultados.rename(columns={0:'Rodada', 1:'Timestamp', 2:'Frequência Dominante', 3:'Power', 4:'Predição de cor', 5:'Faixa de Frequência'}, inplace=True)

        for columns in (resultados.loc[:,['Rodada','Predição de cor']]):
            resultados[columns] = resultados[columns].astype(dtype='uint8')
        for columns in resultados.loc[:,'Timestamp':'Power']:
            resultados[columns] = resultados[columns].astype(dtype='float32')
        resultados['Faixa de Frequência'] = resultados['Faixa de Frequência'].astype(dtype='category')

        arq_name: str = f'Gravação {tipo}_{time.strftime("%d_%m_%Y_%H_%M_%S", time.localtime())}'
        nome_arquivo: str = f'{Querybox.get_string(prompt=f"Dê um nome para o arquivo EXCEL com os dados de {tipo}:", initialvalue=arq_name)}.xlsx'
        guilogger.logger.info(f"Nome de arquivo escolhido pelo usuário: {nome_arquivo}")
        
        try:
            time_samples.to_excel(rf"{basepath}\{nome_arquivo}", index=False, sheet_name='Data')

            with pd.ExcelWriter(rf'{basepath}\{nome_arquivo}', mode='a', engine='openpyxl', if_sheet_exists='new') as excel_writer:
                resultados.to_excel(excel_writer, sheet_name=f'Analysis', index=False)

            return guilogger.logger.info(f'Dados salvos com sucesso em {f"{basepath}\\{nome_arquivo}"}')

        except (PermissionError, ValueError) as error:
            guilogger.logger.error(f'Não foi possível salvar a aquisição. Erro = {error}')
            return Messagebox.show_error(title='Erro no salvamento de dados!', message=f'Não foi possível salvar a aquisição. Erro = {error}')

    elif 'amp' in registros: #(timestamp, dado_eeg, hsv_prediction)
        
        tipo = 'Amplitude'
        guilogger.logger.info('Salvando os dados de Amplitude')

        time_samples = registros['amp'].reshape(nrows, 3)
        time_sample_data = pd.DataFrame(time_samples)
        time_sample_data.rename(columns={0:'Timestamp', 1:'Dados EEG', 2:'HSV Prediction'}, inplace=True)
        time_sample_data['Timestamp'] = time_sample_data['Timestamp'].astype(dtype='float32')
        time_sample_data['Dados EEG'] = time_sample_data['Dados EEG'].astype(dtype='float32')
        time_sample_data['HSV Prediction'] = time_sample_data['HSV Prediction'].astype(dtype='uint8')

        arq_name = f'Gravação {tipo}_{time.strftime("%d_%m_%Y__%H_%M_%S", time.localtime())}'

        try:
            nome_arquivo = f'{Querybox.get_string(prompt=f"Dê um nome para o arquivo EXCEL com os dados de {tipo}:", initialvalue=arq_name)}.xlsx'
            guilogger.logger.info(f"Nome de arquivo escolhido pelo usuário: {nome_arquivo}")
            time_sample_data.to_excel(rf"{basepath}\{nome_arquivo}", index=False, sheet_name='Data')
            return guilogger.logger.info(f'Dados salvos com sucesso em {rf"{basepath}\{nome_arquivo}"}')

        except (PermissionError, ValueError) as error:
            guilogger.logger.error(f'Não foi possível salvar a aquisição. Erro = {error}')
            return Messagebox.show_error(title='Erro no salvamento de dados!', message=f'Não foi possível salvar a aquisição. Erro = {error}')

