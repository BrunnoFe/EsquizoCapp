# Mecânica de módulos QML (`qmldir` + import path) no PySide6

Pesquisa para o ticket wayfinder #10 (`BrunnoFe/EsquizoCapp`). Fontes primárias:
documentação oficial Qt 6 (`doc.qt.io`) e a documentação oficial do PySide6
(`pyside/pyside-setup`). Cada afirmação cita a fonte.

Contexto do repo hoje: PySide6 + `QQmlApplicationEngine`; ~19 arquivos `.qml` flat em
`src/esquizocap/interface_qt/`; raiz `EsquizoCapView.qml` carregada em `main.py:52` via
`engine.load(QUrl.fromLocalFile(...))`. Alvo: pastas temáticas viram módulos
`import EsquizoCap.<Nome>`.

---

## 1. Formato do arquivo `qmldir`

Fonte: <https://doc.qt.io/qt-6/qtqml-modules-qmldir.html>

**Identificador de módulo (module identifier).** Primeira linha do arquivo; exatamente uma
por `qmldir`:

```text
module <ModuleIdentifier>
```

> "module `<ModuleIdentifier>` — Declares the module identifier of the module. The
> `<ModuleIdentifier>` is the (dotted URI notation) identifier for the module, which must
> match the module's install path. [...] The `module` identifier directive must be the
> first line of the file. Exactly one module identifier directive may exist in the qmldir
> file." (doc.qt.io/qt-6/qtqml-modules-qmldir.html)

Para o alvo, a notação pontilhada `EsquizoCap.Componentes` mapeia para o caminho de
instalação `EsquizoCap/Componentes/` (ver §3).

**Linha de componente (object type declaration).** Uma por tipo exportado:

```text
[singleton] <TypeName> <InitialVersion> <File>
```

> "[singleton] `<TypeName>` `<InitialVersion>` `<File>` — Declares a QML object type to be
> made available by the module." (doc.qt.io/qt-6/qtqml-modules-qmldir.html)

Exemplo verbatim da doc: `CustomButton 2.0 CustomButton20.qml`. O `<TypeName>` é o nome com
que o QML importa o tipo (não precisa bater com o nome do arquivo).

**Singletons.** Duas exigências combinadas:

1. O `.qml` do singleton começa com `pragma Singleton`.
2. A linha no `qmldir` recebe o prefixo `singleton`.

> Exemplo da doc: `singleton Style 1.0 Style.qml` — e o arquivo `Style.qml` deve conter
> `pragma Singleton`. (doc.qt.io/qt-6/qtqml-modules-qmldir.html)

**Linha de versão / import interno.** Um módulo pode declarar dependências de outros
módulos com `import <ModuleIdentifier> [<Version>]`:

> "Omitting the version imports the latest version available. Specifying `auto` as the
> version imports the same version as the version of the module importing it."
> (doc.qt.io/qt-6/qtqml-modules-qmldir.html)

**Exemplo mínimo de `qmldir` para o EsquizoCap:**

```text
module EsquizoCap.Componentes
Chip 1.0 Chip.qml
Toggle 1.0 Toggle.qml
Dropdown 1.0 Dropdown.qml
singleton Tema 1.0 Tema.qml
```

---

## 2. `engine.addImportPath(...)` vs registro por `QML_IMPORT_NAME` / `@QmlElement`

São dois mecanismos para dois problemas diferentes:

- **`@QmlElement` + `QML_IMPORT_NAME` / `QML_IMPORT_MAJOR_VERSION`** registra **classes
  Python** (tipos definidos em `.py`, decoradas) como tipos QML. Fonte:
  <https://doc.qt.io/qtforpython-6/PySide6/QtQml/QQmlEngine.html> e
  <https://doc.qt.io/qtforpython-6/overviews/qtqml-python-integration.html> — o decorator
  `@QmlElement` usa as variáveis de módulo `QML_IMPORT_NAME` e
  `QML_IMPORT_MAJOR_VERSION` para expor a classe Python sob um nome de módulo QML.

