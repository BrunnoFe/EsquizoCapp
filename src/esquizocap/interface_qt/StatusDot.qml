import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: status
    property string label: ""
    property bool ok: true
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
    }
    Text { text: status.label; color: "#5a5a64"; font.pixelSize: 9
        Layout.alignment: Qt.AlignHCenter }
}
