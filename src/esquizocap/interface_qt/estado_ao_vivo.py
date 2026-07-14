"""Estado que só existe enquanto a aquisição está rodando.

É o retrato do último `ResultadoCiclo` recebido da thread de aquisição, mais o
relógio da animação de transição de cor. Fica separado de `ConfiguracaoSelecionada`
porque tem um ciclo de vida diferente: é reiniciado a cada início de aquisição, nunca
persiste entre sessões, e quem o atualiza é a drenagem da fila de eventos
(`EsquizoController._tick`/`_pintar_resultado`), não uma escolha direta do usuário.
"""

from dataclasses import dataclass


@dataclass
class LeituraAoVivo:
    """Último resultado do ciclo de aquisição, e o progresso da transição visual."""

    adquirindo: bool = False
    """Se a thread de aquisição está rodando agora."""

    matiz_atual: int = 128
    """Matiz (hue) do resultado mais recente, na escala do firmware (0–255)."""

    matiz_anterior: int = 128
    """Matiz do resultado anterior — usado para animar a transição até `matiz_atual`."""

    fase_transicao: float = 1.0
    """Progresso da transição de `matiz_anterior` para `matiz_atual`, de 0.0 a 1.0.
    Em 1.0, a transição já terminou e o LED/órbita mostram só `matiz_atual`."""

    inicio_transicao_ms: float = 0.0
    """Instante (relógio monotônico, em ms) em que a transição atual começou."""

    frequencia_dominante_texto: str = "0.0"
    """Frequência dominante do último bloco, já formatada (modo Frequência)."""

    indice_banda: int = 2
    """Índice em `bandas_eeg.BANDAS_EEG` da banda do último bloco (modo Frequência)."""

    amplitude_texto: str = "0.0"
    """Amplitude bruta da última amostra, já formatada (modo Amplitude)."""
