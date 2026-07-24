"""Testes da fábrica: a variável ESQUIZOCAP_FAKE decide real vs. simulado.

Errar aqui é caro de um jeito silencioso: escolher o fake sem querer faria a aplicação
"funcionar" mostrando dados sintéticos como se fossem EEG do sujeito.
"""

import pytest

from esquizocap.hardware import fabrica
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL


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
