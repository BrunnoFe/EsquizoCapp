# Notas futuras

Ideias levantadas e **deliberadamente adiadas**. Não são compromissos, e nenhuma está
implementada. Estão aqui para não se perderem e para que quem encontrar o assunto no código
saiba que já foi pensado.

## Presets de aparência nomeados

A aparência tem hoje **dois** níveis: fábrica (os defaults de `AparenciaVisual`) e atual (o
que está nos sliders, gravado sozinho em `preferencias.json` com um atraso deliberado). Não
existe um terceiro — um ponto de retorno escolhido pelo operador.

Surgiu a ideia de um botão "Salvar aparência". Descartada como está: a aparência **já**
persiste automaticamente, então o botão seria um no-op decorado, e ainda sugeriria um estado
"não salvo" inexistente.

O que faria sentido é o passo maior: **presets nomeados** ("Galeria A", "Projetor da sala 2").
Uma instalação itinerante troca de espaço, e cada espaço quer um ajuste de brilho e escala
diferente. Um único slot anônimo — o meio-termo — paga o custo conceitual inteiro do terceiro
nível (incluindo explicar num ícone de 14 px se o reset volta à fábrica ou ao salvo) e entrega
justamente a parte que menos serve a esse caso de uso.

Se for feito, é ticket próprio, com tela própria.

## Migrar os componentes QML antigos para o singleton `Theme`

`Base/Theme.qml` nasceu com a caixa de mensagem (ver `docs/adr/0002-...`) e é hoje a única
definição das cores do app. Mas só os componentes novos consomem dele: `Configuracoes/`,
`Controles/`, `Base/` e `Janela/` continuam redigitando os mesmos hexadecimais na mão, e
`EsquizoCapView.qml` mantém aliases `readonly property` que só delegam ao Theme.

Não foi feito junto porque é refactor de paleta enfiado dentro de uma feature de erro: o
diff pararia de ser revisável, e uma regressão visual não teria como ser atribuída a uma das
duas mudanças. Merece um ticket próprio, com conferência visual tela a tela.

## Auditar os `ValueError` crus do protocolo do BITalino

