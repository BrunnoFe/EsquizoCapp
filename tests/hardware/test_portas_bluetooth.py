"""Testes da derivação da porta de acesso a partir do MAC do dispositivo.

Os hwid usados aqui foram COPIADOS de uma máquina real, com o BITalino e outros dois
dispositivos pareados. Inventá-los derrotaria o teste: o que se verifica é justamente se o
formato que o Windows produz é lido corretamente.
"""

import pytest

from esquizocap.hardware import portas_bluetooth

# Porta de SAÍDA de um par Bluetooth: traz o MAC do dispositivo. É a que funciona.
HWID_BITALINO = (
    r'BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0002'
    r'\7&2B886E8&2&201709186029_C00000000'
)
MAC_BITALINO = '20:17:09:18:60:29'

HWID_OUTRO_DISPOSITIVO = (
    r'BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0002'
    r'\7&2B886E8&2&98D391FE40DE_C00000000'
)
MAC_OUTRO_DISPOSITIVO = '98:D3:91:FE:40:DE'

# Serviço LOCAL de entrada: endereço zerado. A porta existe, mas nunca alcança dispositivo
# nenhum — é a metade do par que faz o operador escolher errado.
HWID_SERVICO_LOCAL = (
    r'BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0000'
    r'\7&2B886E8&2&000000000000_00000004'
)

HWID_PORTA_USB = r'USB VID:PID=1A86:7523 SER= LOCATION=1-2'


class TestExtrairMac:
    def test_le_o_mac_de_uma_porta_de_saida(self) -> None:
        assert portas_bluetooth.mac_do_hwid(hwid=HWID_BITALINO) == MAC_BITALINO

    def test_le_o_mac_de_outro_dispositivo_pareado(self) -> None:
        assert portas_bluetooth.mac_do_hwid(hwid=HWID_OUTRO_DISPOSITIVO) == MAC_OUTRO_DISPOSITIVO

    def test_o_servico_local_nao_tem_mac(self) -> None:
        """O endereço zerado é o que distingue a porta inútil da porta que funciona.

        Sem esta regra, um par Bluetooth ofereceria duas portas indistinguíveis, e escolher
        a errada dá uma porta que abre e nunca entrega dado.
        """
        assert portas_bluetooth.mac_do_hwid(hwid=HWID_SERVICO_LOCAL) is None

    def test_porta_usb_comum_nao_tem_mac(self) -> None:
        """O Arduino entra por USB, não por Bluetooth: não pode ser confundido com um
        dispositivo pareado."""
        assert portas_bluetooth.mac_do_hwid(hwid=HWID_PORTA_USB) is None

    def test_hwid_vazio_nao_estoura(self) -> None:
        assert portas_bluetooth.mac_do_hwid(hwid='') is None

    def test_o_mac_sai_normalizado_em_maiuscula_com_dois_pontos(self) -> None:
        """O MAC no hwid vem sem separadores; o resto do sistema usa `AA:BB:...`."""
        hwid_minusculo = HWID_BITALINO.replace('201709186029', '201709186029'.lower())

        assert portas_bluetooth.mac_do_hwid(hwid=hwid_minusculo) == MAC_BITALINO


class TestDerivarPorta:
    def _portas_de_referencia(self) -> list[tuple[str, str]]:
        """A situação real da máquina de referência: 6 portas, 3 delas inúteis."""
        return [
            ('COM3', HWID_SERVICO_LOCAL),
            ('COM4', HWID_OUTRO_DISPOSITIVO),
            ('COM5', HWID_SERVICO_LOCAL),
            ('COM6', HWID_BITALINO),
            ('COM8', HWID_OUTRO_DISPOSITIVO),
            ('COM9', HWID_SERVICO_LOCAL),
        ]

    def test_encontra_a_porta_do_mac_pedido(self) -> None:
        porta = portas_bluetooth.derivar_porta(
            mac=MAC_BITALINO, portas_do_sistema=self._portas_de_referencia()
        )

        assert porta == 'COM6'

    def test_ignora_maiuscula_e_minuscula_no_mac(self) -> None:
        porta = portas_bluetooth.derivar_porta(
            mac=MAC_BITALINO.lower(), portas_do_sistema=self._portas_de_referencia()
        )

        assert porta == 'COM6'

    def test_dispositivo_nao_pareado_nao_tem_porta(self) -> None:
        """Devolve None em vez de chutar: uma porta errada abre e não entrega nada, o que é
        pior de diagnosticar do que a ausência declarada."""
        porta = portas_bluetooth.derivar_porta(
            mac='12:25:33:81:92:44', portas_do_sistema=self._portas_de_referencia()
        )

        assert porta is None

    def test_sem_portas_no_sistema_devolve_none(self) -> None:
        assert portas_bluetooth.derivar_porta(mac=MAC_BITALINO, portas_do_sistema=[]) is None

    def test_com_portas_duplicadas_para_o_mesmo_mac_devolve_a_primeira(self) -> None:
        """Não observado na prática, mas possível. Escolher é melhor que falhar: a saída de
        emergência da interface cobre o caso de a escolhida estar errada."""
        duplicadas = [('COM6', HWID_BITALINO), ('COM7', HWID_BITALINO)]

        assert portas_bluetooth.derivar_porta(mac=MAC_BITALINO, portas_do_sistema=duplicadas) == 'COM6'


class TestLeituraDoSistema:
    def test_listar_portas_do_sistema_devolve_pares_de_string(self) -> None:
        """Não depende de haver porta alguma: numa máquina sem nada pareado a lista é vazia,
        e isso é resposta válida."""
        portas = portas_bluetooth.listar_portas_do_sistema()

        assert isinstance(portas, list)
        for dispositivo, hwid in portas:
            assert isinstance(dispositivo, str)
            assert isinstance(hwid, str)


@pytest.mark.parametrize(
    ('hwid', 'esperado'),
    [
        (HWID_BITALINO, MAC_BITALINO),
        (HWID_SERVICO_LOCAL, None),
        (HWID_PORTA_USB, None),
    ],
)
def test_resumo_do_comportamento(hwid: str, esperado: str | None) -> None:
    """Tabela-resumo: só porta de saída de par Bluetooth tem MAC."""
    assert portas_bluetooth.mac_do_hwid(hwid=hwid) == esperado
