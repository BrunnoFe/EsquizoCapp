"""Testes das preferências do usuário.

A política aqui é o oposto da de `config.py`, e é isso que se testa: o arquivo é escrito
pela própria aplicação, então nada nele pode impedir a instalação de subir. Um JSON
corrompido, uma chave de uma versão anterior ou um valor com o tipo errado têm que virar
default + log, nunca exceção.
"""

import json
import logging
from pathlib import Path

import pytest

from esquizocap.infraestrutura import preferencias
from esquizocap.infraestrutura.preferencias import Preferencias


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    return tmp_path / 'preferencias.json'


class TestRoundTrip:
    def test_grava_e_le_de_volta_o_que_foi_salvo(self, arquivo: Path) -> None:
        original = Preferencias(
            componentes_simulados=frozenset({'arduino', 'bitalino'}),
            pasta_gravacoes=Path('D:/Gravacoes'),
            perguntar_onde_salvar=False,
            borda_de_simulacao=True,
            aparencia={'quantidade_leds': 90.0},
        )

        preferencias.salvar(original, arquivo)

        assert preferencias.carregar(arquivo) == original

    def test_arquivo_ausente_devolve_os_padroes(self, arquivo: Path) -> None:
        assert preferencias.carregar(arquivo) == Preferencias()

    def test_o_padrao_e_nada_simulado_e_perguntar_onde_salvar(self) -> None:
        """O default TEM que preservar o comportamento de hoje: hardware real, com diálogo."""
        padrao = Preferencias()

        assert padrao.componentes_simulados == frozenset()
        assert padrao.perguntar_onde_salvar is True
        assert padrao.borda_de_simulacao is False

    def test_cria_a_pasta_do_arquivo_se_faltar(self, tmp_path: Path) -> None:
        destino = tmp_path / 'settings' / 'preferencias.json'

        preferencias.salvar(Preferencias(), destino)

        assert destino.exists()

    def test_nao_deixa_arquivo_temporario_para_tras(self, arquivo: Path) -> None:
        preferencias.salvar(Preferencias(), arquivo)

        assert list(arquivo.parent.iterdir()) == [arquivo]


class TestToleranciaALixo:
    """Nada aqui pode levantar: a instalação sobe mesmo com o arquivo estragado."""

    def test_json_corrompido_cai_nos_padroes(self, arquivo: Path, caplog: pytest.LogCaptureFixture) -> None:
        arquivo.write_text('{"pasta_gravacoes": "D:/x"', encoding='utf-8')

        with caplog.at_level(logging.WARNING):
            assert preferencias.carregar(arquivo) == Preferencias()

        assert caplog.records, 'falhar em silêncio esconderia a perda das preferências'

    def test_json_que_nao_e_objeto_cai_nos_padroes(self, arquivo: Path) -> None:
        arquivo.write_text('[1, 2, 3]', encoding='utf-8')

        assert preferencias.carregar(arquivo) == Preferencias()

    def test_chave_desconhecida_e_ignorada_com_aviso(self, arquivo: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Ao contrário de `config.py`, aqui não falha alto: a chave pode ser de outra versão."""
        arquivo.write_text(json.dumps({'tema': 'solar', 'borda_de_simulacao': True}), encoding='utf-8')

        with caplog.at_level(logging.WARNING):
            carregadas = preferencias.carregar(arquivo)

        assert carregadas.borda_de_simulacao is True, 'a chave válida ao lado tem que sobreviver'
        assert 'tema' in caplog.text

    @pytest.mark.parametrize(
        ('chave', 'valor'),
        [
            ('componentes_simulados', 'arduino'),  # string onde se espera lista
            ('componentes_simulados', [1, 2]),
            ('pasta_gravacoes', 42),
            ('pasta_gravacoes', ''),
            ('perguntar_onde_salvar', 'sim'),
            ('borda_de_simulacao', 1),
            ('aparencia', ['quantidade_leds']),
        ],
    )
    def test_valor_com_tipo_errado_cai_no_padrao_do_campo(self, arquivo: Path, chave: str, valor: object) -> None:
        arquivo.write_text(json.dumps({chave: valor}), encoding='utf-8')

        carregadas = preferencias.carregar(arquivo)

        assert getattr(carregadas, chave) == getattr(Preferencias(), chave)

    def test_valor_estragado_nao_contamina_os_outros_campos(self, arquivo: Path) -> None:
        """Cada campo é lido isolado: um lixo custa só o seu próprio default."""
        arquivo.write_text(
            json.dumps({'pasta_gravacoes': 42, 'perguntar_onde_salvar': False}),
            encoding='utf-8',
        )

        carregadas = preferencias.carregar(arquivo)

        assert carregadas.pasta_gravacoes == Preferencias().pasta_gravacoes
        assert carregadas.perguntar_onde_salvar is False


class TestAparencia:
    def test_descarta_apenas_o_slider_invalido(self, arquivo: Path) -> None:
        arquivo.write_text(
            json.dumps({'aparencia': {'quantidade_leds': 90, 'largura_anel_px': 'grosso'}}),
            encoding='utf-8',
        )

        assert preferencias.carregar(arquivo).aparencia == {'quantidade_leds': 90.0}

    def test_booleano_nao_passa_por_numero(self, arquivo: Path) -> None:
        """`True` é `int` em Python, e viraria 1.0 — um valor plausível vindo do tipo errado."""
        arquivo.write_text(json.dumps({'aparencia': {'quantidade_leds': True}}), encoding='utf-8')

        assert preferencias.carregar(arquivo).aparencia == {}

    def test_faixa_nao_e_conferida_aqui(self, arquivo: Path) -> None:
        """O clamp é de quem aplica: a tabela de limites vive na camada de interface."""
        arquivo.write_text(json.dumps({'aparencia': {'quantidade_leds': 99999}}), encoding='utf-8')

        assert preferencias.carregar(arquivo).aparencia == {'quantidade_leds': 99999.0}
