"""A aquisição numa thread própria, publicando resultados numa fila.

Este módulo existe para resolver o defeito estrutural mais sério do projeto: a aquisição
rodava na thread da interface, via `after()` do Tkinter. Isso significava que uma leitura
bloqueante do LSL congelava a janela por até um segundo, que o filtro Butterworth e o
Welch de milhares de amostras rodavam na thread da UI, e — o pior — que **a cadência de
amostragem de um sinal biológico ficava refém do laço de eventos da interface**.

O desenho agora é o clássico produtor/consumidor:

    [thread de aquisição]  --(fila de eventos)-->  [thread da GUI]
      roda o CicloAquisicao                          drena e pinta

Regras que sustentam isso, e que NÃO devem ser quebradas:

1. **A thread de aquisição nunca toca em Tkinter.** Widget e variável Tk só podem ser
   lidos ou escritos pela thread que criou o root. É por isso que os controles do usuário
   (saturação, brilho, intervalo) chegam aqui como um `ControlesUsuario` congelado, em
   vez de a thread ir buscar o valor no medidor.
2. **A GUI nunca bloqueia esperando a fila.** Ela drena o que houver e volta ao laço de
   eventos.
3. **A gravação vive aqui, não na GUI.** Assim a fila pode descartar resultados quando a
   interface não acompanha o ritmo, sem que isso signifique perder dado gravado.
"""

import logging
import queue
import threading
from dataclasses import dataclass

from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ControlesUsuario, ResultadoCiclo
from esquizocap.hardware.contratos import (
    ErroConexaoArduino,
    ErroConexaoBitalino,
    ErroStreamPerdido,
)

# A fila é só para PINTAR. Uma interface a 30 fps não consegue exibir mais do que algumas
# dezenas de resultados por segundo de qualquer forma, e a gravação (que precisa de todos)
# é acumulada aqui dentro. Um limite pequeno mantém o que a tela mostra próximo do agora.
TAMANHO_FILA_PADRAO: int = 64

# Quanto esperar pela thread ao parar. Uma leitura em curso pode estar bloqueada por até
# `TIMEOUT_LEITURA_SEGUNDOS` (1 s) no pior caso; o dobro disso dá folga sem travar a GUI.
TIMEOUT_PARADA_SEGUNDOS: float = 3.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventoResultado:
    """Um ciclo produziu uma predição. É o evento comum."""

    resultado: ResultadoCiclo


@dataclass(frozen=True)
class EventoErro:
    """A aquisição morreu por causa de um erro. A thread já parou quando isto chega."""

    erro: Exception

    mensagem_usuario: str
    """Texto pronto para a interface mostrar. Montado aqui porque é aqui que se sabe o
    que aconteceu — a GUI não deveria estar traduzindo tipos de exceção em português."""


@dataclass(frozen=True)
class EventoParado:
    """A thread terminou. SEMPRE chega, tanto na parada normal quanto após um erro.

    É o sinal para a GUI encerrar o laço de drenagem e voltar ao estado ocioso.
    """

    total_gravado: int
    """Quantos `ResultadoCiclo` foram acumulados para gravação (0 se não estava gravando)."""


Evento = EventoResultado | EventoErro | EventoParado
"""O que trafega na fila. Uma união fechada: a GUI trata os três casos e acabou."""


