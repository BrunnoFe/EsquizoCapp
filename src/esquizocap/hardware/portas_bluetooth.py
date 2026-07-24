"""Descobre qual porta de acesso corresponde a qual dispositivo Bluetooth.

Existe para resolver a armadilha central do Modo Direto: ao parear um BITalino, o Windows
cria DUAS portas COM, e só uma alcança o dispositivo. Numa máquina com três dispositivos
pareados aparecem seis portas, todas com a mesma descrição ("Serial Padrão por link
Bluetooth"), e escolher a errada dá uma porta que ABRE e nunca entrega dado — falha difícil
de diagnosticar, porque não parece falha.

A saída é que o `hwid` que o pyserial já entrega carrega o MAC do dispositivo pareado:

    porta de SAÍDA   ...LOCALMFG&0002\\7&2B886E8&2&201709186029_C00000000
                                                  ^^^^^^^^^^^^ o MAC, sem separadores
    serviço LOCAL    ...LOCALMFG&0000\\7&2B886E8&2&000000000000_00000004
                                                  ^^^^^^^^^^^^ zerado: não alcança nada

Ou seja, o próprio sistema distingue a porta útil da inútil — basta ler. Isso reduz seis
candidatas a uma, e faz o operador escolher o DISPOSITIVO (identidade permanente) em vez da
PORTA (endereço volátil, que muda de máquina e de pareamento).

LIMITAÇÃO: o formato do `hwid` é do Windows. Em outros sistemas a derivação simplesmente
não encontra nada, e quem chama precisa oferecer um caminho manual — nunca tratar a
ausência de porta como impossibilidade de conectar.
"""

import re

from serial.tools import list_ports

PADRAO_MAC_NO_HWID: re.Pattern[str] = re.compile(r'&([0-9A-Fa-f]{12})_')
"""O MAC aparece entre um `&` e um `_`, com doze dígitos hexadecimais e sem separadores."""

MAC_ZERADO: str = '0' * 12
"""Endereço dos serviços locais de entrada. Marca a porta que nunca alcança dispositivo."""

BYTES_DO_MAC: int = 6


def mac_do_hwid(hwid: str) -> str | None:
    """Extrai o MAC do dispositivo embutido no identificador de hardware da porta.

    Args:
        hwid: O `hwid` que o pyserial reporta para a porta.

    Returns:
        O MAC normalizado (`20:17:09:18:60:29`), ou `None` se a porta não for a saída de um
        par Bluetooth — inclui portas USB comuns (o Arduino) e os serviços locais de
        entrada, cujo endereço vem zerado.
    """
    achado = PADRAO_MAC_NO_HWID.search(hwid)

    if achado is None:
        return None

    bruto = achado.group(1).upper()

    if bruto == MAC_ZERADO:
        return None

    return ':'.join(bruto[posicao : posicao + 2] for posicao in range(0, BYTES_DO_MAC * 2, 2))


def listar_portas_do_sistema() -> list[tuple[str, str]]:
    """Lê as portas seriais visíveis agora, como pares `(porta, hwid)`.

    É a única função impura daqui: as demais recebem essa lista, para serem testáveis sem
    depender do que estiver plugado na máquina.
    """
    return [(porta.device, porta.hwid) for porta in list_ports.comports()]


def derivar_porta(mac: str, portas_do_sistema: list[tuple[str, str]]) -> str | None:
    """Descobre a porta de acesso do dispositivo com o MAC informado.

    Args:
        mac: MAC do dispositivo, com ou sem maiúsculas.
        portas_do_sistema: Pares `(porta, hwid)`, tipicamente de `listar_portas_do_sistema`.

    Returns:
        A porta (`COM6`), ou `None` se nenhuma corresponder — o que significa dispositivo
        não pareado, desligado, ou um sistema cujo `hwid` não segue o formato do Windows.

        Devolver `None` é melhor que chutar: uma porta errada abre e não entrega nada, e o
        operador levaria muito mais tempo para entender isso do que uma ausência declarada.
    """
    mac_procurado = mac.upper()

    for porta, hwid in portas_do_sistema:
        if mac_do_hwid(hwid=hwid) == mac_procurado:
            return porta

    return None
