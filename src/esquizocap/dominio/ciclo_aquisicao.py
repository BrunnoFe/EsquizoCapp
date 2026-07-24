"""O ciclo de aquisição: ler o EEG, prever a cor e distribuí-la aos consumidores.

Esta classe é o núcleo do sistema e não sabe que existe interface gráfica. Ela
devolve um `ResultadoCiclo`; quem chama decide o que fazer com ele (hoje, pintar
widgets; amanhã, o que for).

A integração com a engine visual (Godot) foi REMOVIDA daqui: o núcleo não abre socket,
não lança processo e não envia nada pela rede. Os parâmetros que seriam mandados para
ela continuam sendo calculados, em `ParametrosVisual`, prontos para uma engine nova.
Ver `tools/hardware/_engine_legado/README.md`.

As interfaces de hardware entram apenas como anotação de tipo, sob `TYPE_CHECKING`:
importá-las em runtime executaria o `__init__` de `esquizocap.hardware`, que carrega as
implementações concretas e, com elas, o ttkbootstrap. Como o que se exige das
dependências são Protocols (tipagem estrutural), nada é perdido — e o núcleo fica
importável sem GUI nenhuma.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy

from esquizocap.dominio import pre_processamento
from esquizocap.dominio.cor import hsv_para_rgb_hex
from esquizocap.dominio.pre_processamento import SinalEEG
from esquizocap.dominio.predicao import ModeloPreditor, prever_hue

if TYPE_CHECKING:
    from esquizocap.hardware.contratos import ControladorLedArduino, LeitorBitalino

TAMANHO_BLOCO_LEITURA: int = 500
TIMEOUT_LEITURA_SEGUNDOS: float = 1.0

# Faixas dos parâmetros de shader, herdadas do protocolo da engine antiga
# (`tools/hardware/_engine_legado/engine_protocolo.py`). Eles NÃO derivam do sinal:
# são sorteados a cada ciclo, e é assim desde a versão original.
FAIXA_OCTAVES: tuple[int, int] = (100, 310)
FAIXA_ZOOM_FATOR: tuple[float, float] = (10.0, 18.5)
FAIXA_ZOOM_COEFICIENTE: tuple[float, float] = (1.2, 1.32)
FAIXA_BRILHO_SHADER: tuple[int, int] = (1, 3)
FAIXA_POTENCIA: tuple[int, int] = (1, 3)
FAIXA_INTENSIDADE: tuple[float, float] = (0.0, 0.1)
CASAS_DECIMAIS: int = 3


class ModoAnalise(Enum):
    """Como o sinal vira a métrica que alimenta o modelo."""

    AMPLITUDE = 'Amplitude'
    """Cada amostra individual vira uma predição, pela sua amplitude."""

    FREQUENCIA = 'Frequência'
    """Blocos são acumulados até dar para extrair a frequência dominante."""


@dataclass
class ParametrosVisual:
    """Os 9 valores que alimentariam uma engine visual de shaders.

    Nada aqui é enviado a lugar nenhum: a integração com o Godot foi desligada. Os
    parâmetros seguem sendo calculados para que uma engine nova possa consumi-los sem
    ter que reconstruir essa lógica. Ver `tools/hardware/_engine_legado/README.md`.

    Os três primeiros campos são RGB — não HSV. Isso foi confirmado no fonte da engine
    antiga (`godot/ChangeColor.cs`, `Color color = new(r, g, b)`), apesar de comentários
    dos dois lados afirmarem "H,S,V".

    Os seis últimos são sorteados a cada ciclo e não têm relação nenhuma com o EEG.
    Está preservado assim de propósito; se devem passar a reagir ao sinal é uma decisão
    em aberto (ver DECISOES_PENDENTES.md).
    """

    vermelho: int
    """Canal R, de 0 a 255. Vem da cor prevista, convertida de HSV."""

    verde: int
    """Canal G, de 0 a 255."""

    azul: int
    """Canal B, de 0 a 255."""

    octaves: int
    """Nº de iterações do fractal no shader. Sorteado."""

    zoom_fator: float
    """Zoom inicial do fractal. Sorteado. (No shader antigo, marcado como "frequência".)"""

    zoom_coeficiente: float
    """Fator de zoom aplicado a cada oitava. Sorteado."""

    brilho_shader: int
    """Multiplicador de intensidade do shader, de 1 a 3. Sorteado.

    NÃO confundir com o `brilho` do HSV/Arduino: aquele é o V da cor (0–255, vindo do
    medidor da interface); este é um parâmetro do shader, com outra escala e outro papel.
    """

    potencia: int
    """Expoente da curva de contraste do shader. Sorteado."""

    intensidade: float
    """Brilho do "glow" das linhas do shader. Sorteado."""


def gerar_parametros_visual(rgb: tuple[int, int, int]) -> ParametrosVisual:
    """Monta os parâmetros visuais de um ciclo, a partir da cor prevista.

    Os seis campos não-cromáticos são sorteados nas mesmas faixas do protocolo original.
    Diferente do protocolo antigo, aqui eles ficam como números — a formatação com
    vírgula decimal era exigência do parser do Godot, ou seja, um detalhe de transporte,
    e transporte é justamente o que deixou de existir.
    """
    return ParametrosVisual(
        vermelho=rgb[0],
        verde=rgb[1],
        azul=rgb[2],
        octaves=random.randint(*FAIXA_OCTAVES),
        zoom_fator=round(random.uniform(*FAIXA_ZOOM_FATOR), CASAS_DECIMAIS),
        zoom_coeficiente=round(random.uniform(*FAIXA_ZOOM_COEFICIENTE), CASAS_DECIMAIS),
        brilho_shader=random.randint(*FAIXA_BRILHO_SHADER),
        potencia=random.randint(*FAIXA_POTENCIA),
        intensidade=round(random.uniform(*FAIXA_INTENSIDADE), CASAS_DECIMAIS),
    )


@dataclass(frozen=True)
class ControlesUsuario:
    """O que o usuário controla ao vivo, enquanto a aquisição acontece.

    Nada aqui vem do modelo nem do sinal: são os medidores da interface. Estão juntos
    num objeto IMUTÁVEL de propósito — a aquisição roda numa thread separada, e trocar
    um valor congelado inteiro é uma operação atômica, enquanto ler três campos soltos
    de um objeto mutável poderia pegar metade de uma mudança do usuário.
    """

    saturacao: int
    """Saturação do HSV, de 0 a 255."""

    brilho: int
    """Brilho (V do HSV), de 0 a 255. NÃO confundir com `ParametrosVisual.brilho_shader`."""

    intervalo_predicao_segundos: float = 0.0
    """Quanto sinal deve passar entre duas predições. Só vale no modo Amplitude.

    Zero significa "prever a cada amostra lida". O modo Frequência ignora este campo:
    lá a cadência já é dada pelo tamanho da janela de análise.
    """


@dataclass
class JanelaAnalisada:
    """A janela bruta de sinal que originou uma análise de frequência.

    Só existe no modo Frequência, e serve à gravação: é o que vai para a aba "Data" do
    Excel. O núcleo não persiste nada — apenas devolve os dados a quem quiser gravar.
    """

    amostras: SinalEEG
    """As amostras acumuladas do canal ativo, já filtradas pela seleção de canal."""

    timestamps: SinalEEG
    """Os timestamps correspondentes, um por amostra."""


@dataclass
class ResultadoCiclo:
    """O que um ciclo completo produziu, sem qualquer noção de interface.

    `ParametrosVisual` vem aninhado aqui, e não como segundo valor de retorno: os dois
    descrevem o MESMO ciclo, e no modo Frequência um ciclo pode não produzir nada
    (retorno `None`). Aninhando, o "tem resultado ou não" continua sendo uma única
    pergunta; com uma tupla, quem chama teria que lidar com `(None, None)`.
    """

    metrica_bruta: float
    """Amplitude em microvolts (modo Amplitude) ou frequência dominante em Hz (modo Frequência)."""

    faixa_frequencia: str | None
    """Banda de EEG identificada. Sempre None no modo Amplitude, que não analisa espectro."""

    hue: int
    """Matiz previsto pelo modelo, de 0 a 255."""

    saturacao: int
    """Saturação usada, de 0 a 255. Vem de quem chama, não do modelo."""

    brilho: int
    """Brilho (V do HSV) usado, de 0 a 255. Vem de quem chama, não do modelo."""

    cor_hex: str
    """A cor final em `#RRGGBB`, já convertida de HSV."""

    parametros_visual: ParametrosVisual
    """Parâmetros prontos para uma engine visual. Calculados, mas não enviados a ninguém."""

    timestamp: float
    """Instante do dado que gerou a predição.

    No modo Amplitude, o timestamp da amostra. No modo Frequência, o timestamp da última
    amostra da janela analisada.
    """

    potencia: float | None = None
    """Potência da frequência dominante. Só no modo Frequência; None no Amplitude."""

    janela: JanelaAnalisada | None = None
    """A janela bruta analisada. Só no modo Frequência; None no Amplitude.

    Existe para que quem grava tenha acesso ao sinal cru sem precisar acumulá-lo por
    fora, duplicando o que o ciclo já faz.
    """


class CicloAquisicao:
    """Executa o ciclo ler -> pré-processar -> prever -> distribuir.

    Um ciclo nem sempre produz resultado, e por motivos diferentes em cada modo:

    - **Frequência**: os blocos são acumulados até atingir `tamanho_amostra_frequencia`,
      e só então há uma predição.
    - **Amplitude**: toda amostra é lida (é o que evita atraso), mas a predição só sai a
      cada `ControlesUsuario.intervalo_predicao_segundos` de sinal.

    Nos dois casos, "sem resultado" é `None` — nunca uma exceção, e nunca uma pausa.

    A classe é sequencial e SEM sincronização: ela não sabe que existe thread. Quem a
    roda numa thread (ver `esquizocap.aplicacao.servico_aquisicao`) é responsável por
    usá-la de um lado só.

    `tamanho_amostra_frequencia` é apenas o tamanho da janela de análise (quantas
    amostras acumular). A taxa de amostragem usada na análise espectral vem sempre de
    `leitor.taxa_amostragem_nominal()`.
    """

    def __init__(
        self,
        leitor: LeitorBitalino,
        arduino: ControladorLedArduino,
        modelo: ModeloPreditor,
        modo_analise: ModoAnalise,
        canal_bitalino: int,
        modo_luminosidade: int,
        tamanho_amostra_frequencia: int = 3000,
    ) -> None:
        self._leitor = leitor
        self._arduino = arduino
        self._modelo = modelo
        self._modo_analise = modo_analise
        self._canal_bitalino = canal_bitalino
        self._modo_luminosidade = modo_luminosidade
        self._tamanho_amostra_frequencia = tamanho_amostra_frequencia

        self._amostras_acumuladas: numpy.ndarray = numpy.array([])
        self._timestamps_acumulados: numpy.ndarray = numpy.array([])
        self._timestamp_ultima_predicao: float | None = None

    @property
    def modo_analise(self) -> ModoAnalise:
        return self._modo_analise

    @property
    def amostras_acumuladas(self) -> int:
        """Quantas amostras já foram acumuladas rumo à próxima análise de frequência."""
        return self._amostras_acumuladas.size

    @property
    def tamanho_amostra_frequencia(self) -> int:
        return self._tamanho_amostra_frequencia

    def processar_amostra(self, controles: ControlesUsuario) -> ResultadoCiclo | None:
        """Roda um ciclo completo: lê o EEG, prevê a cor e a envia ao Arduino.

        Cada chamada consome exatamente uma leitura do stream. Chamar isto em laço,
        sem pausa, é o uso pretendido: quem dita a cadência é o próprio dispositivo,
        porque a leitura bloqueia até haver sinal. NÃO espace as chamadas com um timer
        para "amostrar mais devagar" — o LSL entrega a amostra mais ANTIGA do buffer, e
        ler mais devagar do que o dispositivo produz faz o atraso crescer sem limite.
        Para espaçar as PREDIÇÕES, use `ControlesUsuario.intervalo_predicao_segundos`.

        Args:
            controles: Saturação, brilho e cadência de predição — tudo o que o usuário
                ajusta ao vivo. Nada disso vem do modelo.

        Returns:
            O `ResultadoCiclo` — que traz o `ParametrosVisual` aninhado — ou `None`
            quando o ciclo consumiu uma leitura sem produzir predição: no modo
            Frequência, enquanto a janela de análise não fecha; no modo Amplitude,
            enquanto não passou `intervalo_predicao_segundos` desde a última predição.

        Raises:
            ErroStreamPerdido: Se o stream do BITalino cair durante a leitura.
            ErroConexaoArduino: Se a porta serial cair ao enviar a cor.
        """
        if self._modo_analise is ModoAnalise.AMPLITUDE:
            return self._processar_amplitude(controles=controles)
        return self._processar_frequencia(controles=controles)

    def _deve_prever(self, timestamp: float, intervalo_segundos: float) -> bool:
        """Decide se já passou sinal suficiente para uma nova predição (modo Amplitude).

        O relógio usado é o do PRÓPRIO SINAL (o timestamp da amostra), não o relógio de
        parede. Assim "uma predição a cada 900 ms" significa 900 ms de EEG, e não 900 ms
        de execução — que é o que o usuário quer dizer, e o que sobrevive a uma thread
        que travou por um instante.
        """
        if intervalo_segundos <= 0.0 or self._timestamp_ultima_predicao is None:
            return True
        return (timestamp - self._timestamp_ultima_predicao) >= intervalo_segundos

    def _processar_amplitude(self, controles: ControlesUsuario) -> ResultadoCiclo | None:
        leitura = self._leitor.ler_amostra(timeout=TIMEOUT_LEITURA_SEGUNDOS)

        # O leitor devolve `(None, None)` quando o timeout expira sem sinal. Antes isso
        # virava um `IndexError` lá na frente, e a GUI o traduzia como "o hardware
        # falhou". Um timeout não é falha: é só um ciclo sem leitura.
        if leitura[0] is None:
            return None

        amostra, timestamp = leitura

        # A amostra foi LIDA de qualquer forma — é isso que impede o buffer do LSL de
        # acumular atraso. O que o intervalo controla é só a PREDIÇÃO.
        if not self._deve_prever(timestamp=timestamp, intervalo_segundos=controles.intervalo_predicao_segundos):
            return None

        self._timestamp_ultima_predicao = timestamp
        amplitude = pre_processamento.extrair_amplitude(amostra=amostra, canal=self._canal_bitalino)

        return self._prever_e_distribuir(
            metrica=float(amplitude),
            faixa=None,
            controles=controles,
            timestamp=timestamp,
        )

    def _processar_frequencia(self, controles: ControlesUsuario) -> ResultadoCiclo | None:
        bloco, timestamps = self._leitor.ler_bloco(timeout=TIMEOUT_LEITURA_SEGUNDOS, max_amostras=TAMANHO_BLOCO_LEITURA)

        # Bloco vazio = o timeout expirou sem sinal novo. Não é erro; é só um ciclo sem
        # leitura. Sair cedo evita empilhar arrays vazios no acumulador.
        if not bloco:
            return None

        sinal = pre_processamento.extrair_sinal_do_bloco(bloco=bloco, canal=self._canal_bitalino)
        self._amostras_acumuladas = numpy.append(self._amostras_acumuladas, sinal)
        self._timestamps_acumulados = numpy.append(
            self._timestamps_acumulados, numpy.array(timestamps, dtype='float32')
        )

        # `tamanho_amostra_frequencia` define SÓ o tamanho da janela: quantas amostras
        # acumular antes de analisar. A escala do eixo de frequência vem da taxa real
        # do dispositivo, e não daqui.
        if self._amostras_acumuladas.size < self._tamanho_amostra_frequencia:
            return None

        analise = pre_processamento.analisar_frequencia(
            eeg=self._amostras_acumuladas, taxa_amostragem=self._leitor.taxa_amostragem_nominal()
        )

        janela = JanelaAnalisada(amostras=self._amostras_acumuladas, timestamps=self._timestamps_acumulados)

        resultado = self._prever_e_distribuir(
            metrica=float(analise.frequencia),
            faixa=analise.faixa,
            controles=controles,
            timestamp=float(self._timestamps_acumulados[-1]),
            potencia=float(analise.potencia),
            janela=janela,
        )

        # Arrays novos, e não `.clear()`: a `JanelaAnalisada` acima segue apontando para
        # os antigos, e quem for gravar precisa deles intactos.
        self._amostras_acumuladas = numpy.array([])
        self._timestamps_acumulados = numpy.array([])

        return resultado

    def _prever_e_distribuir(
        self,
        metrica: float,
        faixa: str | None,
        controles: ControlesUsuario,
        timestamp: float,
        potencia: float | None = None,
        janela: JanelaAnalisada | None = None,
    ) -> ResultadoCiclo:
        saturacao: int = controles.saturacao
        brilho: int = controles.brilho

        hue: int = prever_hue(modelo=self._modelo, metrica=metrica)
        cor_hex, rgb = hsv_para_rgb_hex(hue=hue, saturacao=saturacao, brilho=brilho)

        # Mantido do código original: acompanhamento da aquisição pelo console.
        # Ver DECISOES_PENDENTES.md.
        if faixa is None:
            print(
                f'H = {hue}| Dados do canal ativo: {metrica:0.2f}uV | '
                f'({self._modo_luminosidade}, {hue}, {saturacao}, {brilho})'
            )
        else:
            print(f'Predição = {hue}| H = {hue}, S = {saturacao}, V = {brilho}')

        # O Arduino é o único consumidor que sobrou. Os parâmetros visuais são
        # calculados e devolvidos, mas não vão para lugar nenhum.
        self._arduino.enviar_comando_cor(modo=self._modo_luminosidade, hue=hue, saturacao=saturacao, brilho=brilho)

        return ResultadoCiclo(
            metrica_bruta=metrica,
            faixa_frequencia=faixa,
            hue=hue,
            saturacao=saturacao,
            brilho=brilho,
            cor_hex=cor_hex,
            parametros_visual=gerar_parametros_visual(rgb=rgb),
            timestamp=timestamp,
            potencia=potencia,
            janela=janela,
        )
