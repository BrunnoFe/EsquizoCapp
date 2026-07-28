import QtQuick
import QtQuick.Shapes

// Ícones vetoriais desenhados (sliders, faders, expand, plugue, gota, engrenagem, recarregar).
//
// Todo ícone do rail vive aqui: um nome desconhecido não desenha nada e não
// levanta erro, então tests/interface/test_icones.py cobre cada nome em uso.
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
    // plugue (setup/hardware): dois pinos, corpo e cabo
    // ocupa a caixa quase inteira de propósito — num corpo menor os dois pinos colam um no
    // outro em 18 px e o desenho deixa de ser reconhecível como plugue.
    Shape { visible: g.name === "plugue"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 6.5; startY: 2; PathLine { x: 6.5; y: 6.5 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 11.5; startY: 2; PathLine { x: 11.5; y: 6.5 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 3; startY: 6.5; PathLine { x: 15; y: 6.5 } PathLine { x: 15; y: 12 } PathLine { x: 3; y: 12 } PathLine { x: 3; y: 6.5 } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 9; startY: 12; PathLine { x: 9; y: 16 } }
    }
    // gota de cor (aparência): ápice em cima, base redonda
    Shape { visible: g.name === "gota"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 9; startY: 3
            PathLine { x: 13.5; y: 10.5 }
            PathArc { x: 4.5; y: 10.5; radiusX: 6.4; radiusY: 6.4
                direction: PathArc.Clockwise; useLargeArc: true }
            PathLine { x: 9; y: 3 } }
    }
    // recarregar (resetar seção): arco quase fechado + farpa da seta na ponta de cima
    //
    // A abertura no topo é o que faz o desenho ler como "volta ao começo" e não como um
    // círculo qualquer. Um único Shape porque test_icones conta formas e exige exatamente 1.
    Shape { visible: g.name === "recarregar"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
            startX: 13.5; startY: 4.5
            PathArc { x: 11.5; y: 3.6; radiusX: 6; radiusY: 6
                direction: PathArc.Counterclockwise; useLargeArc: true } }
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            startX: 13.8; startY: 1
            PathLine { x: 13.8; y: 5 }
            PathLine { x: 10; y: 5 } }
    }
    // engrenagem (configurações): miolo vazado + 6 dentes radiais
    // (8 dentes vira mancha em 18 px)
    Shape { visible: g.name === "engrenagem"; anchors.fill: parent
        ShapePath { strokeColor: g.color; strokeWidth: 2; fillColor: "transparent"
            startX: 6; startY: 9
            PathArc { x: 12; y: 9; radiusX: 3; radiusY: 3; direction: PathArc.Clockwise }
            PathArc { x: 6; y: 9; radiusX: 3; radiusY: 3; direction: PathArc.Clockwise } }
    }
    Repeater { model: g.name === "engrenagem" ? 6 : 0
        Rectangle {
            readonly property real ang: index * Math.PI / 3
            width: 2; height: 4; radius: 1; color: g.color
            x: 9 + 5.5 * Math.sin(ang) - width / 2
            y: 9 - 5.5 * Math.cos(ang) - height / 2
            rotation: index * 60
        } }
}
