import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import EsquizoCap.Layout 1.0

ColumnLayout {
    width: parent ? parent.width : 0
    spacing: 14

    SettingsCard {
        title: "AVISO DE SIMULAÇÃO"
        body: ColumnLayout {
            width: parent.width
            spacing: 16
            LinhaOpcao {
                titulo: "Borda de destaque na janela"
                descricao: "Contorna o app inteiro enquanto algum hardware está simulado. "
                    + "O selo na barra de topo e a marca nos indicadores aparecem sempre."
                ligado: controller.bordaDeSimulacao
                onAlternado: (novoValor) => controller.definirBordaDeSimulacao(novoValor)
            }
        }
    }

    SettingsCard {
        title: "APARÊNCIA"
        body: ColumnLayout {
            width: parent.width
            spacing: 14
            Text {
                Layout.fillWidth: true
                text: "Os controles de aparência ficam no painel lateral direito (ícone de faders). "
                    + "Os valores são guardados e voltam na próxima abertura."
                color: "#8fa6ac"; font.pixelSize: 11; wrapMode: Text.WordWrap
            }
            Button {
                id: restaurar
                implicitWidth: 190; implicitHeight: 34
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle {
                    radius: 8
                    color: restaurar.hovered ? Qt.rgba(0.886, 0.325, 0.294, 0.18) : Qt.rgba(1, 1, 1, 0.06)
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
                contentItem: Text {
                    text: "Restaurar aparência padrão"
                    color: restaurar.hovered ? "#ff8079" : "#8fa6ac"; font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                }
                onClicked: controller.restaurarAparenciaPadrao()
            }
        }
    }
}
