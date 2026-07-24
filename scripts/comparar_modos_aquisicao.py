"""Compara o que os dois modos de aquisição leem do MESMO eletrodo.

Instrumento de bancada, não teste automatizado. Existe porque o risco principal do Modo
Direto — a conversão de unidade e o alinhamento dos canais — é INVISÍVEL para a suíte: o
leitor sintético responde igual pelos dois modos por construção, então nenhum teste com
fake pode revelar divergência entre dois hardwares reais.

Rode uma vez, na bancada, antes de a instalação ir ao ar. Com o eletrodo parado no mesmo
lugar, os dois modos têm que produzir números da mesma ordem de grandeza no canal ativo.

Uso (a partir da raiz do projeto):
    python scripts/comparar_modos_aquisicao.py --mac 20:17:09:18:60:29 --porta COM7
    python scripts/comparar_modos_aquisicao.py --mac ... --porta COM7 --canal 1 --segundos 10
    python scripts/comparar_modos_aquisicao.py --modo direto --porta COM7

Exige o projeto instalado em modo editável (`pip install -e .`), como todo o resto.
"""

import argparse
import statistics
import time
from dataclasses import dataclass

from esquizocap.hardware.bitalino_direto import BitalinoDireto
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.constantes import CANAIS_BITALINO, TAXA_AMOSTRAGEM_PADRAO_HZ
from esquizocap.hardware.contratos import ErroConexaoBitalino, ErroStreamPerdido, LeitorBitalino

SEGUNDOS_PADRAO: float = 10.0
AMOSTRAS_POR_LEITURA: int = 100
TIMEOUT_LEITURA_SEGUNDOS: float = 5.0

MODO_OPENSIGNALS: str = 'opensignals'
MODO_DIRETO: str = 'direto'
MODO_AMBOS: str = 'ambos'

# Acima disto, a diferença entre os modos deixa de ser ruído e vira erro de escala.
# É folgado de propósito: EEG é um sinal vivo, e duas coletas em SEQUÊNCIA nunca dão o
# mesmo número. O que se procura é a ordem de grandeza errada — ADU (centenas) onde
# deveria haver microvolts (dezenas), ou um canal trocado por outro.
FATOR_DE_ALERTA: float = 5.0


@dataclass(frozen=True)
class EstatisticasCanal:
    """Resumo do que um canal produziu durante a coleta."""

    canal: int
    minimo: float
    maximo: float
    media: float
    desvio: float

    @property
    def amplitude(self) -> float:
        """Distância entre o menor e o maior valor lido."""
        return self.maximo - self.minimo


@dataclass(frozen=True)
class Coleta:
    """O resultado de uma coleta inteira, por um dos modos."""

    modo: str
    taxa_hz: int
    amostras: int
    por_canal: list[EstatisticasCanal]


def montar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Compara Modo OpenSignals e Modo Direto lendo o mesmo eletrodo.'
    )
    parser.add_argument('--modo', choices=[MODO_AMBOS, MODO_OPENSIGNALS, MODO_DIRETO], default=MODO_AMBOS)
    parser.add_argument('--mac', default='', help='MAC do dispositivo, para o Modo OpenSignals.')
    parser.add_argument('--porta', default='', help='Porta de acesso (ex.: COM7), para o Modo Direto.')
    parser.add_argument('--canal', type=int, default=1, help='Canal ativo, de 1 a 6. É o único convertido.')
    parser.add_argument('--segundos', type=float, default=SEGUNDOS_PADRAO, help='Duração de cada coleta.')
    parser.add_argument(
        '--taxa',
        type=int,
        default=0,
        help='Taxa do Modo Direto, em Hz. Por padrão, usa a MESMA que o OpenSignals declarar.',
    )
    return parser.parse_args()


