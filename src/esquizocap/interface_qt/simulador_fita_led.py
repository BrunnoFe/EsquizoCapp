"""Simula, no lado Python, o mesmo algoritmo de animação que o firmware do Arduino
roda na fita de LED de verdade — é o que permite a `LedStrip.qml` mostrar uma prévia
fiel sem depender do hardware físico.

A fidelidade ao firmware (`arduino/arduino_comunication_resumed.ino`) importa: um
algoritmo diferente aqui faria a prévia mentir sobre como o LED de verdade vai reagir.
"""

from dataclasses import dataclass

from PySide6.QtGui import QColor

from esquizocap.interface_qt.cores_visuais import hsv_para_qcolor, limitar

COR_LED_APAGADO = QColor(26, 32, 38)
"""Cor de todos os LEDs quando não há aquisição rodando."""

# Índices do modo de luminosidade, na convenção do firmware (base 1) — ver
# `hardware/constantes.py:MODOS_LUMINOSIDADE`.
MODO_UM_A_UM = 1
MODO_TODOS = 2
MODO_GRADIENTE = 3
MODO_A_PARTIR_DO_CENTRO = 4

TETO_BRILHO_LED = 150
"""O firmware real recebe o brilho já limitado a 150
(`arduino_comunication_resumed.ino`, `min(num3String.toInt(), 150)`) — reproduzido
aqui para a prévia bater com o LED de verdade."""

REALCE_BRILHO_CENTRO = 50
"""Quanto o modo "A partir do Centro" acrescenta ao brilho da margem central,
espelhando a função `a_partir_do_centro` do firmware."""

PROPORCAO_MARGEM_CENTRO = 0.08
"""Fração da fita, a partir do centro, que recebe o realce de brilho no modo
"A partir do Centro"."""


@dataclass(frozen=True)
class ParametrosQuadroLed:
    """Retrato dos valores que afetam a cor dos LEDs num instante.

    Usado como chave de cache: enquanto nenhum campo mudar entre dois quadros, a
    lista de cores memorizada é reaproveitada — é o que faz o `Canvas` da fita não
    repintar à toa (identidade de objeto igual = QML entende que nada mudou).
    """

    adquirindo: bool
    quantidade_leds: int
    matiz_atual: int
    matiz_anterior: int
    fase_transicao: float
    saturacao: int
    brilho: int
    modo_luminosidade: int


class SimuladorFitaLed:
    """Calcula, com cache, a cor de cada LED da fita para o quadro atual."""

    def __init__(self) -> None:
        self._parametros_do_cache: ParametrosQuadroLed | None = None
        self._cores_em_cache: list[QColor] = []

    def cores_para_quadro(self, parametros: ParametrosQuadroLed) -> list[QColor]:
        """Devolve uma cor por LED, do primeiro ao último da fita.

        Reaproveita a lista do quadro anterior se `parametros` for idêntico ao
        último calculado.
        """
        if parametros == self._parametros_do_cache:
            return self._cores_em_cache
        self._parametros_do_cache = parametros
        self._cores_em_cache = self._calcular(parametros)
        return self._cores_em_cache

    def _calcular(self, p: ParametrosQuadroLed) -> list[QColor]:
        quantidade = int(limitar(p.quantidade_leds, 6, 120))
        if not p.adquirindo:
            return [COR_LED_APAGADO] * quantidade

        centro = quantidade // 2
        margem_do_centro = max(2, round(quantidade * PROPORCAO_MARGEM_CENTRO))
        brilho_base = min(p.brilho, TETO_BRILHO_LED)

        cores: list[QColor] = []
        for indice_led in range(quantidade):
            brilho_deste_led = brilho_base
            if p.modo_luminosidade == MODO_TODOS:
                matiz_deste_led = p.matiz_atual
            elif p.modo_luminosidade == MODO_UM_A_UM:
                progresso = indice_led / quantidade
                matiz_deste_led = p.matiz_atual if progresso <= p.fase_transicao else p.matiz_anterior
            elif p.modo_luminosidade == MODO_A_PARTIR_DO_CENTRO:
                distancia_do_centro = abs(indice_led - centro)
                progresso = distancia_do_centro / max(1, centro)
                dentro_da_transicao = progresso <= p.fase_transicao
                matiz_deste_led = p.matiz_atual if dentro_da_transicao else p.matiz_anterior
                if distancia_do_centro <= margem_do_centro and dentro_da_transicao:
                    brilho_deste_led = min(p.brilho + REALCE_BRILHO_CENTRO, TETO_BRILHO_LED)
            else:  # Gradiente (MODO_GRADIENTE, e fallback de qualquer índice desconhecido)
                matiz_deste_led = round(p.matiz_anterior + (p.matiz_atual - p.matiz_anterior) * p.fase_transicao)
            cores.append(hsv_para_qcolor(matiz_deste_led, p.saturacao, brilho_deste_led))
        return cores
