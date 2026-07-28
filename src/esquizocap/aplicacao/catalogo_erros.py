"""O catálogo de mensagens que a interface mostra quando algo dá errado.

Existe por dois motivos.

O primeiro é que a mensagem de erro é **texto de produto**, não detalhe de implementação.
Espalhada em f-strings por dentro do controller, ninguém consegue revisar a redação de
todas de uma vez, nem garantir que duas situações parecidas falem a mesma língua. Aqui elas
ficam lado a lado. É o mesmo raciocínio que pôs `TEXTO_PORTA_NAO_ENCONTRADA` numa constante
compartilhada em `interface/estado/prontidao.py`.

O segundo é que a camada de aplicação já assumiu essa responsabilidade — o `EventoErro` de
`servico_aquisicao.py` diz na própria docstring que a GUI não deveria estar traduzindo tipo
de exceção em português. Na prática só um punhado de pontos passava por lá. Este módulo é
onde a regra passa a valer para todos.

A tradução é feita por **situação**, não por tipo de exceção, e isso é deliberado: o mesmo
`OSError` significa "escolha outra pasta de gravação" num lugar e "seu explorador de
arquivos não abriu" noutro. Quem carrega a informação útil é o local da chamada, não a
classe do erro.

Cada situação é uma função que monta a `EspecificacaoCaixa` já com os valores do momento
(a porta, o caminho, o detalhe do erro). A identidade estável de cada uma vive em
`Situacao`, e é por ela que os testes afirmam qual erro aconteceu — comparar por substring
em português faria todo teste quebrar na primeira revisão de copy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, unique
from pathlib import Path


@unique
class Severidade(Enum):
    """Quão grave é, e por consequência onde a mensagem aparece.

    A gravidade decide sozinha o destino na tela (ver `abre_caixa`): o que interrompe a
    obra merece uma caixa no centro; o que é recado de ferramenta não pode roubar a cena.
    """

    CRITICO = 'critico'
    """A obra parou ou está mostrando coisa errada agora. Interrompe."""

    ERRO = 'erro'
    """Uma ação pedida não aconteceu. Interrompe, mas nada em curso foi perdido."""

    AVISO = 'aviso'
    """Algo merece atenção, sem impedir o que estava sendo feito."""

    INFO = 'info'
    """Recado de ferramenta. Aparece e sai sozinho."""

    @property
    def abre_caixa(self) -> bool:
        """Se abre a caixa modal central. Caso contrário, vira um toast passageiro."""
        return self in (Severidade.CRITICO, Severidade.ERRO)


@unique
class PapelAcao(Enum):
    """O que um botão significa — não o que ele diz.

    O papel, e não o rótulo, é o que decide a cor do botão, qual deles o Enter aciona e
    qual o ESC aciona. Uma lista de rótulos soltos não carrega nada disso.
    """

    ACEITAR = 'aceitar'
    """Dar ciência. Não desfaz nem confirma nada; é o "OK"."""

    CONFIRMAR = 'confirmar'
    """Seguir com a ação proposta. Acionado pelo Enter."""

    RECUSAR = 'recusar'
    """Não seguir, tendo havido uma pergunta de verdade."""

    CANCELAR = 'cancelar'
    """Sair sem decidir. É o papel que o ESC e o X acionam, quando existe."""

    DESFAZER = 'desfazer'
    """Reverter o que a mensagem está anunciando.

    Só faz sentido num toast: a caixa modal aparece ANTES do fato, o toast aparece depois.
    Ignorá-lo (deixar o toast expirar) confirma a ação."""


@unique
class Situacao(Enum):
    """A identidade estável de cada entrada do catálogo.

    Ser um `Enum` com `@unique` é o que garante que dois erros não compartilhem nome, sem
    precisar de um teste que varra o módulo.
    """

    AQUISICAO_PAROU_BITALINO = 'aquisicao_parou_bitalino'
    AQUISICAO_PAROU_ARDUINO = 'aquisicao_parou_arduino'
    FALHA_CONEXAO_ARDUINO = 'falha_conexao_arduino'
    FALHA_CONEXAO_BITALINO = 'falha_conexao_bitalino'
    CONECTANDO_BITALINO = 'conectando_bitalino'
    """Segundo caso do catálogo em que nada deu errado — aqui nem sequer terminou.

    É uma mensagem EM ANDAMENTO: aparece quando a tentativa de conexão começa e é retirada
    quando ela acaba, com sucesso ou não. Vive no catálogo pelo mesmo motivo que
    `APARENCIA_RESTAURADA`: `EspecificacaoCaixa` é o contrato de qualquer mensagem do app,
    e abrir um segundo caminho só para esperas custaria mais do que resolve."""
    SIMULACAO_BLOQUEADA = 'simulacao_bloqueada'
    FALHA_AO_SALVAR_GRAVACAO = 'falha_ao_salvar_gravacao'
    PASTA_GRAVACOES_NAO_CRIADA = 'pasta_gravacoes_nao_criada'
    PASTA_GRAVACOES_INACESSIVEL = 'pasta_gravacoes_inacessivel'
    PASTA_LOGS_INACESSIVEL = 'pasta_logs_inacessivel'
    SEM_ARQUIVO_DE_LOG = 'sem_arquivo_de_log'
    LOG_INACESSIVEL = 'log_inacessivel'
    ERRO_INESPERADO_NA_AQUISICAO = 'erro_inesperado_na_aquisicao'
    FALHA_INESPERADA = 'falha_inesperada'
    APARENCIA_RESTAURADA = 'aparencia_restaurada'
    """Único caso do catálogo em que nada deu errado.

    Está aqui porque `EspecificacaoCaixa` é o contrato de qualquer mensagem do app, e não
    só das ruins — manter um segundo caminho paralelo para confirmações seria pior."""


@dataclass(frozen=True)
class Acao:
    """Um botão da caixa."""

    papel: PapelAcao
    rotulo: str


ACAO_OK = Acao(papel=PapelAcao.ACEITAR, rotulo='OK')
"""O único botão que o catálogo usa hoje. Confirmações virão pelo mesmo caminho."""


@dataclass(frozen=True)
class EspecificacaoCaixa:
    """Tudo o que a interface precisa para desenhar uma caixa de mensagem.

    Deliberadamente não sabe o que é um erro: é o contrato genérico de qualquer pop-up do
    app. Erro é apenas o primeiro cliente — uma confirmação futura ("descartar a gravação?")
    monta a mesma estrutura com dois botões e severidade `AVISO`.

    Levanta:
        ValueError: se uma caixa não-dispensável não tiver nenhuma ação. Ver `__post_init__`.
    """

    situacao: Situacao
    severidade: Severidade
    titulo: str
    mensagem: str
    """Texto humano. Pode ter várias linhas, e tipicamente tem: o que aconteceu, linha em
    branco, o que fazer a respeito. A segunda metade é a que importa para quem está com a
    instalação montada e a exposição para abrir."""

    acoes: tuple[Acao, ...]
    dispensavel: bool
    """Se ESC, o X e o clique fora fecham a caixa.

    Sem valor padrão de propósito. Uma caixa que não pode ser dispensada prende quem está
    operando a obra, possivelmente com público na sala — isso tem que ser uma escolha
    consciente por situação, não o que sobra de um descuido."""

    detalhe: str = ''
    """Contexto técnico (tipo da exceção, mensagem original). Fica numa seção recolhida e é
    opcional: situações que não têm nada técnico a dizer não mostram a seção."""

    def __post_init__(self) -> None:
        if not self.dispensavel and not self.acoes:
            raise ValueError(
                f'A caixa "{self.situacao.value}" não é dispensável e não tem nenhuma ação: '
                'quem estiver operando ficaria preso na tela, sem ESC nem botão. '
                'Dê a ela ao menos uma ação, ou marque-a como dispensável.'
            )

    def com_detalhe(self, erro: BaseException) -> EspecificacaoCaixa:
        """Devolve uma cópia com o detalhe técnico preenchido a partir da exceção."""
        return replace(self, detalhe=f'{type(erro).__name__}: {erro}')


def _caixa(
    situacao: Situacao,
    severidade: Severidade,
    titulo: str,
    mensagem: str,
    dispensavel: bool = True,
    acoes: tuple[Acao, ...] = (ACAO_OK,),
) -> EspecificacaoCaixa:
    """Atalho interno: toda entrada do catálogo tem botão "OK" e é dispensável, salvo dito."""
    return EspecificacaoCaixa(
        situacao=situacao,
        severidade=severidade,
        titulo=titulo,
        mensagem=mensagem,
        acoes=acoes,
        dispensavel=dispensavel,
    )


# ---- aquisição ------------------------------------------------------------------
# Estas são CRÍTICAS porque a fita de LED continua acesa depois que a aquisição morre: sem
# um aviso no centro da tela, a cor congelada passa por escolha artística.


def aquisicao_parou_bitalino(erro: BaseException) -> EspecificacaoCaixa:
    """A aquisição morreu por perda do stream ou queda do BITalino."""
    return _caixa(
        situacao=Situacao.AQUISICAO_PAROU_BITALINO,
        severidade=Severidade.CRITICO,
        titulo='A aquisição parou',
        mensagem=(
            f'O sinal do BITalino foi interrompido: {erro}\n\n'
            'A fita de LED parou de acompanhar o sinal e segue na última cor calculada.\n\n'
            'Verifique se o OpenSignals continua aberto, com o compartilhamento '
            '"Lab Streaming Layer" ativo, e se o BITalino segue ligado e ao alcance. '
            'Depois disso, inicie a aquisição outra vez.'
        ),
    ).com_detalhe(erro)


def aquisicao_parou_arduino(erro: BaseException) -> EspecificacaoCaixa:
    """A aquisição morreu porque o Arduino saiu do ar no meio."""
    return _caixa(
        situacao=Situacao.AQUISICAO_PAROU_ARDUINO,
        severidade=Severidade.CRITICO,
        titulo='A aquisição parou',
        mensagem=(
            f'A comunicação com o Arduino foi interrompida: {erro}\n\n'
            'A fita de LED parou de receber comandos.\n\n'
            'Verifique o cabo USB e se a placa continua energizada. Se o cabo foi '
            'reconectado, a porta serial pode ter mudado de nome — confira a porta '
            'selecionada antes de tentar de novo.'
        ),
    ).com_detalhe(erro)


def erro_inesperado_na_aquisicao(erro: BaseException) -> EspecificacaoCaixa:
    """A thread de aquisição morreu por um erro que não é de hardware — ou seja, um bug."""
    return _caixa(
        situacao=Situacao.ERRO_INESPERADO_NA_AQUISICAO,
        severidade=Severidade.CRITICO,
        titulo='Erro inesperado na aquisição',
        mensagem=(
            'A aquisição parou por um defeito do programa, não do hardware.\n\n'
            'Nada que você fez causou isto, e tentar de novo provavelmente esbarra no '
            'mesmo ponto. O traceback completo está no arquivo de log — a aba '
            '"Diagnóstico" das configurações abre a pasta.'
        ),
    ).com_detalhe(erro)


# ---- conexão --------------------------------------------------------------------


def falha_conexao_arduino(erro: BaseException) -> EspecificacaoCaixa:
    """Não foi possível abrir a porta serial do Arduino."""
    return _caixa(
        situacao=Situacao.FALHA_CONEXAO_ARDUINO,
        severidade=Severidade.ERRO,
        titulo='Não foi possível conectar ao Arduino',
        mensagem=(
            f'A porta serial não respondeu: {erro}\n\n'
            'Confira se o cabo USB está firme, se a porta selecionada é mesmo a da placa '
            'e se nenhum outro programa (a IDE do Arduino, um monitor serial) está com a '
            'porta aberta — duas coisas não podem usar a mesma porta ao mesmo tempo.'
        ),
    ).com_detalhe(erro)


def falha_conexao_bitalino(mensagem_erro: str) -> EspecificacaoCaixa:
    """A tentativa de conexão do BITalino terminou sem sucesso.

    Recebe texto e não exceção porque a conexão roda numa thread auxiliar e volta pelo
    sinal `bitalinoConexaoFinalizada`, que só atravessa tipos simples.
    """
    return _caixa(
        situacao=Situacao.FALHA_CONEXAO_BITALINO,
        severidade=Severidade.ERRO,
        titulo='Não foi possível conectar ao BITalino',
        mensagem=(
            f'A conexão não se completou: {mensagem_erro}\n\n'
            'No modo OpenSignals, confira se o programa está aberto e com o '
            'compartilhamento "Lab Streaming Layer" ativo. No modo Direto, confira se o '
            'aparelho está ligado, pareado por Bluetooth e se o endereço informado é o dele.'
        ),
        # O detalhe repetiria a mesma frase que já está na mensagem: o texto que chega aqui
        # já é a mensagem da exceção original, não o objeto.
    )


def conectando_bitalino() -> EspecificacaoCaixa:
    """A conexão do BITalino começou e ainda não voltou.

    Existe porque conectar leva SEGUNDOS — resolver o stream LSL ou abrir a porta serial —
    e até aqui o app não dizia nada nesse intervalo. Iniciar a aquisição com o aparelho
    desconectado conecta primeiro (ver `EsquizoController.iniciarAquisicao`), então a espera
    acontece longe do painel de setup, onde nem o botão de conectar está à vista.

    É INFO: vira toast, nunca caixa modal. Uma caixa no centro da tela por causa de uma
    espera normal atrapalharia mais do que a espera. Quem a mostra retira quando ela termina
    (`_ao_concluir_conexao_bitalino`) — não é um recado que expira sozinho.
    """
    return _caixa(
        situacao=Situacao.CONECTANDO_BITALINO,
        severidade=Severidade.INFO,
        titulo='Conectando ao BITalino',
        mensagem='Procurando o aparelho. Pode levar alguns segundos.',
    )


# ---- simulação ------------------------------------------------------------------


def simulacao_bloqueada(motivo: str) -> EspecificacaoCaixa:
    """A troca de simulação foi recusada porque há hardware em uso.

    É AVISO, e não erro: nada quebrou, o pedido só não cabe agora. Vira um toast — abrir
    uma caixa modal por causa de um clique num interruptor seria desproporcional.
    """
    return _caixa(
        situacao=Situacao.SIMULACAO_BLOQUEADA,
        severidade=Severidade.AVISO,
        titulo='Simulação não pode ser alterada agora',
        mensagem=f'{motivo}\n\nDesconecte o aparelho ou pare a aquisição e tente de novo.',
    )


# ---- gravação -------------------------------------------------------------------


def falha_ao_salvar_gravacao(erro: BaseException) -> EspecificacaoCaixa:
    """O arquivo da gravação não pôde ser escrito."""
    return _caixa(
        situacao=Situacao.FALHA_AO_SALVAR_GRAVACAO,
        severidade=Severidade.ERRO,
        titulo='Não foi possível salvar a gravação',
        mensagem=(
            f'O arquivo não pôde ser escrito: {erro}\n\n'
            'Os dados NÃO foram perdidos: a gravação segue pendente e você pode escolher '
            'outro destino. Se o arquivo já existe e está aberto no Excel, feche-o antes '
            'de tentar outra vez.'
        ),
    ).com_detalhe(erro)


def pasta_gravacoes_nao_criada(pasta: Path, erro: BaseException) -> EspecificacaoCaixa:
    """A pasta configurada para as gravações não pôde ser criada."""
    return _caixa(
        situacao=Situacao.PASTA_GRAVACOES_NAO_CRIADA,
        severidade=Severidade.ERRO,
        titulo='Não foi possível criar a pasta de gravações',
        mensagem=(
            f'A pasta "{pasta}" não pôde ser criada: {erro}\n\n'
            'Os dados NÃO foram perdidos: a gravação segue pendente. Escolha outra pasta '
            'na aba "Gravação" das configurações — uma em que seu usuário possa escrever — '
            'e salve de novo.'
        ),
    ).com_detalhe(erro)


def pasta_gravacoes_inacessivel(pasta: Path, erro: BaseException | None = None) -> EspecificacaoCaixa:
    """O explorador de arquivos não abriu a pasta de gravações.

    Irritação de ferramenta: nada do que importa quebrou, então vira toast.
    """
    caixa = _caixa(
        situacao=Situacao.PASTA_GRAVACOES_INACESSIVEL,
        severidade=Severidade.INFO,
        titulo='Não foi possível abrir a pasta de gravações',
        mensagem=(
            f'O explorador de arquivos não abriu "{pasta}".\n\n'
            'A pasta continua valendo para salvar; só a abertura falhou. Você pode chegar '
            'nela pelo explorador do sistema.'
        ),
    )
    return caixa.com_detalhe(erro) if erro is not None else caixa


# ---- diagnóstico ----------------------------------------------------------------


def pasta_logs_inacessivel(pasta: Path) -> EspecificacaoCaixa:
    """O explorador de arquivos não abriu a pasta de logs."""
    return _caixa(
        situacao=Situacao.PASTA_LOGS_INACESSIVEL,
        severidade=Severidade.INFO,
        titulo='Não foi possível abrir a pasta de logs',
        mensagem=(
            f'O explorador de arquivos não abriu "{pasta}".\n\n'
            'O caminho acima é o correto — dá para chegar nele pelo explorador do sistema.'
        ),
    )


def sem_arquivo_de_log() -> EspecificacaoCaixa:
    """Pediram para abrir o log, mas esta execução ainda não escreveu nenhum."""
    return _caixa(
        situacao=Situacao.SEM_ARQUIVO_DE_LOG,
        severidade=Severidade.INFO,
        titulo='Ainda não há arquivo de log',
        mensagem=(
            'Esta execução ainda não escreveu nada em disco.\n\n'
            'O arquivo é criado na primeira mensagem registrada; tente de novo depois de '
            'usar o programa um pouco.'
        ),
    )


def log_inacessivel(arquivo: Path) -> EspecificacaoCaixa:
    """O arquivo de log existe, mas não abriu no programa padrão do sistema."""
    return _caixa(
        situacao=Situacao.LOG_INACESSIVEL,
        severidade=Severidade.INFO,
        titulo='Não foi possível abrir o log',
        mensagem=(
            f'O sistema não abriu "{arquivo}".\n\n'
            'É um arquivo de texto comum: qualquer editor abre, se você chegar nele pelo '
            'explorador do sistema.'
        ),
    )


# ---- rede de segurança ----------------------------------------------------------


def falha_inesperada(erro: BaseException) -> EspecificacaoCaixa:
    """Uma exceção que ninguém previu escapou até o topo.

    Esta é a única entrada NÃO dispensável do catálogo, e a razão é o modo de falha que
    mais custa neste projeto: sem isso, a exceção sobe até o Qt, que a imprime no console e
    segue. Janela viva, fita acesa, dado mentindo, nada na tela. Aqui alguém precisa dar
    ciência antes de continuar usando um programa cujo estado é desconhecido.
    """
    return _caixa(
        situacao=Situacao.FALHA_INESPERADA,
        severidade=Severidade.CRITICO,
        titulo='Erro inesperado',
        mensagem=(
            'O programa encontrou um defeito interno.\n\n'
            'Isto não é falha do hardware nem do que você fez. O que estava em curso pode '
            'ter ficado num estado inconsistente — se a aquisição estava rodando, vale '
            'pará-la e começar de novo.\n\n'
            'O traceback completo está no arquivo de log, e o botão abaixo copia o '
            'resumo técnico para você anexar a um relato.'
        ),
        dispensavel=False,
    ).com_detalhe(erro)


# ---- confirmações -----------------------------------------------------------------


ACAO_DESFAZER = Acao(papel=PapelAcao.DESFAZER, rotulo='Desfazer')


def aparencia_restaurada(secao: str) -> EspecificacaoCaixa:
    """Confirma que uma seção do painel de aparência voltou à fábrica, oferecendo o desfazer.

    O toast é a única rede de segurança deste gesto — não há diálogo antes, de propósito:
    um modal na frente da projeção durante a exposição custa mais do que o clique errado.
    """
    return _caixa(
        situacao=Situacao.APARENCIA_RESTAURADA,
        severidade=Severidade.INFO,
        titulo=f'{secao} restaurado',
        mensagem='Os controles desta seção voltaram aos valores de fábrica.',
        acoes=(ACAO_DESFAZER,),
    )
