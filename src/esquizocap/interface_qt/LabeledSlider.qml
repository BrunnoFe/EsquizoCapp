import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    property string label: ""
    property var readout: ""
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property real value: 0
    property color accent: "#14b8c4"
    signal moved()
    Layout.fillWidth: true; spacing: 5
    RowLayout { Layout.fillWidth: true
        Text { text: label; color: "#c3d6d9"; font.pixelSize: 12 }
        Item { Layout.fillWidth: true }
        Text { text: readout; color: "#c3d6d9"; font.family: "Consolas, monospace"; font.pixelSize: 12 } }
    Slider {
        id: s; Layout.fillWidth: true
        from: parent.from; to: parent.to; stepSize: parent.stepSize; value: parent.value
        onMoved: { parent.value = value; parent.moved() }
        background: Rectangle { x: s.leftPadding; y: s.topPadding + s.availableHeight/2 - 2
            width: s.availableWidth; height: 4; radius: 2; color: Qt.rgba(1,1,1,0.12)
            Rectangle { width: s.visualPosition * parent.width; height: parent.height; radius: 2; color: accent } }
        handle: Rectangle { x: s.leftPadding + s.visualPosition*(s.availableWidth-14)
            y: s.topPadding + s.availableHeight/2 - 7; width: 14; height: 14; radius: 7; color: "#fff" }
    }
}
