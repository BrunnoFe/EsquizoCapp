"""Parâmetros puramente cosméticos da view: tamanho da órbita, velocidade dos anéis,
brilho dos LEDs simulados, etc.

Nada aqui influencia o sinal, o modelo ou o Arduino — são só os controles do painel
"Aparência", ajustáveis ao vivo pelo usuário para o gosto da instalação artística.
"""

from dataclasses import dataclass, fields

from esquizocap.interface.constantes import LimiteNumerico


@dataclass
class AparenciaVisual:
    """Um campo por controle deslizante do painel "Aparência"."""

    tamanho_orbita: int = 300
    intensidade_glow: float = 1.0
    velocidade_anel_segundos: int = 18
    largura_anel_px: int = 18
    velocidade_pulso_segundos: float = 3.2
    amplitude_pulso_percentual: int = 3
    largura_traco_eeg: float = 1.5
    opacidade_traco_eeg_percentual: int = 16
    duracao_transicao_cor_segundos: float = 0.5
    brilho_leds_px: int = 6
    espacamento_leds_px: int = 2
    quantidade_leds: int = 60
    quantidade_fitas: int = 3
    escala_eixo_y_microvolts: int = 100
    janela_grafico_segundos: int = 6
    velocidade_animacao_segundos: int = 9


LIMITES_APARENCIA_VISUAL: dict[str, LimiteNumerico] = {
    'tamanho_orbita': LimiteNumerico(200, 380),
    'intensidade_glow': LimiteNumerico(0.3, 1.8),
    'velocidade_anel_segundos': LimiteNumerico(4, 40),
    'largura_anel_px': LimiteNumerico(6, 30),
    'velocidade_pulso_segundos': LimiteNumerico(1.5, 6),
    'amplitude_pulso_percentual': LimiteNumerico(0, 12),
    'largura_traco_eeg': LimiteNumerico(0.5, 4),
    'opacidade_traco_eeg_percentual': LimiteNumerico(5, 60),
    'duracao_transicao_cor_segundos': LimiteNumerico(0.1, 1.5),
    'brilho_leds_px': LimiteNumerico(0, 16),
    'espacamento_leds_px': LimiteNumerico(0, 6),
    'quantidade_leds': LimiteNumerico(6, 120),
    'quantidade_fitas': LimiteNumerico(1, 6),
    'escala_eixo_y_microvolts': LimiteNumerico(20, 300),
    'janela_grafico_segundos': LimiteNumerico(2, 20),
    'velocidade_animacao_segundos': LimiteNumerico(3, 16),
}
"""Faixa válida para cada campo de `AparenciaVisual`, na mesma ordem — usada pelos
setters do controller para não deixar o usuário arrastar um slider a um valor absurdo."""


SECAO_APARENCIA_TUDO = 'tudo'
"""Chave da pseudo-seção que abrange os 16 campos, usada pelo botão global da aba Interface.

Existe para que o reset global passe pelo mesmo slot — e portanto ganhe o mesmo desfazer —
que os botões de seção, em vez de ser um caminho paralelo sem rede."""

SECOES_APARENCIA: dict[str, tuple[str, ...]] = {
    'leds': (
        'quantidade_leds',
        'quantidade_fitas',
        'brilho_leds_px',
        'espacamento_leds_px',
    ),
    'animacao': (
        'tamanho_orbita',
        'intensidade_glow',
        'velocidade_anel_segundos',
        'largura_anel_px',
        'velocidade_pulso_segundos',
        'amplitude_pulso_percentual',
        'largura_traco_eeg',
        'opacidade_traco_eeg_percentual',
        'duracao_transicao_cor_segundos',
    ),
    'grafico': (
        'escala_eixo_y_microvolts',
        'janela_grafico_segundos',
        'velocidade_animacao_segundos',
    ),
    SECAO_APARENCIA_TUDO: tuple(campo.name for campo in fields(AparenciaVisual)),
}
"""Quais campos cada botão "Resetar" do painel de aparência devolve à fábrica.

As três primeiras chaves espelham, uma a uma, os três `SettingsCard` do painel lateral
direito (`EsquizoCapView.qml`), e `tests/interface/test_estado.py` garante que juntas
cobrem os 16 campos sem sobreposição — um slider novo que ninguém mapeie aqui faz o teste
falhar em vez de ficar de fora do reset em silêncio.

O que o teste NÃO alcança é a correspondência visual: mover um `SetSlider` de um card para
outro no QML sem atualizar este mapa deixa o botão resetando um campo que não está à vista.
Foi um risco aceito conscientemente — esse erro é cometido de olho no painel, então aparece
na hora."""

ROTULOS_DAS_SECOES_APARENCIA: dict[str, str] = {
    'leds': 'Fitas de LED',
    'animacao': 'Animação & feel',
    'grafico': 'Gráfico em tempo real',
    SECAO_APARENCIA_TUDO: 'Aparência',
}
"""Como cada seção se chama no toast de confirmação.

São os títulos dos cards, repetidos: o toast diz "Fitas de LED restaurado" e precisa falar
a mesma língua do card que foi clicado."""
