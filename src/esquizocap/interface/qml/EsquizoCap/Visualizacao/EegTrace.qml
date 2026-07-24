import QtQuick

// Traço de EEG desenhado via Canvas (mesma série do protótipo).
Canvas {
    id: c
    property color stroke: "#14b8c4"
    property real lineW: 1.5
    property real yScale: 1.0
    readonly property var ys: [60,55,68,50,72,45,90,30,64,58,62,54,66,48,58,62,52,70,44,80,35,60,57,63,53,67,49,58,61,55,65,51,60,42,88,32,64,56,62,58]
    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineW;
        ctx.lineJoin = "round";
        ctx.beginPath();
        var n = ys.length;
        var step = width / n;
        for (var i = 0; i < n; i++) {
            var yy = height/2 + (ys[i] - 60) * yScale;
            var xx = i * step;
            if (i === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
        }
        ctx.stroke();
    }
    onStrokeChanged: requestPaint()
    onLineWChanged: requestPaint()
    onYScaleChanged: requestPaint()
    onWidthChanged: requestPaint()
    Component.onCompleted: requestPaint()
}
