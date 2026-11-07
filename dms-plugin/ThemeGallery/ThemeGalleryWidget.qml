import QtQuick
import Quickshell
import Quickshell.Io
import qs.Common
import qs.Widgets
import qs.Modules.Plugins

// Leisten-Widget: Palette-Symbol + Name des aktiven Themes.
// Klick öffnet eine Galerie aller themectl-Themes mit Wallpaper und Farben.
PluginComponent {
    id: root

    layerNamespacePlugin: "theme-gallery"

    readonly property string themectl: Quickshell.env("HOME") + "/.local/bin/themectl"
    property var themes: []
    readonly property var currentTheme: themes.find(t => t.current) || null

    Process {
        id: listProc
        command: [root.themectl, "list", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.themes = JSON.parse(this.text) } catch (e) { root.themes = [] }
            }
        }
    }

    function refresh() {
        if (!listProc.running)
            listProc.running = true
    }

    function applyTheme(id) {
        Quickshell.execDetached([root.themectl, "apply", id])
        root.themes = root.themes.map(t => Object.assign({}, t, { current: t.id === id }))
        refreshTimer.restart()
    }

    // Nach einem Wechsel (auch über Launcher/Hotkey) den Namen in der Leiste aktuell halten
    Timer {
        id: refreshTimer
        interval: 1500
        onTriggered: root.refresh()
    }
    Timer {
        interval: 30000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Component.onCompleted: refresh()

    horizontalBarPill: Component {
        Row {
            spacing: Theme.spacingXS
            DankIcon {
                name: "palette"
                size: root.iconSize
                color: Theme.surfaceText
                anchors.verticalCenter: parent.verticalCenter
            }
            StyledText {
                text: root.currentTheme ? root.currentTheme.name : ""
                visible: text.length > 0
                font.pixelSize: Theme.fontSizeSmall
                color: Theme.surfaceText
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    verticalBarPill: Component {
        DankIcon {
            name: "palette"
            size: root.iconSize
            color: Theme.surfaceText
        }
    }

    popoutWidth: 560
    popoutHeight: 600

    popoutContent: Component {
        PopoutComponent {
            id: popout

            headerText: "Themes"
            detailsText: root.themes.length + " gespeichert · Klick zum Anwenden"

            Component.onCompleted: root.refresh()

            Item {
                width: parent.width
                implicitHeight: root.popoutHeight - popout.headerHeight - popout.detailsHeight - Theme.spacingXL

                // Omarchy-Themes online suchen (öffnet ein Terminal mit Suche + Auswahl)
                Rectangle {
                    id: searchButton
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: searchRow.implicitWidth + Theme.spacingL * 2
                    height: 36
                    radius: Theme.cornerRadius
                    color: searchMouse.containsMouse ? Theme.surfaceContainerHigh : Theme.surfaceContainer
                    border.color: Theme.outlineStrong
                    border.width: 1

                    Row {
                        id: searchRow
                        anchors.centerIn: parent
                        spacing: Theme.spacingS
                        DankIcon {
                            name: "travel_explore"
                            size: 18
                            color: Theme.surfaceText
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        StyledText {
                            text: "Omarchy-Themes online suchen…"
                            font.pixelSize: Theme.fontSizeSmall
                            color: Theme.surfaceText
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: searchMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            Quickshell.execDetached(["ghostty", "--class=themectl.picker", "-e", "bash", "-c",
                                "read -p 'Theme suchen (leer = beliebteste): ' q; " + root.themectl +
                                " omarchy search $q --limit 60 --pick; echo; read -p 'Enter zum Schließen'"])
                            if (popout.closePopout)
                                popout.closePopout()
                        }
                    }
                }

                StyledText {
                    anchors.centerIn: parent
                    visible: root.themes.length === 0
                    text: "Noch keine Themes.\nthemectl save <name> oder themectl omarchy import …"
                    horizontalAlignment: Text.AlignHCenter
                    color: Theme.surfaceVariantText
                }

                GridView {
                    id: grid
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: searchButton.top
                    anchors.bottomMargin: Theme.spacingS
                    clip: true
                    cellWidth: Math.floor(width / 2)
                    cellHeight: 190
                    model: root.themes
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Item {
                        id: cell
                        required property var modelData
                        width: grid.cellWidth
                        height: grid.cellHeight

                        Rectangle {
                            id: card
                            anchors.fill: parent
                            anchors.margins: Theme.spacingXS
                            radius: Theme.cornerRadius
                            color: cardMouse.containsMouse ? Theme.surfaceContainerHigh : Theme.surfaceContainer
                            border.width: cell.modelData.current ? 2 : 1
                            border.color: cell.modelData.current ? Theme.primary : Theme.outlineStrong
                            clip: true

                            Column {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingS
                                spacing: Theme.spacingXS

                                // Wallpaper mit Mini-Fenster in den Theme-Farben
                                Rectangle {
                                    width: parent.width
                                    height: 112
                                    radius: Theme.cornerRadius / 2
                                    clip: true
                                    color: cell.modelData.background

                                    Image {
                                        anchors.fill: parent
                                        visible: !!cell.modelData.wallpaper
                                        source: cell.modelData.wallpaper ? "file://" + cell.modelData.wallpaper : ""
                                        sourceSize.width: 520
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: parent.width * 0.6
                                        height: parent.height * 0.55
                                        radius: 5
                                        color: cell.modelData.background
                                        border.color: cell.modelData.accent
                                        border.width: 2

                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 7
                                            spacing: 4
                                            Repeater {
                                                model: [[1, 0.55], [4, 0.8], [2, 0.4], [5, 0.65]]
                                                Rectangle {
                                                    required property var modelData
                                                    height: 4
                                                    radius: 2
                                                    width: parent.width * modelData[1]
                                                    color: cell.modelData.colors ? cell.modelData.colors[modelData[0]] : "gray"
                                                }
                                            }
                                        }
                                    }

                                    // "Aktiv"-Markierung
                                    Rectangle {
                                        visible: !!cell.modelData.current
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 6
                                        width: 24
                                        height: 24
                                        radius: 12
                                        color: Theme.primary
                                        DankIcon {
                                            anchors.centerIn: parent
                                            name: "check"
                                            size: 16
                                            color: Theme.primaryText
                                        }
                                    }
                                }

                                Row {
                                    width: parent.width
                                    spacing: Theme.spacingXS
                                    StyledText {
                                        width: parent.width - swatches.width - Theme.spacingXS
                                        text: cell.modelData.name
                                        elide: Text.ElideRight
                                        font.pixelSize: Theme.fontSizeMedium
                                        color: Theme.surfaceText
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                    Row {
                                        id: swatches
                                        spacing: 2
                                        anchors.verticalCenter: parent.verticalCenter
                                        Repeater {
                                            model: cell.modelData.colors ? cell.modelData.colors.slice(1, 7) : []
                                            Rectangle {
                                                required property var modelData
                                                width: 12
                                                height: 12
                                                radius: 3
                                                color: modelData
                                            }
                                        }
                                    }
                                }
                            }

                            MouseArea {
                                id: cardMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.applyTheme(cell.modelData.id)
                                    if (popout.closePopout)
                                        popout.closePopout()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
