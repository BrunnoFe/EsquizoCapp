import QtQuick
import QtQuick.Layouts
import EsquizoCap.Layout 1.0

ColumnLayout {
    width: parent ? parent.width : 0
    spacing: 14

    SettingsCard {
        title: "HARDWARE SIMULADO"
        body: ColumnLayout {
            width: parent.width
            spacing: 16

            Text {
                Layout.fillWidth: true
                text: "Permite rodar a instalação inteira sem o hardware plugado. "
                    + "Tudo funciona igual — conexão, aquisição, gravação — mas o sinal é sintético."
                color: "#8fa6ac"; font.pixelSize: 11; wrapMode: Text.WordWrap
            }

            LinhaOpcao {
                titulo: "Simular o Arduino"
                descricao: "A fita de LED não acende; os comandos vão para um controlador falso."
                ligado: controller.arduinoSimulado
                travada: !controller.podeAlterarSimulacao
                onAlternado: (novoValor) => controller.definirSimulacao("arduino", novoValor)
            }

            LinhaOpcao {
                titulo: "Simular o BITalino"
                descricao: "Gera EEG sintético. A escolha entre Modo OpenSignals e Modo Direto "
                    + "deixa de ter efeito — o mesmo leitor responde pelos dois."
                ligado: controller.bitalinoSimulado
                travada: !controller.podeAlterarSimulacao
                onAlternado: (novoValor) => controller.definirSimulacao("bitalino", novoValor)
            }

            // O motivo da trava é a informação mais útil da aba: sem ele, uma chave que
            // não responde ao clique parece um defeito.
            Rectangle {
                Layout.fillWidth: true
                visible: controller.motivoSimulacaoTravada.length > 0
                implicitHeight: motivo.implicitHeight + 20
                radius: 9
                color: Qt.rgba(0.078, 0.72, 0.769, 0.08)
                border.color: Qt.rgba(0.078, 0.72, 0.769, 0.25)
                Text {
                    id: motivo
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                              leftMargin: 12; rightMargin: 12 }
                    text: controller.motivoSimulacaoTravada
                    color: "#9fd4da"; font.pixelSize: 11; wrapMode: Text.WordWrap
                }
            }
        }
    }
}
