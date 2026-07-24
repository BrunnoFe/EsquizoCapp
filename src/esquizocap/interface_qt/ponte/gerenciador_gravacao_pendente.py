"""Gerencia a gravação pendente: os resultados de uma aquisição já terminada, à
espera de o usuário escolher onde salvar (ou descartar).

Encapsula a chamada a `infraestrutura/persistencia.py` para o controller não
precisar conhecer o formato de arquivo nem tratar a exceção de gravação diretamente.
"""

from pathlib import Path

from esquizocap.dominio.ciclo_aquisicao import ResultadoCiclo
from esquizocap.infraestrutura import persistencia
from esquizocap.infraestrutura.persistencia import ErroDeGravacao

__all__ = ['ErroDeGravacao', 'GerenciadorGravacaoPendente']


class GerenciadorGravacaoPendente:
    """Guarda os `ResultadoCiclo` de uma aquisição terminada até serem salvos ou
    descartados pelo usuário."""

    def __init__(self) -> None:
        self._resultados: list[ResultadoCiclo] = []
        self.nome_sugerido: str = ''

    @property
    def pendente(self) -> bool:
        """Há uma gravação esperando decisão do usuário?"""
        return bool(self._resultados)

    def oferecer(self, resultados: list[ResultadoCiclo], modo: str) -> None:
        """Registra os resultados de uma aquisição recém-terminada como pendentes.

        Args:
            resultados: Os ciclos gravados durante a aquisição. Uma lista vazia não
                torna nada pendente.
            modo: `ModoAnalise.value` usado na aquisição, para sugerir um nome de
                arquivo condizente.
        """
        if not resultados:
            return
        self._resultados = resultados
        self.nome_sugerido = persistencia.nome_sugerido(modo)

    def salvar_em(self, destino: Path) -> None:
        """Grava os resultados pendentes em `destino` e limpa a pendência.

        Não faz nada se não houver resultados pendentes (chamada seguinte a um
        `descartar`, por exemplo).

        Raises:
            ErroDeGravacao: Se o arquivo não puder ser escrito — propagada para o
                controller decidir como mostrar o erro ao usuário. A pendência é
                limpa mesmo quando a gravação falha: um erro de gravação não deve
                deixar a interface presa oferecendo salvar de novo o mesmo arquivo.
        """
        try:
            if self._resultados:
                persistencia.salvar_gravacao(resultados=self._resultados, destino=destino)
        finally:
            self._resultados = []

    def descartar(self) -> None:
        """Descarta os resultados pendentes sem salvar."""
        self._resultados = []
