import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// slider de configurações (accent fixo teal, label acinzentado)
ColumnLayout {
    property string label: ""
    property var readout: ""
    property real from: 0
    property real to: 100
    property real step: 1
    property real value: 0
    signal moved()
    Layout.fillWidth: true; spacing: 5
    RowLayout { Layout.fillWidth: true
        Text { text: label; color: "#8fa6ac"; font.pixelSize: 12 }
        Item { Layout.fillWidth: true }
        Text { text: readout; color: "#14b8c4"; font.family: "Consolas, monospace"; font.pixelSize: 12 } }
    Slider {
        id: s; Layout.fillWidth: true
        from: parent.from; to: parent.to; stepSize: parent.step; value: parent.value
        onMoved: { parent.value = value; parent.moved() }
        background: Rectangle { x: s.leftPadding; y: s.topPadding + s.availableHeight/2 - 2
            width: s.availableWidth; height: 4; radius: 2; color: Qt.rgba(1,1,1,0.12)
            Rectangle { width: s.visualPosition * parent.width; height: parent.height; radius: 2; color: "#14b8c4" } }
        handle: Rectangle { x: s.leftPadding + s.visualPosition*(s.availableWidth-14)
            y: s.topPadding + s.availableHeight/2 - 7; width: 14; height: 14; radius: 7; color: "#fff" }
    }
}
