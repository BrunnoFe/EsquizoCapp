"""Por qual caminho o sinal do BITalino chega à aplicação.

É escolha do operador, feita antes de conectar, e não uma propriedade do dispositivo — o
mesmo BITalino serve aos dois modos. O que muda é quem dirige a aquisição.
"""

from enum import Enum


class ModoAquisicao(Enum):
    """Os dois caminhos possíveis até o sinal.

    Mutuamente exclusivos NO HARDWARE: o BITalino aceita um cliente por vez, então usar o
    Modo Direto exige o OpenSignals fechado, e vice-versa.
    """

    OPENSIGNALS = 'OpenSignals (LSL)'
    """A aplicação assina o stream que o OpenSignals publica.

    Exige o programa aberto, com o compartilhamento "Lab Streaming Layer" ativo e a gravação
    iniciada. Em troca, é o caminho comprovado em bancada e permite gravar em disco pelo
    OpenSignals em paralelo. Taxa e canais são escolhidos LÁ, não aqui.
    """

    DIRETO = 'Direto (Bluetooth)'
    """A aplicação fala com o dispositivo pela porta de acesso, sem intermediário.

    Dispensa o ritual do OpenSignals e devolve à aplicação o controle sobre a taxa acordada.
    Exige o OpenSignals FECHADO.
    """

    @property
    def exige_porta_de_acesso(self) -> bool:
        """Indica se este modo alcança o dispositivo por porta serial.

        O Modo OpenSignals encontra o dispositivo pelo MAC, que é o `type` do stream; o Modo
        Direto precisa da porta, que a aplicação deriva do MAC.
        """
        return self is ModoAquisicao.DIRETO


MODOS_AQUISICAO: tuple[str, ...] = tuple(modo.value for modo in ModoAquisicao)
"""Rótulos oferecidos no seletor, na ordem em que aparecem."""

MODO_AQUISICAO_PADRAO: ModoAquisicao = ModoAquisicao.OPENSIGNALS
"""O padrão é o caminho comprovado: quem quiser o Modo Direto escolhe de propósito."""


def modo_do_rotulo(rotulo: str) -> ModoAquisicao:
    """Traduz o texto escolhido no seletor para o modo correspondente.

    Raises:
        ValueError: Se o rótulo não corresponder a modo nenhum.
    """
    return ModoAquisicao(rotulo)
