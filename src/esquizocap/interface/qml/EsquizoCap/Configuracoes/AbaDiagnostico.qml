import QtQuick
import QtQuick.Layouts
import EsquizoCap.Controles 1.0
import EsquizoCap.Layout 1.0

ColumnLayout {
    width: parent ? parent.width : 0
    spacing: 14

    SettingsCard {
        title: "REGISTRO (LOG)"
        body: ColumnLayout {
            width: parent.width
            spacing: 14

            Text {
                Layout.fillWidth: true
                text: "DEBUG registra tudo e ajuda a diagnosticar um problema intermitente, "
                    + "ao custo de arquivos bem maiores. A troca vale na hora, sem reiniciar."
                color: "#8fa6ac"; font.pixelSize: 11; wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Text { text: "Nível"; color: "#c3d6d9"; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
                Dropdown {
                    id: nivel
                    implicitWidth: 150
                    model: controller.niveisLogDisponiveis
                    currentIndex: controller.niveisLogDisponiveis.indexOf(controller.nivelLog)
                    onActivated: {
                        controller.definirNivelLog(currentValue)
                        // Escrever currentIndex mata o binding; restaurá-lo mantém o
                        // dropdown fiel ao controller (mesmo padrão do painel de setup).
                        nivel.currentIndex = Qt.binding(function () {
                            return controller.niveisLogDisponiveis.indexOf(controller.nivelLog)
                        })
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                BotaoSecundario {
                    text: "Abrir log desta sessão"
                    enabled: controller.temArquivoDeLog
                    opacity: enabled ? 1 : 0.45
                    onClicked: controller.abrirLogAtual()
                }
                BotaoSecundario { text: "Abrir pasta de logs"; onClicked: controller.abrirPastaLogs() }
                Item { Layout.fillWidth: true }
            }
        }
    }

    SettingsCard {
        title: "RELATAR UM PROBLEMA"
        body: ColumnLayout {
            width: parent.width
            spacing: 14
            Text {
                Layout.fillWidth: true
                text: "Copia modo, taxa, canal, estado das conexões, simulação e o caminho do log — "
                    + "tudo o que costuma ser perguntado de volta."
                color: "#8fa6ac"; font.pixelSize: 11; wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.min(diagnostico.implicitHeight + 22, 190)
                radius: 9
                color: Qt.rgba(0, 0, 0, 0.25); border.color: Qt.rgba(1, 1, 1, 0.06)
                Flickable {
                    anchors { fill: parent; margins: 11 }
                    contentHeight: diagnostico.implicitHeight
                    clip: true
                    Text {
                        id: diagnostico
                        width: parent.width
                        text: controller.textoDiagnostico
                        color: "#8fa6ac"
                        font.family: "Consolas, 'IBM Plex Mono', monospace"
                        font.pixelSize: 11
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                BotaoSecundario {
                    id: copiar
                    text: "Copiar diagnóstico"
                    onClicked: { controller.copiarDiagnostico(); avisoCopiado.restart() }
                }
                Text {
                    id: confirmacao
                    text: "Copiado."
                    color: "#3fce8f"; font.pixelSize: 11
                    opacity: 0
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                }
                Item { Layout.fillWidth: true }
            }

            // Sem retorno visível, o botão parece não ter feito nada: a área de
            // transferência é invisível por natureza.
            Timer {
                id: avisoCopiado
                interval: 1800
                onTriggered: confirmacao.opacity = 0
                onRunningChanged: if (running) confirmacao.opacity = 1
            }
        }
    }
}
