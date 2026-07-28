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

---

## 5. Caixa de mensagem de erro

**Quando:** ao mexer em `Dialogos/CaixaDeMensagem.qml`, `Dialogos/Toast.qml` ou no
`catalogo_erros`.

**Por que exige bancada:** a suíte carrega o QML sem janela e confirma que nenhum binding
está errado, mas nada offscreen prova que o texto **cabe** — e caber era exatamente o
defeito do banner anterior, que cortava a metade acionável de toda mensagem. Legibilidade e
recorte de cantos só a tela mostra.

1. Com a aquisição rodando, feche o OpenSignals (ou desligue o BITalino). A caixa deve abrir
   **no centro**, e a mensagem inteira precisa estar legível: tanto o que aconteceu quanto o
   parágrafo do que fazer. Nada cortado, nada saindo pela borda.
2. Confirme os cantos arredondados: a caixa vive dentro do `shell`, então o backdrop escuro
   tem que respeitar o arredondamento da janela — em modo normal e em tela cheia.
3. Expanda "Detalhes técnicos" e clique em **Copiar detalhes**. Cole num editor: deve vir
   título, mensagem e o tipo da exceção.
4. Abra a janela de Configurações e, com ela aberta, provoque um erro. A caixa tem que
   aparecer **sobre** a janela de configurações, nunca atrás. Pressione ESC: fecha a caixa e
   a janela de configurações **continua aberta**.
5. Clique em **Diagnóstico → abrir pasta de logs** com um caminho inválido. Deve virar um
   toast no topo, discreto, que **some sozinho em ~7 segundos** — e não uma caixa modal.
6. Provoque um erro grave e, sem fechá-lo, dispare um toast. O toast não pode apagar a
   caixa; os dois convivem.
7. Redimensione a janela até o mínimo (940×620) com a caixa aberta: ela deve encolher e o
   corpo ganhar rolagem, sem que os botões do rodapé sumam.

### Caixa não dispensável

A `FALHA_INESPERADA` é a única que não fecha por ESC, X ou clique fora — de propósito. Para
exercitá-la é preciso provocar uma exceção não prevista (ex.: um `raise` temporário num
slot). Confirme que **o botão OK fecha**. Se algum dia uma caixa não dispensável aparecer
sem botão, é uma tela travada: a suíte tem uma invariante contra isso
(`tests/aplicacao/test_catalogo_erros.py`), mas confirme na mão se mexer no catálogo.

---

## 6. PENDENTE — troca real↔simulado sem reiniciar

**Quando:** ao mexer em `EsquizoController._reconstruir_hardware` ou na fábrica de hardware.

**Por que exige bancada:** a suíte cobre a troca com dublês e confirma que os objetos mudam
de identidade, que os leitores antigos são encerrados e que o canal ativo é reaplicado. O
que ela **não** alcança é o recurso do sistema operacional: um leitor órfão segurando a
porta serial só se manifesta na próxima conexão real, que falha sem motivo aparente.

Rode com o BITalino ligado e pareado, e o Arduino plugado. **Sem** `ESQUIZOCAP_FAKE` no
terminal — com ela definida os controles ficam travados de propósito.

1. Abra **Configurações → Simulação**. Ligue Arduino e BITalino.
2. Confirme o selo âmbar na barra de topo e o anel âmbar em ARD e BIT.
3. Rode uma aquisição simulada inteira, com gravação, até salvar o `.xlsx`.
4. Desligue as duas simulações **na mesma sessão**, sem fechar o app.
5. Conecte o BITalino e o Arduino de verdade e rode uma aquisição real.
   - **É aqui que o teste vale.** Se o passo 4 deixou um objeto órfão, esta conexão falha.
6. Confirme que o seletor de modo de aquisição voltou a ficar **habilitado** (sob simulação
   ele fica travado, porque o sintético responde igual pelos dois modos).
7. Confirme que o canal ativo escolhido antes da troca continua sendo o canal lido — troque
   para o canal 4 antes do passo 4 e verifique que o sinal real vem do A4, não do A1.
   Falha silenciosa clássica: números plausíveis, cor errada, nenhum erro.
8. Com o BITalino conectado, tente ligar a simulação: deve **recusar** e explicar o motivo.
9. Feche e reabra o app: as escolhas de simulação e os sliders de aparência devem voltar
   como estavam (gravados em `settings/preferencias.json`).

## 7. Rail: alternância dos painéis, ESC e desenho dos ícones

**Quando:** ao mexer no rail de `EsquizoCapView.qml`, no `IconGlyph` ou nos atalhos.

**Por que exige janela:** a suíte confirma que cada `iconName` desenha uma forma
(`tests/interface/test_icones.py`) e que `alternarTelaCheia()` vai e volta, mas nada disso
diz se o ícone ficou **legível** em 18 px nem se o clique chega ao botão certo. Não há
hardware envolvido — basta abrir o app, com `ESQUIZOCAP_FAKE=tudo` se preferir.

1. Clique **Setup / hardware** duas vezes: abre e fecha no mesmo ícone. Idem **Aparência**.
2. Com o Setup aberto, clique **Aparência**: o Setup fecha e a Aparência abre. Os dois
   **nunca** ficam visíveis ao mesmo tempo — antes disso era possível, porque o rail continua
   clicável atrás do backdrop.
3. Com um painel aberto e o app em tela cheia, aperte **ESC**: fecha o painel e **continua**
   em tela cheia. Aperte ESC de novo: aí sim sai da tela cheia. Um ESC nunca desfaz os dois.