- **`qmldir` + `addImportPath`** expõe **arquivos `.qml` em disco** como um módulo. Fonte:
  <https://doc.qt.io/qt-6/qqmlengine.html#addImportPath> — "Adds `path` as a directory
  where the engine searches for installed modules in a URL-based directory structure."

**Recomendação para este repo: `qmldir` + `addImportPath`.**
O EsquizoCap carrega a view raiz via `engine.load(QUrl.fromLocalFile(...))` e os ~19
componentes são **arquivos `.qml` em disco**, não tipos Python. `@QmlElement` só se aplica
a tipos declarados em Python; forçá-lo aqui exigiria reescrever componentes de UI como
classes Python, o que é o oposto do objetivo. A rota `qmldir` mantém os componentes como
QML e apenas agrupa pastas em módulos importáveis.

---

## 3. Empacotar os `.qml` em disco e apontar o import path pelo Python

**Mapeamento diretório ↔ identificador de módulo.** O engine resolve um import
`EsquizoCap.Componentes` procurando o subdiretório `EsquizoCap/Componentes/` (com um
`qmldir` dentro) sob **cada** caminho registrado por `addImportPath`. Fonte:
<https://doc.qt.io/qt-6/qqmlengine.html#importPathList> — "if `/opt/MyApp/lib/imports` is
in the path, then QML that imports `com.mycompany.Feature` will cause the engine to look
in `/opt/MyApp/lib/imports/com/mycompany/Feature/` for the module."

Ou seja, a notação pontilhada vira barras no filesystem. Layout proposto:

```
src/esquizocap/interface_qt/
  EsquizoCapView.qml            <- raiz, continua carregada por QUrl.fromLocalFile
  qml/                          <- ISTO é o import path registrado
    EsquizoCap/
      Componentes/
        qmldir                  <- module EsquizoCap.Componentes
        Chip.qml
        Toggle.qml
        Dropdown.qml
        ...
      Grafico/
        qmldir                  <- module EsquizoCap.Grafico
        EegTrace.qml
        LedStrip.qml
```

**Import path a partir do Python.** `addImportPath` recebe o diretório *raiz* que contém a
árvore `EsquizoCap/...` — **não** o diretório do módulo. E deve ser chamado **antes** do
`engine.load` (§4). Patch conceitual para `main.py`:

```python
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine

BASE_QML = Path(__file__).resolve().parent / "src" / "esquizocap" / "interface_qt"

engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("controller", controller)

# 1) registrar o import path ANTES de qualquer engine.load
engine.addImportPath(str(BASE_QML / "qml"))

# 2) só então carregar a view raiz
raiz = BASE_QML / "EsquizoCapView.qml"
engine.load(QUrl.fromLocalFile(str(raiz)))
```

Fonte da assinatura/semântica: <https://doc.qt.io/qt-6/qqmlengine.html#addImportPath>
("Adds `path` as a directory where the engine searches for installed modules") e o exemplo
oficial do PySide6 que chama `addImportPath` antes de `loadFromModule`
(`pyside/pyside-setup`, tutorial `basictutorial/qml.rst`).

**Import statement no QML.** Dentro de `EsquizoCapView.qml` (ou de qualquer componente):

```qml
import EsquizoCap.Componentes 1.0
import EsquizoCap.Grafico 1.0

Chip { }
EegTrace { }
```

O `1.0` bate com o `<InitialVersion>` declarado nas linhas do `qmldir`.

---

## 4. Convivência com carregamento HEADLESS (`QT_QPA_PLATFORM=offscreen`)

