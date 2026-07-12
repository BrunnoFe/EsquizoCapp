# 🧠 EsquizoCap

**Sinal cerebral vira luz.** EsquizoCap lê EEG de um BITalino, transforma o dado em uma
cor via um modelo de machine learning e acende uma fita de LED em tempo real —
para uma instalação de arte que expõe atividade eletrofisiológica como experiência visual.

<!--
  IMAGEM 1 (topo do README, logo abaixo do título): uma foto ou GIF da fita de LED
  acesa durante uma sessão real, ou a instalação montada (pessoa com o BITalino + fita
  de LED reagindo). É a imagem que "vende" o projeto em 3 segundos.
-->

> ⚠️ Projeto Windows-only, de uso artístico/experimental — não é um dispositivo médico.

---

## ✨ O que ele faz

```
  🧑  BITalino (EEG)
   │  Bluetooth
   ▼
  📡 OpenSignals  ──publica──▶  Lab Streaming Layer (LSL)
   │
   ▼
  🐍 EsquizoCap (Python)
   │   lê o sinal (µV) ──▶ prevê uma cor (HSV) ──▶ envia via serial
   ▼
  💡 Arduino + fita de LED
```

1. O **BITalino** capta o sinal eletrofisiológico e o **OpenSignals** publica esse sinal
   como um stream **LSL** (a aplicação nunca fala com o BITalino diretamente).
2. O EsquizoCap lê esse stream e obtém uma métrica bruta, de um de dois jeitos —
   **Amplitude** ou **Frequência** (ver abaixo).
3. Um modelo de **árvore de decisão** (scikit-learn) prevê um **matiz (HUE)** a partir
   dessa métrica. Saturação e brilho são ajustados ao vivo pelo usuário, na interface.
4. A cor HSV resultante é convertida e enviada por **porta serial** a um **Arduino**, que
   comanda a fita de LED.

<!--
  IMAGEM 2: screenshot da janela principal do EsquizoCap rodando, mostrando os
  medidores de Hue/Saturação/Brilho e os painéis de configuração (Arduino, BITalino,
  modo de análise).
-->

### Os dois modos de análise

| Modo | Como funciona | Quando usar |
| --- | --- | --- |
| **Amplitude** | Cada amostra bruta (µV) já lida do BITalino vira uma predição de cor. Uma leitura, uma cor. | Resposta mais imediata; a cor reage a cada instante do sinal. |
| **Frequência** | Um bloco de amostras é acumulado, filtrado (Butterworth passa-alta + passa-baixa) e analisado por densidade espectral (Welch). A frequência dominante do bloco vira a predição, e é também classificada numa banda de EEG humana (Delta, Theta, Alpha, Beta, Gamma). | Quando o que importa é o *estado* geral do sinal (relaxamento, atenção, etc.), não o instante. |

Em ambos os modos, **só o matiz vem do modelo**. Saturação e brilho são escolhas do
usuário, feitas ao vivo por medidores na interface — o modelo nunca decide a intensidade
ou a pureza da cor, só qual cor.

---

## 🏗️ Como o código está organizado

O projeto segue uma separação em camadas, cada uma com uma responsabilidade e sem
depender da que vem depois dela na lista:

```
src/esquizocap/
├── dominio/          🧮  As regras de negócio. Sem GUI, sem hardware, sem threading.
├── hardware/         🔌  As bordas físicas: BITalino e Arduino, cada um com uma
│                         implementação REAL e uma FAKE (para rodar sem hardware).
├── aplicacao/        🧵  Orquestração: a thread que roda o domínio e publica
│                         resultados para a interface, sem travar a tela.
├── infraestrutura/   ⚙️  Logging, configuração, persistência (Excel), assets.
└── interface/        🖼️  Tudo que é Tkinter/ttkbootstrap.
```

- **`dominio/`** é o coração: `CicloAquisicao` executa ler → pré-processar → prever →
  distribuir, e devolve um `ResultadoCiclo`. Não sabe que existe interface gráfica nem
  que existe hardware de verdade — por isso é a camada mais fácil de testar.
- **`hardware/`** define contratos (`ControladorLedArduino`, `LeitorBitalino`) como
  classes abstratas. Cada um tem uma implementação real (`arduino_real.py`,
  `bitalino_real.py`) e uma **fake** (`arduino_fake.py`, `bitalino_fake.py`) que simula
  um EEG sintético plausível — é o que permite rodar e testar o projeto inteiro sem
  nenhum hardware plugado.
- **`aplicacao/`** existe porque a aquisição de um sinal biológico não pode depender do
  loop de eventos de uma interface gráfica: ela roda numa thread própria, publicando
  eventos (`EventoResultado`, `EventoErro`, `EventoParado`) numa fila que a GUI apenas
  drena e pinta.

