"""O que o usuário escolheu na tela de configuração.

É um dataclass MUTÁVEL de propósito: a view altera um campo de cada vez (um slider,
um dropdown), e cada alteração passa pelo `EsquizoController`, que decide se precisa
reavaliar a prontidão e/ou empurrar o novo valor para a thread de aquisição. Não há
necessidade de imutabilidade aqui como há em `ControlesUsuario`
(`dominio/ciclo_aquisicao.py`), que atravessa a fronteira da thread — este objeto
nunca sai da GUI thread.
"""

from dataclasses import dataclass

from esquizocap.dominio.ciclo_aquisicao import ModoAnalise
from esquizocap.hardware import constantes
from esquizocap.hardware.modo_aquisicao import MODO_AQUISICAO_PADRAO
from esquizocap.interface_qt.estado import MODELOS_DISPONIVEIS


@dataclass
class ConfiguracaoSelecionada:
    """Escolhas do usuário que precisam persistir entre ajustes e o início da aquisição."""

    modo_analise: str
    """`ModoAnalise.AMPLITUDE.value` ou `ModoAnalise.FREQUENCIA.value`."""

    modo_luminosidade: int
    """Índice (base 1) do modo de animação da fita de LED — ver `hardware/constantes.py`."""

    saturacao: int
    """Saturação do HSV enviado ao Arduino, de 0 a 255."""

    brilho: int
    """Brilho do HSV enviado ao Arduino, de 0 a 255."""

    intervalo_amostragem_ms: int
    """Intervalo entre predições no modo Amplitude, em milissegundos."""

    tamanho_janela_amostras: int
    """Tamanho do bloco acumulado antes de prever, no modo Frequência."""

    gravar_aquisicao: bool
    """Se a aquisição em andamento deve ser oferecida para exportação ao terminar."""

    sensor: str
    """Rótulo do tipo de sensor exibido na tela — estado de UI puro, não alimenta
    nada em `hardware/` nem `dominio/` hoje."""

    modelo_selecionado: str
    """Um dos nomes em `MODELOS_DISPONIVEIS`."""

    porta_arduino: str
    baud_rate: str
    canal_bitalino: str
    mac_bitalino: str
    tela_cheia: bool

    taxa_amostragem_hz: int
    """Taxa acordada para a aquisição, em Hz.

    Só tem efeito no Modo Direto: no Modo OpenSignals a taxa é fixada dentro do OpenSignals,
    e o leitor ignora este valor.
    """

    modo_aquisicao: str
    """Rótulo do modo de aquisição escolhido — ver `hardware/modo_aquisicao.py`.

    A porta de acesso NÃO mora aqui: ela é derivada do MAC a cada consulta, e guardá-la
    criaria uma segunda fonte de verdade que envelhece quando o operador troca de
    dispositivo ou repareia o BITalino.
    """


def criar_configuracao_inicial(
    porta_arduino_inicial: str, canal_bitalino_inicial: str, mac_bitalino_inicial: str
) -> ConfiguracaoSelecionada:
    """Monta a configuração com os valores padrão da tela, mais o que foi descoberto
    em tempo de execução (primeira porta serial listada, primeiro canal, primeiro MAC).
    """
    return ConfiguracaoSelecionada(
        modo_analise=ModoAnalise.FREQUENCIA.value,
        modo_luminosidade=2,
        saturacao=227,
        brilho=196,
        intervalo_amostragem_ms=900,
        tamanho_janela_amostras=500,
        gravar_aquisicao=True,
        sensor="EEG",
        modelo_selecionado=MODELOS_DISPONIVEIS[0],
        porta_arduino=porta_arduino_inicial,
        baud_rate=str(constantes.BAUDRATE_PADRAO),
        canal_bitalino=canal_bitalino_inicial,
        mac_bitalino=mac_bitalino_inicial,
        tela_cheia=False,
        taxa_amostragem_hz=constantes.TAXA_AMOSTRAGEM_PADRAO_HZ,
        modo_aquisicao=MODO_AQUISICAO_PADRAO.value,
    )
