import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import EsquizoCap.Layout 1.0

ColumnLayout {
    width: parent ? parent.width : 0
    spacing: 14

    SettingsCard {
        title: "DESTINO DAS GRAVAÇÕES"
        body: ColumnLayout {
            width: parent.width
            spacing: 16

            LinhaOpcao {
                titulo: "Perguntar onde salvar"
                descricao: "Desligue para gravar direto na pasta abaixo, sem diálogo — "
                    + "útil quando a instalação roda sozinha."
                ligado: controller.perguntarOndeSalvar
                onAlternado: (novoValor) => controller.definirPerguntarOndeSalvar(novoValor)
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 7
                Text { text: "Pasta padrão"; color: "#8fa6ac"; font.pixelSize: 12 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 34; radius: 8
                        color: Qt.rgba(1, 1, 1, 0.04); border.color: Qt.rgba(1, 1, 1, 0.08)
                        Text {
                            anchors { fill: parent; leftMargin: 11; rightMargin: 11 }
                            verticalAlignment: Text.AlignVCenter
                            text: controller.pastaGravacoes
                            color: "#c3d6d9"; font.family: "Consolas, 'IBM Plex Mono', monospace"
                            font.pixelSize: 11; elide: Text.ElideMiddle
                        }
                    }
                    Button {
                        id: escolher
                        implicitWidth: 92; implicitHeight: 34
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        background: Rectangle {
                            radius: 8
                            color: escolher.hovered ? Qt.rgba(1, 1, 1, 0.11) : Qt.rgba(1, 1, 1, 0.06)
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        contentItem: Text {
                            text: "Escolher..."; color: "#9fd4da"; font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: dialogoPasta.open()
                    }
                }
            }
        }
    }

    FolderDialog {
        id: dialogoPasta
        title: "Pasta das gravações"
        currentFolder: controller.pastaGravacoesUrl
        onAccepted: controller.definirPastaGravacoes(selectedFolder.toString())
    }
}
