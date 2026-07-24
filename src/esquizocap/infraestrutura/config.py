"""Configuração da aplicação.

O `settings/configs.json` antigo tinha 15 chaves, mas quase nada ali era configuração:
eram constantes de protocolo, textos de tooltip, índices de grid da GUI e caminhos de
assets. Isso foi distribuído para as camadas certas (`hardware/constantes.py`,
`interface/textos.py`, `infraestrutura/recursos.py`), e aqui sobrou só o que é
genuinamente uma escolha do usuário.

Regras deste módulo:

- A configuração é **imutável** (`frozen=True`). Nada a reescreve em runtime — o desenho
  anterior tinha uma função de *busca* que varria o disco e regravava o JSON, o que
  corrompia o arquivo se dois processos rodassem juntos.
- Os **defaults vivem no código**. O JSON é opcional e apenas sobrepõe. Assim existe uma
  única fonte de verdade e a aplicação sobe mesmo sem o arquivo.
- Um JSON inválido **falha alto**, com mensagem clara. Não se recria arquivo em silêncio.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CAMINHO_PADRAO = Path('settings') / 'configs.json'


class ErroDeConfiguracao(Exception):
    """O arquivo de configuração existe, mas está inválido."""


@dataclass(frozen=True)
class Configuracao:
    """As escolhas do usuário. Tudo mais é constante ou asset."""

    macs_bitalino: tuple[str, ...] = ('20:17:09:18:60:29', '12:25:33:81:92:44')
    """Endereços MAC dos BITalinos conhecidos.

    O MAC é também o `type` do stream LSL publicado pelo OpenSignals. Ainda é uma lista
    fixa: o certo seria descobrir os streams LSL disponíveis — ver PLANO_ACAO.md, item 7.
    """

    caminho_modelo: Path = Path('models') / 'BestModel_HSV_v1.pickle'
    """Modelo de árvore de decisão usado para prever o matiz."""

    pasta_gravacoes: Path = field(default_factory=lambda: Path.home() / 'Documents' / 'EsquizoCap' / 'Data')
    """Onde as gravações em Excel são salvas."""

    tema: str = 'solar'
    """Tema visual inicial da interface."""

    def validar(self) -> None:
        """Confere o que dá para conferir sem tocar no hardware.

        Raises:
            ErroDeConfiguracao: Se algo estiver inconsistente.
        """
        if not self.macs_bitalino:
            raise ErroDeConfiguracao('Nenhum endereço MAC de BITalino configurado.')

        for mac in self.macs_bitalino:
            if len(mac.split(':')) != 6:
                raise ErroDeConfiguracao(
                    f'Endereço MAC inválido na configuração: "{mac}". O formato esperado é "20:17:09:18:60:29".'
                )

        if not self.caminho_modelo.exists():
            raise ErroDeConfiguracao(
                f'Modelo não encontrado em "{self.caminho_modelo}". '
                'Rode a aplicação a partir da raiz do projeto, ou aponte "caminho_modelo" '
                'no arquivo de configuração para o .pickle correto.'
            )


def carregar(caminho: Path = CAMINHO_PADRAO) -> Configuracao:
    """Carrega a configuração, sobrepondo os defaults com o JSON, se ele existir.

    Args:
        caminho: Arquivo JSON opcional. Ausente = usa só os defaults.

    Raises:
        ErroDeConfiguracao: Se o JSON estiver malformado, tiver chaves desconhecidas ou
            valores inconsistentes.
    """
    if not caminho.exists():
        configuracao = Configuracao()
        configuracao.validar()
        return configuracao

    try:
        with open(caminho, encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ErroDeConfiguracao(f'O arquivo de configuração "{caminho}" não é um JSON válido: {erro}') from erro

    campos_validos = {campo.name for campo in Configuracao.__dataclass_fields__.values()}
    desconhecidas = set(dados) - campos_validos

    if desconhecidas:
        # Falha alto em vez de ignorar: uma chave com nome errado significa que o usuário
        # achou que estava configurando algo, e não estava.
        raise ErroDeConfiguracao(
            f'Chaves desconhecidas em "{caminho}": {sorted(desconhecidas)}. As válidas são: {sorted(campos_validos)}.'
        )

    if 'macs_bitalino' in dados:
        dados['macs_bitalino'] = tuple(dados['macs_bitalino'])
    for chave in ('caminho_modelo', 'pasta_gravacoes'):
        if chave in dados:
            dados[chave] = Path(dados[chave])

    configuracao = Configuracao(**dados)
    configuracao.validar()
    return configuracao
