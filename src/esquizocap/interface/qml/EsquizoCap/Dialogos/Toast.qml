import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import EsquizoCap.Base 1.0

// Recado passageiro no topo da janela, para o que não merece interromper: avisos e
// informações de ferramenta ("não consegui abrir a pasta de logs").
//
// É o banner vermelho antigo consertado. Os defeitos que ficaram para trás: altura fixa de
// 40px sem `wrapMode` (mensagem de duas linhas era cortada), largura crescendo sem limite
// com o tamanho do texto, ficar FORA do `shell` e portanto ignorar os cantos arredondados,
// e não sumir sozinho.
Item {
    id: toast

    property bool aberto: false
    property string severidade: "info"   // aviso | info
    property string titulo: ""
    property string mensagem: ""
    // Identidade do que está sendo mostrado. O timer confere isto antes de fechar: sem
    // essa checagem, um recado novo chegando faria o timer do anterior apagar o atual.
    property string identidade: ""
    property int duracaoMs: 7000

    signal dispensado()

    readonly property color destaque: Theme.corDaSeveridade(severidade)

    anchors.fill: parent
    // Item transparente que só hospeda a bolha: sem isto, um `anchors.fill` capturaria
    // cliques na janela inteira.
    visible: opacity > 0
    opacity: aberto ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.duracaoFade; easing.type: Easing.OutCubic } }

    onIdentidadeChanged: if (aberto) relogio.restart()
    onAbertoChanged: aberto ? relogio.restart() : relogio.stop()

    Timer {
        id: relogio
        interval: toast.duracaoMs
        property string identidadeAoIniciar: ""
        onRunningChanged: if (running) identidadeAoIniciar = toast.identidade
        onTriggered: if (toast.identidade === identidadeAoIniciar) toast.dispensado()
    }

    Rectangle {
        id: bolha
        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 16 }
        width: Math.min(toast.width - 120, 460)
        implicitHeight: linha.implicitHeight + 24
        height: implicitHeight
        radius: 10
        color: Theme.cardBg
        border.color: Qt.rgba(toast.destaque.r, toast.destaque.g, toast.destaque.b, 0.45)

        y: toast.aberto ? 0 : -8
        Behavior on y { NumberAnimation { duration: Theme.duracaoEscala; easing.type: Easing.OutCubic } }

        // Faixa da severidade na borda esquerda: é o "destaque para identificar o tipo"
        // sem mudar o resto da aparência.
        Rectangle {
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: 3
            radius: 2
            color: toast.destaque
        }

        RowLayout {
            id: linha
            anchors { fill: parent; leftMargin: 16; rightMargin: 8; topMargin: 12; bottomMargin: 12 }
            spacing: 10

            Rectangle {
                Layout.alignment: Qt.AlignTop
                implicitWidth: 18; implicitHeight: 18; radius: 9
                color: toast.destaque
                Text {
                    anchors.centerIn: parent
                    text: Theme.glifoDaSeveridade(toast.severidade)
                    color: "#0b0b0e"; font.pixelSize: 11; font.bold: true
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Text {
                    Layout.fillWidth: true
                    visible: toast.titulo !== ""
                    text: toast.titulo
                    color: "#e8f1f2"
                    font.pixelSize: 13; font.bold: true; font.family: Theme.sansFam
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    text: toast.mensagem
                    color: Theme.muted
                    font.pixelSize: 12; font.family: Theme.sansFam
                    lineHeight: 1.3
                    wrapMode: Text.WordWrap
                }
            }

            Button {
                id: fechar
                Layout.alignment: Qt.AlignTop
                implicitWidth: 22; implicitHeight: 22; padding: 0
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle {
                    radius: 6
                    color: fechar.hovered ? Qt.rgba(1, 1, 1, 0.10) : "transparent"
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
                contentItem: Text {
                    text: "✕"
                    color: fechar.hovered ? "#e8f1f2" : Theme.dim; font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                onClicked: toast.dispensado()
            }
        }
    }
}
