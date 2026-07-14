// EsquizoCapView.qml — réplica fiel do protótipo 2a
// PySide6 / Qt Quick. Todos os valores de cor/estado vêm do `controller` (Python).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import Qt5Compat.GraphicalEffects

ApplicationWindow {
    id: win
    width: 1200; height: 760
    minimumWidth: 940; minimumHeight: 620
    visible: true
    // transparente: quem pinta o fundo é o `shell`, que tem os cantos arredondados
    color: "transparent"
    title: "EsquizoCap"
    flags: Qt.Window | Qt.FramelessWindowHint

    // fecha o hardware (Arduino/BITalino) antes da janela morrer de verdade
    onClosing: (close) => { controller.encerrarTudo() }

    // paleta de chrome
    readonly property color panelBg: "#0d1418"
    readonly property color cardBg: "#111d23"
    readonly property color stroke: Qt.rgba(1,1,1,0.06)
    readonly property color teal: "#14b8c4"
    readonly property color muted: "#8fa6ac"
    readonly property color dim: "#5f8a90"
    readonly property color verde: "#3fce8f"
    readonly property color vermelho: "#e2534b"
    readonly property int fontPx: 13

    FontLoader { id: mono; source: "" } // troque por IBM Plex Mono se quiser embutir
    readonly property string monoFam: "Consolas, 'IBM Plex Mono', monospace"
    readonly property string sansFam: "'Segoe UI', 'Space Grotesk', sans-serif"

    // ===================================================================
    //  SHELL — recorta a janela inteira num retângulo de cantos arredondados.
    //  Em tela cheia o layer desliga e os cantos voltam a ser retos.
    // ===================================================================
    Item {
        id: shell
        anchors.fill: parent
        layer.enabled: !controller.telaCheia
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: shell.width; height: shell.height; radius: 16
            }
        }

        // fundo da janela (antes era a cor da ApplicationWindow)
        Rectangle { anchors.fill: parent; color: "#060608" }

    // ===================================================================
    //  RAIL DO OPERADOR (esquerda)
    // ===================================================================
    Rectangle {
        id: rail
        visible: !controller.telaCheia
        width: 76; anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
        color: "#0b0b0e"
        z: 5
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: stroke }

        ColumnLayout {
            anchors.fill: parent
            anchors.topMargin: 16; anchors.bottomMargin: 16
            spacing: 20

            // engrenagem — setup/hardware
            RailButton { glyph: "⚙"; tip: "Setup / hardware"
                Layout.alignment: Qt.AlignHCenter
                onClicked: setupPanel.open = true }

            // status do hardware (o LSL não é mais exibido)
            ColumnLayout {
                spacing: 18; Layout.alignment: Qt.AlignHCenter
                StatusDot { label: "ARD"; ok: controller.arduinoConectado }
                StatusDot { label: "BIT"; ok: controller.bitalinoConectado }
            }

            Item { Layout.fillHeight: true }

            // configurações do app / tela cheia / sobre
            ColumnLayout {
                spacing: 12; Layout.alignment: Qt.AlignHCenter
                RailButton { iconName: "sliders"; tip: "Configurações do app"; small: true
                    onClicked: settingsPanel.open = true }
                RailButton { iconName: "expand"; tip: "Modo tela cheia"; small: true
                    onClicked: controller.alternarTelaCheia() }
                RailButton { glyph: "i"; tip: "Sobre"; small: true; italic: true }
            }
        }
    }

    // ===================================================================
    //  PALCO
    // ===================================================================
    Item {
        id: stage
        anchors { top: parent.top; bottom: parent.bottom; right: parent.right
                  left: rail.visible ? rail.right : parent.left }
        clip: true

        // fundo radial fixo
        Rectangle { anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#08333b" }
                GradientStop { position: 0.42; color: "#08282e" }
                GradientStop { position: 0.85; color: "#060608" }
            }
        }
        // bloom que segue a cor predita
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            RadialGradient {
                anchors.fill: parent
                horizontalOffset: 0; verticalOffset: -parent.height*0.06
                gradient: Gradient {
                    GradientStop { position: 0.0
                        color: controller.adquirindo
                            ? Qt.rgba(controller.corAoVivo.r, controller.corAoVivo.g, controller.corAoVivo.b, 0.18)
                            : Qt.rgba(0.05,0.29,0.32,0.13) }
                    GradientStop { position: Math.min(0.75, 0.52 + 0.18*controller.intensidadeGlow); color: "transparent" }
                }
                Behavior on opacity { NumberAnimation { duration: 500 } }
            }
        }

        // ---------- EEG de fundo (scroll infinito) ----------
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width; height: 240
            opacity: controller.opacidadeTracoEegPercentual / 100
            clip: true
            Row {
                id: eegRow
                property real ux: 0
                x: -ux
                Repeater {
                    model: 2
                    EegTrace {
                        width: stage.width; height: 240
                        stroke: controller.corAoVivo
                        lineW: controller.larguraTracoEeg
                        yScale: controller.escalaEixoYMicroVolts / 100
                    }
                }
            }
            NumberAnimation {
                target: eegRow; property: "ux"
                from: 0; to: stage.width
                duration: controller.velocidadeAnimacaoSegundos * 1000
                loops: Animation.Infinite; running: true
            }
        }

        // Faixa de arraste da janela. Declarada ANTES do topbar (mesmo z): assim o
        // topbar fica por cima e seus botões continuam clicáveis, enquanto textos e
        // logo (que não consomem eventos) deixam o clique chegar aqui. Uma faixa
        // larga é o que faz a janela arrastar de qualquer ponto da barra, e não só
        // na tira fininha que a altura implícita do RowLayout ocupava.
        MouseArea {
            id: dragBand
            visible: !controller.telaCheia
            anchors { top: parent.top; left: parent.left; right: parent.right }
            height: 64
            onPressed: win.startSystemMove()
        }

        // ---------- TOP BAR ----------
        RowLayout {
            id: topbar
            visible: !controller.telaCheia
            anchors { top: parent.top; left: parent.left; right: parent.right
                      topMargin: 20; leftMargin: 22; rightMargin: 22 }
            spacing: 12

            LogoMark {}
            Text { text: "esquizo"; color: "#f0eef2"; font.pixelSize: 18; font.bold: true
                Text { text: "cap"; color: teal; font: parent.font; anchors.left: parent.right } }

            Item { Layout.fillWidth: true }

            RowLayout {
                spacing: 8
                Rectangle { width: 7; height: 7; radius: 4; color: teal
                    SequentialAnimation on opacity { loops: Animation.Infinite
                        NumberAnimation { to: 0.35; duration: 800 }
                        NumberAnimation { to: 1.0; duration: 800 } } }
                Text { text: "MODO EXPOSIÇÃO"; color: dim; font.pixelSize: 12; font.letterSpacing: 2 }
            }
            // controles de janela
            RowLayout {
                spacing: 16; Layout.leftMargin: 12
                WinBtn { kind: "min"; onClicked: win.showMinimized() }
                WinBtn { kind: "max"; onClicked: controller.alternarTelaCheia() }
                WinBtn { kind: "close"; onClicked: win.close() }
            }
        }

        // ---------- CENTRO: anel + órbita + bandas ----------
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 20

            Item {
                Layout.alignment: Qt.AlignHCenter
                width: controller.tamanhoOrbita; height: controller.tamanhoOrbita
                Behavior on width  { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                Behavior on height { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

                // anel cônico girando
                Item {
                    id: ring; anchors.fill: parent
                    opacity: controller.adquirindo ? 1 : 0.25
                    Behavior on opacity { NumberAnimation { duration: controller.duracaoTransicaoCorSegundos*1000 } }
                    ConicalGradient {
                        id: conic; anchors.fill: parent
                        source: Rectangle { width: ring.width; height: ring.height; radius: width/2; visible: false }
                        gradient: Gradient {
                            GradientStop { position: 0.0;  color: "#4f5bd5" }
                            GradientStop { position: 0.16; color: "#2e86de" }
                            GradientStop { position: 0.33; color: "#14b8c4" }
                            GradientStop { position: 0.5;  color: "#22c9b0" }
                            GradientStop { position: 0.66; color: "#14b8c4" }
                            GradientStop { position: 0.83; color: "#2e86de" }
                            GradientStop { position: 1.0;  color: "#4f5bd5" }
                        }
                        // recorta o miolo -> vira anel (a máscara é a própria coroa:
                        // só a borda tem alpha, o miolo fica transparente)
                        layer.enabled: true
                        layer.effect: OpacityMask {
                            maskSource: Rectangle {
                                width: ring.width; height: ring.height
                                radius: width/2
                                color: "transparent"
                                border.width: controller.larguraAnelPx
                                border.color: "white"
                            }
                        }
                        RotationAnimator on rotation {
                            from: 0; to: 360
                            duration: controller.velocidadeAnelSegundos * 1000
                            loops: Animation.Infinite; running: true
                        }
                    }
                    layer.enabled: true
                    layer.effect: Glow {
                        radius: 16 * controller.intensidadeGlow; samples: 24; spread: 0.2
                        color: controller.adquirindo ? controller.corAoVivo : "transparent"
                    }
                }

                // órbita (gradiente radial + glow + pulsação)
                Rectangle {
                    id: orb
                    anchors.centerIn: parent
                    width: parent.width - controller.larguraAnelPx*2 - 20
                    height: width; radius: width/2
                    color: "transparent"
                    scale: controller.pulsacao
                    // gradiente radial real:
                    Rectangle { anchors.fill: parent; radius: width/2; color: "transparent"
                        RadialGradient {
                            anchors.fill: parent
                            horizontalOffset: -parent.width*0.12; verticalOffset: -parent.height*0.18
                            gradient: Gradient {
                                GradientStop { position: 0.0;  color: controller.corClara }
                                GradientStop { position: 0.46; color: controller.corAoVivo }
                                GradientStop { position: 1.0;  color: controller.corEscura }
                            }
                        }
                        layer.enabled: true
                        layer.effect: OpacityMask { maskSource: Rectangle { width: orb.width; height: orb.height; radius: width/2 } }
                    }
                    Behavior on scale { NumberAnimation { duration: 120 } }

                    layer.enabled: true
                    layer.effect: Glow {
                        radius: 96 * controller.intensidadeGlow; samples: 40; spread: 0.15
                        color: controller.adquirindo ? controller.corAoVivo : "transparent"
                    }

                    ColumnLayout {
                        anchors.centerIn: parent; spacing: 9
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter; spacing: 5
                            Text { text: controller.orbitaTextoPrincipal; color: "#04252b"
                                font.family: "'Fraunces', Georgia, serif"; font.pixelSize: 46 }
                            Text { text: controller.orbitaUnidade; color: "#04252b"
                                font.family: monoFam; font.pixelSize: 18; font.bold: true
                                Layout.alignment: Qt.AlignBottom; bottomPadding: 6 }
                        }
                        Text { text: controller.orbitaSubtexto; color: "#0a3d44"
                            font.pixelSize: 11; font.letterSpacing: 1.5
                            Layout.alignment: Qt.AlignHCenter }
                    }
                }
            }

            // pílulas de banda
            RowLayout {
                Layout.alignment: Qt.AlignHCenter; spacing: 7
                Repeater {
                    model: controller.bandasEegModel
                    Rectangle {
                        id: pilula
                        radius: 20; height: 26
                        // largura medida sempre em negrito: a banda ativa não pode
                        // alargar a pílula e empurrar as vizinhas de lado
                        implicitWidth: reguaBanda.implicitWidth + 24
                        color: modelData.active ? controller.corAoVivo : Qt.rgba(1,1,1,0.05)
                        opacity: modelData.dim ? 0.4 : 1
                        Behavior on color { ColorAnimation { duration: 400 } }
                        Text { id: reguaBanda; visible: false; text: modelData.name
                            font.pixelSize: 11; font.bold: true }
                        Text { anchors.centerIn: parent; text: modelData.name
                            color: modelData.active ? "#04252b" : dim
                            font.pixelSize: 11; font.bold: modelData.active }
                    }
                }
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: controller.corHex + " · " + controller.leituraHsv
                color: "#7fbcc2"; font.family: monoFam; font.pixelSize: 13; font.letterSpacing: 2
            }
        }

        // ---------- CONTROLES AO VIVO (colapsáveis, topo-direita) ----------
        ColumnLayout {
            id: liveCtl
            visible: controller.adquirindo
            anchors { top: parent.top; right: parent.right; topMargin: 80; rightMargin: 30 }
            spacing: 0; z: 6
            property bool open: false

            RailButton { iconName: "faders"; tip: "Controles ao vivo"; boxed: true
                Layout.alignment: Qt.AlignRight
                onClicked: liveCtl.open = !liveCtl.open }

            Rectangle {
                Layout.topMargin: 8
                width: 250; implicitHeight: liveCol.implicitHeight + 32
                radius: 14; color: Qt.rgba(0.04,0.055,0.067,0.9)
                border.color: stroke
                transformOrigin: Item.TopRight
                scale: liveCtl.open ? 1 : 0.8
                opacity: liveCtl.open ? 1 : 0
                Behavior on scale   { NumberAnimation { duration: 300; easing.type: Easing.OutBack } }
                Behavior on opacity { NumberAnimation { duration: 250 } }

                ColumnLayout {
                    id: liveCol; anchors.fill: parent; anchors.margins: 16; spacing: 12
                    Text { text: "CONTROLES AO VIVO"; color: dim; font.pixelSize: 10; font.letterSpacing: 1.4 }
                    LabeledSlider { label: "Saturação"; from: 0; to: 255
                        value: controller.saturacao; readout: controller.saturacao
                        accent: controller.corAoVivo
                        onMoved: controller.saturacao = value }
                    LabeledSlider { label: "Brilho"; from: 0; to: 255
                        value: controller.brilho; readout: controller.brilho
                        accent: controller.corAoVivo
                        onMoved: controller.brilho = value }
                    LabeledSlider {
                        label: controller.rotuloControleAmostragem
                        from: controller.modoAmplitude ? 100 : 128
                        to:   controller.modoAmplitude ? 2000 : 2048
                        stepSize: controller.modoAmplitude ? 50 : 32
                        value: controller.modoAmplitude ? controller.intervaloAmostragemMs : controller.tamanhoJanelaAmostras
                        readout: controller.leituraControleAmostragem; accent: controller.corAoVivo
                        onMoved: controller.modoAmplitude ? controller.intervaloAmostragemMs = value
                                                  : controller.tamanhoJanelaAmostras = value }
                }
            }
        }

        // ---------- FITAS DE LED (base) ----------
        ColumnLayout {
            id: ledArea
            anchors { left: parent.left; right: parent.right; leftMargin: 30; rightMargin: 30 }
            anchors.bottom: transport.visible ? transport.top : parent.bottom
            anchors.bottomMargin: 12
            spacing: 3; z: 2
            Repeater {
                // o model é a CONTAGEM de fitas (int estável). Antes o Repeater de
                // dentro usava `controller.coresLeds` como model: uma lista nova a
                // cada tick, o que fazia o Qt destruir e recriar todos os delegates.
                model: controller.quantidadeFitas
                LedStrip {
                    Layout.fillWidth: true; Layout.preferredHeight: 8
                    cores: controller.coresLeds
                    gap: controller.espacamentoLedsPx
                    layer.enabled: controller.adquirindo && controller.brilhoLedsPx > 0
                    layer.effect: Glow { radius: controller.brilhoLedsPx; samples: 12
                                         color: controller.corAoVivo; spread: 0.3 }
                }
            }
        }

        // ---------- TRANSPORTE ----------
        Rectangle {
            id: transport
            visible: !controller.telaCheia
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 62; color: Qt.rgba(0.024,0.024,0.031,0.6)
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: stroke }
            z: 2

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 30; anchors.rightMargin: 30
                spacing: 14
                Button {
                    id: btnParar
                    visible: controller.adquirindo
                    // tamanho próprio: antes o background lia o implicitWidth do
                    // contentItem, criando uma dependência circular que deformava o botão
                    implicitWidth: 122; implicitHeight: 40
                    padding: 0
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    background: Rectangle {
                        radius: 20
                        color: btnParar.hovered ? Qt.rgba(1,1,1,0.16) : Qt.rgba(1,1,1,0.08)
                        border.color: btnParar.hovered ? Qt.rgba(0.886,0.325,0.294,0.55) : stroke
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }
                    }
                    contentItem: Item {
                        Row {
                            anchors.centerIn: parent; spacing: 10
                            Rectangle { width: 11; height: 11; radius: 2; color: "#e2534b"
                                anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Parar"; color: "#f0eef2"; font.pixelSize: 13; font.bold: true
                                anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                    onClicked: controller.pararAquisicao()
                }
                Button {
                    id: btnComecar
                    visible: !controller.adquirindo
                    enabled: controller.podeIniciarAquisicao
                    opacity: enabled ? 1 : 0.5
                    implicitWidth: 190; implicitHeight: 40
                    padding: 0
                    HoverHandler { cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
                    background: Rectangle {
                        radius: 12
                        color: btnComecar.hovered ? Qt.lighter(teal, 1.15) : teal
                        Behavior on color { ColorAnimation { duration: 150 } }
                    }
                    contentItem: Text { text: "Começar aquisição"; color: "#042026"; font.bold: true
                        font.pixelSize: 14; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: controller.iniciarAquisicao()
                }
                // pílula GRAVANDO
                Rectangle {
                    visible: controller.adquirindo && controller.gravando
                    radius: 20; height: 28; implicitWidth: grow.implicitWidth + 22
                    color: Qt.rgba(0.886,0.325,0.294,0.14); border.color: Qt.rgba(0.886,0.325,0.294,0.3)
                    RowLayout { id: grow; anchors.centerIn: parent; spacing: 7
                        Rectangle { width: 8; height: 8; radius: 4; color: "#e2534b"
                            SequentialAnimation on opacity { loops: Animation.Infinite
                                NumberAnimation { to: 0.35; duration: 550 }
                                NumberAnimation { to: 1; duration: 550 } } }
                        Text { text: "GRAVANDO"; color: "#ff8079"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 0.5 } }
                }
                Text {
                    text: controller.estadoTexto
                    color: "#6f9096"; font.family: monoFam; font.pixelSize: 12
                }
                Item { Layout.fillWidth: true }
                Text { text: controller.leituraControleAmostragem; color: dim; font.pixelSize: 12 }
                Text { text: "Canal " + controller.canalBitalino + " · " + controller.sensor; color: dim; font.pixelSize: 12 }
            }
        }

        // ---------- sair da tela cheia ----------
        Button {
            id: btnSairTela
            visible: controller.telaCheia
            anchors { top: parent.top; left: parent.left; topMargin: 16; leftMargin: 20 }
            z: 12
            implicitWidth: 150; implicitHeight: 34
            padding: 0
            HoverHandler { cursorShape: Qt.PointingHandCursor }
            background: Rectangle { radius: 30
                color: btnSairTela.hovered ? Qt.rgba(0.07,0.1,0.12,0.9) : Qt.rgba(0.04,0.055,0.067,0.7)
                border.color: btnSairTela.hovered ? Qt.rgba(1,1,1,0.18) : stroke
                Behavior on color { ColorAnimation { duration: 150 } } }
            contentItem: Text { text: "Sair da tela cheia"
                color: btnSairTela.hovered ? "#f0eef2" : "#c3d6d9"; font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            onClicked: controller.alternarTelaCheia()
        }

        // ================= PAINEL DE SETUP (esquerda, desliza) =================
        Rectangle {
            id: setupBackdrop; anchors.fill: parent; color: Qt.rgba(0.016,0.016,0.024,0.55)
            visible: setupPanel.open; z: 8
            MouseArea { anchors.fill: parent; onClicked: setupPanel.open = false }
        }
        SlidePanel {
            id: setupPanel; side: "left"; title: "CONFIGURAÇÃO"; z: 9
            content: ColumnLayout {
                width: parent.width; spacing: 10
                Accordion { title: "Modelo de ML"; dotColor: verde; expanded: true
                    body: Dropdown {
                        width: parent.width
                        model: controller.modelosDisponiveis
                        currentIndex: controller.modelosDisponiveis.indexOf(controller.modeloSelecionado)
                        onActivated: controller.modeloSelecionado = currentValue
                    } }
                Accordion { title: "Arduino"
                    dotColor: controller.arduinoConectado ? verde : vermelho
                    badge: controller.arduinoStatusTexto
                    body: ColumnLayout { spacing: 8; width: parent.width
                        RowLayout { Layout.fillWidth: true; spacing: 7
                            Dropdown { Layout.fillWidth: true
                                model: controller.portasSeriaisDisponiveis
                                currentIndex: controller.portasSeriaisDisponiveis.indexOf(controller.portaArduino)
                                onActivated: controller.portaArduino = currentValue }
                            Dropdown { Layout.preferredWidth: 92
                                model: controller.baudRatesDisponiveis
                                currentIndex: controller.baudRatesDisponiveis.indexOf(controller.baudRateArduino)
                                onActivated: controller.baudRateArduino = currentValue } }
                        ConnectButton { Layout.fillWidth: true
                            conectado: controller.arduinoConectado
                            onClicked: controller.alternarConexaoArduino() }
                        Text { text: "Modo de luminosidade das fitas"; color: dim; font.pixelSize: 11 }
                        Flow { Layout.fillWidth: true; spacing: 6
                            Repeater { model: [[1,"Um a um"],[2,"Todos"],[3,"Gradiente"],[4,"A partir do centro"]]
                                Chip { text: modelData[1]; on: controller.modoLuminosidade === modelData[0]
                                    onClicked: controller.definirModoLuminosidade(modelData[0]) } } } } }
                Accordion { title: "BITalino"
                    dotColor: controller.bitalinoConectado ? verde : vermelho
                    badge: controller.bitalinoStatusTexto
                    body: ColumnLayout { spacing: 8; width: parent.width
                        RowLayout { Layout.fillWidth: true; spacing: 7
                            Dropdown { Layout.fillWidth: true
                                model: controller.canaisBitalinoDisponiveis
                                currentIndex: controller.canaisBitalinoDisponiveis.indexOf(controller.canalBitalino)
                                onActivated: controller.canalBitalino = currentValue }
                            Dropdown { Layout.fillWidth: true
                                model: controller.macsBitalinoDisponiveis
                                currentIndex: controller.macsBitalinoDisponiveis.indexOf(controller.macBitalino)
                                onActivated: controller.macBitalino = currentValue } }
                        ConnectButton { Layout.fillWidth: true
                            conectado: controller.bitalinoConectado
                            onClicked: controller.alternarConexaoBitalino() }
                        Text { text: "Tipo de sensor"; color: dim; font.pixelSize: 11 }
                        Flow { Layout.fillWidth: true; spacing: 6
                            Repeater { model: ["EEG","EDA","EOG","ECG","EMG"]
                                Chip { text: modelData; on: controller.sensor === modelData
                                    onClicked: controller.definirSensor(modelData) } } } } }
                Accordion { title: "Modo de análise"; dotColor: "#e3a52b"; expanded: true
                    body: Segmented { options: ["Amplitude","Frequência"]
                        current: controller.modoAnalise; onPicked: controller.definirModoAnalise(opt) } }
                RowLayout {
                    width: parent.width
                    Rectangle { Layout.fillWidth: true; height: 46; radius: 11; color: cardBg; border.color: stroke
                        RowLayout { anchors.fill: parent; anchors.margins: 14
                            Text { text: "Gravar aquisição"; color: "#c3d6d9"; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Toggle { on: controller.gravando; onClicked: controller.alternarGravacao() } } }
                }
            }
            footer: Button {
                id: btnSetupComecar
                width: parent.width; height: 48
                padding: 0
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                background: Rectangle { radius: 12
                    color: btnSetupComecar.hovered ? Qt.lighter(teal, 1.15) : teal
                    Behavior on color { ColorAnimation { duration: 150 } } }
                contentItem: Text { text: "Começar aquisição"; color: "#042026"; font.bold: true
                    font.pixelSize: 15; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: { controller.iniciarAquisicao(); setupPanel.open = false }
            }
        }

        // ============ PAINEL DE CONFIGURAÇÕES DO APP (direita, desliza) ============
        Rectangle {
            id: setBackdrop; anchors.fill: parent; color: Qt.rgba(0.016,0.016,0.024,0.55)
            visible: settingsPanel.open; z: 8
            MouseArea { anchors.fill: parent; onClicked: settingsPanel.open = false }
        }
        SlidePanel {
            id: settingsPanel; side: "right"; title: "CONFIGURAÇÕES DO APP"; z: 9; width: 340
            content: ColumnLayout {
                width: parent.width; spacing: 14
                SettingsCard { title: "Fitas de LED"
                    body: ColumnLayout { width: parent.width; spacing: 13
                        SetSlider { label: "Nº de LEDs por fita"; from: 6; to: 120; step: 2
                            value: controller.quantidadeLeds; readout: controller.quantidadeLeds
                            onMoved: controller.quantidadeLeds = value }
                        SetSlider { label: "Nº de fitas"; from: 1; to: 6; step: 1
                            value: controller.quantidadeFitas; readout: controller.quantidadeFitas
                            onMoved: controller.quantidadeFitas = value }
                        SetSlider { label: "Brilho dos LEDs (glow)"; from: 0; to: 16; step: 1
                            value: controller.brilhoLedsPx; readout: controller.brilhoLedsPx + " px"
                            onMoved: controller.brilhoLedsPx = value }
                        SetSlider { label: "Espaço entre LEDs"; from: 0; to: 6; step: 1
                            value: controller.espacamentoLedsPx; readout: controller.espacamentoLedsPx + " px"
                            onMoved: controller.espacamentoLedsPx = value } } }
                SettingsCard { title: "Animação & feel"
                    body: ColumnLayout { width: parent.width; spacing: 13
                        SetSlider { label: "Tamanho do círculo"; from: 200; to: 380; step: 4
                            value: controller.tamanhoOrbita; readout: controller.tamanhoOrbita + " px"
                            onMoved: controller.tamanhoOrbita = value }
                        SetSlider { label: "Intensidade do palco (glow)"; from: 0.3; to: 1.8; step: 0.05
                            value: controller.intensidadeGlow; readout: controller.intensidadeGlow.toFixed(2) + "×"
                            onMoved: controller.intensidadeGlow = value }
                        SetSlider { label: "Rotação do anel"; from: 4; to: 40; step: 1
                            value: controller.velocidadeAnelSegundos; readout: controller.velocidadeAnelSegundos + " s"
                            onMoved: controller.velocidadeAnelSegundos = value }
                        SetSlider { label: "Espessura do anel"; from: 6; to: 30; step: 1
                            value: controller.larguraAnelPx; readout: controller.larguraAnelPx + " px"
                            onMoved: controller.larguraAnelPx = value }
                        SetSlider { label: "Velocidade da pulsação"; from: 1.5; to: 6; step: 0.1
                            value: controller.velocidadePulsoSegundos; readout: controller.velocidadePulsoSegundos.toFixed(1) + " s"
                            onMoved: controller.velocidadePulsoSegundos = value }
                        SetSlider { label: "Amplitude da pulsação"; from: 0; to: 12; step: 1
                            value: controller.amplitudePulsoPercentual; readout: controller.amplitudePulsoPercentual + " %"
                            onMoved: controller.amplitudePulsoPercentual = value }
                        SetSlider { label: "Espessura da linha EEG"; from: 0.5; to: 4; step: 0.1
                            value: controller.larguraTracoEeg; readout: controller.larguraTracoEeg.toFixed(1)
                            onMoved: controller.larguraTracoEeg = value }
                        SetSlider { label: "Opacidade do EEG"; from: 5; to: 60; step: 1
                            value: controller.opacidadeTracoEegPercentual; readout: controller.opacidadeTracoEegPercentual + " %"
                            onMoved: controller.opacidadeTracoEegPercentual = value }
                        SetSlider { label: "Suavidade da transição de cor"; from: 0.1; to: 1.5; step: 0.05
                            value: controller.duracaoTransicaoCorSegundos; readout: controller.duracaoTransicaoCorSegundos.toFixed(2) + " s"
                            onMoved: controller.duracaoTransicaoCorSegundos = value } } }
                SettingsCard { title: "Gráfico em tempo real"
                    body: ColumnLayout { width: parent.width; spacing: 13
                        SetSlider { label: "Escala do eixo Y"; from: 20; to: 300; step: 10
                            value: controller.escalaEixoYMicroVolts; readout: "±" + controller.escalaEixoYMicroVolts + " µV"
                            onMoved: controller.escalaEixoYMicroVolts = value }
                        SetSlider { label: "Janela de dados"; from: 2; to: 20; step: 1
                            value: controller.janelaGraficoSegundos; readout: controller.janelaGraficoSegundos + " s"
                            onMoved: controller.janelaGraficoSegundos = value }
                        SetSlider { label: "Velocidade da animação"; from: 3; to: 16; step: 1
                            value: controller.velocidadeAnimacaoSegundos; readout: controller.velocidadeAnimacaoSegundos + " s/ciclo"
                            onMoved: controller.velocidadeAnimacaoSegundos = value }
                        RowLayout { width: parent.width
                            Text { text: "Taxa de amostragem"; color: dim; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Text { text: "1000 Hz · do dispositivo"; color: dim; font.family: monoFam; font.pixelSize: 12 } } } }
            }
        }
    }
    }

    // fecha painéis com ESC / alterna tela cheia com F11
    Shortcut { sequence: "Escape"; onActivated: { setupPanel.open=false; settingsPanel.open=false } }
    Shortcut { sequence: "F11"; onActivated: controller.alternarTelaCheia() }
    onVisibilityChanged: {}
    Connections { target: controller
        function onEstadoMudou() { if (controller.telaCheia && win.visibility !== Window.FullScreen) win.showFullScreen()
                               else if (!controller.telaCheia && win.visibility === Window.FullScreen) win.showNormal() } }

    // ---- diálogo de gravação: aberto quando o controller sinaliza que há dados
    //      gravados esperando um destino (ver EsquizoController._finalizar_aquisicao) ----
    FileDialog {
        id: dialogoGravacao
        title: "Salvar gravação"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Planilha Excel (*.xlsx)"]
        currentFile: "file:///" + encodeURIComponent(controller.nomeSugeridoGravacao) + ".xlsx"
        onAccepted: controller.salvarGravacao(selectedFile.toString())
        onRejected: controller.descartarGravacao()
    }
    Connections { target: controller
        function onEstadoMudou() { if (controller.gravacaoPendente && !dialogoGravacao.visible) dialogoGravacao.open() } }

    // ---- banner de erro dispensável (falha de conexão, falha ao gravar...) ----
    Rectangle {
        id: bannerErro
        visible: controller.erroTexto.length > 0
        anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 16 }
        z: 20; radius: 10; height: 40
        implicitWidth: erroRow.implicitWidth + 28
        color: "#2a1416"; border.color: Qt.rgba(0.886,0.325,0.294,0.4)
        RowLayout { id: erroRow; anchors.centerIn: parent; spacing: 10
            Text { text: controller.erroTexto; color: "#ffb4ae"; font.pixelSize: 12 }
            Button { implicitWidth: 22; implicitHeight: 22; padding: 0
                background: Rectangle { color: "transparent" }
                contentItem: Text { text: "✕"; color: "#ffb4ae"; font.pixelSize: 12
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                onClicked: controller.limparErro() } }
    }
}
