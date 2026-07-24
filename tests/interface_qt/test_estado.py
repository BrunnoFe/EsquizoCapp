"""Testes da máquina de estados da interface.

Estes testes existem porque a regra virou uma função PURA. Antes, ela era uma cascata de
comparações de string dentro de um `after(10 ms)` da GUI: para testá-la seria preciso
abrir uma janela Tk e simular cliques. Agora é entrada -> saída.
"""

import pytest

from esquizocap.interface_qt.estado import (
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    mensagem_de_aquisicao,
)

MACS = ('20:17:09:18:60:29', '98:D3:B1:FD:3D:1F')
MODELO = 'Preditor HSV baseado em Amplitude'


def selecao(**mudancas: object) -> SelecaoUsuario:
    """Uma seleção COMPLETA, com um campo estragado por vez nos testes."""
    campos = {
        'modelo': MODELO,
        'porta_arduino': 'COM99 - Arduino simulado (fake)',
        'modo_luminosidade': 'Todos',
        'arduino_conectado': True,
        'canal_bitalino': '3',
        'mac_bitalino': MACS[0],
    }
    campos.update(mudancas)
    return SelecaoUsuario(**campos)  # type: ignore[arg-type]


def test_tudo_escolhido_fica_pronto() -> None:
    estado, mensagem = avaliar_prontidao(selecao=selecao(), macs_validos=MACS)

    assert estado is EstadoApp.PRONTO
    assert 'Começar aquisição' in mensagem


class TestOQueFaltaVemNaOrdemDePreenchimento:
    """A mensagem tem que apontar o PRÓXIMO passo, não uma pendência qualquer.

    A ordem das checagens é a ordem visual da tela — modelo, Arduino, BITalino. Se ela se
    inverter, o usuário que ainda não escolheu o modelo será mandado a "Configurar o
    Bitalino", e vai preencher a tela de trás para frente.
    """

    def test_sem_modelo(self) -> None:
        estado, mensagem = avaliar_prontidao(
            # Nada mais está escolhido também, mas o modelo é o primeiro passo.
            selecao=selecao(modelo='Selecione um modelo ...', porta_arduino='', mac_bitalino=''),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'modelo' in mensagem

    def test_sem_porta_do_arduino(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(porta_arduino='Selecione a porta do Arduino'), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Arduino'

    def test_sem_modo_de_luminosidade(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(modo_luminosidade='Selecione um modo de luminosidade'),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Arduino'

    def test_arduino_configurado_mas_nao_conectado(self) -> None:
        """O caso mais fácil de errar: tudo escolhido, mas o botão "Conectar" não foi clicado."""
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(arduino_conectado=False), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert 'Conectar' in mensagem

    def test_sem_canal_do_bitalino(self) -> None:
        estado, mensagem = avaliar_prontidao(
            selecao=selecao(canal_bitalino='Selecione o canal ativo do Bitalino'),
            macs_validos=MACS,
        )

        assert estado is EstadoApp.CONFIGURANDO
        assert mensagem == 'Configure o Bitalino'

    def test_mac_fora_da_configuracao(self) -> None:
        estado, _mensagem = avaliar_prontidao(
            selecao=selecao(mac_bitalino='00:00:00:00:00:00'), macs_validos=MACS
        )

        assert estado is EstadoApp.CONFIGURANDO


@pytest.mark.parametrize('canal', ['1', '2', '3', '4', '5', '6'])
def test_todos_os_canais_do_dispositivo_sao_aceitos(canal: str) -> None:
    estado, _mensagem = avaliar_prontidao(selecao=selecao(canal_bitalino=canal), macs_validos=MACS)

    assert estado is EstadoApp.PRONTO


@pytest.mark.parametrize('canal', ['0', '7', '', 'A1'])
def test_canal_inexistente_no_dispositivo_e_recusado(canal: str) -> None:
    estado, _mensagem = avaliar_prontidao(selecao=selecao(canal_bitalino=canal), macs_validos=MACS)

    assert estado is EstadoApp.CONFIGURANDO


def test_a_mensagem_de_aquisicao_diz_se_esta_gravando() -> None:
    assert 'gravando' in mensagem_de_aquisicao(gravando=True)
    assert 'gravando' not in mensagem_de_aquisicao(gravando=False)
