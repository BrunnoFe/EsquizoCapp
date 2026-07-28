"""Varredura de portas fora da GUI thread.

Descobrir portas custa caro e o custo é invisível no código: `listar_portas` percorre os
dispositivos seriais do sistema, e `portas_bluetooth.listar_portas_do_sistema` consulta o
SetupAPI do Windows — dezenas de milissegundos cada, num pente que o Windows não promete
ser rápido. Feito na GUI thread, isso congela a janela; e como congelamento não levanta
exceção, o sintoma é a interface "engasgando" sem nada no log.

Pior: enquanto o event loop está parado, NENHUM indicador de espera consegue desenhar um
quadro. Ou seja, tirar a varredura da GUI thread não é otimização — é o que torna possível
mostrar que se está esperando.

A volta é por CAIXA DE CORREIO (`coletar`), e não por callback como em
`conexao_bitalino_assincrona`: a thread deposita o resultado aqui e quem quiser vem buscar.
A diferença tem motivo. Devolver por `Signal` Qt enfileira um evento endereçado ao
controller, e esse evento sobrevive ao controller — se o objeto morrer antes de o event loop
drenar (o que acontece a cada `processEvents` da suíte de testes), o Qt entrega a um ponteiro
morto e o processo cai com access violation, sem traceback Python. Uma caixa de correio não
tem endereçado: se ninguém vier buscar, o resultado simplesmente é descartado com o objeto.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from esquizocap.hardware import portas_bluetooth

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoVarredura:
    """O que uma varredura encontrou.

    Carrega o `mac` de volta de propósito: a varredura leva tempo, e o operador pode ter
    trocado de dispositivo no meio dela. Sem saber a QUAL mac esta porta pertence, o
    resultado atrasado sobrescreveria o cache com a porta do dispositivo anterior — número
    de COM plausível, dispositivo errado, e nenhum erro até a conexão falhar.
    """

    portas_seriais: list[str] = field(default_factory=list)
    """As portas oferecidas ao Arduino, como o controlador do Arduino as reporta."""

    mac: str = ''
    """O MAC do BITalino para o qual `porta_bitalino` foi derivada."""

    porta_bitalino: str = ''
    """A porta de acesso do BITalino, ou vazio quando não há — dispositivo não pareado,
    desligado, ou sistema fora do Windows."""


class VarredorDePortasAssincrono:
    """Varre as portas numa thread auxiliar e guarda o resultado até alguém buscar.

    Uso: `varrer(...)` dispara e retorna na hora; `coletar()` devolve o resultado quando
    ele estiver pronto, e `None` enquanto não estiver. Quem usa numa interface Qt chama
    `coletar` de dentro do `QTimer` que já drena a fila da aquisição — assim o resultado
    chega na GUI thread sem nenhum evento Qt endereçado a um objeto que pode morrer antes.
    """

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._resultado: ResultadoVarredura | None = None

    def varrer(self, listar_portas_seriais: Callable[[], list[str]], mac: str) -> None:
        """Inicia a varredura numa thread auxiliar e retorna imediatamente.

        Args:
            listar_portas_seriais: Como listar as portas do Arduino. Vem como função, e não
                como o objeto do Arduino, porque o Arduino é substituído inteiro ao ligar e
                desligar a simulação — guardar o objeto deixaria a varredura consultando um
                controlador órfão.
            mac: MAC do BITalino escolhido, para derivar a porta de acesso dele. Vazio pula
                a derivação.
        """

        def alvo_da_thread() -> None:
            portas_seriais: list[str] = []
            porta_bitalino = ''
            try:
                portas_seriais = list(listar_portas_seriais())
                if mac:
                    porta_bitalino = (
                        portas_bluetooth.derivar_porta(
                            mac=mac, portas_do_sistema=portas_bluetooth.listar_portas_do_sistema()
                        )
                        or ''
                    )
            except OSError as erro:
                # Enumerar dispositivos é uma chamada ao sistema operacional, e ela pode
                # falhar por motivos que não são culpa da aplicação (driver removido no
                # meio, permissão negada). Deixar a exceção subir mataria a thread sem
                # depositar nada, e o indicador giraria para sempre.
                logger.warning(f'A varredura de portas falhou: {erro}')
            with self._trava:
                self._resultado = ResultadoVarredura(
                    portas_seriais=portas_seriais, mac=mac, porta_bitalino=porta_bitalino
                )

        threading.Thread(target=alvo_da_thread, name='varrer-portas', daemon=True).start()

    def coletar(self) -> ResultadoVarredura | None:
        """Retira o resultado da caixa, ou `None` se ainda não houver um.

        Retira em vez de só ler: o resultado é consumido uma única vez, então chamar isto
        num laço de relógio não reprocessa a mesma varredura a cada batida.
        """
        with self._trava:
            resultado, self._resultado = self._resultado, None
        return resultado
