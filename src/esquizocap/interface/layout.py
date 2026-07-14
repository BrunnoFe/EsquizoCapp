"""Medidas, ritmos e opções de layout da janela principal.

Isto não é configuração do usuário — é a aparência da janela. Vivia solto no topo do
`main.py` (e, antes disso, no `configs.json`, como se índices de grid fossem uma escolha
de quem usa o programa).
"""

INTERVALO_DRENAGEM_MS: int = 33
"""De quanto em quanto tempo a GUI drena a fila da thread de aquisição.

É só o ritmo do DESENHO — a aquisição roda no ritmo do BITalino, independentemente disto.
33 ms dá ~30 quadros por segundo, mais do que suficiente para acompanhar uma cor mudando.
"""

LARGURA_JANELA: int = 1680
ALTURA_JANELA: int = 1000

COLUNAS_GRID: tuple[int, ...] = (0, 1, 2, 3, 4)
LINHAS_GRID: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7, 8)

VALOR_MAXIMO_HSV: int = 255
"""Fundo de escala dos medidores de matiz, saturação e brilho."""

PASSO_AMOSTRA_FREQUENCIA: int = 500
"""Granularidade do medidor "Tamanho da Amostra", em amostras."""

_ESPESSURA_MEDIDOR: int = 12
_TAMANHO_MEDIDOR: int = 200
_FONTE_MEDIDOR: str = '-size 20 -weight bold'
_FONTE_SUBTEXTO_MEDIDOR: str = '-size 12 -weight bold'

OPCOES_MEDIDOR: dict[str, object] = {
    'metertype': 'semi',
    'meterthickness': _ESPESSURA_MEDIDOR,
    'metersize': _TAMANHO_MEDIDOR,
    'showtext': True,
    'textfont': _FONTE_MEDIDOR,
    'subtextfont': _FONTE_SUBTEXTO_MEDIDOR,
}
"""Opções comuns a TODOS os medidores. Cada um só declara o que o distingue."""

COR_FUNDO_TOOLTIP: str = '#bc951a'
COR_TEXTO_TOOLTIP: str = 'white'
ATRASO_TOOLTIP_MS: int = 1000
