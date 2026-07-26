import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import EsquizoCap.Layout 1.0

ColumnLayout {
    width: parent ? parent.width : 0
    spacing: 14

    SettingsCard {
        title: "AVISO DE SIMULAÇÃO"
        body: ColumnLayout {
            width: parent.width
            spacing: 16
            LinhaOpcao {
                titulo: "Borda de destaque na janela"
                descricao: "Contorna o app inteiro enquanto algum hardware está simulado. "
                    + "O selo na barra de topo e a marca nos indicadores aparecem sempre."
                ligado: controller.bordaDeSimulacao
                onAlternado: (novoValor) => controller.definirBordaDeSimulacao(novoValor)
            }
        }
    }

    SettingsCard {
        title: "JANELA"
        body: ColumnLayout {
            width: parent.width
            spacing: 16
            LinhaOpcao {
                titulo: "Iniciar em tela cheia"
                descricao: "Para a instalação em projetor, que sempre abre assim."
                ligado: controller.iniciarEmTelaCheia
                onAlternado: (novoValor) => controller.definirIniciarEmTelaCheia(novoValor)
            }
            LinhaOpcao {
                titulo: "Lembrar posição e tamanho"
                descricao: "Reabre a janela onde ela estava. Desligar descarta a geometria guardada."
                ligado: controller.lembrarGeometriaJanela
                onAlternado: (novoValor) => controller.definirLembrarGeometriaJanela(novoValor)
            }
            LinhaOpcao {
                titulo: "Selo \"MODO EXPOSIÇÃO\""
                descricao: "O indicador pulsante na barra de topo."
                ligado: controller.mostrarSeloExposicao
                onAlternado: (novoValor) => controller.definirMostrarSeloExposicao(novoValor)
            }
        }
    }

    SettingsCard {
        title: "APARÊNCIA"
        body: ColumnLayout {
            width: parent.width
            spacing: 14
            Text {
                Layout.fillWidth: true
                text: "Os controles de aparência ficam no painel lateral direito (ícone de faders). "
                    + "Os valores são guardados e voltam na próxima abertura."
                color: "#8fa6ac"; font.pixelSize: 11; wrapMode: Text.WordWrap
            }
            BotaoSecundario {
                text: "Restaurar aparência padrão"
                destrutivo: true
                onClicked: controller.restaurarAparenciaPadrao()
            }
        }
    }
}
