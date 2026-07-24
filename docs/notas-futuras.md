# Notas futuras

Ideias levantadas e **deliberadamente adiadas**. Não são compromissos, e nenhuma está
implementada. Estão aqui para não se perderem e para que quem encontrar o assunto no código
saiba que já foi pensado.

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

## "Modo teste" na GUI

Substituir a variável de ambiente `ESQUIZOCAP_FAKE` (ver `hardware/fabrica.py`) por uma opção
na interface: um liga/desliga de "Modo teste", com escolha de simular só o Arduino, só o
BITalino, ou ambos. Motivação: quem opera a instalação não deve precisar de terminal.

Nota de projeto: a fábrica hoje decide antes da GUI existir. O modo de aquisição já força essa
decisão a virar escolha de runtime, então parte do caminho fica pronta.

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
| `interface_qt/bandas_eeg.py` (exibido ao operador) | 30–45 Hz |
| `hardware/constantes.py` (docstring da taxa padrão) | até 45 Hz |
| `dominio/pre_processamento.py:categorizar_frequencia` | 30–50 Hz |

Quem decide a cor é o classificador do domínio (50 Hz), então é ele que a regra de Nyquist
usa em `interface_qt/estado.py`. A tabela exibida diz outra coisa.

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
