import QtQuick
import QtQuick.Layouts

Rectangle {
    property string title: ""
    property alias body: holder.data
    Layout.fillWidth: true
    radius: 11; color: "#111d23"; border.color: Qt.rgba(1,1,1,0.06)
    implicitHeight: col.implicitHeight + 28
    ColumnLayout {
        id: col; anchors.fill: parent; anchors.margins: 14; spacing: 13
        Text { text: title; color: "#c3d6d9"; font.pixelSize: 12; font.bold: true }
        Item { id: holder; Layout.fillWidth: true; implicitHeight: childrenRect.height }
    }
}