`hardware/protocolo_bitalino.py` levanta `ValueError` em cinco pontos (canal inválido, taxa
não suportada, frame malformado) e `hardware/constantes.py` em mais um. Nenhum tem entrada
no `catalogo_erros`, então todos caem na `FALHA_INESPERADA` genérica ("isto é um defeito do
programa") — o que é impreciso: taxa não suportada é escolha do usuário, não bug.

A rede de segurança garante que nenhum deles passa despercebido enquanto isso, que era o
risco real. Dar mensagem própria a cada um é trabalho de domínio de hardware, não de UI.

## Entrada de texto na caixa de mensagem

A `EspecificacaoCaixa` foi desenhada para receber um campo opcional de entrada sem
reescrever nada, mas isso não foi construído. O que falta decidir: validar antes de aceitar,
o que "OK" faz com valor inválido, foco e ordem de tab. É outro contrato, não uma variação
da caixa informativa.

## Migrar a confirmação de gravação pendente para a caixa

Hoje, decidir salvar ou descartar uma gravação pendente passa pelo `FileDialog` do sistema.
Com a `CaixaDeMensagem` e os papéis `CONFIRMAR`/`RECUSAR` já prontos, isso pode virar uma
confirmação no idioma visual do app. Seria o primeiro caso de uso com resposta de verdade —
e o que vai exercitar o caminho `respondida(papel)` que hoje só fecha a caixa.

## Tela cheia iniciada pelo sistema operacional dessincroniza o estado

Quem manda em tela cheia é o `controller.telaCheia`; a janela só espelha, pelo `Connections`
em `EsquizoCapView.qml`. O caminho de volta não existe: `onVisibilityChanged: {}` é um stub
vazio. Se o usuário sair da tela cheia por meio do SO (duplo clique na barra, atalho do gestor
de janelas, F11 do compositor), a janela restaura mas `telaCheia` continua `true` — e o rail,
o topbar e a barra de transporte seguem escondidos numa janela normal.

Não foi corrigido junto com o ESC porque fechar o laço exige cuidado: reagir a
`visibilityChanged` chamando `alternarTelaCheia()` cria recursão com o próprio espelho, que
por sua vez chama `showFullScreen()`/`showNormal()`. Precisa comparar antes de agir, e o teste
disso pede janela de verdade.

## O botão "Sobre" não faz nada

O `RailButton { glyph: "i"; tip: "Sobre" }` no rail não tem `onClicked`. Clicar não produz
efeito nenhum e nem erro. Falta decidir o que ele mostraria (versão, licença, créditos) e onde
— provavelmente mais uma aba em `JanelaConfiguracoes`, não uma janela nova.

## Seletor de tipo de sensor

Hoje a conversão ADU→unidade física assume **sempre EEG**. O BITalino aceita outros sensores
(EDA, ECG, EMG, EOG, EGG), cada um com sua função de transferência. A ideia é perguntar o tipo
de sensor na tela de conexão e converter conforme a escolha.

O que torna isso maior do que parece:

- **A unidade de saída muda.** ECG, EMG, EOG e EGG saem em mV; EEG em µV; **EDA sai em µS
  (microsiemens)** — condutância, não tensão. Não é a mesma fórmula com outra constante. Hoje
  `dominio/ciclo_aquisicao.py` escreve `uV` fixo no log.
- **Tipo de sensor é propriedade do canal, não do dispositivo.** Nada impede EEG no A1 e EDA no
  A2. Como o sistema só consome o canal ativo, um seletor único ligado a ele provavelmente
  basta — ao custo de o vetor devolvido ficar heterogêneo (uma coluna em unidade física, cinco
  em ADU).
- **As bandas de EEG deixam de fazer sentido.** Delta/Theta/Alpha/Beta/Gamma não significam
  nada para EDA (que vive abaixo de 1 Hz) nem para EMG. O modo de predição Frequência teria de
  saber disso.
- **O modelo de predição de hue foi calibrado num domínio de valores.** Entregar mV de ECG onde
  ele espera µV de EEG dá cor errada, mesmo com a conversão correta.

## "Modo teste" na GUI — RESOLVIDO

Feito: a aba "Simulação" do menu de configurações liga e desliga Arduino e BITalino
separadamente, em runtime, e a escolha é gravada em `settings/preferencias.json`. A
`ESQUIZOCAP_FAKE` continua existindo e **tem precedência** — serve aos testes e à CI, e a
interface mostra os controles travados explicando isso quando a variável está definida.

O obstáculo previsto ("a fábrica decide antes da GUI existir") foi resolvido dando à fábrica
um parâmetro `simulados` e ao controller um `_reconstruir_hardware()`, permitido só com tudo
desconectado — a mesma regra que o seletor de modo já usava.

Fica em aberto: o `BitalinoSintetico` segue respondendo igual pelos dois modos de aquisição,
então o modo simulado **não** exercita a diferença entre Modo OpenSignals e Modo Direto (ciclo
vazio, unidade, escala). O seletor de modo continua travado sob simulação por causa disso.

## Canal sem sensor chega ao domínio em ADU

**Não é assunto do Modo Direto — já vale hoje, no Modo OpenSignals.** Descoberto ao sondar o
stream real antes de implementar a #4.

O OpenSignals aplica a função de transferência **apenas nos canais em que há sensor
configurado**. No setup de referência, o stream de 7 canais vem assim:

| Índice | Rótulo | Unidade |
| --- | --- | --- |
| 0 | `nSeq` | — |
| 1 | `EEGBITREV0` | µV |
| 2 | `RAW1` | — (ADU cru) |
| 3 | `EDABITREV2` | µS |
| 4, 5, 6 | `RAW3/4/5` | — (ADU cru) |

Se o operador escolher na interface um canal sem sensor declarado, o domínio recebe **ADU**
(inteiro de 0 a 1023, sempre positivo, centrado em ~512) onde espera microvolts (faixa
±39,49, média zero). O modelo de predição prevê cor a partir de um número numa escala
completamente diferente, sem erro nenhum — só cor errada na fita.

Pior: escolher o canal do EDA entrega **microsiemens**, que é outra grandeza física.

A interface hoje apresenta os seis canais como equivalentes e não tem como saber quais têm
sensor. Duas saídas possíveis, nenhuma implementada: ler os rótulos que o stream LSL já
declara nos metadados (`EEGBITREV0`, `RAW1`, ...) e refleti-los no seletor de canal; ou
assumir a configuração e documentá-la. A primeira é factível — a sonda leu esses rótulos sem
dificuldade.

Ver também o seletor de tipo de sensor, acima: é o mesmo problema visto do outro lado.

## Taxa real do OpenSignals é 100 Hz, e isso deixa a predição lenta

Medido no stream de referência: `nominal_srate = 100.0`. É coerente com o sensor, que filtra
em 0,8–48 Hz (Nyquist de 50 Hz cobre a banda inteira), mas tem efeito visível na obra:

- `TAMANHO_BLOCO_LEITURA = 500` a 100 Hz são **5 segundos por bloco**.
- A janela máxima de 2048 amostras a 100 Hz são **20 segundos por predição**.

A instalação troca de cor muito mais devagar do que o código sugere à primeira leitura. Vale
decidir se as constantes de bloco e janela deveriam ser expressas em SEGUNDOS em vez de
amostras — hoje o significado delas muda conforme a taxa acordada, sem que ninguém perceba.

## Três fontes discordam sobre onde Gamma termina

| Onde | Faixa de Gamma |
| --- | --- |
| `interface/bandas_eeg.py` (exibido ao operador) | 30–45 Hz |
| `hardware/constantes.py` (docstring da taxa padrão) | até 45 Hz |
| `dominio/pre_processamento.py:categorizar_frequencia` | 30–50 Hz |

Quem decide a cor é o classificador do domínio (50 Hz), então é ele que a regra de Nyquist
usa em `interface/estado.py`. A tabela exibida diz outra coisa.

Na prática pouco muda — o sensor filtra em 0,8–48 Hz por hardware, então nada acima de 48 Hz
chega ao classificador de qualquer jeito, e as duas taxas que sobram no modo Frequência (100
e 1000 Hz) cobrem os dois valores. Mas são três números para um fato só, e o dia em que
alguém ajustar um deles os outros ficarão para trás em silêncio.

Vale escolher uma fonte — provavelmente o classificador — e fazer as outras derivarem dela.

## Canais A5/A6 têm 6 bits

**Não é assunto do modo direto — já vale hoje, no modo OpenSignals.** No BITalino (r)evolution,
A1–A4 são de 10 bits (1024 níveis) e **A5–A6 são de 6 bits (64 níveis)**. EEG é um sinal de
microvolts: com 64 níveis, boa parte do que chega ao pré-processamento é degrau de
quantização, e a FFT do modo Frequência espalha energia por todo o espectro — a "banda
dominante" vira sorteio.

A interface passa a exibir a resolução no combobox de canal, mas os seis seguem selecionáveis:
o eletrodo é físico, e negar a leitura de quem plugou no A5 é pior do que avisar.

## O sensor EEG filtra em 0,8–48 Hz

Do datasheet do sensor. Gamma (30–45 Hz) passa bem, mas **a parte de baixo de Delta (0,5–4 Hz)
é cortada pelo próprio hardware**. A banda Delta exibida na interface, portanto, nunca é
observada por inteiro. Vale checar se isso enviesa a predição no modo Frequência.

## Tela de carregamento ligada ao carregamento de verdade

`Layout/TelaDeCarregamento.qml` já existe e aparece no boot, mas é **decorativa**: o gatilho
é um `Timer` de 2200 ms marcado com `// PROVISÓRIO:` em `EsquizoCapView.qml`, e a linha de
status mostra um texto neutro ("carregando") que não afirma nada sobre o que está sendo feito.
Falta (a) decidir o que de fato é carregado no boot e vale ser medido, (b) expor isso no
`controller.py` como propriedade, e (c) trocar o Timer por `aberta: controller.<essa
propriedade>`, alimentando `mensagem` com o status real.

O detalhe que decide o desenho: o **modelo é carregado em `main.py` ANTES de a janela
existir**, então hoje a tela nem chega a estar de pé enquanto ele sobe. Cobrir essa etapa
exige mover o carregamento para depois do `engine.load` — mudança de ordem de inicialização,
com risco próprio, e por isso deliberadamente fora da sessão que construiu a tela.

## Convenção: espera visível = `IndicadorCarregando`, nunca `BusyIndicator`

Toda espera perceptível mostra `Base/IndicadorCarregando.qml` (a marca animada em escala
pequena). O `BusyIndicator` do QtQuick.Controls **não é usado em lugar nenhum** e não deve
entrar: o indicador da casa é a marca. Duas regras que vão junto — o gate tem que ser uma
`Property` real do controller, nunca um `Timer` chutado no QML, e no máximo **um** indicador
visível por região da tela ao mesmo tempo (coincidindo dois, vence o rótulo mais específico).

Fica em aberto quais outras esperas merecem tratamento. As três cobertas hoje são conexão do
BITalino, varredura de portas e o diagnóstico que depende dela; `pararAquisicao` ainda bloqueia
a GUI thread por 1–3 s (comportamento herdado do Tkinter, ver o docstring do método) e por isso
não tem como mostrar indicador nenhum — resolvê-lo é tornar a parada assíncrona, ticket próprio.
