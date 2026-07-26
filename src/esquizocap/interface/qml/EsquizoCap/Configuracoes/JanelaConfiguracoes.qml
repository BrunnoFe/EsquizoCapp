import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Janela de configurações: sobreposta ao centro do palco, abas à esquerda.
//
// Não é um Popup nem um Window: é um Item ancorado ao `shell`, para respeitar o
// OpacityMask de cantos arredondados da janela sem moldura. Um Window separado teria
// barra de título do sistema, que é justamente o que o app não usa.
Item {
    id: janela
    property bool open: false
    property int abaAtual: 0

    readonly property var abas: ["Simulação", "Gravação", "Interface", "Diagnóstico"]

    anchors.fill: parent
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

    // Backdrop: fecha ao clicar fora, mesmo padrão dos painéis deslizantes.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.016, 0.016, 0.024, 0.62)
        MouseArea { anchors.fill: parent; onClicked: janela.open = false }
    }

    Rectangle {
        id: caixa
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 720)
        height: Math.min(parent.height - 80, 520)
        radius: 14
        color: "#0d1418"
        border.color: Qt.rgba(1, 1, 1, 0.08)

        scale: janela.open ? 1 : 0.96
        Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutBack } }

        // Engole cliques que atravessariam para o backdrop e fechariam a janela.
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ---------- cabeçalho ----------
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 20
                Layout.bottomMargin: 14
                Text {
                    text: "CONFIGURAÇÕES"
                    color: "#8fa6ac"; font.pixelSize: 13; font.bold: true; font.letterSpacing: 1.6
                }
                Item { Layout.fillWidth: true }
                Button {
                    id: fechar
                    implicitWidth: 30; implicitHeight: 30
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    background: Rectangle {
                        radius: 8
                        color: fechar.hovered ? Qt.rgba(0.886, 0.325, 0.294, 0.22) : Qt.rgba(1, 1, 1, 0.06)
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                    contentItem: Text {
                        text: "✕"
                        color: fechar.hovered ? "#ff8079" : "#8fa6ac"; font.pixelSize: 15
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: janela.open = false
                }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.rgba(1, 1, 1, 0.06) }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // ---------- lista de abas ----------
                Rectangle {
                    Layout.fillHeight: true
                    implicitWidth: 176
                    color: Qt.rgba(0, 0, 0, 0.18)
                    Rectangle {
                        anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
                        width: 1; color: Qt.rgba(1, 1, 1, 0.06)
                    }
                    ColumnLayout {
                        anchors { fill: parent; margins: 12 }
                        spacing: 4
                        Repeater {
                            model: janela.abas
                            delegate: Rectangle {
                                required property int index
                                required property string modelData
                                Layout.fillWidth: true
                                implicitHeight: 36
                                radius: 8
                                color: index === janela.abaAtual ? Qt.rgba(0.078, 0.72, 0.769, 0.16)
                                     : (hh.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent")
                                Behavior on color { ColorAnimation { duration: 150 } }
                                Text {
                                    anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                    text: parent.modelData
                                    color: parent.index === janela.abaAtual ? "#9fd4da" : "#8fa6ac"
                                    font.pixelSize: 13
                                    Behavior on color { ColorAnimation { duration: 150 } }
                                }
                                HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
                                TapHandler { onTapped: janela.abaAtual = index }
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                // ---------- conteúdo da aba ----------
                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: pilha.implicitHeight + 40
                    clip: true

                    StackLayout {
                        id: pilha
                        x: 20; y: 20
                        width: parent.width - 40
                        currentIndex: janela.abaAtual
                        implicitHeight: children[currentIndex] ? children[currentIndex].implicitHeight : 0

                        AbaSimulacao {}
                        AbaGravacao {}
                        AbaInterface {}
                        AbaDiagnostico {}
                    }
                }
            }
        }
    }
}