class ServicoAquisicao:
    """Roda o `CicloAquisicao` numa thread e publica os resultados numa fila.

    Uso típico::

        servico = ServicoAquisicao(ciclo=ciclo, gravar=True)
        servico.atualizar_controles(ControlesUsuario(saturacao=255, brilho=120))
        servico.iniciar()
        ...
        for evento in servico.drenar():   # chamado pela GUI a cada ~30 ms
            ...
        ...
        servico.parar()
        resultados = servico.gravacao

    O serviço é de uso único: depois de `parar()`, crie outro. Reiniciar uma thread não
    existe em Python, e fingir que existe só esconde estado velho.
    """

    def __init__(
        self,
        ciclo: CicloAquisicao,
        gravar: bool = False,
        tamanho_fila: int = TAMANHO_FILA_PADRAO,
    ) -> None:
        self._ciclo = ciclo
        self._gravar = gravar

        self._fila: queue.Queue[Evento] = queue.Queue(maxsize=tamanho_fila)
        self._parar_pedido = threading.Event()
        self._thread: threading.Thread | None = None

        self._gravacao: list[ResultadoCiclo] = []

        # Protege a troca dos controles entre a GUI (escreve) e a thread (lê). Como
        # `ControlesUsuario` é imutável, o lock guarda uma única referência — a thread
        # nunca vê "meio ajuste" do usuário. Um lock, e não confiança no GIL: o Python
        # 3.14 já roda sem GIL em modo free-threading.
        self._trava_controles = threading.Lock()
        self._controles = ControlesUsuario(saturacao=255, brilho=120)

    @property
    def esta_rodando(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def gravacao(self) -> list[ResultadoCiclo]:
        """Os resultados acumulados para gravação.

        Só leia isto DEPOIS de `parar()`: enquanto a thread roda, a lista está sendo
        escrita por ela.
        """
        return self._gravacao

    @property
    def progresso_janela(self) -> int:
        """Quantas amostras já foram acumuladas rumo à próxima análise (modo Frequência).

        Serve a um rótulo de status, e é lido sem trava de propósito: o valor pode estar
        um ciclo atrasado, o que é irrelevante para um texto na tela. Não há risco de
        leitura corrompida — a thread REBIND o array acumulador, e ler uma referência é
        atômico.
        """
        return self._ciclo.amostras_acumuladas

    def atualizar_controles(self, controles: ControlesUsuario) -> None:
        """Troca os controles do usuário. Chamado pela thread da GUI, a cada ajuste."""
        with self._trava_controles:
            self._controles = controles

    def _controles_atuais(self) -> ControlesUsuario:
        with self._trava_controles:
            return self._controles

    def iniciar(self) -> None:
        """Sobe a thread de aquisição."""
        if self.esta_rodando:
            logger.warning('Aquisição já está rodando; ignorando o pedido de iniciar.')
            return

        self._parar_pedido.clear()
        # daemon=True para que um fechamento abrupto não deixe o processo pendurado. Não
        # é a via normal de encerramento — essa é o `parar()`, que fecha o hardware.
        self._thread = threading.Thread(target=self._rodar, name='aquisicao', daemon=True)
        self._thread.start()
        logger.info('Thread de aquisição iniciada')

    def parar(self, timeout: float = TIMEOUT_PARADA_SEGUNDOS) -> None:
        """Pede a parada e espera a thread terminar.

        A thread pode estar bloqueada numa leitura; ela só percebe o pedido ao voltar
        dela. Por isso há um timeout — mas o normal é sair em menos de um segundo.
        """
        self._parar_pedido.set()

        if self._thread is None:
            return

        self._thread.join(timeout=timeout)

        if self._thread.is_alive():
            logger.error(f'A thread de aquisição não terminou em {timeout} s. O stream do BITalino pode estar travado.')
        else:
            logger.info('Thread de aquisição encerrada')

    def drenar(self) -> list[Evento]:
        """Devolve todos os eventos pendentes, sem bloquear.

        É o que a GUI chama no seu `after()`. Nunca bloqueia: se não houver nada, devolve
        lista vazia e a interface segue viva.
        """
        eventos: list[Evento] = []

        while True:
            try:
                eventos.append(self._fila.get_nowait())
            except queue.Empty:
                return eventos

    def _publicar(self, evento: Evento) -> None:
        """Põe um evento na fila, descartando o mais ANTIGO se ela estiver cheia.

        Fila cheia significa que a GUI não está drenando no ritmo da aquisição. Nesse
        caso, o resultado velho é o descartável: ninguém quer ver na tela uma cor de
        cinco segundos atrás. Isso só é seguro porque a gravação NÃO depende da fila —
        ela é acumulada em `self._gravacao`, dentro da thread.
        """
        while True:
            try:
                self._fila.put_nowait(evento)
                return
            except queue.Full:
                try:
                    descartado = self._fila.get_nowait()
                    logger.debug(f'Fila cheia: descartando {type(descartado).__name__} antigo')
                except queue.Empty:
                    # A GUI drenou entre as duas chamadas. Tenta de novo.
                    continue

    def _rodar(self) -> None:
        """O corpo da thread. Roda até pedirem para parar, ou até o hardware falhar."""
        logger.info(f'Aquisição em curso (modo {self._ciclo.modo_analise.value})')

        try:
            self._laco()

        except (ErroStreamPerdido, ErroConexaoBitalino) as erro:
            logger.exception('Aquisição interrompida: falha no BITalino')
            self._publicar(
                EventoErro(
                    erro=erro,
                    mensagem_usuario=(
                        f'A aquisição parou: {erro}\n\n'
                        'Verifique se o OpenSignals segue aberto, com o compartilhamento '
                        '"Lab Streaming Layer" ativo, e se o BITalino continua ligado.'
                    ),
                )
            )

        except ErroConexaoArduino as erro:
            logger.exception('Aquisição interrompida: falha no Arduino')
            self._publicar(
                EventoErro(
                    erro=erro,
                    mensagem_usuario=(f'A aquisição parou: {erro}\n\nVerifique o cabo USB do Arduino.'),
                )
            )

        except Exception as erro:  # noqa: BLE001
            # Um erro que não é de hardware é BUG — e um bug numa thread morre em
            # silêncio, levando a aquisição junto sem nenhum sinal na tela. Este `except`
            # não engole nada: ele registra o traceback completo e força o erro a
            # aparecer para o usuário. É o oposto do `except` genérico que a versão antiga
            # usava para fingir que todo problema era "falha de hardware".
            logger.exception('Erro inesperado na thread de aquisição (isto é um bug)')
            self._publicar(
                EventoErro(
                    erro=erro,
                    mensagem_usuario=(
                        f'Erro inesperado na aquisição: {type(erro).__name__}: {erro}\n\n'
                        'Isto é um defeito do programa, não do hardware. '
                        'O traceback completo está no arquivo de log.'
                    ),
                )
            )

        finally:
            # SEMPRE publicado, inclusive após erro: é o que devolve a GUI ao estado
            # ocioso e libera os widgets.
            self._publicar(EventoParado(total_gravado=len(self._gravacao)))

    def _laco(self) -> None:
        """O laço quente. Sem `sleep`: quem dita a cadência é o dispositivo.

        `processar_amostra` bloqueia na leitura até haver sinal, e é exatamente essa
        espera que sincroniza o laço com o BITalino. Um `sleep` aqui faria a leitura
        ficar mais lenta que a produção, e o buffer do LSL acumularia atraso sem limite.
        """
        while not self._parar_pedido.is_set():
            resultado = self._ciclo.processar_amostra(controles=self._controles_atuais())

            # `None` é normal: o ciclo consumiu uma leitura sem fechar uma predição
            # (janela ainda acumulando, ou intervalo de predição não vencido).
            if resultado is None:
                continue

            if self._gravar:
                self._gravacao.append(resultado)

            self._publicar(EventoResultado(resultado=resultado))