def coletar(leitor: LeitorBitalino, modo: str, canal_ativo: int, segundos: float) -> Coleta:
    """Lê pelo tempo pedido e resume canal a canal.

    Raises:
        ErroStreamPerdido: Se a aquisição cair no meio. Deixa propagar de propósito: uma
            coleta interrompida não serve para comparar.
    """
    leitor.definir_canal_ativo(canal=canal_ativo)
    taxa_hz = leitor.taxa_amostragem_nominal()

    colunas: list[list[float]] = [[] for _ in CANAIS_BITALINO]
    limite = time.monotonic() + segundos
    total = 0

    while time.monotonic() < limite:
        bloco, _timestamps = leitor.ler_bloco(
            timeout=TIMEOUT_LEITURA_SEGUNDOS, max_amostras=AMOSTRAS_POR_LEITURA
        )

        for linha in bloco:
            total += 1
            for indice, canal in enumerate(CANAIS_BITALINO):
                # O canal N mora no índice N: o índice 0 é o número de sequência, nos dois
                # modos. Se isto mudar, a comparação inteira perde o sentido.
                if canal < len(linha):
                    colunas[indice].append(float(linha[canal]))

    por_canal = [
        EstatisticasCanal(
            canal=canal,
            minimo=min(valores),
            maximo=max(valores),
            media=statistics.fmean(valores),
            desvio=statistics.pstdev(valores) if len(valores) > 1 else 0.0,
        )
        for canal, valores in zip(CANAIS_BITALINO, colunas, strict=True)
        if valores
    ]

    return Coleta(modo=modo, taxa_hz=taxa_hz, amostras=total, por_canal=por_canal)


def coletar_opensignals(mac: str, canal_ativo: int, segundos: float) -> Coleta:
    print('\n--- Modo OpenSignals ---')
    print('  Requer: OpenSignals ABERTO, compartilhamento "Lab Streaming Layer" ativo, gravação INICIADA.')

    with BitalinoLSL() as leitor:
        # Taxa e canais são IGNORADOS neste modo — quem os fixou foi o OpenSignals. Vão
        # preenchidos com o padrão só porque o contrato os exige.
        leitor.conectar(
            endereco=mac, taxa_amostragem_hz=TAXA_AMOSTRAGEM_PADRAO_HZ, canais=list(CANAIS_BITALINO)
        )
        print(f'  Conectado. Coletando {segundos:.0f}s ...')
        return coletar(leitor=leitor, modo=MODO_OPENSIGNALS, canal_ativo=canal_ativo, segundos=segundos)


def coletar_direto(porta: str, taxa_hz: int, canal_ativo: int, segundos: float) -> Coleta:
    print('\n--- Modo Direto ---')
    print('  Requer: OpenSignals FECHADO. O dispositivo aceita um cliente por vez.')

    with BitalinoDireto() as leitor:
        leitor.conectar(endereco=porta, taxa_amostragem_hz=taxa_hz, canais=list(CANAIS_BITALINO))
        print(f'  Conectado a {taxa_hz} Hz. Coletando {segundos:.0f}s ...')
        return coletar(leitor=leitor, modo=MODO_DIRETO, canal_ativo=canal_ativo, segundos=segundos)


def imprimir_coleta(coleta: Coleta) -> None:
    print(f'\n=== {coleta.modo} | {coleta.taxa_hz} Hz | {coleta.amostras} amostras ===')
    print(f'  {"canal":>5}  {"mínimo":>12}  {"máximo":>12}  {"média":>12}  {"desvio":>12}')
    for estatistica in coleta.por_canal:
        print(
            f'  {estatistica.canal:>5}  {estatistica.minimo:>12.3f}  {estatistica.maximo:>12.3f}  '
            f'{estatistica.media:>12.3f}  {estatistica.desvio:>12.3f}'
        )


