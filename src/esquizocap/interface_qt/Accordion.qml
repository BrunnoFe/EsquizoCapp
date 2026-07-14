import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: a
    property string title: ""
    property color dotColor: "#3fce8f"
    property string badge: ""
    property bool expanded: false
    property alias body: bodyHolder.data
    Layout.fillWidth: true
    width: parent ? parent.width : 320
    radius: 11; color: "#111d23"; border.color: Qt.rgba(1,1,1,0.06)
    implicitHeight: col.implicitHeight + 4
    ColumnLayout {
        id: col; width: parent.width; spacing: 0
        // header
        MouseArea {
            id: header
            Layout.fillWidth: true; implicitHeight: 46; cursorShape: Qt.PointingHandCursor
            hoverEnabled: true
            onClicked: a.expanded = !a.expanded
            Rectangle {
                anchors.fill: parent; radius: 11
                color: header.containsMouse ? Qt.rgba(1,1,1,0.04) : "transparent"
                Behavior on color { ColorAnimation { duration: 150 } }
            }
            RowLayout { anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 8
                Rectangle { width: 6; height: 6; radius: 3; color: a.dotColor
                    Behavior on color { ColorAnimation { duration: 220 } } }
                Text { text: a.title; color: "#f0eef2"; font.pixelSize: 14; font.bold: true }
                Item { Layout.fillWidth: true }
                Text { visible: a.badge.length; text: a.badge; color: a.dotColor; font.pixelSize: 11
                    Behavior on color { ColorAnimation { duration: 220 } } }
                Text { text: a.expanded ? "\u2212" : "+"
                    color: header.containsMouse ? "#c3d6d9" : "#6f858b"; font.pixelSize: 15 } }
        }
        // corpo animado
        Item {
            Layout.fillWidth: true; clip: true
            implicitHeight: a.expanded ? bodyHolder.childrenRect.height + 14 : 0
            Behavior on implicitHeight { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            opacity: a.expanded ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Item { id: bodyHolder; x: 14; width: parent.width - 28; implicitHeight: childrenRect.height }
        }
    }
}
