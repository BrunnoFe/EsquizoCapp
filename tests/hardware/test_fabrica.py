"""Testes da fábrica: a variável ESQUIZOCAP_FAKE decide real vs. simulado.

Errar aqui é caro de um jeito silencioso: escolher o fake sem querer faria a aplicação
"funcionar" mostrando dados sintéticos como se fossem EEG do sujeito.
"""

import pytest

from esquizocap.hardware import fabrica
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_direto import BitalinoDireto
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.modo_aquisicao import ModoAquisicao


class TestPadraoEHardwareReal:
    def test_sem_a_variavel_usa_tudo_real(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """O default TEM que ser o hardware real: simular por acidente é o pior cenário."""
        monkeypatch.delenv(fabrica.NOME_VARIAVEL_FAKE, raising=False)

        assert fabrica.componentes_simulados() == set()
        assert isinstance(fabrica.criar_arduino(), ArduinoSerial)
        assert isinstance(fabrica.criar_bitalino(), BitalinoLSL)

    def test_variavel_vazia_tambem_usa_tudo_real(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, '   ')

        assert fabrica.componentes_simulados() == set()
        assert isinstance(fabrica.criar_arduino(), ArduinoSerial)


class TestLeitoresPorModo:
    """Os dois modos de aquisição nascem juntos no arranque."""

    def test_cada_modo_ganha_a_implementacao_certa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(fabrica.NOME_VARIAVEL_FAKE, raising=False)

        leitores = fabrica.criar_leitores_por_modo()

        assert isinstance(leitores[ModoAquisicao.OPENSIGNALS], BitalinoLSL)
        assert isinstance(leitores[ModoAquisicao.DIRETO], BitalinoDireto)

    def test_todos_os_modos_tem_leitor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Um modo sem leitor viraria KeyError no clique de conectar."""
        monkeypatch.delenv(fabrica.NOME_VARIAVEL_FAKE, raising=False)

        assert set(fabrica.criar_leitores_por_modo()) == set(ModoAquisicao)

    def test_construir_os_dois_nao_toca_o_hardware(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A premissa que permite criar ambos no arranque: os construtores são inertes.

        Se um deles abrisse porta ou resolvesse stream, a aplicação não subiria sem o
        hardware presente — e o modo NÃO escolhido seguraria um recurso à toa.
        """
        monkeypatch.delenv(fabrica.NOME_VARIAVEL_FAKE, raising=False)

        fabrica.criar_leitores_por_modo()  # não levanta, mesmo sem BITalino nenhum plugado

    def test_com_fake_o_mesmo_leitor_responde_pelos_dois(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A escolha de modo perde o efeito, e a interface tem que avisar em vez de fingir."""
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'bitalino')

        leitores = fabrica.criar_leitores_por_modo()

        assert isinstance(leitores[ModoAquisicao.DIRETO], BitalinoSintetico)
        assert leitores[ModoAquisicao.DIRETO] is leitores[ModoAquisicao.OPENSIGNALS]


class TestSelecaoDeFakes:
    @pytest.mark.parametrize('valor', ['1', 'true', 'tudo', 'all', 'TUDO', ' 1 '])
    def test_valores_de_atalho_simulam_tudo(self, monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, valor)

        assert fabrica.componentes_simulados() == set(fabrica.COMPONENTES_CONHECIDOS)
        assert isinstance(fabrica.criar_arduino(), ArduinoFake)
        assert isinstance(fabrica.criar_bitalino(), BitalinoSintetico)

    def test_simula_apenas_o_componente_citado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'arduino')

        assert fabrica.usar_fake('arduino') is True
        assert fabrica.usar_fake('bitalino') is False
        assert isinstance(fabrica.criar_arduino(), ArduinoFake)
        assert isinstance(fabrica.criar_bitalino(), BitalinoLSL), 'BITalino não foi citado'

    def test_aceita_lista_separada_por_virgula(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'arduino, bitalino')

        assert fabrica.componentes_simulados() == {'arduino', 'bitalino'}
        assert isinstance(fabrica.criar_arduino(), ArduinoFake)
        assert isinstance(fabrica.criar_bitalino(), BitalinoSintetico)

    def test_componente_desconhecido_nao_simula_nada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Um nome errado não pode virar "simula tudo" nem quebrar a aplicação."""
        monkeypatch.setenv(fabrica.NOME_VARIAVEL_FAKE, 'godot')

        assert fabrica.usar_fake('arduino') is False
        assert isinstance(fabrica.criar_arduino(), ArduinoSerial)
