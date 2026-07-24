import QtQuick
import QtQuick.Shapes

// Ícones vetoriais desenhados (sliders, faders, expand).
Item {
    id: g
    property string name: "sliders"
    property color color: "#7f9aa0"
    width: 18; height: 18
    // sliders verticais (config do app)
    Shape { visible: g.name === "sliders"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 5; startY: 3; PathLine { x: 5; y: 15 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 9; startY: 3; PathLine { x: 9; y: 15 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 13; startY: 3; PathLine { x: 13; y: 15 } }
    }
    // faders horizontais (controles ao vivo)
    Shape { visible: g.name === "faders"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; capStyle: ShapePath.RoundCap; fillColor: "transparent"
            startX: 3; startY: 5; PathLine { x: 15; y: 5 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; capStyle: ShapePath.RoundCap; fillColor: "transparent"
            startX: 3; startY: 10; PathLine { x: 15; y: 10 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; capStyle: ShapePath.RoundCap; fillColor: "transparent"
            startX: 3; startY: 15; PathLine { x: 15; y: 15 } }
    }
    Repeater { model: g.name === "faders" ? [[12,5],[7,10],[13,15]] : []
        Rectangle { x: modelData[0]-2; y: modelData[1]-2; width: 4; height: 4; radius: 2; color: g.color } }
    // expand (tela cheia)
    Shape { visible: g.name === "expand"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 3; startY: 7; PathLine { x: 3; y: 3 } PathLine { x: 7; y: 3 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 15; startY: 7; PathLine { x: 15; y: 3 } PathLine { x: 11; y: 3 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 3; startY: 11; PathLine { x: 3; y: 15 } PathLine { x: 7; y: 15 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 15; startY: 11; PathLine { x: 15; y: 15 } PathLine { x: 11; y: 15 } }
    }
}
