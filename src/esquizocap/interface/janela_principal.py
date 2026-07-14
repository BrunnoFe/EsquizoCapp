"""A janela principal do EsquizoCap.

Esta classe é a CASCA: liga os painéis (`paineis`, `medidores`) aos eventos, reage aos
cliques e pinta o que a thread de aquisição publica. Ela não constrói widget nenhum
diretamente — isso é dos módulos de painel — e não lê EEG, não decide cor e não grava
arquivo — isso é do `dominio`, do `aplicacao` e da `infraestrutura`, respectivamente.

A regra que a mantém honesta: *nenhuma decisão que possa ser tomada sem um widget deve
ser tomada aqui*. A prontidão da interface é uma função pura (`estado.avaliar_prontidao`),
a cadência de predição é do domínio, e o que aparece na tela é sempre reflexo de um
`ResultadoCiclo` já pronto.
"""

import logging
from pathlib import Path
from tkinter import Widget

from ttkbootstrap.constants import SE, N
from ttkbootstrap.dialogs import Messagebox, Querybox

from esquizocap import hardware
from esquizocap.aplicacao import EventoErro, EventoParado, EventoResultado, ServicoAquisicao
from esquizocap.dominio.ciclo_aquisicao import CicloAquisicao, ModoAnalise, ResultadoCiclo
from esquizocap.dominio.predicao import ModeloPreditor
from esquizocap.hardware import constantes
from esquizocap.infraestrutura import config, persistencia, recursos
from esquizocap.interface import arduino_gui, hovertip_config, layout, medidores, paineis, textos
from esquizocap.interface.custom_gui import CreateCustomGui, ttk
from esquizocap.interface.estado import (
    EstadoApp,
    SelecaoUsuario,
    avaliar_prontidao,
    mensagem_de_aquisicao,
)
from esquizocap.interface.medidores import PainelMedidores

logger = logging.getLogger(__name__)

TEXTO_OCIOSO: str = 'Aguardando início da aquisição'