def comparar(opensignals: Coleta, direto: Coleta, canal_ativo: int) -> None:
    """Põe as duas coletas lado a lado e diz o que a diferença significa."""
    print('\n' + '=' * 78)
    print(f'COMPARAÇÃO — canal ativo {canal_ativo} (o único convertido no Modo Direto)')
    print('=' * 78)
    print(f'  {"canal":>5}  {"amplitude LSL":>16}  {"amplitude direto":>18}  {"razão":>10}  ')

    por_canal_direto = {estatistica.canal: estatistica for estatistica in direto.por_canal}

    for estatistica in opensignals.por_canal:
        equivalente = por_canal_direto.get(estatistica.canal)
        if equivalente is None:
            continue

        razao = equivalente.amplitude / estatistica.amplitude if estatistica.amplitude else float('inf')
        marca = ''
        if estatistica.canal == canal_ativo and not 1 / FATOR_DE_ALERTA <= razao <= FATOR_DE_ALERTA:
            marca = '  <-- DIVERGE'

        print(
            f'  {estatistica.canal:>5}  {estatistica.amplitude:>16.3f}  '
            f'{equivalente.amplitude:>18.3f}  {razao:>10.2f}{marca}'
        )

    print(
        '\nCOMO LER:\n'
        f'  - Só o canal {canal_ativo} precisa bater. Ele é o único que o Modo Direto converte para\n'
        '    microvolts, e no Modo OpenSignals só sai convertido se houver sensor declarado nele.\n'
        '  - Os demais canais divergem POR PROJETO: o Modo Direto os entrega em ADU cru, e o\n'
        '    OpenSignals entrega em ADU ou na unidade do sensor, conforme a configuração dele.\n'
        f'  - Uma razão perto de 1 é o esperado. Acima de {FATOR_DE_ALERTA:.0f}x ou abaixo de\n'
        f'    1/{FATOR_DE_ALERTA:.0f} no canal ativo indica erro de ESCALA — tipicamente ADU (centenas)\n'
        '    onde deveria haver microvolts (dezenas).\n'
        '  - Uma razão perto de 1 no canal errado, com o canal ativo divergindo, indica canal\n'
        '    DESLOCADO no desempacotamento.\n'
        '  - EEG é sinal vivo: duas coletas em sequência nunca dão o mesmo número. O que se\n'
        '    procura aqui é ordem de grandeza, não igualdade.'
    )

    if opensignals.taxa_hz != direto.taxa_hz:
        print(
            f'\nATENÇÃO: as taxas diferem ({opensignals.taxa_hz} Hz contra {direto.taxa_hz} Hz). '
            'Isso muda o desvio padrão e a\n  amplitude observada. Rode sem --taxa para que o Modo '
            'Direto use a mesma taxa do OpenSignals.'
        )


def main() -> None:
    argumentos = montar_argumentos()

    if argumentos.modo in (MODO_AMBOS, MODO_OPENSIGNALS) and not argumentos.mac:
        raise SystemExit('Faltou --mac: o Modo OpenSignals precisa do MAC do dispositivo.')
    if argumentos.modo in (MODO_AMBOS, MODO_DIRETO) and not argumentos.porta:
        raise SystemExit('Faltou --porta: o Modo Direto precisa da porta de acesso (ex.: COM7).')

    coleta_opensignals: Coleta | None = None
    coleta_direto: Coleta | None = None

    try:
        if argumentos.modo in (MODO_AMBOS, MODO_OPENSIGNALS):
            coleta_opensignals = coletar_opensignals(
                mac=argumentos.mac, canal_ativo=argumentos.canal, segundos=argumentos.segundos
            )
            imprimir_coleta(coleta_opensignals)

        if argumentos.modo == MODO_AMBOS:
            print(
                '\n>>> FECHE O OPENSIGNALS AGORA e tecle ENTER para a coleta do Modo Direto.\n'
                '    O dispositivo aceita um cliente por vez; com o OpenSignals aberto, a porta\n'
                '    não abre. NÃO mexa no eletrodo entre as duas coletas.'
            )
            input()

        if argumentos.modo in (MODO_AMBOS, MODO_DIRETO):
            # Sem --taxa, espelha a taxa que o OpenSignals declarou: comparar coletas em
            # taxas diferentes mistura o efeito da taxa com o que se quer medir.
            taxa = argumentos.taxa or (coleta_opensignals.taxa_hz if coleta_opensignals else 0)
            if not taxa:
                raise SystemExit('Sem --taxa e sem coleta do OpenSignals para espelhar: informe --taxa.')

            coleta_direto = coletar_direto(
                porta=argumentos.porta,
                taxa_hz=taxa,
                canal_ativo=argumentos.canal,
                segundos=argumentos.segundos,
            )
            imprimir_coleta(coleta_direto)

    except ErroConexaoBitalino as erro:
        raise SystemExit(f'\nFALHA DE CONEXÃO: {erro}') from erro
    except ErroStreamPerdido as erro:
        raise SystemExit(f'\nA AQUISIÇÃO CAIU no meio da coleta: {erro}') from erro

    if coleta_opensignals is not None and coleta_direto is not None:
        comparar(opensignals=coleta_opensignals, direto=coleta_direto, canal_ativo=argumentos.canal)


if __name__ == '__main__':
    main()
