"""Todo `iconName` usado no QML desenha alguma coisa.

O `IconGlyph` casa `name` contra uma lista fixa de `Shape`s e não tem caso padrão. Um nome
digitado errado não quebra a carga do QML nem emite aviso: só deixa todas as formas
invisíveis, e o botão aparece vazio. É a armadilha de sempre aqui — o erro não levanta
exceção, ele produz uma tela plausível.

Os nomes não são escritos à mão: saem do próprio QML, para que um ícone novo entre na
cobertura sem ninguém lembrar de vir aqui.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).parent / 'carga_icones_offscreen.py'
QML = RAIZ / 'src' / 'esquizocap' / 'interface' / 'qml' / 'EsquizoCap'
NOME_INEXISTENTE = 'nao_existe_este_icone'
TEMPO_LIMITE_SEGUNDOS = 120


def _nomes_usados_no_qml() -> list[str]:
    nomes = {
        achado
        for arquivo in QML.rglob('*.qml')
        for achado in re.findall(r'iconName:\s*"([^"]+)"', arquivo.read_text(encoding='utf-8'))
    }
    assert nomes, 'Nenhum iconName encontrado no QML — o padrão de busca ficou obsoleto.'
    return sorted(nomes)


@pytest.fixture(scope='module')
def formas_por_icone() -> dict[str, int]:
    """Instancia todos os ícones de uma vez: subir o motor QML custa alguns segundos."""
    nomes = [*_nomes_usados_no_qml(), NOME_INEXISTENTE]
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT), *nomes],
        capture_output=True,
        text=True,
        timeout=TEMPO_LIMITE_SEGUNDOS,
        cwd=RAIZ,
    )
    assert resultado.returncode == 0, f'{resultado.stdout}\n{resultado.stderr}'

    return {
        nome: int(quantidade) for nome, quantidade in (linha.split('\t') for linha in resultado.stdout.splitlines())
    }


@pytest.mark.parametrize('nome', _nomes_usados_no_qml())
def test_cada_icone_do_qml_desenha_exatamente_uma_forma(nome: str, formas_por_icone: dict[str, int]) -> None:
    assert formas_por_icone[nome] == 1, (
        f'IconGlyph "{nome}" desenhou {formas_por_icone[nome]} formas. '
        'Zero quase sempre é typo entre o iconName do QML e o switch do IconGlyph.'
    )


def test_um_nome_desconhecido_nao_desenha_nada(formas_por_icone: dict[str, int]) -> None:
    """Sem isto, o teste acima passaria mesmo que a contagem sempre desse 1."""
    assert formas_por_icone[NOME_INEXISTENTE] == 0
