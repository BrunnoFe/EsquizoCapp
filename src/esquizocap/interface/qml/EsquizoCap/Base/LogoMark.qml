import QtQuick
import QtQuick.Shapes
import EsquizoCap.Base

// Marca EsquizoCap — 12 LEDs percorrendo a roda de matiz + traço de EEG.
// O anel É a fita de LED; a roda de matiz É o espaço HSV que o modelo pode prever.
// liveHue >= 0 colapsa os 12 LEDs no matiz previsto pelo modelo (marca como indicador).
// Matizes/saturação/luminosidade vêm do Theme para que marca e paleta não divirjam.
Item {
    id: root

    property real size: 26
    property bool spin: true
    property int spinDuration: 14000
    property real liveHue: -1
    property color waveColor: "#f0eef2"
    property real phase: 0

    readonly property real u: size / 120
    readonly property var pts: [
        [60, 16, 7.5], [82, 21.9, 7], [98.1, 38, 6.5], [104, 60, 6],
        [98.1, 82, 5.5], [82, 98.1, 5], [60, 104, 4.6], [38, 98.1, 4.6],
        [21.9, 82, 5], [16, 60, 5.5], [21.9, 38, 6.5], [38, 21.9, 7]
    ]
    readonly property var hues: Theme.logoHues

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size

    Repeater {
        model: 12
        Rectangle {
            readonly property real d: root.pts[index][2] * 2 * root.u
            width: d
            height: d
            radius: d / 2
            x: root.pts[index][0] * root.u - d / 2
            y: root.pts[index][1] * root.u - d / 2
            color: root.liveHue >= 0
                ? Qt.hsla(root.liveHue / 360, Theme.logoSat, Theme.logoLum, 1)
                : Qt.hsla((((root.hues[index] + root.phase) % 360) + 360) % 360 / 360, Theme.logoSat, Theme.logoLum, 1)
            Behavior on color { ColorAnimation { duration: 320 } }
        }
    }

    // Abaixo de 24 px o traço central vira borrão: fica só o anel.
    Shape {
        anchors.fill: parent
        visible: root.size >= 24
        antialiasing: true
        ShapePath {
            strokeColor: root.waveColor
            strokeWidth: 6 * root.u
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            startX: 30 * root.u; startY: 60 * root.u
            PathLine { x: 40 * root.u; y: 60 * root.u }
            PathLine { x: 45.5 * root.u; y: 47 * root.u }
            PathLine { x: 52.5 * root.u; y: 73 * root.u }
            PathLine { x: 59 * root.u; y: 54 * root.u }
            PathLine { x: 65 * root.u; y: 65 * root.u }
            PathLine { x: 70 * root.u; y: 60 * root.u }
            PathLine { x: 90 * root.u; y: 60 * root.u }
        }
    }

    NumberAnimation on phase {
        running: root.spin && root.liveHue < 0
        from: 0; to: 360
        duration: root.spinDuration
        loops: Animation.Infinite
    }
}
