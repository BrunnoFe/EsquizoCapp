"""Roda o ciclo de aquisição sem GUI e sem hardware, para provar a extração do núcleo.

Monta o `CicloAquisicao` com as implementações FAKE de `esquizocap.hardware` e imprime o
`ResultadoCiclo` de cada volta. Não abre janela nem precisa de BITalino nem Arduino.

Exige o projeto instalado em modo editável (`pip install -e .`), como todo o resto.

Uso (a partir da raiz do projeto):
    python scripts/rodar_ciclo_sem_gui.py
    python scripts/rodar_ciclo_sem_gui.py --modo Frequência --ciclos 4
"""

import argparse

from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ModoAnalise
from esquizocap.dominio.predicao import carregar_modelo
from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.constantes import CANAIS_BITALINO, TAXA_AMOSTRAGEM_PADRAO_HZ

CAMINHO_MODELO: str = 'models/BestModel_HSV_v1.pickle'
MAC_SIMULADO: str = '20:17:09:18:60:29'
PORTA_SIMULADA: str = 'COM99 - Arduino simulado (fake)'


def montar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Roda o ciclo de aquisição com hardware simulado.')
    parser.add_argument('--modo', choices=[modo.value for modo in ModoAnalise], default=ModoAnalise.AMPLITUDE.value)
    parser.add_argument('--ciclos', type=int, default=5, help='Quantas voltas do ciclo executar.')
    parser.add_argument('--canal', type=int, default=1, help='Canal do BITalino (1 a 6).')
    parser.add_argument('--saturacao', type=int, default=255)
    parser.add_argument('--brilho', type=int, default=120)
    parser.add_argument('--modo-luminosidade', type=int, default=2, help='1 a 4; 2 = "Todos".')
    parser.add_argument('--tamanho-amostra', type=int, default=3000, help='Amostras por análise de frequência.')
    return parser.parse_args()


def main() -> None:
    argumentos = montar_argumentos()
    modo_analise = ModoAnalise(argumentos.modo)

    # As bordas de hardware são context managers: o `with` garante que a porta serial e
    # o stream sejam fechados ao sair, mesmo se um ciclo levantar exceção no meio.
    with BitalinoSintetico() as leitor, ArduinoFake() as arduino:
        leitor.conectar(
            endereco=MAC_SIMULADO,
            taxa_amostragem_hz=TAXA_AMOSTRAGEM_PADRAO_HZ,
            canais=list(CANAIS_BITALINO),
        )
        arduino.conectar(porta=PORTA_SIMULADA, baudrate=9600)

        ciclo = CicloAquisicao(
            leitor=leitor,
            arduino=arduino,
            modelo=carregar_modelo(caminho_modelo=CAMINHO_MODELO),
            modo_analise=modo_analise,
            canal_bitalino=argumentos.canal,
            modo_luminosidade=argumentos.modo_luminosidade,
            tamanho_amostra_frequencia=argumentos.tamanho_amostra,
        )

        controles = ControlesUsuario(saturacao=argumentos.saturacao, brilho=argumentos.brilho)

        print(f'\n=== Modo {modo_analise.value} | {argumentos.ciclos} ciclos | hardware SIMULADO ===\n')

        resultados_produzidos: int = 0
        for volta in range(1, argumentos.ciclos + 1):
            resultado = ciclo.processar_amostra(controles=controles)

            if resultado is None:
                print(
                    f'[ciclo {volta}] acumulando: '
                    f'{ciclo.amostras_acumuladas}/{ciclo.tamanho_amostra_frequencia} amostras'
                )
                continue

            resultados_produzidos += 1
            visual = resultado.parametros_visual

            print(f'[ciclo {volta}] metrica={resultado.metrica_bruta:.2f} | faixa={resultado.faixa_frequencia}')
            print(
                f'           cor    : hue={resultado.hue} sat={resultado.saturacao} '
                f'brilho={resultado.brilho} hex={resultado.cor_hex}'
            )
            print(f'           serial : {arduino.ultimo_comando!r}')
            # Calculados, mas não enviados a lugar nenhum: a engine foi desligada.
            print(
                f'           visual : RGB=({visual.vermelho},{visual.verde},{visual.azul}) '
                f'octaves={visual.octaves} zoom_fator={visual.zoom_fator} '
                f'zoom_coef={visual.zoom_coeficiente} brilho_shader={visual.brilho_shader} '
                f'potencia={visual.potencia} intensidade={visual.intensidade}\n'
            )

        comandos_enviados: int = arduino.comandos_enviados

    # Fora do `with`: o Arduino e o stream já foram fechados pelo `__exit__`.
    print(
        f'=== Fim: {resultados_produzidos} resultado(s), '
        f'{comandos_enviados} comando(s) ao Arduino. '
        f'Parâmetros visuais calculados, mas NÃO enviados (engine desligada). ==='
    )
    print(f'=== Arduino conectado ao sair do `with`? {arduino.esta_conectado} (esperado: False) ===')


if __name__ == '__main__':
    main()
