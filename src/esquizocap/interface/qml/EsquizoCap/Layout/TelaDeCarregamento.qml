import QtQuick
import Qt5Compat.GraphicalEffects
import EsquizoCap.Base 1.0

// Tela de carregamento — a marca animada ocupando a janela inteira enquanto o app sobe.
//
// Este arquivo só sabe DESENHAR e obedecer `aberta`. Nada de Timer, nada de `controller`,
// nada de lógica de negócio: quem decide quando a tela some é quem a instancia. As duas
// propriedades públicas (`aberta`, `mensagem`) são toda a superfície de ligação — é por
// elas que o carregamento real vai entrar, sem tocar no resto do arquivo.
Item {
    id: tela

    // ---- superfície pública (e só ela) ----
    property bool aberta: true
    property string mensagem: ""

    anchors.fill: parent
    // Só some DEPOIS do fade terminar — nunca corta a desaceleração no meio.
    visible: opacity > 0

    // A onda desacelera até quase parar antes do fade começar. Como o ciclo termina com
    // o pico no topo (índice 0 = [60, 16]), o último quadro da animação é exatamente a
    // marca estática: a logo parada é o fim do movimento, não um corte.
    property int cicloDaOnda: aberta ? 1800 : 9000
    Behavior on cicloDaOnda {
        NumberAnimation { duration: Theme.duracaoEscala; easing.type: Easing.OutCubic }
    }

    // A roda de matiz gira no mesmo sentido, num ciclo mais lento e que NÃO é múltiplo do
    // da onda — a combinação nunca se repete igual. Na saída desacelera no mesmo fator (5×)
    // que a onda, para que a marca inteira assente junto em vez de a cor continuar girando
    // sobre um anel já parado.
    property int cicloDoMatiz: aberta ? 7000 : 35000
    Behavior on cicloDoMatiz {
        NumberAnimation { duration: Theme.duracaoEscala; easing.type: Easing.OutCubic }
    }

    opacity: aberta ? 1 : 0
    Behavior on opacity {
        SequentialAnimation {
            // espera a onda desacelerar antes de sumir
            PauseAnimation { duration: Theme.duracaoEscala }
            NumberAnimation { duration: Theme.duracaoFade; easing.type: Easing.InOutQuad }
        }
    }

    // ---- fundo: é uma TELA, não um véu; o app não pode aparecer atrás ----
    Rectangle {
        anchors.fill: parent
        color: Theme.fundoJanela

        // mesmo tratamento de brilho central que o palco já usa
        RadialGradient {
            anchors.fill: parent
            horizontalOffset: 0; verticalOffset: -parent.height * 0.06
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.05, 0.29, 0.32, 0.20) }
                GradientStop { position: 0.62; color: "transparent" }
            }
        }
    }

    // engole cliques: nada atrás da tela deve responder enquanto ela estiver de pé
    MouseArea { anchors.fill: parent }

    Column {
        anchors.centerIn: parent
        spacing: 26

        LogoSpinner {
            anchors.horizontalCenter: parent.horizontalCenter
            size: 168
            cycle: tela.cicloDaOnda
            hueCycle: tela.cicloDoMatiz
            spread: 0.85
            running: tela.visible
        }

        // wordmark — mesma tipografia da barra de título, em escala maior
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: wordmark.width + capmark.width
            height: wordmark.height
            Text {
                id: wordmark
                text: "esquizo"; color: "#f0eef2"
                font.pixelSize: 34; font.bold: true
            }
            Text {
                id: capmark
                anchors.left: wordmark.right
                text: "cap"; color: Theme.teal
                font: wordmark.font
            }
        }

        // ---- linha de status ----
        // Altura reservada mesmo com texto vazio, para o bloco central não pular de lugar
        // quando a mensagem real entrar no futuro.
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: 18
            Text {
                anchors.centerIn: parent
                text: tela.mensagem
                color: Theme.dim
                // 12, e não os 12,5 do desenho: `font.pixelSize` é int no Qt
                font.pixelSize: 12
                font.letterSpacing: 3
                SequentialAnimation on opacity {
                    running: tela.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.85; duration: 1200; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 0.35; duration: 1200; easing.type: Easing.InOutQuad }
                }
            }
        }
    }
}