class JanelaPrincipal:
    """A janela do EsquizoCap: configuração do hardware, aquisição e exibição da cor."""

    def __init__(self, configuracao: config.Configuracao, modelo: ModeloPreditor) -> None:
        self.config = configuracao
        self.modelo = modelo
        """Já carregado na entrada da aplicação: um modelo inválido tem que impedir a
        janela de abrir, e não estourar no clique de "Começar aquisição"."""

        self.custom_gui = CreateCustomGui(
            iconpath=str(recursos.ICONE),
            themename=configuracao.tema,
            width=layout.LARGURA_JANELA,
            heigth=layout.ALTURA_JANELA,
        )
        self.root: ttk.Window = self.custom_gui.root
        self.main_window: ttk.Frame = self.custom_gui.main_window
        self.style: ttk.Style = self.root.style

        self.arduino: hardware.ControladorLedArduino = hardware.criar_arduino()
        self.bitalino: hardware.LeitorBitalino = hardware.criar_bitalino()

        # O estado é EXPLÍCITO. Antes era inferido comparando strings de StringVar, num
        # `after(10 ms)` que rodava para sempre só para escolher a frase do status.
        self.estado: EstadoApp = EstadoApp.CONFIGURANDO

        # Só existem entre o "Começar" e o "Parar". Fora disso são None, e é exatamente
        # isso que significa "não estamos adquirindo".
        self.servico: ServicoAquisicao | None = None
        self.ciclo: CicloAquisicao | None = None
        self._agendamento_drenagem: str | None = None
        self._ultima_faixa_frequencia: str | None = None

        self._montar_paineis()
        self._empilhar_frames()

        self._aplicar_tooltips()
        self.aplicar_tema(self.config.tema)

        self.root.after(100, self.custom_gui.set_appwindow)  # ícone na barra de tarefas
        self.root.bind('<FocusIn>', self.custom_gui.deminimize)

        # Os DOIS caminhos de saída precisam desligar o hardware. O "×" é um botão nosso
        # (a janela não tem barra de título nativa), então o protocolo WM_DELETE_WINDOW
        # sozinho não o cobriria — ele só pega o Alt+F4.
        self.custom_gui.close_button.configure(command=self.ao_fechar)
        self.root.protocol('WM_DELETE_WINDOW', self.ao_fechar)

        # Estado inicial: ninguém escolheu nada ainda. Trava o "Começar" e escreve a
        # primeira mensagem de status.
        self._ao_mudar_selecao()

    def executar(self) -> None:
        """Entra no laço de eventos do Tk. Só retorna quando a janela fecha."""
        self.root.mainloop()

    # ------------------------------------------------------------------ montagem

    def _montar_paineis(self) -> None:
        """Constrói cada painel (já posicionado dentro do próprio frame) e os liga."""
        self.painel_titulo = paineis.criar_painel_titulo(
            master=self.main_window, caminho_foto=str(recursos.FOTO_TITULO)
        )
        self.painel_modelo = paineis.criar_painel_modelo(master=self.main_window)
        self.painel_arduino = paineis.criar_painel_arduino(master=self.main_window, arduino=self.arduino)
        self.painel_bitalino = paineis.criar_painel_bitalino(
            master=self.main_window, macs_conhecidos=self.config.macs_bitalino
        )
        self.painel_analise = paineis.criar_painel_analise(master=self.main_window)

        self.status_frame = ttk.Frame(master=self.main_window, name='status_frame')
        self.start_frame = ttk.Frame(master=self.main_window, name='start_frame')
        self.painel_status = paineis.criar_painel_status_inicio(
            master_status=self.status_frame, master_start=self.start_frame
        )
        self.painel_status.start_button.configure(command=self.iniciar_aquisicao)

        self.notebook = ttk.Notebook(master=self.main_window, name='notebook_frame')
        self.medidores_amplitude = medidores.criar_medidores_amplitude(master=self.notebook)
        self.medidores_frequencia = medidores.criar_medidores_frequencia(master=self.notebook)
        self.notebook.add(child=self.medidores_amplitude.frame, text=ModoAnalise.AMPLITUDE.value, sticky=N)
        self.notebook.add(child=self.medidores_frequencia.frame, text=ModoAnalise.FREQUENCIA.value, sticky=N)
        self.medidores_amplitude.observar_mudancas(self._ao_mudar_medidor)
        self.medidores_frequencia.observar_mudancas(self._ao_mudar_medidor)

        self.painel_cor = paineis.criar_painel_cor(master=self.main_window, texto_inicial=TEXTO_OCIOSO)

        self.imagem_desconectado = ttk.PhotoImage(file=str(recursos.CIRCULO_VERMELHO)).subsample(5, 5)
        self.imagem_conectado = ttk.PhotoImage(file=str(recursos.CIRCULO_VERDE)).subsample(5, 5)
        self.painel_status_arduino = paineis.criar_painel_status_arduino(
            master=self.main_window, imagem_desconectado=self.imagem_desconectado
        )

        self.theme_box, self.theme_var = paineis.criar_seletor_tema(
            master=self.custom_gui.title_bar, tema_atual=self.root.style.theme_use()
        )
        self.theme_box.bind('<<ComboboxSelected>>', lambda _: self.aplicar_tema(self.theme_var.get()))

        self.painel_arduino.button.configure(command=self._alternar_conexao_arduino)

        self.widgets_configuracao: tuple[Widget, ...] = (
            self.painel_modelo.combobox,
            self.painel_modelo.gravar_button,
            self.painel_arduino.button,
            self.painel_arduino.ports_box,
            self.painel_arduino.vel_box,
            self.painel_arduino.lumin_box,
            self.painel_bitalino.canais_box,
            self.painel_bitalino.mac_box,
            # O modo de análise PRECISA estar aqui. Fora desta lista, o usuário podia
            # trocá-lo no meio da aquisição: o ciclo seguia no modo antigo, mas os
            # controles passavam a ser lidos dos medidores da OUTRA aba, e a gravação era
            # salva com o layout de colunas errado.
            self.painel_analise.combobox,
        )

        # Reagir a mudanças, em vez de varrê-las 100 vezes por segundo. O `trace_add`
        # dispara exatamente quando o usuário mexe em alguma coisa — que é o único
        # momento em que a prontidão pode ter mudado.
        for variavel in (
            self.painel_modelo.modelo_var,
            self.painel_arduino.lumin_var,
            self.painel_arduino.porta_var,
            self.painel_arduino.string_var,
            self.painel_bitalino.mac_var,
            self.painel_bitalino.canal_var,
            self.painel_modelo.gravar_var,
        ):
            variavel.trace_add('write', self._ao_mudar_selecao)

    def _empilhar_frames(self) -> None:
        """Empilha os frames de cada painel, um por linha, ocupando a largura toda."""
        frames = (
            self.painel_titulo.frame,
            self.painel_modelo.frame,
            self.painel_arduino.frame,
            self.painel_bitalino.frame,
            self.painel_analise.frame,
            self.status_frame,
            self.start_frame,
            self.notebook,
            self.painel_cor.frame,
        )
        for linha, frame in enumerate(frames):
            frame.grid(row=linha, columnspan=len(layout.COLUNAS_GRID), sticky=N, padx=5, pady=5)

        self.painel_status_arduino.frame.grid(column=0, row=layout.LINHAS_GRID[-1], sticky='sw')
        ttk.Sizegrip(master=self.main_window).grid(
            column=layout.COLUNAS_GRID[-1], row=layout.LINHAS_GRID[-1], sticky=SE
        )

    def _aplicar_tooltips(self) -> None:
        """Casa cada widget com o seu texto de ajuda, pelo NOME.

        O mapa é escrito à mão de propósito: é ele que garante que a tooltip de um widget
        seja a tooltip DAQUELE widget. Ver `hovertip_config.aplicar_tooltips`.
        """
        hovertip_config.aplicar_tooltips(
            widgets={
                'theme_box': self.theme_box,
                'model_box': self.painel_modelo.combobox,
                'gravar_button': self.painel_modelo.gravar_button,
                'arduino_ports_box': self.painel_arduino.ports_box,
                'arduino_vel_box': self.painel_arduino.vel_box,
                'arduino_lumin_box': self.painel_arduino.lumin_box,
                'arduino_button': self.painel_arduino.button,
                'bitalino_canais_box': self.painel_bitalino.canais_box,
                'bitalino_mac_box': self.painel_bitalino.mac_box,
                'analysis_box': self.painel_analise.combobox,
                'start_button': self.painel_status.start_button,
                'amp_hue_meter': self.medidores_amplitude.hue_meter,
                'amp_saturation_meter': self.medidores_amplitude.saturation_meter,
                'amp_value_meter': self.medidores_amplitude.value_meter,
                'amp_sampling_meter': self.medidores_amplitude.sampling_meter,
                'freq_hue_meter': self.medidores_frequencia.hue_meter,
                'freq_saturation_meter': self.medidores_frequencia.saturation_meter,
                'freq_value_meter': self.medidores_frequencia.value_meter,
                'freq_sampling_meter': self.medidores_frequencia.sampling_meter,
            },
            textos=textos.TOOLTIPS,
            fundo=layout.COR_FUNDO_TOOLTIP,
            frente=layout.COR_TEXTO_TOOLTIP,
            atraso_ms=layout.ATRASO_TOOLTIP_MS,
        )

    def aplicar_tema(self, tema: str) -> None:
        """Troca o tema do ttkbootstrap e reaplica os ajustes de estilo da janela."""
        self.style.theme_use(themename=tema)
        self.style.configure('TCombobox', arrowsize=20)
        self.style.configure('TSizegrip', size=50)
        self.style.configure('.', font=self.custom_gui.font)
        logger.info(f'Tema alterado. Novo = {tema}')

    # ------------------------------------------------------------------- interação

    def _alternar_conexao_arduino(self) -> None:
        painel = self.painel_arduino
        arduino_gui.alternar_conexao(
            arduino=self.arduino,
            porta=painel.porta_var.get(),
            baudrate=painel.veloc_var.get(),
            modo=painel.lumin_var.get(),
            widgets=arduino_gui.WidgetsArduino(
                botao=painel.button,
                rotulo_botao=painel.string_var,
                caixas=(painel.ports_box, painel.vel_box, painel.lumin_box),
                rotulo_status=self.painel_status_arduino.label,
                imagem_conectado=self.imagem_conectado,
                imagem_desconectado=self.imagem_desconectado,
            ),
        )

    def _ao_mudar_selecao(self, *_args: object) -> None:
        """Uma escolha do usuário mudou: reavalia o estado e atualiza o status.

        Recebe `*_args` porque o Tk passa (nome, índice, operação) para o callback de
        trace, e nada disso interessa aqui — a regra olha o retrato inteiro da seleção.
        """
        if self.estado in (EstadoApp.ADQUIRINDO, EstadoApp.PARANDO):
            # Durante a aquisição os widgets estão travados; o status pertence à thread.
            return

        selecao = SelecaoUsuario(
            modelo=self.painel_modelo.modelo_var.get(),
            porta_arduino=self.painel_arduino.porta_var.get(),
            modo_luminosidade=self.painel_arduino.lumin_var.get(),
            arduino_conectado=self.arduino.esta_conectado,
            canal_bitalino=self.painel_bitalino.canal_var.get(),
            mac_bitalino=self.painel_bitalino.mac_var.get(),
        )

        self.estado, mensagem = avaliar_prontidao(
            selecao=selecao, macs_validos=self.config.macs_bitalino
        )
        self.painel_status.status_var.set(value=mensagem)
        self.painel_status.start_button['state'] = 'normal' if self.estado is EstadoApp.PRONTO else 'disabled'

    def _travar_widgets_de_configuracao(self, travar: bool) -> None:
        """Trava (ou libera) tudo que não pode mudar durante a aquisição.

        Combobox liberado volta para `readonly`, e não para `normal`: o usuário escolhe da
        lista, nunca digita.
        """
        for widget in self.widgets_configuracao:
            if isinstance(widget, ttk.Combobox):
                widget['state'] = 'disabled' if travar else 'readonly'
            else:
                widget['state'] = 'disabled' if travar else 'normal'

    def _medidores_ativos(self) -> PainelMedidores:
        """O painel de medidores do modo em uso agora.

        Antes da aquisição começar (`self.ciclo is None`) não há "modo em uso" ainda;
        cair no de Frequência é inofensivo, porque essa leitura só serve para inicializar
        `ServicoAquisicao` com QUALQUER controle válido — o modo de verdade só é fixado em
        `iniciar_aquisicao`, e é ele quem decide qual painel vale dali em diante.
        """
        if self.ciclo is not None and self.ciclo.modo_analise is ModoAnalise.AMPLITUDE:
            return self.medidores_amplitude
        return self.medidores_frequencia

    def _ao_mudar_medidor(self, *_args: object) -> None:
        """O usuário mexeu num medidor: repassa os novos controles à thread de aquisição.

        É este empurrão que substitui a thread ir "buscar" o valor no widget — o que
        seria tocar em Tkinter de fora da thread da interface, e é comportamento
        indefinido.
        """
        if self.servico is not None:
            self.servico.atualizar_controles(self._medidores_ativos().controles_usuario())

    # -------------------------------------------------------------------- aquisição

    def iniciar_aquisicao(self) -> None:
        """Conecta o BITalino, monta o núcleo e entrega a aquisição a uma thread.

        A partir daqui a GUI não lê mais o EEG: ela só drena a fila do serviço e pinta.
        """
        if self.estado is not EstadoApp.PRONTO:
            logger.warning(f'"Começar aquisição" pressionado no estado {self.estado.name}; ignorando.')
            return

        try:
            self.bitalino.conectar(mac_addr=self.painel_bitalino.mac_var.get())
        except hardware.ErroConexaoBitalino as erro:
            logger.error(f'Não foi possível conectar ao BITalino: {erro}')
            Messagebox.show_error(title='Bitalino error!', message=f'{erro}')
            return

        modo = ModoAnalise(self.painel_analise.analise_var.get())
        canal = int(self.painel_bitalino.canal_var.get())
        logger.info(
            f'Iniciando aquisição no modo {modo.value}, canal A{canal}, '
            f'taxa de amostragem = {self.bitalino.taxa_amostragem_nominal()} Hz'
        )

        self.notebook.select(
            self.medidores_amplitude.frame if modo is ModoAnalise.AMPLITUDE else self.medidores_frequencia.frame
        )

        # O núcleo é montado aqui, e não no __init__, porque só agora existem todas as
        # escolhas do usuário: canal, modo de análise e tamanho da janela.
        self.ciclo = CicloAquisicao(
            leitor=self.bitalino,
            arduino=self.arduino,
            modelo=self.modelo,
            modo_analise=modo,
            canal_bitalino=canal,
            modo_luminosidade=constantes.indice_do_modo(self.painel_arduino.lumin_var.get()),
            tamanho_amostra_frequencia=self.medidores_frequencia.sampling_meter.amountusedvar.get(),
        )

        # A gravação vive DENTRO do serviço. É o que permite a fila de desenho descartar
        # resultados quando a interface não acompanha, sem perder dado gravado.
        self.servico = ServicoAquisicao(ciclo=self.ciclo, gravar=self.painel_modelo.gravar_var.get())
        self.servico.atualizar_controles(self._medidores_ativos().controles_usuario())

        self._ultima_faixa_frequencia = None
        self.estado = EstadoApp.ADQUIRINDO

        self.painel_status.start_button.configure(command=self.pedir_parada, text='Parar aquisição')
        self._travar_widgets_de_configuracao(travar=True)
        self.medidores_frequencia.travar_amostragem(travar=True)
        self.painel_status.status_var.set(
            value=mensagem_de_aquisicao(gravando=self.painel_modelo.gravar_var.get())
        )

        self.servico.iniciar()
        self._drenar_eventos()

    def _drenar_eventos(self) -> None:
        """Consome o que a thread de aquisição publicou e reflete na tela.

        Roda na thread da GUI, a cada `INTERVALO_DRENAGEM_MS`. Nunca bloqueia: se a fila
        estiver vazia, sai na hora e a janela segue respondendo. É o único ponto em que
        um resultado da aquisição toca em widget.
        """
        if self.servico is None:
            return

        self._agendamento_drenagem = None

        for evento in self.servico.drenar():
            match evento:
                case EventoResultado():
                    self._pintar_resultado(evento.resultado)

                case EventoErro():
                    logger.error(f'A thread de aquisição reportou: {evento.erro}')
                    Messagebox.show_error(title='Erro na aquisição!', message=evento.mensagem_usuario)

                case EventoParado():
                    logger.info(f'Aquisição encerrada. {evento.total_gravado} resultados gravados.')
                    self._finalizar_aquisicao()
                    return

        self._pintar_progresso()
        self._agendamento_drenagem = self.main_window.after(
            ms=layout.INTERVALO_DRENAGEM_MS, func=self._drenar_eventos
        )

    def _pintar_progresso(self) -> None:
        """Mostra o quanto falta para fechar a próxima janela de análise (modo Frequência)."""
        if self.servico is None or self.ciclo is None:
            return
        if self.ciclo.modo_analise is ModoAnalise.AMPLITUDE:
            return

        faixa = f' | {self._ultima_faixa_frequencia}' if self._ultima_faixa_frequencia else ''
        self.painel_cor.cor_var.set(
            value=f'Analisando amostras = {self.servico.progresso_janela}'
            f'/{self.ciclo.tamanho_amostra_frequencia}{faixa}'
        )

    def _pintar_resultado(self, resultado: ResultadoCiclo) -> None:
        """Reflete um `ResultadoCiclo` nos widgets. Nenhuma lógica de negócio aqui."""
        if resultado.faixa_frequencia is None:
            self.medidores_amplitude.hue_meter.amountusedvar.set(resultado.hue)
            self.painel_cor.cor_var.set(value=f'Amplitude = {resultado.metrica_bruta:0.2f}uV')
        else:
            self.medidores_frequencia.hue_meter.amountusedvar.set(resultado.hue)
            self._ultima_faixa_frequencia = (
                f'Frequência = {resultado.metrica_bruta:0.2f}Hz | {resultado.faixa_frequencia}'
            )

        self.painel_cor.label.configure(background=resultado.cor_hex)

    def pedir_parada(self) -> None:
        """Confirma com o usuário e pede a parada. NÃO espera aqui.

        A thread pode levar até ~1 s para perceber o pedido, se estiver no meio de uma
        leitura bloqueante. Quem conclui o encerramento é o `EventoParado`, quando ele
        chegar pela fila — daí o estado PARANDO no meio do caminho, que impede um segundo
        clique de pedir a parada de novo.
        """
        if self.estado is not EstadoApp.ADQUIRINDO:
            return

        if Messagebox.yesno(message='Deseja parar a aquisição?', alert=True) != 'Yes':
            logger.info('Usuário escolheu voltar para a aquisição')
            return

        logger.info('Usuário selecionou "Parar aquisição".')
        self.estado = EstadoApp.PARANDO
        self.painel_status.status_var.set(value='Parando a aquisição ...')
        self.painel_status.start_button['state'] = 'disabled'

        if self.servico is not None:
            self.servico.parar()

    def _finalizar_aquisicao(self) -> None:
        """Fecha o hardware, oferece a gravação e devolve a interface ao estado ocioso.

        Chamado ao receber o `EventoParado` — que a thread SEMPRE publica, tanto na parada
        normal quanto depois de um erro. É por isso que uma falha do BITalino no meio da
        aquisição também passa por aqui: não existe caminho de saída que esqueça de fechar
        a porta serial.
        """
        if self.servico is None:
            return

        modo = self.ciclo.modo_analise if self.ciclo is not None else ModoAnalise.FREQUENCIA

        # A thread já terminou (o EventoParado é a última coisa que ela publica), mas o
        # `parar()` também cobre o caso do erro, em que ninguém pediu a parada.
        self.servico.parar()
        resultados = self.servico.gravacao
        self.servico = None
        self.ciclo = None
        self._cancelar_drenagem()

        self._encerrar_hardware()

        if resultados:
            self._salvar_gravacao(resultados=resultados, modo=modo)

        self.painel_arduino.string_var.set('Conectar')
        self.painel_status_arduino.label.configure(image=self.imagem_desconectado)
        self.painel_status.start_button.configure(command=self.iniciar_aquisicao, text='Começar aquisição')
        self.painel_status.start_button['state'] = 'normal'
        self.medidores_frequencia.travar_amostragem(travar=False)
        self.painel_cor.cor_var.set(value=TEXTO_OCIOSO)

        self._travar_widgets_de_configuracao(travar=False)

        self.estado = EstadoApp.CONFIGURANDO
        self._ao_mudar_selecao()

    def _salvar_gravacao(self, resultados: list[ResultadoCiclo], modo: ModoAnalise) -> None:
        """Pergunta o nome ao usuário e manda gravar.

        Quem pergunta é a interface. A `persistencia` só recebe o caminho pronto — antes,
        ela abria um diálogo no meio da função de dados.
        """
        nome_escolhido = Querybox.get_string(
            prompt=f'Dê um nome para o arquivo EXCEL com os dados de {modo.value}:',
            initialvalue=persistencia.nome_sugerido(modo.value),
        )

        if not nome_escolhido:
            logger.warning('Usuário cancelou o salvamento. A gravação foi descartada.')
            return

        destino = Path(self.config.pasta_gravacoes) / f'{nome_escolhido}.xlsx'

        try:
            persistencia.salvar_gravacao(resultados=resultados, destino=destino)
        except persistencia.ErroDeGravacao as erro:
            logger.error(f'Falha ao salvar a gravação em "{destino}": {erro}')
            Messagebox.show_error(title='Erro no salvamento de dados!', message=str(erro))

    # ----------------------------------------------------------------- encerramento

    def _cancelar_drenagem(self) -> None:
        """Cancela o `after` pendente da drenagem, se houver.

        Sem isto, fechar a janela no meio de uma aquisição deixava um callback agendado
        para uma janela que já não existe — e o Tk o executava mesmo assim, estourando
        um `TclError` na saída.
        """
        if self._agendamento_drenagem is None:
            return

        self.main_window.after_cancel(self._agendamento_drenagem)
        self._agendamento_drenagem = None

    def _encerrar_hardware(self) -> None:
        """Fecha as duas bordas físicas. Idempotente por contrato: chamar duas vezes é seguro."""
        self.bitalino.encerrar_stream()
        self.arduino.desconectar()
        logger.info('Arduino e Bitalino desconectados.')

    def ao_fechar(self) -> None:
        """Desligamento ordenado: para a thread e fecha o hardware ANTES de destruir a janela.

        Antes, o "×" chamava `root.destroy()` direto: a porta serial e o stream do LSL
        ficavam abertos até o processo morrer, e a próxima execução podia não conseguir
        abrir a porta.
        """
        logger.info('Fechando o EsquizoCap ...')

        self._cancelar_drenagem()

        if self.servico is not None:
            self.servico.parar()
            self.servico = None

        self._encerrar_hardware()
        self.root.destroy()
