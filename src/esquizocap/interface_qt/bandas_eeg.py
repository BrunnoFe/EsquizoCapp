"""Bandas de EEG humano exibidas na órbita da interface (Delta a Gamma).

É uma tabela de EXIBIÇÃO, não de classificação: quem classifica a frequência
dominante numa banda é `dominio/pre_processamento.py`, que devolve uma string como
"Alpha (Relaxamento, calma)". Este módulo só traduz essa string para o índice que a
órbita usa para destacar a banda certa.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BandaEeg:
    """Uma banda de frequência de EEG, com o rótulo exibido na órbita."""

    nome: str
    faixa_frequencia: str


BANDAS_EEG: tuple[BandaEeg, ...] = (
    BandaEeg("Delta", "0.5–4 Hz"),
    BandaEeg("Theta", "4–8 Hz"),
    BandaEeg("Alpha", "8–13 Hz"),
    BandaEeg("Beta", "13–30 Hz"),
    BandaEeg("Gamma", "30–45 Hz"),
)

_NOMES_BANDAS_EEG: tuple[str, ...] = tuple(banda.nome for banda in BANDAS_EEG)


def indice_da_banda(faixa_frequencia_do_dominio: str) -> int:
    """Traduz a string de banda do domínio para o índice usado pela órbita.

    Args:
        faixa_frequencia_do_dominio: ex. "Alpha (Relaxamento, calma)" — o domínio
            anexa uma descrição depois do nome da banda.

    Returns:
        Índice em `BANDAS_EEG` (0=Delta .. 4=Gamma). Se a string não bater com
        nenhuma banda conhecida, devolve 0 (Delta) em vez de lançar — uma banda nova
        do lado do domínio não deveria derrubar a GUI.
    """
    primeira_palavra = faixa_frequencia_do_dominio.split(" ", 1)[0]
    try:
        return _NOMES_BANDAS_EEG.index(primeira_palavra)
    except ValueError:
        return 0