**`addImportPath` DEVE vir antes do `engine.load`.** A resolução do import acontece no
momento em que o engine analisa o `.qml` carregado; caminhos adicionados depois não são
consultados retroativamente para aquele carregamento. A doc oficial reforça a regra de
"configurar o engine antes de carregar fontes": "All required image providers should be
added to the engine before any QML source files are loaded"
(<https://doc.qt.io/qt-6/qqmlengine.html>) — a mesma ordem se aplica a import paths, que
são consultados durante o parse do `import`.

**Funciona offscreen.** `QT_QPA_PLATFORM=offscreen` troca apenas o *plugin de plataforma*
(a camada de janela/GPU). A resolução de módulos QML — leitura de `qmldir`, casamento de
import path, criação de tipos — é feita pelo `QQmlEngine`/`QQml`, independente do plugin de
plataforma. Não há dependência de janela para carregar um módulo. Isso é exatamente o que o
projeto já faz para validar a GUI sem hardware (ver `CLAUDE.md` → "verificação da GUI sem
janela"): carregar o `QQmlApplicationEngine` de verdade offscreen e ligar `engine.warnings`
— um `qmldir` mal formado ou um import não resolvido aparece ali como warning, o que dá um
teste headless para o novo layout de módulos.

Referência da plataforma offscreen: <https://doc.qt.io/qt-6/qpa.html> (o plugin QPA
substitui apenas a integração de plataforma/janela).

---

## 5. Versionamento de módulo QML: é obrigatório?

- **No `qmldir` (object type declaration): a versão é obrigatória pela especificação.** A
  gramática documentada é `[singleton] <TypeName> <InitialVersion> <File>`, e todos os
  exemplos oficiais trazem a versão (`CustomButton 2.0 CustomButton20.qml`,
  `singleton Style 1.0 Style.qml`). A doc não descreve omitir `<InitialVersion>` nessa
  linha. Fonte: <https://doc.qt.io/qt-6/qtqml-modules-qmldir.html>.

- **No `import` (dentro do QML ou no `import` interno do `qmldir`): a versão é opcional.**
  "Omitting the version imports the latest version available." Fonte:
  <https://doc.qt.io/qt-6/qtqml-modules-qmldir.html>. Ou seja, `import EsquizoCap.Componentes`
  (sem número) também funciona e pega a última versão disponível.

- **Convenção mínima recomendada para Qt6/PySide6:** declarar `1.0` em cada linha de tipo
  do `qmldir` (satisfaz a gramática) e importar **com** a versão (`import ... 1.0`) para o
  código ficar explícito e à prova de futuras versões. É a mesma convenção dos exemplos
  oficiais do PySide6 (`Main 254.0 Main.qml` no tutorial `basictutorial/qml.rst`; o número
  alto ali é só didático).

---

## Receita recomendada para o EsquizoCap

1. **Layout.** Criar `src/esquizocap/interface_qt/qml/` como raiz de import path. Sob ela,
   uma árvore por módulo: `qml/EsquizoCap/<Nome>/` com um `qmldir` e os `.qml` daquela
   pasta temática (ex.: `EsquizoCap/Componentes`, `EsquizoCap/Grafico`). A raiz
   `EsquizoCapView.qml` continua carregada por `QUrl.fromLocalFile` — ela não precisa virar
   módulo.

2. **`qmldir` por pasta.** Primeira linha `module EsquizoCap.<Nome>`; uma linha
   `TypeName 1.0 Arquivo.qml` por componente; singletons (ex.: um `Tema.qml`) com prefixo
   `singleton` + `pragma Singleton` no arquivo.

3. **Python (`main.py`).** Antes do `engine.load(...)`, chamar
   `engine.addImportPath(str(BASE_QML / "qml"))` apontando para a *raiz* da árvore (o
   diretório que contém `EsquizoCap/`), não para a pasta do módulo.

4. **QML.** Trocar imports relativos por `import EsquizoCap.<Nome> 1.0` e usar os tipos
   pelo `TypeName`.

5. **Versão.** `1.0` em toda linha do `qmldir` (obrigatório na gramática) e nos imports
   (opcional, mas recomendado por clareza).

6. **Teste headless.** Cobrir o novo layout com o carregamento offscreen já usado no
   projeto: `QT_QPA_PLATFORM=offscreen`, subir o `QQmlApplicationEngine`, carregar a raiz e
   afirmar ausência de `engine.warnings` — pega `qmldir` mal formado, `module` com nome
   errado ou import não resolvido, tudo sem janela nem hardware.

**Armadilha silenciosa a vigiar:** um `module` com nome que não bate com o caminho de
disco, ou um import path apontado para dentro do módulo em vez da raiz, **não** levanta
exceção — o componente só some / cai no erro de tipo desconhecido. O teste headless com
`engine.warnings` é o que transforma esse silêncio em falha visível.
