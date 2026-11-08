// Theme Galerie als eigenes Fenster (Quickshell).
// Start: themectl gallery   (oder direkt: qs -p app/ThemeGallery/shell.qml)
//
// Tab "Meine Themes": alle gespeicherten Themes, ohne Begrenzung, mit Suche.
// Tab "Online": Omarchy-Themes auf GitHub suchen (bis 100 Treffer), importieren, anwenden.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    id: shell

    readonly property string themectl: Quickshell.env("THEMECTL") || (Quickshell.env("HOME") + "/.local/bin/themectl")
    property var themes: []
    property var online: []
    property string onlineError: ""
    property bool searching: false
    property string busyRepo: ""
    property string status: ""

    // Farben vom aktiven Theme
    readonly property var cur: themes.find(t => t.current) || null
    readonly property color bg: cur ? cur.background : "#1b1e28"
    readonly property color fg: cur ? cur.foreground : "#e4f0fb"
    readonly property color accent: cur ? cur.accent : "#5de4c7"
    readonly property color surface: Qt.tint(bg, Qt.rgba(fg.r, fg.g, fg.b, 0.06))
    readonly property color surfaceHigh: Qt.tint(bg, Qt.rgba(fg.r, fg.g, fg.b, 0.12))
    readonly property color outline: Qt.tint(bg, Qt.rgba(fg.r, fg.g, fg.b, 0.22))
    readonly property color muted: Qt.tint(fg, Qt.rgba(bg.r, bg.g, bg.b, 0.4))

    function contrastOn(c) {
        const l = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
        return l > 0.55 ? "#111111" : "#ffffff"
    }

    Process {
        id: listProc
        command: [shell.themectl, "list", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { shell.themes = JSON.parse(this.text) } catch (e) { shell.themes = [] }
                shell.markInstalled()
            }
        }
    }
    function refresh() { if (!listProc.running) listProc.running = true }

    Process {
        id: applyProc
        onExited: (code) => {
            shell.status = code === 0 ? "Angewendet" : "Anwenden fehlgeschlagen"
            shell.refresh()
        }
    }
    function applyTheme(id) {
        shell.status = "Wende " + id + " an …"
        shell.themes = shell.themes.map(t => Object.assign({}, t, { current: t.id === id }))
        applyProc.command = [shell.themectl, "apply", id]
        applyProc.running = true
    }

    Process {
        id: searchProc
        stdout: StdioCollector {
            onStreamFinished: {
                shell.searching = false
                try {
                    const data = JSON.parse(this.text)
                    if (Array.isArray(data)) {
                        shell.online = data
                        shell.onlineError = data.length ? "" : "Nichts gefunden."
                    } else {
                        shell.online = []
                        shell.onlineError = data.error || "Suche fehlgeschlagen."
                    }
                } catch (e) {
                    shell.online = []
                    shell.onlineError = "Suche fehlgeschlagen."
                }
            }
        }
    }
    function search(q) {
        if (searchProc.running) return
        shell.searching = true
        shell.onlineError = ""
        const words = q.trim().length ? q.trim().split(/\s+/) : []
        searchProc.command = [shell.themectl, "omarchy", "search", ...words, "--limit", "100", "--json"]
        searchProc.running = true
    }
    function markInstalled() {
        const ids = shell.themes.map(t => t.id.toLowerCase())
        shell.online = shell.online.map(r => Object.assign({}, r, { installed: ids.indexOf(r.name.toLowerCase()) >= 0 }))
    }

    Process {
        id: importProc
        property bool applyAfter: false
        stdout: StdioCollector { id: importOut }
        stderr: StdioCollector { id: importErr }
        onExited: (code) => {
            shell.status = code === 0 ? "Importiert: " + shell.busyRepo
                                      : "Import fehlgeschlagen: " + (importErr.text || importOut.text).trim().split("\n").pop()
            shell.busyRepo = ""
            shell.refresh()
        }
    }
    function importTheme(r, andApply) {
        if (importProc.running) return
        shell.busyRepo = r.repo
        shell.status = "Importiere " + r.repo + " …"
        importProc.command = [shell.themectl, "omarchy", "import", r.url, "-f"].concat(andApply ? ["--apply"] : [])
        importProc.running = true
    }

    Timer { interval: 30000; running: true; repeat: true; onTriggered: shell.refresh() }
    Component.onCompleted: {
        refresh()
        // themectl gallery --online [begriff]
        if (Quickshell.env("THEME_GALLERY_TAB") === "online") {
            tabs.currentIndex = 1
            filterField.text = Quickshell.env("THEME_GALLERY_QUERY") || ""
            search(filterField.text)
        }
    }

    FloatingWindow {
        id: win
        visible: true
        title: "Theme Galerie"
        implicitWidth: 1180
        implicitHeight: 800
        color: shell.bg
        onVisibleChanged: if (!visible) Qt.quit()

        Shortcut { sequence: "Escape"; onActivated: Qt.quit() }
        Shortcut { sequence: "Ctrl+F"; onActivated: filterField.forceActiveFocus() }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 14

            // Kopfzeile: Tabs + Suche
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Repeater {
                    model: ["Meine Themes", "Online (Omarchy)"]
                    Rectangle {
                        required property int index
                        required property string modelData
                        readonly property bool active: tabs.currentIndex === index
                        implicitWidth: tabLabel.implicitWidth + 28
                        implicitHeight: 36
                        radius: 18
                        color: active ? shell.accent : (tabMouse.containsMouse ? shell.surfaceHigh : shell.surface)
                        Text {
                            id: tabLabel
                            anchors.centerIn: parent
                            text: parent.modelData + (parent.index === 0 ? "  " + shell.themes.length : "")
                            color: parent.active ? shell.contrastOn(shell.accent) : shell.fg
                            font.pixelSize: 14
                            font.bold: parent.active
                        }
                        MouseArea {
                            id: tabMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                tabs.currentIndex = parent.index
                                if (parent.index === 1 && shell.online.length === 0 && !shell.searching)
                                    shell.search(filterField.text)
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    Layout.preferredWidth: 340
                    implicitHeight: 36
                    radius: 18
                    color: shell.surface
                    border.color: filterField.activeFocus ? shell.accent : shell.outline
                    TextField {
                        id: filterField
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        background: null
                        color: shell.fg
                        placeholderText: tabs.currentIndex === 0 ? "Themes filtern …" : "Online suchen, Enter (leer = beliebteste)"
                        placeholderTextColor: shell.muted
                        font.pixelSize: 14
                        verticalAlignment: TextInput.AlignVCenter
                        onAccepted: if (tabs.currentIndex === 1) shell.search(text)
                    }
                }
            }

            StackLayout {
                id: tabs
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: 0

                // ---------- Meine Themes ----------
                GridView {
                    id: grid
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    readonly property int cols: Math.max(1, Math.floor(width / 270))
                    cellWidth: Math.floor(width / cols)
                    cellHeight: 214
                    ScrollBar.vertical: ScrollBar {}
                    model: {
                        const q = filterField.text.trim().toLowerCase()
                        return q.length === 0 ? shell.themes
                             : shell.themes.filter(t => (t.name + " " + t.id + " " + (t.source || "")).toLowerCase().indexOf(q) >= 0)
                    }

                    delegate: Item {
                        id: cell
                        required property var modelData
                        width: grid.cellWidth
                        height: grid.cellHeight

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 6
                            radius: 12
                            color: m.containsMouse ? shell.surfaceHigh : shell.surface
                            border.width: cell.modelData.current ? 2 : 1
                            border.color: cell.modelData.current ? shell.accent : shell.outline
                            clip: true

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 8

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 128
                                    radius: 8
                                    clip: true
                                    color: cell.modelData.background

                                    Image {
                                        anchors.fill: parent
                                        visible: !!cell.modelData.wallpaper
                                        source: cell.modelData.wallpaper ? "file://" + cell.modelData.wallpaper : ""
                                        sourceSize.width: 480
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }
                                    // Mini-Fenster in den Theme-Farben
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
                                            anchors.margins: 8
                                            spacing: 5
                                            Repeater {
                                                model: [[1, 0.55], [4, 0.8], [2, 0.4], [5, 0.65]]
                                                Rectangle {
                                                    required property var modelData
                                                    height: 5
                                                    radius: 2
                                                    width: parent.width * modelData[1]
                                                    color: cell.modelData.colors ? cell.modelData.colors[modelData[0]] : "gray"
                                                }
                                            }
                                        }
                                    }
                                    Rectangle {
                                        visible: !!cell.modelData.current
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        anchors.margins: 6
                                        width: 24; height: 24; radius: 12
                                        color: shell.accent
                                        Text { anchors.centerIn: parent; text: "✓"; color: shell.contrastOn(shell.accent); font.bold: true }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Text {
                                        Layout.fillWidth: true
                                        text: cell.modelData.name
                                        elide: Text.ElideRight
                                        color: shell.fg
                                        font.pixelSize: 14
                                    }
                                    Repeater {
                                        model: cell.modelData.colors ? cell.modelData.colors.slice(1, 7) : []
                                        Rectangle { required property var modelData; width: 12; height: 12; radius: 3; color: modelData }
                                    }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: (cell.modelData.source || "").replace(/^omarchy:/, "omarchy · ").replace(/^aether-blueprint:/, "aether · ")
                                    elide: Text.ElideMiddle
                                    color: shell.muted
                                    font.pixelSize: 11
                                }
                            }

                            MouseArea {
                                id: m
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: shell.applyTheme(cell.modelData.id)
                            }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: grid.count === 0
                        text: shell.themes.length ? "Kein Theme passt zum Filter." : "Noch keine Themes."
                        color: shell.muted
                        font.pixelSize: 15
                    }
                }

                // ---------- Online ----------
                GridView {
                    id: onlineGrid
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    readonly property int cols: Math.max(1, Math.floor(width / 300))
                    cellWidth: Math.floor(width / cols)
                    cellHeight: 262
                    ScrollBar.vertical: ScrollBar {}
                    model: shell.online

                    delegate: Item {
                        id: ocell
                        required property var modelData
                        readonly property bool busy: shell.busyRepo === modelData.repo
                        width: onlineGrid.cellWidth
                        height: onlineGrid.cellHeight

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 6
                            radius: 12
                            color: shell.surface
                            border.width: 1
                            border.color: ocell.modelData.installed ? shell.accent : shell.outline
                            clip: true

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 6

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 132
                                    radius: 8
                                    clip: true
                                    color: shell.surfaceHigh
                                    Text {
                                        anchors.centerIn: parent
                                        visible: preview.status !== Image.Ready
                                        text: preview.status === Image.Loading || preview.attempt < preview.names.length ? "lädt …" : "keine Vorschau"
                                        color: shell.muted
                                        font.pixelSize: 12
                                    }
                                    // Die meisten Omarchy-Themes haben ein preview.png im Repo
                                    Image {
                                        id: preview
                                        anchors.fill: parent
                                        // preview.png, sonst andere übliche Namen probieren
                                        readonly property var names: ["preview.png", "screenshot.png", "preview.jpg", "theme.png"]
                                        property int attempt: 0
                                        source: attempt < names.length
                                                ? "https://raw.githubusercontent.com/" + ocell.modelData.repo + "/" + (ocell.modelData.branch || "HEAD") + "/" + names[attempt]
                                                : ""
                                        onStatusChanged: if (status === Image.Error) attempt++
                                        sourceSize.width: 560
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        Layout.fillWidth: true
                                        text: ocell.modelData.name
                                        elide: Text.ElideRight
                                        color: shell.fg
                                        font.pixelSize: 14
                                        font.bold: true
                                    }
                                    Text { text: "★ " + ocell.modelData.stars; color: shell.muted; font.pixelSize: 12 }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    text: ocell.modelData.description || ocell.modelData.repo
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideRight
                                    maximumLineCount: 2
                                    color: shell.muted
                                    font.pixelSize: 11
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Repeater {
                                        model: ocell.modelData.installed
                                               ? [["Anwenden", "apply"]]
                                               : [["Importieren", "import"], ["Import + Anwenden", "both"]]
                                        Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 30
                                            radius: 15
                                            opacity: (ocell.busy || (shell.busyRepo && !ocell.busy)) && modelData[1] !== "apply" ? 0.5 : 1
                                            color: bm.containsMouse ? Qt.lighter(shell.accent, 1.15) : shell.accent
                                            Text {
                                                anchors.centerIn: parent
                                                text: ocell.busy ? "importiere …" : parent.modelData[0]
                                                color: shell.contrastOn(shell.accent)
                                                font.pixelSize: 12
                                                font.bold: true
                                            }
                                            MouseArea {
                                                id: bm
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    const a = parent.modelData[1]
                                                    if (a === "apply") shell.applyTheme(ocell.modelData.name.toLowerCase())
                                                    else shell.importTheme(ocell.modelData, a === "both")
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: onlineGrid.count === 0
                        text: shell.searching ? "Suche auf GitHub …" : (shell.onlineError || "Suchbegriff eingeben und Enter drücken.")
                        color: shell.muted
                        font.pixelSize: 15
                    }
                }
            }

            // Fußzeile
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: shell.status || (tabs.currentIndex === 0
                          ? "Klick = anwenden · Strg+F = filtern · Esc = schließen"
                          : (shell.searching ? "Suche …" : shell.online.length + " Treffer · ✓-Rahmen = schon vorhanden"))
                    color: shell.muted
                    font.pixelSize: 12
                    elide: Text.ElideRight
                }
                Text {
                    text: shell.cur ? "aktiv: " + shell.cur.name : ""
                    color: shell.accent
                    font.pixelSize: 12
                }
            }
        }
    }
}
