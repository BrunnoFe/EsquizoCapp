"""Parâmetros puramente cosméticos da view: tamanho da órbita, velocidade dos anéis,
brilho dos LEDs simulados, etc.

Nada aqui influencia o sinal, o modelo ou o Arduino — são só os controles do painel
"Aparência", ajustáveis ao vivo pelo usuário para o gosto da instalação artística.
"""

from dataclasses import dataclass

from esquizocap.interface_qt.constantes_gui import LimiteNumerico


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
