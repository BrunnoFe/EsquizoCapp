import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import EsquizoCap.Base 1.0

Rectangle {
    id: card
    property string title: ""
    property alias body: holder.data

    // Botão "Resetar" no canto do cabeçalho. Opt-in: este componente também desenha os
    // cards da aba Interface, que não têm o que restaurar — vazio significa sem botão.
    property string secao: ""
    property bool podeResetar: true
    signal resetSolicitado()

    Layout.fillWidth: true
    radius: 11; color: "#111d23"; border.color: Qt.rgba(1,1,1,0.06)
    implicitHeight: col.implicitHeight + 28
    ColumnLayout {
        id: col; anchors.fill: parent; anchors.margins: 14; spacing: 13
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: card.title; color: "#c3d6d9"; font.pixelSize: 12; font.bold: true }
            Item { Layout.fillWidth: true }
            Button {
                id: reset
                visible: card.secao !== ""
                // Esmaecido, e não escondido: sumir com o botão mexeria no layout do
                // cabeçalho a cada slider tocado. Esmaecido ele vira indicador de
                // "mexi aqui", que é informação que o painel não dá em lugar nenhum.
                enabled: card.podeResetar
                opacity: enabled ? 1 : 0.3
                Behavior on opacity { NumberAnimation { duration: 150 } }
                implicitWidth: 22; implicitHeight: 22; padding: 0
                ToolTip.visible: hovered
                ToolTip.text: enabled ? "Resetar" : "Já está no padrão"
                HoverHandler { cursorShape: reset.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
                background: Rectangle {
                    radius: 6
                    color: reset.hovered && reset.enabled ? Qt.rgba(1, 1, 1, 0.10) : "transparent"
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
                contentItem: Item {
                    IconGlyph {
                        anchors.centerIn: parent
                        width: 14; height: 14
                        name: "recarregar"
                        color: reset.hovered && reset.enabled ? "#9fd4da" : "#7f9aa0"
                    }
                }
                onClicked: card.resetSolicitado()
            }
        }
        Item { id: holder; Layout.fillWidth: true; implicitHeight: childrenRect.height }
    }
}
