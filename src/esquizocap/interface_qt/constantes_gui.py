"""Constantes da interface: cadência de atualização e faixas válidas de controles.

Nada aqui é decisão de domínio ou de protocolo de hardware — para isso, ver
`hardware/constantes.py`. Isto é só o que faz a GUI se comportar bem (intervalo de
repintura, limites de sliders). Os valores INICIAIS dos controles ficam nos módulos
`estado_configuracao.py` e `estado_aparencia_visual.py`, não aqui.
"""

from dataclasses import dataclass

INTERVALO_DRENAGEM_MS: int = 33
"""Cadência de leitura da fila de eventos do `ServicoAquisicao`, em milissegundos
(~30 quadros por segundo) — mesmo valor que a interface Tkinter usava
(`layout.INTERVALO_DRENAGEM_MS`, hoje arquivada em `interface_tkinter_legado/`)."""

DURACAO_TRANSICAO_MATIZ_MS: float = 650.0
"""Tempo que uma transição de matiz (hue) leva para completar na animação da órbita e
da fita de LED, em milissegundos."""


@dataclass(frozen=True)
class LimiteNumerico:
    """Faixa `[minimo, maximo]` válida para um controle numérico ao vivo da view."""

    minimo: float
    maximo: float


LIMITE_SATURACAO = LimiteNumerico(0, 255)
LIMITE_BRILHO = LimiteNumerico(0, 255)
LIMITE_INTERVALO_AMOSTRAGEM_MS = LimiteNumerico(100, 2000)

LIMITE_TAMANHO_JANELA_AMOSTRAS = LimiteNumerico(128, 2048)
"""NOTA: o tamanho típico de janela usado no domínio é ~3000 amostras (ver
DECISOES_PENDENTES.md); o teto de 2048 aqui é herdado do protótipo visual e pode
merecer revisão de produto — não ajustado neste refactor por não ter sido pedido."""
