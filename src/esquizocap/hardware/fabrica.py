"""Escolhe entre as implementações reais e as fakes de cada borda de hardware.

A seleção vem da variável de ambiente `ESQUIZOCAP_FAKE`, para que a app rode sem
hardware plugado.

Valores aceitos em `ESQUIZOCAP_FAKE`:
    - vazio ou ausente: usa todo o hardware real (comportamento padrão).
    - `1`, `true` ou `tudo`: usa fake para todos os componentes.
    - lista separada por vírgula: usa fake só nos componentes citados,
      ex.: `arduino` ou `arduino,bitalino`.
"""

import os

from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.contratos import ControladorLedArduino, LeitorBitalino

NOME_VARIAVEL_FAKE: str = 'ESQUIZOCAP_FAKE'
VALORES_PARA_TODOS: frozenset[str] = frozenset({'1', 'true', 'tudo', 'all'})
COMPONENTES_CONHECIDOS: frozenset[str] = frozenset({'arduino', 'bitalino'})


def componentes_simulados() -> set[str]:
    """Lê `ESQUIZOCAP_FAKE` e devolve os componentes que devem ser simulados."""
    valor: str = os.environ.get(NOME_VARIAVEL_FAKE, '').strip().lower()

    if not valor:
        return set()

    if valor in VALORES_PARA_TODOS:
        return set(COMPONENTES_CONHECIDOS)

    return {componente.strip() for componente in valor.split(',') if componente.strip()}


def usar_fake(componente: str) -> bool:
    """Indica se um componente específico deve ser simulado."""
    return componente in componentes_simulados()


def criar_arduino() -> ControladorLedArduino:
    """Cria o controlador da fita de LED, real ou simulado conforme `ESQUIZOCAP_FAKE`."""
    if usar_fake('arduino'):
        return ArduinoFake()
    return ArduinoSerial()


def criar_bitalino() -> LeitorBitalino:
    """Cria o leitor de EEG, real ou simulado conforme `ESQUIZOCAP_FAKE`.

    O fake sai daqui em TEMPO REAL: quem o consome é a thread de aquisição, que lê em
    laço contínuo. Um gerador que entrega amostras instantaneamente faria esse laço
    queimar uma CPU inteira e simular horas de EEG em segundos. Os testes constroem o
    `BitalinoSintetico` direto, sem tempo real, justamente para não pagar esse relógio.
    """
    if usar_fake('bitalino'):
        return BitalinoSintetico(tempo_real=True)
    return BitalinoLSL()
