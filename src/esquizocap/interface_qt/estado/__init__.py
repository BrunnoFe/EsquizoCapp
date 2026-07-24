"""Estado da interface: a regra pura de prontidão e os dataclasses de estado por concern.

O subpacote reúne, num lugar só, o que a GUI precisa saber sobre "em que ponto do fluxo
estamos" e "o que o usuário escolheu": a regra de prontidão (`prontidao`) e os quatro
retratos de estado por concern (`configuracao`, `ao_vivo`, `aparencia_visual`,
`conexoes_hardware`). Este `__init__` reexporta a superfície pública de `prontidao` para que
quem já importava `from ...interface_qt.estado import EstadoApp` continue funcionando sem
saber que a regra passou a morar num submódulo.
"""

from esquizocap.interface_qt.estado.prontidao import (
    CANAIS_COM_ROTULO,
    CANAIS_NA_ORDEM_DO_SELETOR,
    CANAIS_VALIDOS,
    MODELOS_DISPONIVEIS,
    ROTULOS_DOS_CANAIS,
    TEXTO_CANAL_NAO_ESCOLHIDO,
    TEXTO_PORTA_NAO_ENCONTRADA,
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    aviso_de_taxa,
    aviso_do_canal,
    mensagem_de_aquisicao,
    rotulo_do_canal,
    taxa_minima_para_analise_espectral,
    taxas_selecionaveis,
)

__all__ = [
    'CANAIS_COM_ROTULO',
    'CANAIS_NA_ORDEM_DO_SELETOR',
    'CANAIS_VALIDOS',
    'MODELOS_DISPONIVEIS',
    'ROTULOS_DOS_CANAIS',
    'TEXTO_CANAL_NAO_ESCOLHIDO',
    'TEXTO_PORTA_NAO_ENCONTRADA',
    'EstadoApp',
    'SelecaoUsuario',
    'avaliar_prontidao',
    'aviso_de_taxa',
    'aviso_do_canal',
    'mensagem_de_aquisicao',
    'rotulo_do_canal',
    'taxa_minima_para_analise_espectral',
    'taxas_selecionaveis',
]
