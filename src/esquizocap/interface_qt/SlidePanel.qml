import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Painel lateral que desliza (side: "left" | "right").
Rectangle {
    id: p
    property string side: "left"
    property string title: ""
    property bool open: false
    property alias content: bodyHolder.data
    property alias footer: footHolder.data
    width: 360
    anchors.top: parent.top; anchors.bottom: parent.bottom
    color: "#0d1418"

    // Anima-se o PROGRESSO de abertura (0 = fechado, 1 = aberto), nunca o `x`.
    // Animar `x` direto era um bug: o x do painel fechado à direita depende de
    // `parent.width`, então ao entrar em tela cheia o palco crescia, o destino
    // mudava, e o Behavior animava essa mudança de geometria — o painel atravessava
    // a tela sozinho. Assim o redimensionamento reposiciona na hora, sem animação.
    readonly property real recuo: width + 40
    property real progresso: open ? 1 : 0
    Behavior on progresso { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }

    x: side === "left"
        ? -recuo + progresso * recuo
        : parent.width + 40 - progresso * recuo
    Rectangle { anchors { top: parent.top; bottom: parent.bottom
                right: side === "left" ? parent.right : undefined
                left: side === "right" ? parent.left : undefined }
        width: 1; color: Qt.rgba(1,1,1,0.08) }

    ColumnLayout {
        anchors.fill: parent; spacing: 0
        RowLayout {
            Layout.fillWidth: true; Layout.margins: 20; Layout.bottomMargin: 14
            Text { text: p.title; color: "#8fa6ac"; font.pixelSize: 13; font.bold: true; font.letterSpacing: 1.2 }
            Item { Layout.fillWidth: true }
            Button { id: fechar
                implicitWidth: 30; implicitHeight: 30
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle { radius: 8
                    color: fechar.hovered ? Qt.rgba(0.886,0.325,0.294,0.22) : Qt.rgba(1,1,1,0.06)
                    Behavior on color { ColorAnimation { duration: 150 } } }
                contentItem: Text { text: "\u2715"
                    color: fechar.hovered ? "#ff8079" : "#8fa6ac"; font.pixelSize: 15
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: p.open = false }
        }
        Flickable {
            Layout.fillWidth: true; Layout.fillHeight: true
            contentHeight: bodyHolder.childrenRect.height + 32; clip: true
            Item { id: bodyHolder; x: 20; width: parent.width - 40
                implicitHeight: childrenRect.height }
        }
        Rectangle { Layout.fillWidth: true; height: footHolder.children.length ? 81 : 0
            color: "transparent"; visible: footHolder.children.length
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Qt.rgba(1,1,1,0.06) }
            Item { id: footHolder; anchors.fill: parent; anchors.margins: 16 } }
    }
}
