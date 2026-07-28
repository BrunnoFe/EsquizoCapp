import QtQuick
import QtQuick.Layouts

// A marca em movimento como indicador de espera INLINE — o BusyIndicator da casa.
//
// Mesmo desenho da `LogoSpinner` que a tela de carregamento usa, com outra personalidade:
// lá a onda é larga e lenta (spread 0.85, ciclo 1800 ms), uma respiração; aqui ela é SECA
// — um LED estoura e apaga rápido, do mesmo jeito que o modo "Um a um" do firmware acende
// a fita. É o que faz uma espera de 18 px parecer atividade em vez de decoração parada.
//
// Abaixo de 40 px a `LogoSpinner` já deixa de desenhar o traço de EEG sozinha, então o
// tamanho pequeno não precisa de nenhum tratamento especial aqui.
//
// REGRA DE USO: no máximo UM indicador visível por região da tela ao mesmo tempo. Dois
// anéis girando lado a lado não dizem "duas coisas acontecendo", dizem "a tela travou".
// Quando dois estados de espera coincidem, quem chama escolhe um — o mais específico — e
// suprime o outro no próprio `running`. Ver o painel de setup em `App/EsquizoCapView.qml`.
RowLayout {
    id: raiz

    property real size: 18
    property bool running: true
    // Texto opcional ao lado. Vazio deixa só o anel.
    property string rotulo: ""

    spacing: 10

    visible: running
    // Não reserva espaço quando não está rodando: um vão fixo faria a linha inteira pular
    // de lugar ao entrar e sair da espera. `opacity: 0` não serviria — continuaria ocupando
    // o espaço, que é justamente o defeito.
    Layout.preferredWidth: running ? implicitWidth : 0
    Layout.preferredHeight: running ? implicitHeight : 0

    // A `LogoSpinner` amarra o próprio `width`/`height` ao `size`; deixá-la direto num
    // layout poria os dois disputando a mesma propriedade. Esta caixa absorve o layout e a
    // marca vive centrada dentro dela.
    Item {
        Layout.preferredWidth: raiz.size
        Layout.preferredHeight: raiz.size

        LogoSpinner {
            anchors.centerIn: parent
            size: raiz.size
            cycle: 1100
            spread: 0.45
            // PARA de verdade quando a espera acaba, e não só some. Um Item invisível com
            // NumberAnimation infinita segue acordando o render loop — numa instalação que
            // fica horas aberta, isso é GPU queimada para desenhar nada.
            running: raiz.running
        }
    }

    Text {
        visible: raiz.rotulo !== ""
        text: raiz.rotulo
        color: Theme.muted
        font.pixelSize: Theme.fontPx
        font.family: Theme.sansFam
    }
}
