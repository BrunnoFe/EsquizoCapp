"""Camada de aplicação: orquestra o domínio e o hardware, sem ser nenhum dos dois.

Aqui mora o que coordena — hoje, a thread que roda o `CicloAquisicao` e publica os
resultados para quem estiver desenhando a tela. Não é domínio (o núcleo é sequencial e
não sabe que existe concorrência), não é hardware (não fala com serial nem com LSL) e
não é interface (não importa Tkinter). É a cola entre eles.

A dependência aponta só para dentro: `aplicacao` conhece `dominio` e `hardware`; nenhum
dos dois conhece `aplicacao`.
"""

from esquizocap.aplicacao.servico_aquisicao import (
    Evento,
    EventoErro,
    EventoParado,
    EventoResultado,
    ServicoAquisicao,
)

__all__ = [
    'Evento',
    'EventoErro',
    'EventoParado',
    'EventoResultado',
    'ServicoAquisicao',
]
