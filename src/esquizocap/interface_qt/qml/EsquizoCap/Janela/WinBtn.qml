import QtQuick
import QtQuick.Shapes

// min / max / close
Item {
    property string kind: "min"
    signal clicked()
    width: 16; height: 16
    property color c: ma.containsMouse ? "#c3d6d9" : "#5f7176"
    Rectangle { visible: kind === "min"; anchors.centerIn: parent; width: 13; height: 2; color: parent.c }
    Rectangle { visible: kind === "max"; anchors.centerIn: parent; width: 12; height: 12; radius: 2
        color: "transparent"; border.color: parent.c; border.width: 1.5 }
    Text { visible: kind === "close"; anchors.centerIn: parent; text: "\u2715"; color: parent.c; font.pixelSize: 15 }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: parent.clicked() }
}
