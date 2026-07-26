"""Escolhe entre as implementações reais e as fakes de cada borda de hardware.

A seleção tem **duas fontes**, nesta ordem de precedência:

1. A variável de ambiente `ESQUIZOCAP_FAKE`, quando definida. Serve ao desenvolvimento,
   aos testes e à CI.
2. O parâmetro `simulados`, que a aplicação preenche a partir do menu de configurações
   (`infraestrutura/preferencias.py`).

O ambiente vence de propósito: quem exportou a variável está depurando ou rodando um
teste, e uma preferência gravada num boot anterior não pode desfazer isso em silêncio.
Quando o ambiente manda, a interface mostra os controles de simulação desabilitados e diz
por quê — em vez de deixar dois donos da mesma decisão discordarem sem aviso.

Valores aceitos em `ESQUIZOCAP_FAKE`:
    - vazio ou ausente: a decisão fica com o parâmetro `simulados`.
    - `1`, `true` ou `tudo`: usa fake para todos os componentes.
    - lista separada por vírgula: usa fake só nos componentes citados,
      ex.: `arduino` ou `arduino,bitalino`.
"""

import os

from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_direto import BitalinoDireto
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.contratos import ControladorLedArduino, LeitorBitalino
from esquizocap.hardware.modo_aquisicao import ModoAquisicao

NOME_VARIAVEL_FAKE: str = 'ESQUIZOCAP_FAKE'
VALORES_PARA_TODOS: frozenset[str] = frozenset({'1', 'true', 'tudo', 'all'})
COMPONENTES_CONHECIDOS: frozenset[str] = frozenset({'arduino', 'bitalino'})


def simulacao_vem_do_ambiente() -> bool:
    """Indica se `ESQUIZOCAP_FAKE` está mandando, ignorando a preferência do usuário.

    A interface usa isto para desabilitar os controles de simulação e explicar o motivo.
    """
    return bool(os.environ.get(NOME_VARIAVEL_FAKE, '').strip())


def componentes_simulados(simulados: frozenset[str] | None = None) -> set[str]:
    """Devolve os componentes que devem ser simulados.

    Args:
        simulados: A escolha do usuário, vinda das preferências. Ignorada quando
            `ESQUIZOCAP_FAKE` está definida.
    """
    valor: str = os.environ.get(NOME_VARIAVEL_FAKE, '').strip().lower()

    if not valor:
        return set(simulados or ())

    if valor in VALORES_PARA_TODOS:
        return set(COMPONENTES_CONHECIDOS)

    return {componente.strip() for componente in valor.split(',') if componente.strip()}


def usar_fake(componente: str, simulados: frozenset[str] | None = None) -> bool:
    """Indica se um componente específico deve ser simulado."""
    return componente in componentes_simulados(simulados)


def criar_arduino(simulados: frozenset[str] | None = None) -> ControladorLedArduino:
    """Cria o controlador da fita de LED, real ou simulado."""
    if usar_fake('arduino', simulados):
        return ArduinoFake()
    return ArduinoSerial()


def criar_bitalino(simulados: frozenset[str] | None = None) -> LeitorBitalino:
    """Cria o leitor de EEG do Modo OpenSignals, real ou simulado.

    O fake sai daqui em TEMPO REAL: quem o consome é a thread de aquisição, que lê em
    laço contínuo. Um gerador que entrega amostras instantaneamente faria esse laço
    queimar uma CPU inteira e simular horas de EEG em segundos. Os testes constroem o
    `BitalinoSintetico` direto, sem tempo real, justamente para não pagar esse relógio.
    """
    if usar_fake('bitalino', simulados):
        return BitalinoSintetico(tempo_real=True)
    return BitalinoLSL()


def criar_leitores_por_modo(simulados: frozenset[str] | None = None) -> dict[ModoAquisicao, LeitorBitalino]:
    """Cria um leitor para CADA modo de aquisição, de uma vez.

    Os dois nascem no arranque porque os construtores são inertes — nada toca o hardware
    até `conectar`. Mantê-los vivos não custa recurso nenhum e evita que a referência ao
    leitor vire um opcional que precisa de guarda em todo uso.

    Com o BITalino simulado, o MESMO leitor sintético responde pelos dois modos: a escolha
    do operador deixa de ter efeito, e a interface precisa dizer isso em vez de fingir que
    a opção funciona.
    """
    if usar_fake('bitalino', simulados):
        sintetico = BitalinoSintetico(tempo_real=True)
        return {modo: sintetico for modo in ModoAquisicao}

    return {
        ModoAquisicao.OPENSIGNALS: BitalinoLSL(),
        ModoAquisicao.DIRETO: BitalinoDireto(),
    }
