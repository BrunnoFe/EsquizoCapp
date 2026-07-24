# Testes manuais

O que **exige hardware plugado** e por isso não está na suíte automatizada. A suíte cobre
tudo o que é verificável sem BITalino e sem Arduino; o que sobra está aqui.

Registre o resultado no ticket correspondente ao rodar — a data e o que você observou. Um
roteiro sem registro de execução não prova nada.

---

## 1. Comparação entre os modos de aquisição

**Quando:** antes de qualquer instalação que vá usar o Modo Direto, e sempre que a conversão
de unidade ou o desempacotamento do protocolo forem mexidos.

**Por que este é o mais importante:** o risco central do Modo Direto — canal deslocado ou
unidade errada — é **invisível para a suíte automatizada**. O leitor sintético responde
igual pelos dois modos por construção, então nenhum teste com fake pode revelar divergência
entre dois hardwares reais. Este procedimento é a única defesa.

E as duas falhas são silenciosas: nada levanta exceção, a fita simplesmente acende na cor
errada — indistinguível de uma escolha artística.

### Preparação

1. Eletrodo montado e **parado**. Não mexa nele entre as duas coletas.
2. BITalino ligado e pareado.
3. Anote a porta de acesso (`COM7`, etc.) e o MAC do dispositivo.

### Execução

```bash
python scripts/comparar_modos_aquisicao.py --mac 20:17:09:18:60:29 --porta COM7 --canal 1
```

O script coleta primeiro pelo Modo OpenSignals (que precisa estar aberto, com o
compartilhamento "Lab Streaming Layer" ativo e a gravação iniciada), pede para você fechar o
OpenSignals, e então coleta pelo Modo Direto. Ele usa automaticamente **a mesma taxa** que o
OpenSignals declarar, para que a comparação não misture o efeito da taxa com o que se quer
medir.

### Como ler o resultado

Só o **canal ativo** precisa bater. Ele é o único que o Modo Direto converte para
microvolts, e no Modo OpenSignals só sai convertido se houver sensor declarado nele.

| Sintoma | Significado provável |
| --- | --- |
| Razão perto de 1 no canal ativo | ✅ esperado |
| Razão ~10x ou ~25x no canal ativo | Erro de **escala**: um dos lados está em ADU (centenas) onde deveria haver microvolts (dezenas) |
| Canal ativo diverge, mas um canal VIZINHO bate | Canal **deslocado** no desempacotamento |
| Todos os canais idênticos entre si | Eletrodo solto, ou dispositivo lendo o mesmo valor em tudo |
| Canal ativo saturado em ±39,49 µV | Fundo de escala: eletrodo desconectado ou entrada flutuando |

Os canais **não ativos divergem por projeto** — o Modo Direto os entrega em ADU cru, e o
OpenSignals entrega em ADU ou na unidade do sensor, conforme configurado nele. Não é falha.

EEG é sinal vivo: duas coletas em sequência nunca dão o mesmo número. O que se procura aqui
é ordem de grandeza, não igualdade.

---

## 1b. PENDENTE — alinhamento dos canais 2 a 6

**Por que ficou pendente:** a comparação do procedimento 1 rodou com o eletrodo no fundo de
escala. O canal 1 confirmou que está alinhado (variava, e um canal deslocado apareceria como
valor constante), mas **os canais 2 a 6 liam ADU 0 constante nos dois modos** — e trocar
zeros por zeros é indistinguível.

Ou seja: uma permutação entre A2..A6 no desempacotamento do frame passaria despercebida.

**O que fazer quando houver oportunidade:** repetir o procedimento 1 com **sinal diferente em
canais diferentes**. Não precisa ser EEG bonito — basta:

- plugar sensores (ou apenas fios) em mais de um canal, de modo que cada um leia coisa
  distinta; ou
- mexer nos cabos de um canal por vez durante a coleta, gerando artefato só nele.

Depois, comparar canal a canal. Cada canal deve bater consigo mesmo entre os dois modos, e
**não** com um vizinho. Se o canal 3 do Modo Direto parecer o canal 4 do OpenSignals, há
deslocamento no desempacotamento — ver `hardware/protocolo_bitalino.py:decodificar_frame`.

