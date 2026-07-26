"""Preferências do usuário, gravadas pela própria aplicação.

Este módulo é o irmão **mutável** de `config.py`, e a separação é deliberada:

- `Configuracao` é escrita por um humano, à mão, e descreve a *instalação* (quais MACs,
  qual modelo). Por isso é `frozen=True` e falha alto em chave desconhecida: uma chave com
  nome errado significa que alguém achou que estava configurando algo, e não estava.
- `Preferencias` é escrita pela **aplicação**, a cada ajuste do menu de configurações. Um
  arquivo corrompido, truncado por um desligamento na tomada, ou escrito por uma versão
  anterior **não pode impedir a instalação de subir**. Aqui a política se inverte: chave
  desconhecida ou valor inválido vira log de aviso e cai no default. Nunca levanta.

Sobre `aparencia`: os valores são guardados como um dicionário opaco, sem conferir faixa.
A tabela de faixas (`LIMITES_APARENCIA_VISUAL`) vive na camada de interface, e a
infraestrutura não importa de lá — quem aplica as preferências é que limita cada valor,
usando a tabela que já possui.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CAMINHO_PADRAO = Path('settings') / 'preferencias.json'


def _pasta_gravacoes_padrao() -> Path:
    return Path.home() / 'Documents' / 'EsquizoCap' / 'Data'


@dataclass
class Preferencias:
    """O que o menu de configurações guarda entre execuções."""

    componentes_simulados: frozenset[str] = frozenset()
    """Componentes de hardware a simular, entre os de `hardware.fabrica.COMPONENTES_CONHECIDOS`.

    A variável de ambiente `ESQUIZOCAP_FAKE`, quando definida, tem precedência sobre isto.
    """

    pasta_gravacoes: Path = field(default_factory=_pasta_gravacoes_padrao)
    """Destino das gravações em Excel."""

    perguntar_onde_salvar: bool = True
    """Se o diálogo de arquivo aparece antes de gravar. Falso = grava direto na pasta."""

    borda_de_simulacao: bool = False
    """Se a janela ganha uma borda de destaque enquanto algum hardware está simulado.

    O aviso mínimo (o chip na barra de topo e a marca em cada indicador de dispositivo) é
    sempre visível; esta opção só acrescenta o destaque mais gritante, útil para quem grava
    vídeo da instalação e não quer publicar uma demonstração simulada por engano.
    """

    aparencia: dict[str, float] = field(default_factory=dict)
    """Valores dos controles do painel "Aparência". Vazio = usa os defaults de
    `AparenciaVisual`. Chaves desconhecidas são descartadas por quem aplica."""


def _avisar_valor_invalido(chave: str, valor: object, caminho: Path) -> None:
    logger.warning(f'Valor inválido para "{chave}" em "{caminho}": {valor!r}. Usando o padrão.')


def _converter(dados: dict[str, object], caminho: Path) -> Preferencias:
    """Monta as `Preferencias` a partir do JSON cru, campo a campo, tolerando lixo.

    Cada campo é lido isoladamente para que um valor estragado custe só o seu próprio
    default, e não o arquivo inteiro.
    """
    preferencias = Preferencias()

    for chave in set(dados) - set(Preferencias.__dataclass_fields__):
        logger.warning(f'Chave desconhecida em "{caminho}", ignorada: "{chave}".')

    simulados = dados.get('componentes_simulados')
    if isinstance(simulados, list) and all(isinstance(item, str) for item in simulados):
        preferencias.componentes_simulados = frozenset(simulados)
    elif simulados is not None:
        _avisar_valor_invalido('componentes_simulados', simulados, caminho)

    pasta = dados.get('pasta_gravacoes')
    if isinstance(pasta, str) and pasta.strip():
        preferencias.pasta_gravacoes = Path(pasta)
    elif pasta is not None:
        _avisar_valor_invalido('pasta_gravacoes', pasta, caminho)

    for chave in ('perguntar_onde_salvar', 'borda_de_simulacao'):
        valor = dados.get(chave)
        if isinstance(valor, bool):
            setattr(preferencias, chave, valor)
        elif valor is not None:
            _avisar_valor_invalido(chave, valor, caminho)

    aparencia = dados.get('aparencia')
    if isinstance(aparencia, dict):
        # Os bools passariam por `isinstance(..., int)`, e um `True` virando 1.0 num slider
        # seria um valor plausível vindo de um tipo errado — exatamente o que não se quer.
        preferencias.aparencia = {
            str(nome): float(numero)
            for nome, numero in aparencia.items()
            if isinstance(numero, (int, float)) and not isinstance(numero, bool)
        }
        for nome, numero in aparencia.items():
            if nome not in preferencias.aparencia:
                _avisar_valor_invalido(f'aparencia.{nome}', numero, caminho)
    elif aparencia is not None:
        _avisar_valor_invalido('aparencia', aparencia, caminho)

    return preferencias


def carregar(caminho: Path = CAMINHO_PADRAO) -> Preferencias:
    """Lê as preferências do disco. Nunca levanta: qualquer problema vira default + log.

    Args:
        caminho: Arquivo JSON. Ausente = tudo nos defaults.
    """
    if not caminho.exists():
        return Preferencias()

    try:
        with open(caminho, encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
    except (json.JSONDecodeError, OSError) as erro:
        logger.warning(f'Não foi possível ler as preferências em "{caminho}": {erro}. Usando os padrões.')
        return Preferencias()

    if not isinstance(dados, dict):
        logger.warning(f'As preferências em "{caminho}" não são um objeto JSON. Usando os padrões.')
        return Preferencias()

    return _converter(dados, caminho)


def salvar(preferencias: Preferencias, caminho: Path = CAMINHO_PADRAO) -> None:
    """Grava as preferências. Uma falha é logada, não propagada.

    A escrita passa por um arquivo temporário seguido de `os.replace` (atômico no NTFS e
    no POSIX): a instalação pode ser desligada na tomada a qualquer momento, e um JSON
    escrito pela metade viraria um boot degradado na próxima abertura.
    """
    dados = asdict(preferencias)
    dados['componentes_simulados'] = sorted(preferencias.componentes_simulados)
    dados['pasta_gravacoes'] = str(preferencias.pasta_gravacoes)

    temporario = caminho.with_suffix('.json.tmp')
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(temporario, 'w', encoding='utf-8') as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        os.replace(temporario, caminho)
    except OSError as erro:
        logger.warning(f'Não foi possível gravar as preferências em "{caminho}": {erro}.')
        temporario.unlink(missing_ok=True)
