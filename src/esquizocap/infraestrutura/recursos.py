"""Localização dos arquivos que acompanham a aplicação.

Isto não é configuração: são arquivos que vêm junto com o código. Estavam no
`configs.json` como se fossem ajustáveis, o que não faz sentido — apontar `icone` para
outro caminho não é uma decisão que alguém queira tomar.

Os caminhos ainda são relativos à raiz do projeto, ou seja, a aplicação continua exigindo
o CWD correto. Resolver isso de vez (via `importlib.resources`) está no PLANO_ACAO.md,
item 9.
"""

from pathlib import Path

PASTA_LOGS = Path('logs')

ICONE = Path('assets') / 'ico.ico'
"""Ícone da janela. Antes apontava para `images/esquizo_ico.ico`, um asset exclusivo da
interface Tkinter (junto com a foto de título e os círculos verde/vermelho de status —
a GUI Qt desenha tudo isso em QML vetorial, sem imagem nenhuma). Reaproveita o ícone que
já existia na raiz do repositório."""


class ErroDeRecurso(Exception):
    """Um arquivo que deveria acompanhar a aplicação não foi encontrado."""


def validar() -> None:
    """Confere que os assets essenciais existem, ANTES de a GUI tentar carregá-los.

    Raises:
        ErroDeRecurso: Se o ícone da janela estiver ausente.
    """
    if not ICONE.exists():
        raise ErroDeRecurso(
            f'Ícone da aplicação não encontrado em "{ICONE}". '
            'Rode a aplicação a partir da raiz do projeto.'
        )
