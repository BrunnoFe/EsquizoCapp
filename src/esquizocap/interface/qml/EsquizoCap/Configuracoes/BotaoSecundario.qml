import QtQuick
import QtQuick.Controls.Basic

// Botão discreto de ação, no estilo dos controles do menu.
Button {
    id: botao
    property bool destrutivo: false
    implicitHeight: 34
    implicitWidth: Math.max(120, rotulo.implicitWidth + 28)
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    background: Rectangle {
        radius: 8
        color: botao.hovered
            ? (botao.destrutivo ? Qt.rgba(0.886, 0.325, 0.294, 0.18) : Qt.rgba(1, 1, 1, 0.11))
            : Qt.rgba(1, 1, 1, 0.06)
        Behavior on color { ColorAnimation { duration: 150 } }
    }
    contentItem: Text {
        id: rotulo
        text: botao.text
        color: botao.hovered ? (botao.destrutivo ? "#ff8079" : "#9fd4da") : "#8fa6ac"
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        Behavior on color { ColorAnimation { duration: 150 } }
    }
}