Os testes automatizados cobrem isso com um frame montado à mão
(`tests/hardware/test_protocolo_bitalino.py`), mas nenhum teste alcança a fiação real.

---

## 1c. PENDENTE — dropdown de taxa e seletor de canal com hardware

Duas entregas foram verificadas apenas *headless* (motor QML carregado sem janela,
propriedades conferidas) e **nunca operadas com o BITalino ligado**:

**Taxa de amostragem** (Modo Direto):

1. Escolha uma taxa, conecte e confirme que a duração da janela exibida corresponde ao ritmo
   real com que a fita muda de cor.
2. Troque o modo de predição para Frequência com 1 Hz ou 10 Hz selecionados — a taxa deve
   subir sozinha para 1000 Hz, visivelmente.
3. Escolha 100 Hz em Frequência e confirme que o aviso de Gamma/Nyquist aparece.
4. Com o dispositivo conectado, confirme que o dropdown de taxa está **travado** — a taxa é
   acordada no momento da conexão, e aceitar a troca depois seria mentira.

**Seletor de canal:**

1. Confirme que os rótulos mostram a resolução (`1 · 10 bits` ... `5 · 6 bits (evite para
   EEG)`).
2. Escolha o canal 5 ou 6 e confirme que o aviso de baixa resolução **permanece visível**
   depois de o dropdown fechar.
3. **O mais importante:** troque o canal DURANTE a aquisição e confirme que o sinal exibido
   muda de acordo. Aqui morava um bug — o canal novo não chegava ao leitor, que seguia
   convertendo o antigo. Escolher o canal 3 e ver dados do canal 1 é o sintoma.

---

## 2. Modo OpenSignals continua funcionando

**Quando:** sempre que o contrato da fonte de sinal (`hardware/contratos.py`) ou o
`BitalinoLSL` forem alterados.

É o caminho comprovado em bancada e a rede de segurança durante um evento ao vivo. Uma
regressão aqui custa muito mais do que uma no Modo Direto.

1. Abra o OpenSignals, ative "Lab Streaming Layer", inicie a gravação.
2. Abra a aplicação e conecte pelo Modo OpenSignals.
3. Confirme: conecta sem erro; o valor ao vivo se mexe; a fita de LED responde.
4. Troque o canal ativo durante a sessão — **não pode reconectar nem interromper nada**.
5. Feche o OpenSignals com a aquisição rodando: a aplicação deve **parar e avisar**, não
   travar em silêncio nem congelar a interface.

---

## 3. Modo Direto ponta a ponta

**Quando:** ao mexer no `BitalinoDireto` ou no `protocolo_bitalino`.

1. **Feche o OpenSignals.** O dispositivo aceita um cliente por vez.
2. Conecte pelo Modo Direto, na porta de acesso correta.
3. Confirme: conecta sem erro; o valor ao vivo se mexe; a fita responde.
4. Troque o canal ativo durante a sessão — não pode reconectar.
5. Desligue o BITalino com a aquisição rodando: deve **parar e avisar** em poucos segundos.
6. Religue e reconecte pela interface, **sem reiniciar a aplicação**.

### Armadilhas conhecidas

- O pareamento Bluetooth cria **duas** portas COM, e só uma funciona. Se a porta abrir mas
  nenhum dado chegar, tente a outra.
- Com o OpenSignals aberto, a porta não abre. A mensagem de erro diz isso.
- Passar o MAC no lugar da porta é o engano mais comum; a aplicação recusa com mensagem
  explícita.

---

## 4. Arduino e fita de LED

**Quando:** ao mexer no `ArduinoSerial` ou no formato do comando serial.

1. Conecte o Arduino e selecione a porta na interface.
2. Rode uma aquisição e confirme que a fita muda de cor conforme o matiz previsto.
3. Percorra os quatro modos de luminosidade (Um a um, Todos, Gradiente, A partir do Centro)
   e confirme que a animação corresponde ao nome.
4. Arranque o cabo USB com a aquisição rodando: deve **avisar**, não travar.

O firmware não devolve ACK — o envio é "fire and forget". Um comando malformado não dá erro
do lado Python; só a fita denuncia.
