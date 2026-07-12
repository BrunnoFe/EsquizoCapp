"""Camada de abstração de hardware do EsquizoCap.

Cada borda de hardware (Arduino, BITalino, engine Godot) tem um contrato em
`interfaces.py` e duas implementações: a real e uma fake. A escolha entre elas é
feita pela variável de ambiente `ESQUIZOCAP_FAKE`, para que a app rode sem
hardware plugado.

Valores aceitos em `ESQUIZOCAP_FAKE`:
    - vazio ou ausente: usa todo o hardware real (comportamento padrão).
    - `1`, `true` ou `tudo`: usa fake para todos os componentes.
    - lista separada por vírgula: usa fake só nos componentes citados,
      ex.: `arduino` ou `arduino,bitalino`.
"""

import os

from tools.hardware.arduino_fake import ArduinoFake
from tools.hardware.arduino_real import ArduinoSerial
from tools.hardware.bitalino_fake import BitalinoSintetico
from tools.hardware.bitalino_real import BitalinoLSL
from tools.hardware.engine_fake import EngineSimulada
from tools.hardware.engine_real import EngineGodot
from tools.hardware.interfaces import (
    ControladorLedArduino,
    EngineVisual,
    ErroConexaoArduino,
    ErroConexaoBitalino,
    ErroEngineDesconectada,
    ErroStreamPerdido,
    LeitorBitalino,
)

NOME_VARIAVEL_FAKE: str = 'ESQUIZOCAP_FAKE'
VALORES_PARA_TODOS: frozenset[str] = frozenset({'1', 'true', 'tudo', 'all'})
COMPONENTES_CONHECIDOS: frozenset[str] = frozenset({'arduino', 'bitalino', 'godot'})

__all__ = [
    'ControladorLedArduino',
    'EngineVisual',
    'ErroConexaoArduino',
    'ErroConexaoBitalino',
    'ErroEngineDesconectada',
    'ErroStreamPerdido',
    'LeitorBitalino',
    'componentes_simulados',
    'criar_arduino',
    'criar_bitalino',
    'criar_engine',
    'usar_fake',
]


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
    """Cria o leitor de EEG, real ou simulado conforme `ESQUIZOCAP_FAKE`."""
    if usar_fake('bitalino'):
        return BitalinoSintetico()
    return BitalinoLSL()


def criar_engine(nome_executavel: str, caminho_executavel: str | None) -> EngineVisual:
    """Cria a engine visual, real ou simulada conforme `ESQUIZOCAP_FAKE`.

    A engine simulada ignora o executável: ela não lança processo nenhum.
    """
    if usar_fake('godot'):
        return EngineSimulada()
    return EngineGodot(nome_executavel=nome_executavel, caminho_executavel=caminho_executavel)
