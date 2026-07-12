"""Camada de abstração de hardware do EsquizoCap.

Cada borda de hardware (Arduino, BITalino) tem um contrato em `contratos.py` e duas
implementações: a real e uma fake. A escolha entre elas é feita pela fábrica em
`fabrica.py`, a partir da variável de ambiente `ESQUIZOCAP_FAKE`.

Este `__init__` só reexporta: quem consome escreve `hardware.criar_arduino()` ou
`hardware.ErroStreamPerdido` sem precisar saber em qual módulo cada coisa mora.

A engine visual (Godot) já foi uma terceira borda daqui. A integração foi desligada e
está arquivada em `_engine_legado/` — ver o README de lá.
"""

from esquizocap.hardware.contratos import (
    ControladorLedArduino,
    ErroConexaoArduino,
    ErroConexaoBitalino,
    ErroStreamPerdido,
    LeitorBitalino,
)
from esquizocap.hardware.fabrica import (
    COMPONENTES_CONHECIDOS,
    NOME_VARIAVEL_FAKE,
    componentes_simulados,
    criar_arduino,
    criar_bitalino,
    usar_fake,
)

__all__ = [
    'COMPONENTES_CONHECIDOS',
    'NOME_VARIAVEL_FAKE',
    'ControladorLedArduino',
    'ErroConexaoArduino',
    'ErroConexaoBitalino',
    'ErroStreamPerdido',
    'LeitorBitalino',
    'componentes_simulados',
    'criar_arduino',
    'criar_bitalino',
    'usar_fake',
]
