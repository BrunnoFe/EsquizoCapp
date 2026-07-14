import QtQuick

Rectangle {
    id: chip
    property string text: ""
    property bool on: false
    property bool hovered: hh.hovered
    signal clicked()

    radius: 8; height: 30
    // A largura é medida sempre com o texto em negrito (mesmo quando o chip não
    // está selecionado): assim selecionar não muda o tamanho e o Flow não
    // reposiciona os chips vizinhos a cada clique.
    implicitWidth: regua.implicitWidth + 24
    color: on ? "#14b8c4"
              : (hovered ? Qt.rgba(1, 1, 1, 0.11) : Qt.rgba(1, 1, 1, 0.05))
    Behavior on color { ColorAnimation { duration: 200 } }

    Text {
        id: regua
        visible: false
        text: chip.text
        font.pixelSize: 12
        font.bold: true
    }
    Text {
        anchors.centerIn: parent
        text: chip.text
        color: chip.on ? "#04252b" : (chip.hovered ? "#c3d6d9" : "#8fa6ac")
        font.pixelSize: 12
        font.bold: chip.on
    }

    HoverHandler { id: hh; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: chip.clicked() }
}
