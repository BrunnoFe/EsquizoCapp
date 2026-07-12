"""Exportação das gravações para Excel.

Este módulo NÃO pergunta nada ao usuário e NÃO mostra caixas de diálogo. A versão
anterior abria um `Querybox` pedindo o nome do arquivo no meio da função de dados: quem
decide o nome é a interface; a infraestrutura recebe o caminho pronto e grava.

Também não há mais `reshape` com números mágicos. Os DataFrames são montados a partir da
lista de `ResultadoCiclo`, que já carrega tudo o que a gravação precisa.
"""

import logging
from pathlib import Path

import pandas as pd

from esquizocap.dominio.ciclo_aquisicao import ResultadoCiclo

logger = logging.getLogger(__name__)

COLUNAS_AMPLITUDE = ['Timestamp', 'Dados EEG', 'Predição de cor']
COLUNAS_ANALISE_FREQUENCIA = [
    'Rodada',
    'Timestamp',
    'Frequência Dominante',
    'Power',
    'Predição de cor',
    'Faixa de Frequência',
]


class ErroDeGravacao(Exception):
    """Não foi possível gravar o arquivo (ex.: o Excel está com ele aberto)."""


def nome_sugerido(modo: str) -> str:
    """Nome default para o arquivo, que a interface oferece ao usuário."""
    return f'Gravação {modo}_{pd.Timestamp.now():%d_%m_%Y_%H_%M_%S}'


def salvar_gravacao(resultados: list[ResultadoCiclo], destino: Path) -> None:
    """Grava os resultados de uma aquisição num arquivo Excel.

    O modo é inferido dos próprios dados: só o modo Frequência produz `janela` e
    `potencia`.

    Args:
        resultados: Os ciclos que produziram resultado, na ordem em que aconteceram.
        destino: Caminho completo do `.xlsx` a ser criado.

    Raises:
        ErroDeGravacao: Se o arquivo não puder ser escrito.
        ValueError: Se a lista estiver vazia — gravar nada é um erro de quem chama.
    """
    if not resultados:
        raise ValueError('Nada a gravar: a lista de resultados está vazia.')

    destino.parent.mkdir(parents=True, exist_ok=True)
    e_frequencia = resultados[0].janela is not None

    try:
        if e_frequencia:
            _salvar_frequencia(resultados=resultados, destino=destino)
        else:
            _salvar_amplitude(resultados=resultados, destino=destino)
    except (PermissionError, OSError) as erro:
        raise ErroDeGravacao(
            f'Não foi possível gravar em "{destino}": {erro}. '
            'Se o arquivo estiver aberto no Excel, feche-o e tente de novo.'
        ) from erro

    logger.info(f'Gravação salva em "{destino}" ({len(resultados)} registros)')


def _salvar_amplitude(resultados: list[ResultadoCiclo], destino: Path) -> None:
    dados = pd.DataFrame(
        [(r.timestamp, r.metrica_bruta, r.hue) for r in resultados],
        columns=COLUNAS_AMPLITUDE,
    )
    dados.to_excel(destino, index=False, sheet_name='Data')


def _salvar_frequencia(resultados: list[ResultadoCiclo], destino: Path) -> None:
    # Aba "Data": para cada rodada, uma linha com as amostras e outra com os timestamps.
    # É o mesmo layout de antes, mas montado explicitamente em vez de por um reshape.
    linhas_brutas = []
    for resultado in resultados:
        if resultado.janela is None:  # pragma: no cover - garantido pelo modo
            continue
        linhas_brutas.append(resultado.janela.amostras)
        linhas_brutas.append(resultado.janela.timestamps)

    janelas = pd.DataFrame(linhas_brutas, dtype='float32')

    analise = pd.DataFrame(
        [
            (rodada, r.timestamp, r.metrica_bruta, r.potencia, r.hue, r.faixa_frequencia)
            for rodada, r in enumerate(resultados, start=1)
        ],
        columns=COLUNAS_ANALISE_FREQUENCIA,
    )

    with pd.ExcelWriter(destino, engine='openpyxl') as escritor:
        janelas.to_excel(escritor, sheet_name='Data', index=False)
        analise.to_excel(escritor, sheet_name='Analysis', index=False)
