"""O estado da aplicação, e a regra que decide qual é.

Antes, o estado era INFERIDO comparando strings de `StringVar` — e era reavaliado num
`after(10 ms)` que rodava para sempre, só para decidir qual frase mostrar no rótulo de
status. Polling de estado por string: caro, difícil de ler e impossível de testar.

Aqui o estado é explícito e a regra é uma FUNÇÃO PURA: entra um retrato das escolhas do
usuário, sai um estado e a mensagem correspondente. Nada de Tkinter neste módulo — é o
que permite testar todas as combinações sem abrir uma janela.

Quem chama a função é a GUI, e só quando algo muda (um combobox, o botão do Arduino) —
não a cada 10 ms.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from esquizocap.dominio.ciclo_aquisicao import ModoAnalise
from esquizocap.dominio.pre_processamento import FREQUENCIA_CORTE_SUPERIOR_HZ
from esquizocap.hardware.constantes import (
    CANAIS_BITALINO,
    MODOS_LUMINOSIDADE,
    RESOLUCAO_CANAIS_PRINCIPAIS,
    TAXAS_AMOSTRAGEM_SUPORTADAS,
    resolucao_bits,
)
from esquizocap.hardware.modo_aquisicao import modo_do_rotulo

TEXTO_CANAL_NAO_ESCOLHIDO: str = 'Selecione o canal ativo do Bitalino'

TEXTO_PORTA_NAO_ENCONTRADA: str = (
    'Nenhuma porta encontrada para este Bitalino. Verifique se ele está ligado e pareado no Windows'
)
"""Mora aqui, e não no controller, para que a regra de prontidão e o aviso da tela digam a
MESMA coisa — duas redações do mesmo problema fariam o operador achar que são dois."""

MODELOS_DISPONIVEIS: tuple[str, ...] = ('Preditor HSV baseado em Amplitude',)
"""Nomes dos modelos oferecidos no seletor.

Hoje há um só, e a escolha não muda nada: o caminho do modelo vem da configuração
(`Configuracao.caminho_modelo`). Ver PLANO_ACAO.md, item 1.10 — dívida preexistente,
não introduzida por esta integração. Vivia em `interface/textos.py` (Tkinter, hoje
arquivado); movida para cá porque é a única consumidora restante.
"""

# O combobox entrega o canal como texto; a constante do hardware é `int`. A conversão
# fica aqui, num lugar só, em vez de espalhar `str()` pela regra.
CANAIS_VALIDOS: frozenset[str] = frozenset(str(canal) for canal in CANAIS_BITALINO)


def rotulo_do_canal(canal: int) -> str:
    """Como o canal aparece no seletor: número e resolução do conversor.

    Os seis canais não são equivalentes, e a interface os apresentava como se fossem.
    A1–A4 têm 10 bits (1024 níveis); A5 e A6, apenas 6 (64 níveis). Num sinal de microvolts,
    64 níveis são quase todos degrau de quantização.

    Os canais de baixa resolução seguem selecionáveis — o eletrodo é físico, e quem já
    plugou no A5 precisa poder ler dali. O precedente do projeto para RESTRINGIR opções (só
    um baudrate é oferecido) não se aplica: lá a opção extra quebrava a comunicação, aqui
    ela só produz um sinal ruim, e quem monta a instalação pode ter suas razões.
    """
    bits = resolucao_bits(canal=canal)

    if bits < RESOLUCAO_CANAIS_PRINCIPAIS:
        return f'{canal} · {bits} bits (evite para EEG)'

    return f'{canal} · {bits} bits'


CANAIS_COM_ROTULO: tuple[tuple[int, str], ...] = tuple((canal, rotulo_do_canal(canal)) for canal in CANAIS_BITALINO)
"""Pares `(canal, rótulo)` na ordem do seletor.

