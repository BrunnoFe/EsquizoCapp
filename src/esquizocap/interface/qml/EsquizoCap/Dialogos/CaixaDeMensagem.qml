import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import EsquizoCap.Base 1.0

// A caixa de mensagem central do app.
//
// NÃO sabe o que é um erro. Recebe severidade, título, texto, detalhe técnico e uma lista
// de ações, e desenha — erro é só o primeiro cliente. Uma confirmação futura ("descartar a
// gravação?") usa este mesmo componente com dois botões.
//
// Segue a regra dos overlays daqui: é um Item ancorado ao `shell`, não um Popup nem um
// Window, para respeitar o OpacityMask de cantos arredondados da janela sem moldura (ver
// o cabeçalho de Configuracoes/JanelaConfiguracoes.qml).
//
// Substitui o banner vermelho de 40px de altura fixa que existia antes. O defeito central
// dele era não ter `wrapMode`: as mensagens sempre trouxeram "o que houve" e "o que fazer"
// separados por linha em branco, e a segunda metade — a única acionável — nunca cabia.
Item {
    id: caixaDeMensagem

    // ---- entrada ----
    property bool open: false
    property string severidade: "erro"   // critico | erro | aviso | info
    property string titulo: ""
    property string mensagem: ""
    property string detalhe: ""
    // Cada ação é { papel: "aceitar"|"confirmar"|"recusar"|"cancelar", rotulo: "OK" }.
    property var acoes: []
    // Quando falso, ESC, o X e o clique fora não fecham: alguém precisa escolher um botão.
    property bool dispensavel: true

    // ---- saída ----
    signal respondida(string papel)
    signal dispensada()

    readonly property color destaque: Theme.corDaSeveridade(severidade)
    // A cor da title bar já MISTURADA com o fundo, e portanto opaca.
    //
    // Não é preciosismo: a barra é desenhada por dois retângulos (um arredondado e outro
    // que quadra a base, que encosta no corpo). Com uma cor translúcida, a área onde os
    // dois se sobrepõem recebe o alfa duas vezes e aparece como uma faixa mais escura no
    // meio da barra. `Qt.tint` resolve a mistura uma vez, e os dois retângulos passam a
    // pintar exatamente a mesma cor sólida.
    readonly property color corDaBarra: Qt.tint(Theme.panelBg,
                                                Qt.rgba(destaque.r, destaque.g, destaque.b, 0.14))
    readonly property string tituloEfetivo: titulo !== "" ? titulo : Theme.tituloPadraoDaSeveridade(severidade)

    anchors.fill: parent
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.duracaoFade; easing.type: Easing.OutCubic } }

    // Quem fecha por gesto (ESC, X, clique fora) passa por aqui, e não por `open = false`
    // direto: se existe uma ação de cancelar, o gesto PRECISA acioná-la, senão quem estiver
    // esperando uma resposta nunca a recebe. Hoje nenhuma caixa tem cancelar; no dia da
    // primeira confirmação isto já estará correto.
    function dispensar() {
        if (!dispensavel) return
        for (var i = 0; i < acoes.length; i++) {
            if (acoes[i].papel === "cancelar") { respondida(acoes[i].papel); return }
        }
        dispensada()
    }

    function acionarPadrao() {
        for (var i = 0; i < acoes.length; i++) {
            if (acoes[i].papel === "confirmar" || acoes[i].papel === "aceitar") {
                respondida(acoes[i].papel); return
            }
        }
        dispensar()
    }

    // Backdrop. Existe mesmo quando não é dispensável — aí ele só não fecha nada, mas
    // continua bloqueando cliques no app atrás, que é o ponto de uma caixa bloqueante.
    Rectangle {
        anchors.fill: parent
        color: Theme.backdrop
        MouseArea { anchors.fill: parent; onClicked: caixaDeMensagem.dispensar() }
    }

    Rectangle {
        id: moldura
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 560)
        // Altura pelo conteúdo, com teto: é o oposto do banner antigo, que tinha 40px fixos
        // e cortava tudo que não coubesse.
        implicitHeight: Math.min(parent.height - 80, colunaConteudo.implicitHeight)
        height: implicitHeight
        radius: 14
        color: Theme.panelBg
        border.color: Qt.rgba(caixaDeMensagem.destaque.r, caixaDeMensagem.destaque.g,
                              caixaDeMensagem.destaque.b, 0.45)

        scale: caixaDeMensagem.open ? 1 : 0.96
        Behavior on scale { NumberAnimation { duration: Theme.duracaoEscala; easing.type: Easing.OutBack } }

        // Engole cliques que atravessariam para o backdrop e fechariam a caixa.
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: colunaConteudo
            anchors.fill: parent
            spacing: 0

            // ---------- title bar ----------
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 46
                radius: 14
                color: caixaDeMensagem.corDaBarra
                // O radius arredondaria também a base da barra, que encosta no corpo.
                // Mesma cor OPACA do retângulo de cima: ver `corDaBarra`.
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: parent.radius
                    color: caixaDeMensagem.corDaBarra
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 16; rightMargin: 10 }
                    spacing: 10

                    // Selo da severidade: é o "ícone relativo ao tipo de erro".
                    Rectangle {
                        implicitWidth: 20; implicitHeight: 20; radius: 10
                        color: caixaDeMensagem.destaque
                        Text {
                            anchors.centerIn: parent
                            text: Theme.glifoDaSeveridade(caixaDeMensagem.severidade)
                            color: "#0b0b0e"; font.pixelSize: 12; font.bold: true
                        }
                    }

                    Text {
                        text: Theme.tituloPadraoDaSeveridade(caixaDeMensagem.severidade)
                        color: caixaDeMensagem.destaque
                        font.pixelSize: 12; font.bold: true; font.letterSpacing: 1.6
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        id: fechar
                        visible: caixaDeMensagem.dispensavel
                        implicitWidth: 28; implicitHeight: 28
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        background: Rectangle {
                            radius: 8
                            color: fechar.hovered ? Qt.rgba(0.886, 0.325, 0.294, 0.22) : Qt.rgba(1, 1, 1, 0.06)
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        contentItem: Text {
                            text: "✕"
                            color: fechar.hovered ? "#ff8079" : Theme.muted
                            font.pixelSize: 14
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: caixaDeMensagem.dispensar()
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.stroke }

            // ---------- corpo ----------
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: corpo.implicitHeight + 36
                contentHeight: corpo.implicitHeight + 36
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: corpo
                    x: 20; y: 18
                    width: parent.width - 40
                    spacing: 14

                    Text {
                        Layout.fillWidth: true
                        text: caixaDeMensagem.tituloEfetivo
                        color: "#e8f1f2"
                        font.pixelSize: 16; font.bold: true; font.family: Theme.sansFam
                        wrapMode: Text.WordWrap
                    }

                    // O texto que o banner antigo cortava.
                    Text {
                        Layout.fillWidth: true
                        text: caixaDeMensagem.mensagem
                        color: Theme.muted
                        font.pixelSize: 13; font.family: Theme.sansFam
                        lineHeight: 1.35
                        wrapMode: Text.WordWrap
                    }

                    // ---------- detalhe técnico, recolhido ----------
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: caixaDeMensagem.detalhe !== ""
                        spacing: 8

                        Item {
                            Layout.fillWidth: true
                            implicitHeight: 20
                            RowLayout {
                                spacing: 6
                                Text {
                                    text: detalhes.expandido ? "▾" : "▸"
                                    color: Theme.dim; font.pixelSize: 11
                                }
                                Text {
                                    text: "Detalhes técnicos"
                                    color: Theme.dim; font.pixelSize: 12; font.family: Theme.sansFam
                                }
                            }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: detalhes.expandido = !detalhes.expandido }
                        }

                        Rectangle {
                            id: detalhes
                            property bool expandido: false
                            Layout.fillWidth: true
                            visible: expandido
                            implicitHeight: textoDetalhe.implicitHeight + 20
                            radius: 8
                            color: Qt.rgba(0, 0, 0, 0.28)
                            border.color: Theme.stroke
                            Text {
                                id: textoDetalhe
                                anchors { fill: parent; margins: 10 }
                                text: caixaDeMensagem.detalhe
                                color: Theme.dim
                                font.pixelSize: 12; font.family: Theme.monoFam
                                wrapMode: Text.WrapAnywhere
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.stroke }

            // ---------- rodapé ----------
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 14
                spacing: 10

                // Copiar existe para o detalhe virar anexo de relato sem ninguém transcrever
                // à mão. Sem detalhe, não há o que copiar.
                Button {
                    id: copiar
                    visible: caixaDeMensagem.detalhe !== ""
                    implicitHeight: 32
                    padding: 12
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    background: Rectangle {
                        radius: 8
                        color: copiar.hovered ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.06)
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                    contentItem: Text {
                        text: campoParaCopiar.copiado ? "Copiado" : "Copiar detalhes"
                        color: Theme.muted; font.pixelSize: 12; font.family: Theme.sansFam
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        // TextEdit invisível: é o caminho de copiar para a área de transferência
                        // sem depender de módulo extra do Qt.
                        campoParaCopiar.selectAll()
                        campoParaCopiar.copy()
                        campoParaCopiar.deselect()
                        campoParaCopiar.copiado = true
                        avisoCopiado.restart()
                    }
                }
                TextEdit {
                    id: campoParaCopiar
                    property bool copiado: false
                    visible: false
                    text: caixaDeMensagem.titulo + "\n\n" + caixaDeMensagem.mensagem
                          + "\n\n" + caixaDeMensagem.detalhe
                }
                Timer { id: avisoCopiado; interval: 2000; onTriggered: campoParaCopiar.copiado = false }

                Item { Layout.fillWidth: true }

                Repeater {
                    model: caixaDeMensagem.acoes
                    delegate: Button {
                        id: botaoAcao
                        required property var modelData
                        // O PAPEL, e não o rótulo, decide a aparência: um "Descartar" com
                        // papel de recusa precisa parecer perigoso mesmo que o texto mude.
                        readonly property bool primario: modelData.papel === "aceitar" || modelData.papel === "confirmar"
                        readonly property bool destrutivo: modelData.papel === "recusar"
                        implicitHeight: 34
                        padding: 16
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        background: Rectangle {
                            radius: 8
                            color: botaoAcao.primario
                                   ? (botaoAcao.hovered ? Qt.rgba(0.078, 0.72, 0.769, 0.34)
                                                        : Qt.rgba(0.078, 0.72, 0.769, 0.20))
                                   : botaoAcao.destrutivo
                                     ? (botaoAcao.hovered ? Qt.rgba(0.886, 0.325, 0.294, 0.30)
                                                          : Qt.rgba(0.886, 0.325, 0.294, 0.16))
                                     : (botaoAcao.hovered ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.06))
                            border.color: botaoAcao.primario ? Qt.rgba(0.078, 0.72, 0.769, 0.45) : "transparent"
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        contentItem: Text {
                            text: botaoAcao.modelData.rotulo
                            color: botaoAcao.primario ? "#9fd4da" : (botaoAcao.destrutivo ? "#ff8079" : Theme.muted)
                            font.pixelSize: 13; font.family: Theme.sansFam
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: caixaDeMensagem.respondida(botaoAcao.modelData.papel)
                    }
                }
            }
        }
    }

    // Enter/Return aciona a ação padrão. Só enquanto a caixa está aberta — um Shortcut ativo
    // com a caixa fechada roubaria a tecla do resto do app.
    Shortcut {
        sequences: ["Return", "Enter"]
        enabled: caixaDeMensagem.open
        onActivated: caixaDeMensagem.acionarPadrao()
    }
}
