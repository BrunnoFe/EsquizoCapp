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
                    BotaoSecundario { implicitWidth: 92; text: "Escolher..."; onClicked: dialogoPasta.open() }
                }
                BotaoSecundario {
                    text: "Abrir pasta de gravações"
                    onClicked: controller.abrirPastaGravacoes()
                }
            }

            LinhaOpcao {
                titulo: "Gravar por padrão"
                descricao: "Deixa \"gravar aquisição\" já ligado a cada sessão."
                ligado: controller.gravarPorPadrao
                onAlternado: (novoValor) => controller.definirGravarPorPadrao(novoValor)
            }
        }
    }

    SettingsCard {
        title: "NOME DO ARQUIVO"
        body: ColumnLayout {
            width: parent.width
            spacing: 12

            TextField {
                id: campoFormato
                Layout.fillWidth: true
                implicitHeight: 34
                text: controller.formatoNomeGravacao
                placeholderText: controller.formatoNomePadrao
                color: "#c3d6d9"; placeholderTextColor: "#5f8a90"
                font.family: "Consolas, 'IBM Plex Mono', monospace"; font.pixelSize: 12
                leftPadding: 11; rightPadding: 11
                selectByMouse: true
                background: Rectangle {
                    radius: 8; color: "#0a151a"
                    border.color: campoFormato.activeFocus ? Qt.rgba(0.078, 0.72, 0.769, 0.55)
                                                           : Qt.rgba(1, 1, 1, 0.09)
                    Behavior on border.color { ColorAnimation { duration: 150 } }
                }
                onTextEdited: controller.definirFormatoNomeGravacao(text)
            }

            Flow {
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: controller.marcadoresDoNome
                    delegate: Rectangle {
                        required property string modelData
                        implicitWidth: marcador.implicitWidth + 16; implicitHeight: 24; radius: 6
                        color: hoverMarcador.hovered ? Qt.rgba(1, 1, 1, 0.11) : Qt.rgba(1, 1, 1, 0.05)
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            id: marcador
                            anchors.centerIn: parent
                            text: "{" + parent.modelData + "}"
                            color: "#9fd4da"
                            font.family: "Consolas, 'IBM Plex Mono', monospace"; font.pixelSize: 11
                        }
                        HoverHandler { id: hoverMarcador; cursorShape: Qt.PointingHandCursor }
                        // Clicar insere o marcador: digitar as chaves à mão é onde nasce o
                        // formato inválido que depois cai no padrão sem o usuário entender.
                        TapHandler { onTapped: campoFormato.insert(campoFormato.cursorPosition,
                                                                   "{" + parent.modelData + "}") }
                    }
                }
            }

            // A prévia ao vivo é o que torna o campo usável: sem ela, um marcador digitado
            // errado só aparece quando a gravação já acabou e o nome saiu no padrão.
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { text: "Ficaria:"; color: "#5f8a90"; font.pixelSize: 11 }
                Text {
                    Layout.fillWidth: true
                    text: controller.previaNomeGravacao
                    color: "#3fce8f"
                    font.family: "Consolas, 'IBM Plex Mono', monospace"; font.pixelSize: 11
                    elide: Text.ElideMiddle
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
