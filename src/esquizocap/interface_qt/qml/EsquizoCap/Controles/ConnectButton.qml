import QtQuick
import QtQuick.Controls.Basic

// Botão de conectar/desconectar um dispositivo. Verde quando há o que conectar,
// vermelho quando a ação é desconectar o que já está ligado.
Button {
    id: cb
    property bool conectado: false
    readonly property color acento: conectado ? "#e2534b" : "#3fce8f"

    implicitHeight: 36
    implicitWidth: 160
    padding: 0
    HoverHandler { cursorShape: Qt.PointingHandCursor }

    background: Rectangle {
        radius: 9
        color: cb.hovered ? Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, 0.22)
                          : Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, 0.12)
        border.color: Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, cb.hovered ? 0.7 : 0.35)
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }

    contentItem: Text {
        text: cb.conectado ? "Desconectar" : "Conectar"
        color: cb.acento
        font.pixelSize: 12
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        Behavior on color { ColorAnimation { duration: 150 } }
    }
}