FONTE ÚNICA da correspondência entre posição e canal. O rótulo mostra a resolução, então
não serve de valor, e a escolha na interface vai pela POSIÇÃO — se a lista de rótulos e a
de canais viessem de lugares diferentes, filtrar ou reordenar um lado deslocaria tudo sem
erro nenhum, e o operador escolheria o canal 3 adquirindo o 4.
"""

ROTULOS_DOS_CANAIS: tuple[str, ...] = tuple(rotulo for _canal, rotulo in CANAIS_COM_ROTULO)
"""Só os rótulos, para alimentar o seletor."""

CANAIS_NA_ORDEM_DO_SELETOR: tuple[int, ...] = tuple(canal for canal, _rotulo in CANAIS_COM_ROTULO)
"""Só os canais, na mesma ordem — é o que traduz posição escolhida em canal."""


def aviso_do_canal(canal: int) -> str:
    """O custo de usar este canal para EEG, quando há um. Vazio quando não há.

    Existe além do rótulo porque o rótulo some assim que o dropdown fecha, e a escolha
    permanece — o aviso fica visível enquanto o canal estiver selecionado.
    """
    bits = resolucao_bits(canal=canal)

    if bits >= RESOLUCAO_CANAIS_PRINCIPAIS:
        return ''

    niveis = 2**bits
    return (
        f'O canal {canal} tem {bits} bits ({niveis} níveis) contra {2**RESOLUCAO_CANAIS_PRINCIPAIS} '
        'dos canais 1 a 4. Para EEG, boa parte do sinal vira degrau de quantização e a banda '
        'dominante fica instável.'
    )


def taxa_minima_para_analise_espectral() -> int:
    """A menor taxa acordada com que a análise espectral ainda vale alguma coisa.

    Nyquist: observar um componente de F Hz exige amostrar ACIMA de 2F. A referência é
    `FREQUENCIA_CORTE_SUPERIOR_HZ`, o teto que `categorizar_frequencia` usa para o topo de
    Gamma — é o classificador real, e não a tabela exibida na interface.

    O valor devolvido é exatamente 2F, ou seja, o LIMITE e não uma folga: nele a banda mais
    alta cai na borda e começa a sofrer aliasing. É aceito de propósito, porque abaixo disso
    a análise deixa de ter sentido algum, enquanto na borda ela ainda serve com ressalva —
    e é `aviso_de_taxa` quem comunica essa ressalva.

    NOTA: `interface_qt/bandas_eeg.py` exibe Gamma como 30–45 Hz, enquanto
    `categorizar_frequencia` classifica 30–50. A divergência é anterior a esta função; aqui
    vale o classificador, que é quem decide a cor. Ver `docs/notas-futuras.md`.
    """
    return int(2 * FREQUENCIA_CORTE_SUPERIOR_HZ)


def taxas_selecionaveis(modo_analise: str) -> tuple[int, ...]:
    """As taxas acordadas que fazem sentido para o modo de predição escolhido.

    No modo **Amplitude**, todas: cada amostra vira uma cor, sem análise espectral. Taxa
    baixa é até desejável ali — casa o ritmo de leitura com o do dispositivo, e evita que o
    buffer acumule atraso (ver `LeitorBitalino.ler_amostra`).

    No modo **Frequência**, só as que alcançam as bandas. As outras não falham: a FFT roda,
    devolve uma frequência dominante e a classifica numa banda que o sinal não pode conter.
    O resultado é cor errada, sem erro nenhum — por isso a interface as desabilita em vez de
    apenas avisar.
    """
    if modo_analise == ModoAnalise.FREQUENCIA.value:
        minima = taxa_minima_para_analise_espectral()
        return tuple(taxa for taxa in TAXAS_AMOSTRAGEM_SUPORTADAS if taxa >= minima)

    return TAXAS_AMOSTRAGEM_SUPORTADAS


def aviso_de_taxa(taxa_hz: int, modo_analise: str) -> str:
    """O que a taxa escolhida custa, quando custa algo. Vazio quando não há o que dizer.

    A taxa mínima passa no gate mas fica EXATAMENTE em Nyquist: a banda mais alta cai na
    borda, onde o aliasing começa. É diferente de estar errada, e o operador precisa poder
    escolher sabendo.
    """
    if modo_analise != ModoAnalise.FREQUENCIA.value:
        return ''

    if taxa_hz == taxa_minima_para_analise_espectral():
        return (
            f'A {taxa_hz} Hz, a banda Gamma fica na borda de Nyquist e pode sofrer aliasing. '
            'Use 1000 Hz para a análise de frequência completa.'
        )

    return ''


class EstadoApp(Enum):
    """Em que ponto do fluxo a aplicação está.

    As transições legítimas são:

        CONFIGURANDO <-> PRONTO --> ADQUIRINDO --> PARANDO --> CONFIGURANDO

    Não há transição de ADQUIRINDO de volta para PRONTO: parar a aquisição desconecta o
    hardware, e reconectar é passar por CONFIGURANDO de novo.
    """

    CONFIGURANDO = auto()
    """Falta alguma escolha do usuário. O botão de começar não deve funcionar."""

    PRONTO = auto()
    """Modelo, Arduino (conectado) e BITalino escolhidos. Pode começar."""

    ADQUIRINDO = auto()
    """A thread de aquisição está rodando. Os widgets de configuração ficam travados."""

    PARANDO = auto()
    """Parada pedida: esperando a thread terminar e o hardware fechar.

    É um estado de verdade, e não um instante: a thread pode levar até ~1 s para
    perceber o pedido, se estiver no meio de uma leitura bloqueante. Sem este estado, um
    segundo clique no botão durante a espera pediria a parada duas vezes.
    """


@dataclass(frozen=True)
class SelecaoUsuario:
    """Retrato do que o usuário escolheu na interface, já como valores simples.

    Existe para que a regra de prontidão não precise conhecer widget nenhum: a GUI lê os
    seus `StringVar` uma vez e monta isto.
    """

    modelo: str
    porta_arduino: str
    modo_luminosidade: str
    arduino_conectado: bool
    canal_bitalino: str
    mac_bitalino: str
    modo_aquisicao: str
    modo_analise: str
    taxa_amostragem_hz: int
    porta_bitalino: str
    """Porta de acesso do BITalino, DERIVADA do MAC — não escolhida pelo operador.

    Vazia quando o modo não precisa dela (Modo OpenSignals) ou quando a derivação não achou
    o dispositivo. A regra abaixo distingue os dois casos.
    """


def avaliar_prontidao(selecao: SelecaoUsuario, macs_validos: Sequence[str]) -> tuple[EstadoApp, str]:
    """Diz se dá para começar a aquisição, e o que falta caso não dê.

    A ordem das checagens é a ordem em que o usuário preenche a tela — modelo, Arduino,
    BITalino —, então a mensagem sempre aponta o PRÓXIMO passo, e não uma pendência
    qualquer lá do fim.

    Args:
        selecao: O que está escolhido na interface agora.
        macs_validos: Os MACs aceitos, vindos da configuração.

    Returns:
        `(CONFIGURANDO, "o que fazer a seguir")` ou `(PRONTO, "pode começar")`.
    """
    if selecao.modelo not in MODELOS_DISPONIVEIS:
        return EstadoApp.CONFIGURANDO, 'Selecione o modelo de machine learning'

    if 'COM' not in selecao.porta_arduino or selecao.modo_luminosidade not in MODOS_LUMINOSIDADE:
        return EstadoApp.CONFIGURANDO, 'Configure o Arduino'

    if selecao.arduino_conectado is False:
        return EstadoApp.CONFIGURANDO, 'Arduino configurado! Pressione "Conectar"'

    if selecao.canal_bitalino not in CANAIS_VALIDOS or selecao.mac_bitalino not in macs_validos:
        return EstadoApp.CONFIGURANDO, 'Configure o Bitalino'

    try:
        modo = modo_do_rotulo(selecao.modo_aquisicao)
    except ValueError:
        return EstadoApp.CONFIGURANDO, 'Selecione o modo de aquisição do Bitalino'

    if modo.exige_porta_de_acesso:
        if not selecao.porta_bitalino:
            return EstadoApp.CONFIGURANDO, f'{TEXTO_PORTA_NAO_ENCONTRADA}, ou use o Modo OpenSignals.'

        # A porta do Arduino vem como "COM5 - descrição"; comparar só o prefixo até o " - ".
        porta_arduino = selecao.porta_arduino.split(' - ')[0].strip()
        if porta_arduino.upper() == selecao.porta_bitalino.upper():
            return EstadoApp.CONFIGURANDO, (
                f'Arduino e Bitalino não podem usar a mesma porta ({selecao.porta_bitalino}). '
                'Confira qual é a porta de cada um.'
            )

        # A taxa só é cobrada no Modo Direto: no Modo OpenSignals quem a fixa é o próprio
        # OpenSignals, e a escolha desta tela nem chega ao leitor.
        if selecao.taxa_amostragem_hz not in taxas_selecionaveis(selecao.modo_analise):
            return EstadoApp.CONFIGURANDO, (
                f'A taxa de {selecao.taxa_amostragem_hz} Hz não alcança as bandas de EEG do modo '
                f'Frequência. Escolha ao menos {taxa_minima_para_analise_espectral()} Hz.'
            )

    return EstadoApp.PRONTO, 'Pressione "Começar aquisição"'


def mensagem_de_aquisicao(gravando: bool) -> str:
    """A frase do rótulo de status enquanto a aquisição roda."""
    if gravando:
        return 'Executando e gravando a aquisição de dados'
    return 'Executando aquisição de dados'
