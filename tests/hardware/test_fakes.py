"""Testes dos fakes.

Um fake que mente é pior que nenhum fake: todo teste que depende dele passa a dar falsa
confiança. Aqui garantimos que o sinal sintético tem a forma que a aquisição espera.
"""

import numpy
import pytest
from conftest import conectar_leitor

from esquizocap.dominio.pre_processamento import analisar_frequencia
from esquizocap.hardware.arduino_fake import PORTA_SIMULADA, ArduinoFake
from esquizocap.hardware.bitalino_fake import (
    CANAIS_SIMULADOS,
    FREQUENCIA_DOMINANTE_HZ,
    TAXA_AMOSTRAGEM_SIMULADA,
    BitalinoSintetico,
)


class TestBitalinoSintetico:
    def test_a_porta_simulada_passa_no_gate_da_interface(self) -> None:
        """A GUI só libera a conexão se a string contiver "COM"."""
        assert 'COM' in PORTA_SIMULADA

    def test_a_amostra_cobre_todos_os_canais_ofertados(self) -> None:
        """A interface oferece os canais 1 a 6, então o vetor precisa chegar ao índice 6."""
        leitor = BitalinoSintetico()
        conectar_leitor(leitor)

        canais, _timestamp = leitor.ler_amostra(timeout=1)

        assert len(canais) == CANAIS_SIMULADOS
        assert len(canais) > 6

    def test_o_bloco_tem_o_tamanho_pedido(self) -> None:
        leitor = BitalinoSintetico()
        conectar_leitor(leitor)

        amostras, timestamps = leitor.ler_bloco(timeout=1, max_amostras=500)

        assert len(amostras) == 500
        assert len(timestamps) == 500

    def test_os_timestamps_avancam(self) -> None:
        leitor = BitalinoSintetico()
        conectar_leitor(leitor)

        _amostras, timestamps = leitor.ler_bloco(timeout=1, max_amostras=100)

        assert timestamps == sorted(timestamps)
        assert timestamps[-1] > timestamps[0]

    def test_o_sinal_sintetico_tem_de_fato_a_frequencia_que_promete(self) -> None:
        """Se o fake não gerar 10 Hz de verdade, os testes de frequência não valem nada."""
        leitor = BitalinoSintetico()
        conectar_leitor(leitor)

        amostras, _timestamps = leitor.ler_bloco(timeout=1, max_amostras=3000)
        sinal = numpy.array(amostras)[:, 1].astype('float32')

        analise = analisar_frequencia(eeg=sinal, taxa_amostragem=leitor.taxa_amostragem_nominal())

        assert analise.frequencia == pytest.approx(FREQUENCIA_DOMINANTE_HZ, abs=0.5)
        assert leitor.taxa_amostragem_nominal() == TAXA_AMOSTRAGEM_SIMULADA


class TestArduinoFake:
    def test_monta_o_comando_no_formato_exato_do_firmware(self) -> None:
        """O firmware espera `(modo,hue,sat,brilho)\\n`. Mudar isso quebra o LED em silêncio."""
        arduino = ArduinoFake()
        arduino.conectar(porta=PORTA_SIMULADA, baudrate=9600)

        arduino.enviar_comando_cor(modo=2, hue=205, saturacao=255, brilho=120)

        assert arduino.ultimo_comando == '(2,205,255,120)\n'

    def test_conta_os_comandos_enviados(self) -> None:
        arduino = ArduinoFake()
        arduino.conectar(porta=PORTA_SIMULADA, baudrate=9600)

        for _ in range(3):
            arduino.enviar_comando_cor(modo=1, hue=10, saturacao=20, brilho=30)

        assert arduino.comandos_enviados == 3

    def test_conectar_e_desconectar_alternam_o_estado(self) -> None:
        arduino = ArduinoFake()

        arduino.conectar(porta=PORTA_SIMULADA, baudrate=9600)
        assert arduino.esta_conectado is True

        arduino.desconectar()
        assert arduino.esta_conectado is False