4. Fora da tela cheia, ESC sem painel aberto não deve fazer nada.
5. Olhe os quatro ícones do rail lado a lado — plugue, gota, expandir, engrenagem. Todos são
   vetores de traço 2 px agora; se algum parecer mais grosso, mais fino ou fora de centro que
   os vizinhos, é o desenho no `IconGlyph`, não a fonte do sistema.
6. Confira o mesmo em monitor com escala 125%/150%, onde traço de 2 px costuma borrar.

## 8. Tela de carregamento no boot

**Quando:** ao mexer em `Layout/TelaDeCarregamento.qml`, em `Base/LogoSpinner.qml` ou no
bloco `// PROVISÓRIO:` de `EsquizoCapView.qml`.

**Por que exige janela:** a carga offscreen prova que o QML instancia sem aviso, mas não diz
se a onda **percorre** o anel nem se a saída desacelera em vez de cortar. Animação só se
julga vendo. Não há hardware envolvido — `ESQUIZOCAP_FAKE=tudo` serve.

1. `python main.py`: o app deve abrir **já na tela de carregamento**, opaca, sem a interface
   aparecendo atrás dela.
2. Olhe o anel: uma onda de tamanho percorre os 12 LEDs em **sentido horário**, e a cor gira
   junto. O movimento não pode parecer um loop curto se repetindo.
3. A linha de status ("carregando") pulsa de opacidade, devagar.
4. Depois de ~2,2 s a tela sai: a onda **desacelera** até quase parar, com o pico no topo, e
   só então o overlay some. Se ela sumir com a onda ainda em velocidade normal, o corte está
   acontecendo no meio — regressão.
5. Já na interface normal, abra e feche **Configurações** (e o painel de Setup): a tela de
   carregamento **não pode reaparecer**. Ela é de boot, uma vez só.
6. Confira que o wordmark "esquizocap" da tela usa a mesma tipografia da barra de título, com
   o "cap" em teal.

## 9. Indicadores de carregamento inline

**Quando:** ao mexer em `Base/IndicadorCarregando.qml`, em `Base/LogoSpinner.qml`, ou em
qualquer um dos pontos de espera — `Controles/ConnectButton.qml`, `Dialogos/Toast.qml`,
`Configuracoes/AbaDiagnostico.qml`, o painel de setup em `App/EsquizoCapView.qml`.

**Por que exige janela:** os testes provam que as `Property` existem e que o QML instancia,
mas não que a onda **percorre** o anel a 18 px, que ela é seca (e não a respiração larga do
splash), nem que os elementos ao redor ficam parados quando o indicador entra e sai. Nada
disso é observável offscreen.

**Hardware:** o roteiro inteiro funciona com `ESQUIZOCAP_FAKE=tudo`, exceto o passo 5, que
precisa de um BITalino real para a conexão durar tempo suficiente de ser vista.

1. **Varredura no boot.** `python main.py` e abra **Setup / hardware** o mais rápido que
   conseguir. Na seção **Arduino**, entre o dropdown de porta e o botão Conectar, deve
   aparecer o anel pequeno com **"procurando portas…"**, e o dropdown de porta ainda vazio.
   Some sozinho quando a lista popula. Se você nunca vê (a máquina varreu rápido demais),
   force pelo passo 2.
2. **Varredura forçada.** **Configurações → Diagnóstico → "Reexaminar portas"**. Enquanto
   dura: o anel com **"montando diagnóstico…"** aparece na linha dos botões, e **"Copiar
   diagnóstico"** fica esmaecido e não clicável. Confira que o texto do diagnóstico, depois
   que o indicador some, mostra uma **"Porta de acesso"** preenchida (ou "(não encontrada)"
   se o aparelho não estiver pareado) — nunca em branco.
3. **Personalidade da onda.** Compare o anel de 18 px com o da tela de carregamento: aqui um
   LED deve **estourar e apagar rápido**, um de cada vez, como o modo "Um a um" do firmware.
   Se parecer a mesma respiração larga do splash, `cycle`/`spread` não chegaram na LogoSpinner.
   Em 18 px o traço de EEG **não** pode ser desenhado no meio do anel.
4. **Nada pula de lugar.** Durante os passos 1 e 2, olhe o que está **em volta** do indicador.
   Nem o painel de setup nem a aba de diagnóstico podem deslocar quando o indicador entra ou
   sai. Se algo pular, é espaço sendo reservado a mais (ou a menos).
5. **Botão de conectar** *(precisa de BITalino real)*. No painel de setup, clique **Conectar**
   na seção BITalino. Enquanto a tentativa dura: o texto "Conectar" some, o anel aparece
   **centrado no botão**, o botão **não muda de largura**, e clicar nele de novo não faz nada.
   Ao terminar, volta a "Desconectar" (sucesso) ou "Conectar" + caixa de erro (falha).
6. **Toast em andamento** *(precisa de BITalino real)*. Com o setup **fechado** e o BITalino
   desconectado, clique **Começar aquisição**. No topo deve subir o toast **"Conectando ao
   BITalino"**, com o anel girando **no lugar do glifo de severidade**, à esquerda do título.
   Ele **não pode sumir sozinho** enquanto a conexão durar — mesmo passados 7 s. Deve sair no
   instante em que a conexão terminar.
7. **Um indicador por região.** No passo 6, com o setup **aberto** durante a conexão: o
   "procurando portas…" do painel **não** pode estar girando junto com o do botão Conectar.
   Dois anéis ao mesmo tempo na mesma região é a regressão que este passo procura.
8. **Não fica girando escondido.** Depois que tudo assentou, deixe o app parado e observe o
   uso de CPU/GPU. Um indicador invisível que continua animando é o defeito — `running: false`
   tem que **parar** a animação, não só esconder o item.
