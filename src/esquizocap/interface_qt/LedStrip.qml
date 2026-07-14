import QtQuick

// Uma fita de LED inteira desenhada num único Canvas.
//
// Antes cada LED era um Rectangle com layer.enabled + Glow, ou seja um render
// target próprio na GPU por LED (até 720 no pior caso, recriados a cada tick).
// Aqui a fita toda sai numa passada só, e o glow é aplicado uma vez sobre ela.
Canvas {
    id: fita

    // lista de QColor vinda do controller (uma cor por LED)
    property var cores: []
    property real gap: 2
    property real raio: 2

    onCoresChanged: requestPaint()
    onGapChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();

        var n = cores.length;
        if (n === 0 || width <= 0)
            return;

        var larguraLed = (width - gap * (n - 1)) / n;
        if (larguraLed <= 0)
            return;

        for (var i = 0; i < n; i++) {
            ctx.fillStyle = cores[i];
            ctx.beginPath();
            ctx.roundedRect(i * (larguraLed + gap), 0, larguraLed, height, raio, raio);
            ctx.fill();
        }
    }
}
