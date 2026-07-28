pragma Singleton
import QtQuick

// A paleta do app, num lugar só.
//
// Até aqui as cores viviam como `readonly property` dentro de EsquizoCapView.qml, o que
// só alcança quem está DENTRO daquele arquivo — todo componente extraído (Base/, Controles/,
// Configuracoes/) acabou redigitando os mesmos hexadecimais na mão. Um singleton resolve
// isso para quem nascer daqui em diante; os componentes antigos continuam com suas cópias
// e migram quando forem tocados (ver docs/notas-futuras.md).
QtObject {
    // ---- chrome ----
    readonly property color panelBg: "#0d1418"
    readonly property color cardBg: "#111d23"
    readonly property color fundoJanela: "#060608"
    readonly property color stroke: Qt.rgba(1, 1, 1, 0.06)
    readonly property color strokeForte: Qt.rgba(1, 1, 1, 0.08)

    // ---- texto ----
    readonly property color teal: "#14b8c4"
    readonly property color muted: "#8fa6ac"
    readonly property color dim: "#5f8a90"

    // ---- semântica ----
    readonly property color verde: "#3fce8f"
    readonly property color vermelho: "#e2534b"
    // Âmbar puxado para o dourado em vez do amarelo puro: convive melhor com o teal e com
    // o fundo quase-preto sem gritar. Entrou com as severidades de aviso.
    readonly property color ambar: "#e0a33a"

    // ---- marca ----
    // A roda de matiz da LogoMark: 12 LEDs percorrendo o círculo inteiro sem repetir cor.
    // NÃO é paleta de interface — nada além da marca deve usar estes valores. O anel
    // representa a fita de LED, e a roda representa o espaço HSV que o modelo prevê.
    readonly property var logoHues: [186, 160, 120, 76, 44, 20, 350, 320, 288, 262, 232, 206]
    readonly property real logoSat: 0.62
    readonly property real logoLum: 0.57

    // ---- tipografia ----
    readonly property int fontPx: 13
    readonly property string monoFam: "Consolas, 'IBM Plex Mono', monospace"
    readonly property string sansFam: "'Segoe UI', 'Space Grotesk', sans-serif"

    // ---- sobreposições ----
    // Valores que os overlays do app já compartilhavam por cópia (JanelaConfiguracoes,
    // painéis deslizantes): backdrop, tempos e curvas de animação.
    readonly property color backdrop: Qt.rgba(0.016, 0.016, 0.024, 0.62)
    readonly property int duracaoFade: 180
    readonly property int duracaoEscala: 220

    // ---- severidade ----
    // A cor de destaque de cada nível. As chaves são os valores de
    // `aplicacao.catalogo_erros.Severidade`, que é o que o controller expõe como string.
    function corDaSeveridade(severidade) {
        switch (severidade) {
        case "critico": return vermelho
        case "erro":    return vermelho
        case "aviso":   return ambar
        case "info":    return teal
        }
        return muted
    }

    // Glifo mostrado no cabeçalho da caixa. Texto puro, e não ícone de arquivo, para que a
    // caixa não dependa do conjunto de ícones carregado.
    function glifoDaSeveridade(severidade) {
        switch (severidade) {
        case "critico": return "✕"
        case "erro":    return "!"
        case "aviso":   return "!"
        case "info":    return "i"
        }
        return "?"
    }

    function tituloPadraoDaSeveridade(severidade) {
        switch (severidade) {
        case "critico": return "ERRO"
        case "erro":    return "ERRO"
        case "aviso":   return "AVISO"
        case "info":    return "INFORMAÇÃO"
        }
        return "MENSAGEM"
    }
}
