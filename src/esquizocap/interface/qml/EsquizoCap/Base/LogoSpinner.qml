import QtQuick
import QtQuick.Shapes

// Marca EsquizoCap em movimento — onda de tamanho + cor girando em sentido horário.
Item {
    id: root

    property real size: 120
    property bool running: true
    property int cycle: 1800
    property real spread: 0.85
    property real liveHue: -1
    property color waveColor: "#f0eef2"
    property real phase: 0

    readonly property real u: size / 120
    readonly property var pts: [
        [60, 16], [82, 21.9], [98.1, 38], [104, 60], [98.1, 82], [82, 98.1],
        [60, 104], [38, 98.1], [21.9, 82], [16, 60], [21.9, 38], [38, 21.9]
    ]
    readonly property var hues: [186, 160, 120, 76, 44, 20, 350, 320, 288, 262, 232, 206]

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size

    function bump(index) {
        var d = (phase - index / 12) % 1
        if (d < 0) d += 1
        if (d > 0.5) d -= 1
        var w = Math.max(0, 1 - Math.abs(d) / (0.5 * spread))
        return w * w * (3 - 2 * w)          // smoothstep
    }

    Repeater {
        model: 12
        Rectangle {
            readonly property real k: root.bump(index)
            readonly property real d: (4.2 + 4.4 * k) * root.u * 2
            width: d
            height: d
            radius: d / 2
            x: root.pts[index][0] * root.u - d / 2
            y: root.pts[index][1] * root.u - d / 2
            opacity: 0.42 + 0.58 * k
            color: root.liveHue >= 0
                ? Qt.hsla(root.liveHue / 360, 0.62, 0.57, 1)
                : Qt.hsla((((root.hues[index] + root.phase * 360) % 360) + 360) % 360 / 360,
                          0.62, 0.5 + 0.1 * k, 1)
        }
    }

    Shape {
        anchors.fill: parent
        visible: root.size >= 40
        antialiasing: true
        opacity: 0.55 + 0.45 * root.bump(0)
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
        running: root.running
        from: 0; to: 1
        duration: root.cycle
        loops: Animation.Infinite
    }
}
