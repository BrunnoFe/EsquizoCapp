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
