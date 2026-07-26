"""O QML carrega sem avisos, com o motor de verdade e sem janela.

É o único teste que pega a classe de erro mais comum da camada QML: um nome de `Property`
que não existe no controller. O QML resolve nomes em runtime — `controller.naoExiste` não
quebra nada, só devolve `undefined` e emite um aviso. Nenhum teste de unidade alcança isso,
e na tela o sintoma é um valor em branco que passa por escolha de design.

A carga roda num processo separado; ver `carga_qml_offscreen.py` para o porquê.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / 'carga_qml_offscreen.py'
TEMPO_LIMITE_SEGUNDOS = 120


@pytest.fixture(scope='module')
def carga(tmp_path_factory: pytest.TempPathFactory) -> subprocess.CompletedProcess[str]:
    """Carrega o QML uma única vez: subir o motor custa alguns segundos."""
    preferencias = tmp_path_factory.mktemp('qml') / 'preferencias.json'
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(preferencias)],
        capture_output=True,
        text=True,
        timeout=TEMPO_LIMITE_SEGUNDOS,
        cwd=Path(__file__).resolve().parents[2],
    )


def test_o_qml_carrega_sem_nenhum_aviso(carga: subprocess.CompletedProcess[str]) -> None:
    assert carga.returncode == 0, (
        f'O motor QML reclamou:\n{carga.stdout}\n{carga.stderr}\n\n'
        'Aviso de QML quase sempre é nome de Property errado — confira contra o controller.'
    )
