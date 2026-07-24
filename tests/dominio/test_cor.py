"""Testes da conversão de cor HSV -> RGB/hexadecimal."""

import pytest

from esquizocap.dominio.cor import hsv_para_rgb_hex


class TestConversaoHsv:
    def test_saturacao_zero_produz_cinza(self) -> None:
        """Sem saturação, os três canais RGB são iguais: o matiz deixa de importar."""
        _hex_color, rgb = hsv_para_rgb_hex(hue=200, saturacao=0, brilho=255)

        assert rgb == (255, 255, 255)

    def test_brilho_zero_produz_preto(self) -> None:
        cor_hex, rgb = hsv_para_rgb_hex(hue=200, saturacao=255, brilho=0)

        assert rgb == (0, 0, 0)
        assert cor_hex == '#000000'

    @pytest.mark.parametrize(
        ('hue', 'canal_dominante'),
        [
            (0, 0),  # vermelho
            (85, 1),  # verde  (1/3 de 255)
            (170, 2),  # azul   (2/3 de 255)
        ],
    )
    def test_o_matiz_escolhe_o_canal_dominante(self, hue: int, canal_dominante: int) -> None:
        """A escala do matiz é 0–255 (e não 0–360): é o que o modelo prevê."""
        _hex_color, rgb = hsv_para_rgb_hex(hue=hue, saturacao=255, brilho=255)

        assert rgb[canal_dominante] == max(rgb)

    def test_o_hexadecimal_corresponde_ao_rgb(self) -> None:
        cor_hex, rgb = hsv_para_rgb_hex(hue=205, saturacao=255, brilho=120)

        assert cor_hex == f'#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}'

    def test_valor_conhecido_do_sistema_em_producao(self) -> None:
        """Valor observado na aquisição real: protege o formato contra regressão."""
        cor_hex, rgb = hsv_para_rgb_hex(hue=205, saturacao=255, brilho=120)

        assert cor_hex == '#620078'
        assert rgb == (98, 0, 120)

    @pytest.mark.parametrize('hue', range(0, 256, 15))
    def test_todos_os_canais_ficam_na_faixa_valida(self, hue: int) -> None:
        _hex_color, rgb = hsv_para_rgb_hex(hue=hue, saturacao=255, brilho=255)

        assert all(0 <= canal <= 255 for canal in rgb)
