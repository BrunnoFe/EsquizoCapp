import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: status
    property string label: ""
    property bool ok: true
    // A marca de simulado é SEPARADA da cor do ponto, de propósito: o ponto responde
    // "conectado ou não", e um dispositivo simulado conecta de verdade. Misturar as duas
    // coisas numa cor só faria um fake conectado parecer hardware real.
    property bool simulado: false
    spacing: 5; Layout.alignment: Qt.AlignHCenter
    Rectangle {
        id: dot
        Layout.alignment: Qt.AlignHCenter
        // dentro de um layout, width/height são ignorados (comportamento indefinido):
        // o tamanho tem de vir por implicitWidth/implicitHeight
        implicitWidth: 9; implicitHeight: 9; radius: 4.5
        color: status.ok ? "#3fce8f" : "#e2534b"
        Behavior on color { ColorAnimation { duration: 220 } }
        // brilho suave (sem layer.enabled: o layer recortaria o halo ao bounds do ponto)
        Rectangle { anchors.centerIn: parent; width: 17; height: 17; radius: 8.5
            color: dot.color; opacity: 0.25; z: -1 }
        // Anel âmbar: legível mesmo com o ponto verde por baixo.
        Rectangle { visible: status.simulado; anchors.centerIn: parent
            width: 19; height: 19; radius: 9.5
            color: "transparent"; border.width: 1.5; border.color: "#e8a33d" }
    }
    Text { text: status.label; color: status.simulado ? "#e8a33d" : "#5a5a64"; font.pixelSize: 9
        Layout.alignment: Qt.AlignHCenter
        Behavior on color { ColorAnimation { duration: 220 } } }
    Text { visible: status.simulado; text: "SIM"; color: "#e8a33d"; font.pixelSize: 8
        font.bold: true; font.letterSpacing: 0.6
        Layout.alignment: Qt.AlignHCenter }
}
