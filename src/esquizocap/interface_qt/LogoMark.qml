import QtQuick
import QtQuick.Layouts

// Wordmark = espectro EEG (barras Delta..Gamma)
RowLayout {
    spacing: 4
    Repeater {
        model: [[10,"#4f5bd5"],[17,"#2e86de"],[24,"#14b8c4"],[14,"#e7b84b"],[8,"#e2734b"]]
        Rectangle { width: 5; height: modelData[0]; radius: 2; color: modelData[1]
            Layout.alignment: Qt.AlignBottom }
    }
}
