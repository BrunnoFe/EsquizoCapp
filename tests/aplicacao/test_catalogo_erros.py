"""O catálogo de erros: a invariante que impede prender quem opera a obra, e o roteamento.

O teste mais importante daqui é o `TestInvarianteDeSaida`. Uma caixa não dispensável sem
nenhum botão é uma tela travada — e o momento em que isso apareceria é justamente o pior
possível, com a instalação montada e público na sala. A invariante mora no `__post_init__`,
então vale para qualquer caixa construída em qualquer lugar, não só para as do catálogo.
"""

from pathlib import Path

import pytest

from esquizocap.aplicacao import catalogo_erros
from esquizocap.aplicacao.catalogo_erros import (
    ACAO_OK,
    EspecificacaoCaixa,
    PapelAcao,
    Severidade,
    Situacao,
)


def todas_as_caixas() -> list[EspecificacaoCaixa]:
    """Uma instância de cada entrada do catálogo, montada com valores plausíveis.

    Escrita à mão em vez de descoberta por introspecção: uma entrada nova só entra nesta
    lista se alguém pensar nela, que é exatamente o efeito desejado.
    """
    erro = OSError('acesso negado')
    return [
        catalogo_erros.aquisicao_parou_bitalino(erro),
        catalogo_erros.aquisicao_parou_arduino(erro),
        catalogo_erros.erro_inesperado_na_aquisicao(erro),
        catalogo_erros.falha_conexao_arduino(erro),
        catalogo_erros.falha_conexao_bitalino('tempo esgotado'),
        catalogo_erros.simulacao_bloqueada('há um aparelho conectado'),
        catalogo_erros.falha_ao_salvar_gravacao(erro),
        catalogo_erros.pasta_gravacoes_nao_criada(Path('C:/gravacoes'), erro),
        catalogo_erros.pasta_gravacoes_inacessivel(Path('C:/gravacoes')),
        catalogo_erros.pasta_logs_inacessivel(Path('C:/logs')),
        catalogo_erros.sem_arquivo_de_log(),
        catalogo_erros.log_inacessivel(Path('C:/logs/hoje.log')),
        catalogo_erros.falha_inesperada(erro),
    ]


class TestInvarianteDeSaida:
    """Nenhuma caixa pode deixar o usuário sem saída."""

    @pytest.mark.parametrize('caixa', todas_as_caixas(), ids=lambda c: c.situacao.value)
    def test_caixa_sem_saida_nao_existe_no_catalogo(self, caixa: EspecificacaoCaixa) -> None:
        assert caixa.dispensavel or caixa.acoes, (
            f'"{caixa.situacao.value}" não é dispensável e não tem botão: ninguém conseguiria sair dessa tela'
        )

    def test_construir_caixa_sem_saida_levanta(self) -> None:
        """A invariante está no construtor, então vale fora do catálogo também."""
        with pytest.raises(ValueError, match='não é dispensável'):
            EspecificacaoCaixa(
                situacao=Situacao.FALHA_INESPERADA,
                severidade=Severidade.CRITICO,
                titulo='Presa',
                mensagem='Sem saída.',
                acoes=(),
                dispensavel=False,
            )

    def test_dispensavel_sem_acao_e_valida(self) -> None:
        """Sem botão, mas com ESC e X: é uma saída legítima."""
        caixa = EspecificacaoCaixa(
            situacao=Situacao.SEM_ARQUIVO_DE_LOG,
            severidade=Severidade.INFO,
            titulo='Recado',
            mensagem='Some sozinho.',
            acoes=(),
            dispensavel=True,
        )
        assert caixa.acoes == ()


