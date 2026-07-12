"""Localização dos arquivos que acompanham a aplicação (imagens, ícones).

Isto não é configuração: são arquivos que vêm junto com o código. Estavam no
`configs.json` como se fossem ajustáveis, o que não faz sentido — apontar `icon` para
outro caminho não é uma decisão que alguém queira tomar.

Os caminhos ainda são relativos à raiz do projeto, ou seja, a aplicação continua exigindo
o CWD correto. Resolver isso de vez (via `importlib.resources`) está no PLANO_ACAO.md,
item 9.
"""

from pathlib import Path

PASTA_IMAGENS = Path('images')
PASTA_LOGS = Path('logs')

ICONE = PASTA_IMAGENS / 'esquizo_ico.ico'
FOTO_TITULO = PASTA_IMAGENS / 'esquizo.png'
CIRCULO_VERDE = PASTA_IMAGENS / 'green_circle.png'
CIRCULO_VERMELHO = PASTA_IMAGENS / 'red_circle.png'
PASTA_GIF_CARREGAMENTO = PASTA_IMAGENS / 'gif'


class ErroDeRecurso(Exception):
    """Um arquivo que deveria acompanhar a aplicação não foi encontrado."""


def validar() -> None:
    """Confere que os assets existem, ANTES de a GUI tentar carregá-los.

    Sem isso, um arquivo faltando vira um erro obscuro do Tkinter no meio da montagem da
    janela. Aqui o erro diz o que falta e por quê.

    Raises:
        ErroDeRecurso: Se algum asset essencial estiver ausente.
    """
    essenciais = (ICONE, FOTO_TITULO, CIRCULO_VERDE, CIRCULO_VERMELHO)
    faltando = [str(caminho) for caminho in essenciais if not caminho.exists()]

    if faltando:
        raise ErroDeRecurso(
            f'Arquivos da aplicação não encontrados: {faltando}. '
            'Rode a aplicação a partir da raiz do projeto.'
        )
