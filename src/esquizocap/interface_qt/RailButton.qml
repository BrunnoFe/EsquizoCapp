import QtQuick
import QtQuick.Controls.Basic

// Botão do trilho / caixa. Aceita glyph (texto) OU icon (nome vetorial).
Button {
    id: b
    property string glyph: ""
    property string iconName: ""
    property string tip: ""
    property bool small: false
    property bool italic: false
    property bool boxed: false
    implicitWidth: small ? 40 : 42
    implicitHeight: small ? 40 : 42
    ToolTip.visible: hovered && tip.length > 0
    ToolTip.text: tip
    HoverHandler { cursorShape: Qt.PointingHandCursor }
    scale: b.pressed ? 0.94 : (b.hovered ? 1.06 : 1.0)
    Behavior on scale { NumberAnimation { duration: 130; easing.type: Easing.OutCubic } }
    background: Rectangle {
        radius: boxed ? 11 : (b.small ? 10 : 11)
        color: b.hovered ? Qt.rgba(1,1,1,0.10) : Qt.rgba(1,1,1,b.boxed ? 0.06 : (b.small ? 0.05 : 0.06))
        border.color: b.hovered ? Qt.rgba(0.078,0.72,0.769,0.45)
                                : (b.boxed ? Qt.rgba(1,1,1,0.1) : "transparent")
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }
    contentItem: Item {
        Text {
            visible: b.glyph.length > 0
            anchors.centerIn: parent; text: b.glyph
            color: b.small ? "#7f9aa0" : "#9fd4da"
            font.pixelSize: b.italic ? 17 : 19
            font.italic: b.italic
            font.family: b.italic ? "'Fraunces', Georgia, serif" : "sans-serif"
        }
        IconGlyph {
            visible: b.iconName.length > 0
            anchors.centerIn: parent
            name: b.iconName
            color: b.boxed ? "#9fd4da" : "#7f9aa0"
        }
    }
}
