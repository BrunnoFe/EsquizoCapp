import QtQuick
import QtQuick.Layouts
import EsquizoCap.Controles 1.0

// Uma opção liga/desliga com título, explicação e chave.
// `travada` desabilita a chave sem escondê-la: o operador precisa ver o estado atual
// mesmo quando não pode mudá-lo — esconder faria parecer que a opção não existe.
RowLayout {
    id: linha
    property string titulo: ""
    property string descricao: ""
    property bool ligado: false
    property bool travada: false
    signal alternado(bool novoValor)

    width: parent ? parent.width : 0
    spacing: 14

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 3
        Text {
            text: linha.titulo
            color: linha.travada ? "#5f8a90" : "#c3d6d9"
            font.pixelSize: 13
            Behavior on color { ColorAnimation { duration: 150 } }
        }
        Text {
            visible: linha.descricao.length > 0
            text: linha.descricao
            color: "#5f8a90"
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }

    Toggle {
        Layout.alignment: Qt.AlignVCenter
        on: linha.ligado
        opacity: linha.travada ? 0.4 : 1.0
        Behavior on opacity { NumberAnimation { duration: 150 } }
        onClicked: if (!linha.travada) linha.alternado(!linha.ligado)
    }
}