class TestCatalogo:
    def test_toda_entrada_tem_situacao_distinta(self) -> None:
        """A identidade é o que os testes afirmam; duas entradas iguais tornariam isso mentira."""
        situacoes = [caixa.situacao for caixa in todas_as_caixas()]
        assert len(situacoes) == len(set(situacoes)), 'há entradas do catálogo compartilhando situação'

    @pytest.mark.parametrize('caixa', todas_as_caixas(), ids=lambda c: c.situacao.value)
    def test_mensagem_diz_o_que_fazer(self, caixa: EspecificacaoCaixa) -> None:
        """Toda mensagem tem duas partes: o que houve e o que fazer, separadas por linha em branco.

        É o formato que o banner antigo cortava — a remediação nunca chegava na tela. Se
        uma entrada nova nascer sem a segunda metade, ela volta a ser um erro que só informa
        que algo deu errado, sem ajudar ninguém.
        """
        assert '\n\n' in caixa.mensagem, (
            f'"{caixa.situacao.value}" não tem a parte do "o que fazer" separada por linha em branco'
        )

    @pytest.mark.parametrize('caixa', todas_as_caixas(), ids=lambda c: c.situacao.value)
    def test_titulo_e_curto_e_sem_quebra(self, caixa: EspecificacaoCaixa) -> None:
        """O título vive numa title bar de uma linha."""
        assert '\n' not in caixa.titulo
        assert len(caixa.titulo) <= 60, f'título longo demais para a barra: "{caixa.titulo}"'


class TestRoteamento:
    """A severidade decide sozinha se a mensagem interrompe ou passa."""

    @pytest.mark.parametrize('severidade', [Severidade.CRITICO, Severidade.ERRO])
    def test_grave_abre_a_caixa(self, severidade: Severidade) -> None:
        assert severidade.abre_caixa

    @pytest.mark.parametrize('severidade', [Severidade.AVISO, Severidade.INFO])
    def test_leve_vira_toast(self, severidade: Severidade) -> None:
        assert not severidade.abre_caixa

    def test_aquisicao_interrompida_e_critica(self) -> None:
        """A fita fica acesa na última cor depois que a aquisição morre — isso precisa interromper."""
        caixa = catalogo_erros.aquisicao_parou_bitalino(OSError('stream perdido'))
        assert caixa.severidade is Severidade.CRITICO
        assert caixa.severidade.abre_caixa

    def test_irritacao_de_ferramenta_nao_interrompe(self) -> None:
        """Não abrir uma pasta não pode congelar a tela no meio de uma performance."""
        caixa = catalogo_erros.pasta_logs_inacessivel(Path('C:/logs'))
        assert not caixa.severidade.abre_caixa

    def test_falha_inesperada_exige_ciencia(self) -> None:
        """É a única não dispensável: seguir usando um programa em estado desconhecido é pior."""
        caixa = catalogo_erros.falha_inesperada(RuntimeError('bug'))
        assert not caixa.dispensavel
        assert caixa.acoes, 'não dispensável obriga a ter botão — senão prende'


class TestDetalheTecnico:
    def test_com_detalhe_traz_tipo_e_mensagem(self) -> None:
        """O detalhe existe para ser colado num relato; sem o tipo da exceção ele vale pouco."""
        caixa = catalogo_erros.falha_conexao_arduino(PermissionError('porta ocupada'))
        assert 'PermissionError' in caixa.detalhe
        assert 'porta ocupada' in caixa.detalhe

    def test_detalhe_e_opcional(self) -> None:
        """Situações sem nada técnico a dizer não mostram a seção recolhida."""
        assert catalogo_erros.sem_arquivo_de_log().detalhe == ''

    def test_com_detalhe_nao_altera_o_resto(self) -> None:
        base = catalogo_erros.sem_arquivo_de_log()
        comdetalhe = base.com_detalhe(OSError('x'))
        assert comdetalhe.situacao is base.situacao
        assert comdetalhe.mensagem == base.mensagem
        assert comdetalhe.severidade is base.severidade


class TestAcoes:
    def test_ok_e_aceitar(self) -> None:
        assert ACAO_OK.papel is PapelAcao.ACEITAR

    @pytest.mark.parametrize('caixa', todas_as_caixas(), ids=lambda c: c.situacao.value)
    def test_erros_nao_perguntam_nada(self, caixa: EspecificacaoCaixa) -> None:
        """Hoje todo erro é notícia consumada. Confirmação virá pelo mesmo contrato, com
        `CONFIRMAR`/`RECUSAR` — este teste é o que vai avisar quando isso mudar."""
        assert all(acao.papel is PapelAcao.ACEITAR for acao in caixa.acoes)
