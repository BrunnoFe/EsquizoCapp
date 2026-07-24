import QtQuick

Rectangle {
    id: tg
    property bool on: false
    signal clicked()
    width: 38; height: 21; radius: 11
    color: on ? "#14b8c4" : (hh.hovered ? "#3a464f" : "#2a333a")
    Behavior on color { ColorAnimation { duration: 200 } }
    border.color: hh.hovered ? Qt.rgba(1, 1, 1, 0.18) : "transparent"
    Behavior on border.color { ColorAnimation { duration: 150 } }

    Rectangle { width: 17; height: 17; radius: 8.5; color: "#fff"; y: 2
        x: tg.on ? tg.width - width - 2 : 2
        Behavior on x { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } } }

    HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: tg.clicked() }
}
