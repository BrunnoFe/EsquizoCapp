import QtQuick
import QtQuick.Controls.Basic
import EsquizoCap.Base 1.0

// Botão de conectar/desconectar um dispositivo. Verde quando há o que conectar,
// vermelho quando a ação é desconectar o que já está ligado.
Button {
    id: cb
    property bool conectado: false

    // Espera em curso: o botão vira indicador e para de aceitar cliques.
    //
    // Quem liga isto é quem instancia, e não o botão: só a view sabe QUAL conexão este
    // botão comanda. O do Arduino nunca acende — aquela conexão é síncrona e termina antes
    // do próximo quadro; um indicador ali piscaria por um quadro e pareceria defeito.
    property bool ocupado: false

    readonly property color acento: conectado ? "#e2534b" : "#3fce8f"

    implicitHeight: 36
    implicitWidth: 160
    padding: 0
    // Clicar durante a tentativa dispararia uma segunda conexão sobre a primeira, com o
    // aparelho aceitando um cliente por vez.
    enabled: !ocupado
    HoverHandler { cursorShape: Qt.PointingHandCursor }

    background: Rectangle {
        radius: 9
        color: cb.hovered ? Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, 0.22)
                          : Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, 0.12)
        border.color: Qt.rgba(cb.acento.r, cb.acento.g, cb.acento.b, cb.hovered ? 0.7 : 0.35)
        Behavior on color { ColorAnimation { duration: 150 } }
        Behavior on border.color { ColorAnimation { duration: 150 } }
    }

    // Uma caixa que hospeda os dois conteúdos, em vez de trocar o `contentItem` inteiro: o
    // `implicitWidth` do botão continua sendo os 160 fixos acima, então ele não muda de
    // tamanho ao entrar e sair da espera. Um botão que encolhe no meio de uma tentativa
    // empurraria o painel de setup inteiro para cima.
    contentItem: Item {
        Text {
            anchors.centerIn: parent
            visible: !cb.ocupado
            text: cb.conectado ? "Desconectar" : "Conectar"
            color: cb.acento
            font.pixelSize: 12
            font.bold: true
            Behavior on color { ColorAnimation { duration: 150 } }
        }

        IndicadorCarregando {
            anchors.centerIn: parent
            size: 18
            running: cb.ocupado
        }
    }
}
