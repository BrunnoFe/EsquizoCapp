import QtQuick
import QtQuick.Controls.Basic

// Seletor real (substitui o antigo FakeSelect). Mantém o visual do painel de
// setup: fundo escuro, borda sutil, seta ▾ e popup no tema da aplicação.
ComboBox {
    id: dd

    // Opções que aparecem na lista mas NÃO podem ser escolhidas. Existe para o caso em
    // que sumir com a opção esconderia a informação: quem procura 10 Hz precisa ver que
    // ela existe e está indisponível, não achar que a aplicação a esqueceu.
    property var desabilitados: []

    implicitHeight: 38
    implicitWidth: 200

    background: Rectangle {
        radius: 8
        color: "#0a151a"
        border.color: dd.hovered || dd.popup.visible
                      ? Qt.rgba(0.078, 0.72, 0.769, 0.55)
                      : Qt.rgba(1, 1, 1, 0.09)
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }

    contentItem: Text {
        leftPadding: 11
        rightPadding: 28
        text: dd.displayText
        color: "#b6c8cc"
        font.pixelSize: 12
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

    indicator: Text {
        x: dd.width - width - 11
        y: dd.topPadding + (dd.availableHeight - height) / 2
        text: "▾"
        color: dd.hovered ? "#9fd4da" : "#6f858b"
        font.pixelSize: 12
        rotation: dd.popup.visible ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: 150 } }
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }

    delegate: ItemDelegate {
        id: item
        width: dd.width
        implicitHeight: 34
        enabled: dd.desabilitados.indexOf(modelData) === -1
        opacity: enabled ? 1.0 : 0.4
        highlighted: dd.highlightedIndex === index && enabled
        background: Rectangle {
            color: highlighted ? Qt.rgba(1, 1, 1, 0.07) : "transparent"
        }
        contentItem: Text {
            leftPadding: 11
            text: modelData
            color: !item.enabled ? "#6f9096"
                                 : (dd.currentIndex === index ? "#14b8c4" : "#b6c8cc")
            font.pixelSize: 12
            font.bold: dd.currentIndex === index
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        HoverHandler { cursorShape: item.enabled ? Qt.PointingHandCursor : Qt.ForbiddenCursor }
    }

    popup: Popup {
        y: dd.height + 4
        width: dd.width
        implicitHeight: Math.min(contentItem.implicitHeight + 12, 220)
        padding: 6

        background: Rectangle {
            radius: 8
            color: "#0a151a"
            border.color: Qt.rgba(1, 1, 1, 0.12)
        }
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: dd.popup.visible ? dd.delegateModel : null
            currentIndex: dd.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }
}
