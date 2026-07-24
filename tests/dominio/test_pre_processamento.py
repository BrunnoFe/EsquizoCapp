"""Testes do pré-processamento do sinal, incluindo a regressão de dois bugs conhecidos."""

import pytest

from esquizocap.dominio.pre_processamento import (
    analisar_frequencia,
    categorizar_frequencia,
    extrair_amplitude,
    extrair_sinal_do_bloco,
)
from tests.conftest import TAXA_AMOSTRAGEM_HZ, gerar_senoide

TOLERANCIA_HZ = 0.5
"""A resolução do Welch não é infinita: 10 Hz pode sair como 9,77 Hz."""


class TestExtracaoDeCanal:
    """O canal escolhido pelo usuário precisa ser respeitado nos DOIS modos."""

    def test_amplitude_le_o_canal_escolhido(self) -> None:
        amostra = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]

        assert float(extrair_amplitude(amostra=amostra, canal=1)) == 11.0
        assert float(extrair_amplitude(amostra=amostra, canal=5)) == 15.0

    def test_bloco_le_o_canal_escolhido(self) -> None:
        bloco = [[10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0] for _ in range(4)]

        assert list(extrair_sinal_do_bloco(bloco=bloco, canal=1)) == [11.0] * 4
        assert list(extrair_sinal_do_bloco(bloco=bloco, canal=5)) == [15.0] * 4

    def test_regressao_modo_frequencia_nao_pode_fixar_a_coluna_1(self) -> None:
        """REGRESSÃO (DECISOES_PENDENTES #4).

        O modo Frequência lia sempre a coluna 1, ignorando o canal escolhido — enquanto o
        modo Amplitude respeitava. Este teste falha se alguém voltar a fixar a coluna.
        """
        bloco = [[10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0] for _ in range(4)]

        for canal in (1, 2, 3, 4, 5, 6):
            do_bloco = float(extrair_sinal_do_bloco(bloco=bloco, canal=canal)[0])
            da_amostra = float(extrair_amplitude(amostra=bloco[0], canal=canal))

            assert do_bloco == da_amostra, (
                f'Canal {canal}: o modo Frequência leu {do_bloco} e o Amplitude leu '
                f'{da_amostra}. Os dois modos precisam ler o mesmo canal.'
            )


class TestAnaliseDeFrequencia:
    def test_encontra_a_frequencia_dominante(self) -> None:
        sinal = gerar_senoide(frequencia_hz=10.0, duracao_amostras=3000)

        analise = analisar_frequencia(eeg=sinal, taxa_amostragem=TAXA_AMOSTRAGEM_HZ)

        assert analise.frequencia == pytest.approx(10.0, abs=TOLERANCIA_HZ)
        assert analise.faixa.startswith('Alpha')
        assert analise.potencia > 0

    @pytest.mark.parametrize('tamanho_janela', [1000, 2000, 3000, 5000])
    def test_regressao_frequencia_nao_depende_do_tamanho_da_janela(self, tamanho_janela: int) -> None:
        """REGRESSÃO (DECISOES_PENDENTES #5) — o bug mais grave que o projeto teve.

        O valor do medidor "Tamanho da Amostra" era passado como taxa de amostragem (`fs`),
        no lugar da taxa real do dispositivo. Resultado: mexer num controle da interface
        mudava a frequência reportada e, com ela, a cor prevista. Com janela de 3000 e taxa
        real de 1000 Hz, um sinal de 10 Hz era reportado como ~29,3 Hz (Beta).

        Este teste falha se a taxa de amostragem voltar a ser confundida com o tamanho da
        janela: a frequência precisa dar ~10 Hz para QUALQUER janela.
        """
        sinal = gerar_senoide(frequencia_hz=10.0, duracao_amostras=tamanho_janela)

        analise = analisar_frequencia(eeg=sinal, taxa_amostragem=TAXA_AMOSTRAGEM_HZ)

        assert analise.frequencia == pytest.approx(10.0, abs=TOLERANCIA_HZ), (
            f'Com janela de {tamanho_janela} amostras a frequência saiu '
            f'{analise.frequencia:.2f} Hz, mas o sinal é de 10 Hz. A taxa de amostragem '
            'voltou a ser confundida com o tamanho da janela.'
        )
        assert analise.faixa.startswith('Alpha')

    def test_a_taxa_de_amostragem_define_a_escala(self) -> None:
        """Documenta POR QUE a taxa correta importa: ela escala todo o eixo de frequência.

        Passar uma taxa 3x maior que a real desloca o pico 3x — que é exatamente o que o
        bug #5 fazia.
        """
        sinal = gerar_senoide(frequencia_hz=10.0, duracao_amostras=3000)

        correta = analisar_frequencia(eeg=sinal, taxa_amostragem=TAXA_AMOSTRAGEM_HZ)
        errada = analisar_frequencia(eeg=sinal, taxa_amostragem=TAXA_AMOSTRAGEM_HZ * 3)

        assert correta.frequencia == pytest.approx(10.0, abs=TOLERANCIA_HZ)
        assert errada.frequencia == pytest.approx(30.0, abs=TOLERANCIA_HZ * 3)


class TestCategorizacaoDeBanda:
    @pytest.mark.parametrize(
        ('frequencia', 'banda_esperada'),
        [
            (2.0, 'Delta'),
            (6.0, 'Theta'),
            (10.0, 'Alpha'),
            (20.0, 'Beta'),
            (40.0, 'Gamma'),
            (60.0, 'Fora das bandas'),
            (0.05, 'Fora das bandas'),
        ],
    )
    def test_classifica_nas_bandas_de_eeg(self, frequencia: float, banda_esperada: str) -> None:
        assert categorizar_frequencia(frequencia).startswith(banda_esperada)

    def test_as_fronteiras_das_bandas_nao_tem_buraco(self) -> None:
        """Os limites são fechados à esquerda: 4 Hz é Theta, não Delta."""
        assert categorizar_frequencia(4.0).startswith('Theta')
        assert categorizar_frequencia(8.0).startswith('Alpha')
        assert categorizar_frequencia(12.0).startswith('Beta')
        assert categorizar_frequencia(30.0).startswith('Gamma')
