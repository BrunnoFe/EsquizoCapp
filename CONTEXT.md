# EsquizoCap

Instalação de arte que lê EEG de um BITalino, traduz o sinal em cor e comanda uma fita
de LED. Este arquivo é o glossário do projeto: só define termos, nunca decisões de
implementação (essas moram em `docs/adr/`).

## Language

### Aquisição

**Modo de aquisição**:
O caminho pelo qual o sinal do BITalino chega à aplicação. São dois: **Modo OpenSignals**
(a aplicação assina um stream publicado por outro programa) e **Modo Direto** (a aplicação
fala com o dispositivo por conta própria). Escolhido pelo usuário antes de conectar.
_Avoid_: modo de conexão, backend, driver

**MAC do dispositivo**:
Identidade permanente do BITalino, gravada no hardware. É também o `type` do stream no
Modo OpenSignals. Não muda de máquina para máquina.
_Avoid_: endereço, ID

**Porta de acesso**:
A porta serial (`COM7`) pela qual o Modo Direto alcança o dispositivo. Ao contrário do MAC,
é volátil: muda de máquina, de pareamento e até entre reinicializações. Um mesmo BITalino
tem MAC único e porta de acesso variável.
_Avoid_: endereço, porta (sem qualificar — a fita de LED também usa uma porta serial)

**Taxa acordada**:
A taxa de amostragem, em Hz, sob a qual a aquisição corre. No Modo OpenSignals é uma
propriedade *declarada pelo stream* (a aplicação pergunta); no Modo Direto é uma *escolha
da aplicação* (ela manda, e depois lembra). O dispositivo só aceita 1, 10, 100 ou 1000 Hz.
_Avoid_: taxa nominal, sample rate

**Canal ativo**:
O único canal analógico cujo sinal vira cor. O dispositivo sempre entrega todos os seis;
o canal ativo é escolha de exibição, não de hardware — trocá-lo não reconecta nada.
_Avoid_: canal selecionado, eletrodo

**Ciclo vazio**:
Uma volta do laço de aquisição que não produziu amostra e **não é falha** — quem chama
apenas tenta de novo. Só existe no Modo OpenSignals, onde o silêncio significa "o outro
programa ainda não publicou". No Modo Direto a aplicação é quem dirige o dispositivo, e
silêncio significa que algo quebrou.
_Avoid_: timeout, leitura vazia

**Unidade do sinal**:
A grandeza física em que o sinal chega ao domínio — hoje sempre **microvolts de EEG**. No
Modo OpenSignals a conversão é feita pelo OpenSignals; no Modo Direto o dispositivo entrega
ADU cru (inteiro de 0 a 1023) e a conversão é feita na borda de hardware. Em nenhum dos dois
casos o domínio vê ADU.
_Avoid_: escala, unidade de medida

**ADU**:
O valor bruto do conversor analógico-digital, antes de virar unidade física. A largura
depende do canal: 10 bits (0–1023) em A1–A4, 6 bits (0–63) em A5–A6.
_Avoid_: valor cru, raw

### Predição

**Modo de predição**:
Como uma leitura vira cor. **Amplitude** mapeia cada amostra individual em um matiz;
**Frequência** acumula um bloco, extrai a frequência dominante e mapeia a banda de EEG
correspondente. É ortogonal ao modo de aquisição.
_Avoid_: modo de leitura, algoritmo

**Banda de EEG**:
Faixa de frequência do EEG humano exibida na interface — Delta, Theta, Alpha, Beta ou Gamma.
Conceito exclusivo do modo de predição Frequência.
_Avoid_: faixa, ritmo
