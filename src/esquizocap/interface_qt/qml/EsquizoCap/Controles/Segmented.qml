import QtQuick
import QtQuick.Layouts

Rectangle {
    property var options: []
    property string current: ""
    signal picked(string opt)
    Layout.fillWidth: true; width: parent ? parent.width : 300
    height: 42; radius: 9; color: "#0a151a"; border.color: Qt.rgba(1,1,1,0.09)
    RowLayout {
        anchors.fill: parent; anchors.margins: 3; spacing: 0
        Repeater { model: options
            Rectangle {
                id: seg
                property bool selecionado: modelData === current
                Layout.fillWidth: true; Layout.fillHeight: true; radius: 6
                color: selecionado ? "#14b8c4"
                                   : (hh.hovered ? Qt.rgba(1,1,1,0.07) : "transparent")
                Behavior on color { ColorAnimation { duration: 220 } }
                Text { anchors.centerIn: parent; text: modelData
                    color: seg.selecionado ? "#04252b" : (hh.hovered ? "#c3d6d9" : "#8fa6ac")
                    font.pixelSize: 12; font.bold: seg.selecionado }
                HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: picked(modelData) }
            }
        }
    }
}