Para o mapa completo de módulos e as decisões de arquitetura por trás disso, veja
[`CLAUDE.md`](CLAUDE.md) e [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 🚀 Como rodar

> Assume Windows, Python 3.12+, e que os comandos rodam a partir da **raiz do projeto**
> (o app usa caminhos relativos para `logs\`, `models\` etc.).

```powershell
# 1. Ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar o projeto em modo editável — OBRIGATÓRIO
#    (o código está em layout src/; sem isto, `import esquizocap` não resolve)
pip install -e .

# 4. Rodar
python main.py
```

### Rodando sem hardware

Para testar a interface, os modos de análise ou o modelo sem BITalino nem Arduino
plugados, troque a borda real pela simulada:

```powershell
$env:ESQUIZOCAP_FAKE="1"           # tudo simulado
$env:ESQUIZOCAP_FAKE="arduino"     # só o Arduino simulado
$env:ESQUIZOCAP_FAKE="bitalino"    # só o BITalino simulado
python main.py
```

O BITalino simulado gera uma senoide de 10 Hz (banda Alpha) com ruído gaussiano — sinal
plausível o bastante para exercitar a análise espectral de ponta a ponta.

Também dá para rodar só o núcleo, sem abrir janela nenhuma:

```powershell
python scripts/rodar_ciclo_sem_gui.py --modo Frequência --ciclos 4
```

### ⚠️ Ordem de operação obrigatória

1. Abra o **OpenSignals** manualmente e ative o compartilhamento **"Lab Streaming
   Layer"** — a aplicação não abre o OpenSignals sozinha, e não funciona sem esse passo.
2. Rode `python main.py`.
3. Na interface: escolha o modelo → configure e conecte o Arduino → configure o
   BITalino → "Começar aquisição".

<!--
  IMAGEM 3: screenshot ou GIF curto do OpenSignals com o compartilhamento "Lab
  Streaming Layer" ativado, para servir de referência visual desse passo manual.
-->

---

## 🎨 Do sinal à cor: um exemplo

```
BITalino lê 32.4 µV no canal escolhido
        │
        ▼           (modo Amplitude)
modelo.predict([[32.4]])  →  HUE = 187
        │
        ▼           + Saturação=255, Brilho=120 (medidores da interface)
hsv_para_rgb_hex(187, 255, 120)  →  "#0078F0", RGB=(0, 120, 240)
        │
        ▼
Arduino recebe: "(2,187,255,120)\n"
        │
        ▼
💡 fita de LED acende em azul
```

<!--
  IMAGEM 4: uma tabela ou colagem visual "espectro de EEG → cor", mostrando lado a
  lado as faixas Delta/Theta/Alpha/Beta/Gamma e a cor tipicamente associada a cada
  uma no modelo atual — boa para quem vem do lado artístico do projeto, não técnico.
-->

---

## 🧪 Qualidade

- **Testes automatizados** (`pytest`) cobrem `dominio/`, `hardware/` e `aplicacao/` —
  incluindo testes de regressão para bugs já corrigidos (escala de frequência, canal
  ignorado, atraso de leitura do LSL) e testes de concorrência da thread de aquisição.
- **Tipos estritos** (`mypy --strict`) nas mesmas três camadas.
- **Lint e formatação** via `ruff`.

```powershell
pytest              # testes
mypy                # checagem de tipos
ruff check .        # lint
ruff format --check .  # formatação
```

O que **não** tem cobertura automatizada, de propósito — está documentado em
[`TESTES_MANUAIS.md`](TESTES_MANUAIS.md):

- A interface gráfica (Tkinter é caro e frágil de testar automaticamente).
- Os caminhos das implementações reais que exigem o hardware físico ligado.

---

## 📚 Documentação completa

Este README é a porta de entrada. Para se aprofundar:

| Documento | O que traz |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Mapa de módulos, comandos, pontos críticos — a referência mais densa do repositório. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Fluxo de dados fim a fim, protocolos (serial, LSL), o desenho de concorrência da thread de aquisição, e os pontos frágeis conhecidos. |
| [`DECISOES_PENDENTES.md`](DECISOES_PENDENTES.md) | Comportamentos do código original preservados de propósito, e as decisões em aberto sobre eles. |
| [`PLANO_ACAO.md`](PLANO_ACAO.md) | O plano de trabalho vivo: o que já foi feito e o que falta, por ordem de risco. |
| [`TESTES_MANUAIS.md`](TESTES_MANUAIS.md) | O checklist do que só dá para verificar com o hardware físico na mão. |
| [`src/esquizocap/hardware/_engine_legado/README.md`](src/esquizocap/hardware/_engine_legado/README.md) | A integração com uma engine visual em Godot, hoje desligada e arquivada. |

---

## 🔧 Stack técnica

Python · Tkinter/ttkbootstrap · scikit-learn · pylsl (Lab Streaming Layer) · pyserial ·
scipy · pandas/openpyxl · pytest · mypy · ruff

---

## ⚠️ Limitações conhecidas

- **Não é um dispositivo médico**: as classificações de banda de EEG e a predição de
  cor são para fins artísticos/expressivos, não diagnósticos.
- **Windows-only**: o código usa `ctypes.windll` para integração com a barra de tarefas.
- **O modelo de ML é simples**: uma árvore de decisão sobre um único escalar (amplitude
  *ou* frequência dominante). O treino não está neste repositório — só o artefato
  `.pickle`.
- **A engine visual Godot está desligada** (ver o README arquivado acima).
