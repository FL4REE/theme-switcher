// Theme Galerie als eigenes Fenster (Quickshell).
// Start: themectl gallery   (oder direkt: qs -p app/ThemeGallery/shell.qml)
//
// Tab "Meine Themes": alle gespeicherten Themes, ohne Begrenzung, mit Suche.
// Tab "Online": Themes aus mehreren Quellen (Omarchy Community/Offiziell, iTerm2-Schemata,
// Base16/Base24) ansehen, importieren und anwenden.
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
    property var sources: [
        { key: "omarchy", title: "Omarchy Community", hint: "Enter sucht auf GitHub (leer = beliebteste)" },
        { key: "omarchy-core", title: "Omarchy Offiziell", hint: "Die mitgelieferten Omarchy-Themes" },
        { key: "iterm2", title: "Terminal-Schemata", hint: "Über 400 Farbschemata, ohne Wallpaper" },
        { key: "base16", title: "Base16", hint: "tinted-theming, ohne Wallpaper" },
        { key: "base24", title: "Base24", hint: "tinted-theming, ohne Wallpaper" }
    ]
    property string sourceKey: "omarchy"
    readonly property bool remoteSearch: sourceKey === "omarchy"
    // Farben der Schemata ohne Vorschaubild (raw-URL -> {bg, fg, accent, colors})
    property var colorCache: ({})

    function slug(n) { return n.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase() }

    function parseColors(text, format) {
        const res = { colors: [] }
        if (format === "ghostty") {
            const pal = []
            for (const line of text.split("\n")) {
                let m = line.match(/^\s*palette\s*=\s*(\d+)\s*=\s*(#?[0-9a-fA-F]{6})/)
                if (m) { pal[parseInt(m[1])] = (m[2][0] === "#" ? "" : "#") + m[2]; continue }
                m = line.match(/^\s*(background|foreground)\s*=\s*(#?[0-9a-fA-F]{6})/)
                if (m) res[m[1] === "background" ? "bg" : "fg"] = (m[2][0] === "#" ? "" : "#") + m[2]
            }
            res.colors = pal
            res.accent = pal[4]
        } else {
            const b = {}
            const re = /(base[0-9A-Fa-f]{2})\s*:\s*["']?#?([0-9A-Fa-f]{6})/g
            let m
            while ((m = re.exec(text)) !== null) b[m[1].toLowerCase()] = "#" + m[2]
            res.bg = b.base00; res.fg = b.base05; res.accent = b.base0d
            res.colors = [b.base00, b.base08, b.base0b, b.base0a, b.base0d, b.base0e, b.base0c, b.base05]
        }
        return res.bg ? res : null
    }

    function loadColors(url, format) {
        if (!url || colorCache[url] !== undefined) return
        const c = colorCache; c[url] = null; colorCache = c
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            const parsed = xhr.status === 200 ? shell.parseColors(xhr.responseText, format) : null
            const cc = Object.assign({}, shell.colorCache); cc[url] = parsed || false; shell.colorCache = cc
        }
        xhr.open("GET", url)
        xhr.send()
    }
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
        const words = shell.remoteSearch && q.trim().length ? q.trim().split(/\s+/) : []
        searchProc.command = [shell.themectl, "online", "browse", shell.sourceKey, ...words, "--json"]
        searchProc.running = true
    }
    function markInstalled() {
        const ids = shell.themes.map(t => t.id.toLowerCase())
        shell.online = shell.online.map(r => Object.assign({}, r, { installed: ids.indexOf(shell.slug(r.name)) >= 0 }))
    }

    Process {
        id: importProc
        property bool applyAfter: false
        stdout: StdioCollector { id: importOut }
        stderr: StdioCollector { id: importErr }
        onExited: (code) => {
            shell.status = code === 0 ? "Importiert: " + shell.busyName
                                      : "Import fehlgeschlagen: " + (importErr.text || importOut.text).trim().split("\n").pop()
            shell.busyRepo = ""
            shell.refresh()
        }
    }
    property string busyName: ""
    function importTheme(r, andApply) {
        if (importProc.running) return
        shell.busyRepo = r.source + ":" + r.id
        shell.busyName = r.name
        shell.status = "Importiere " + r.name + " …"
        const base = r.kind === "omarchy-repo" ? [shell.themectl, "omarchy", "import", r.url]
                                               : [shell.themectl, "online", "import", r.source, r.id]
        importProc.command = base.concat(["-f"], andApply ? ["--apply"] : [])
        importProc.running = true
    }

    Timer { interval: 30000; running: true; repeat: true; onTriggered: shell.refresh() }
    Component.onCompleted: {
        refresh()
        // themectl gallery --online [begriff]
        const src = Quickshell.env("THEME_GALLERY_SOURCE")
        if (src && sources.some(x => x.key === src))
            sourceKey = src
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
                    model: ["Meine Themes", "Online"]
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
                        placeholderText: tabs.currentIndex === 0 ? "Themes filtern …"
                                       : (shell.remoteSearch ? "Auf GitHub suchen, Enter" : "Filtern …")
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
                ColumnLayout {
                  spacing: 10

                  Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: shell.sources
                        Rectangle {
                            required property var modelData
                            readonly property bool active: shell.sourceKey === modelData.key
                            width: srcLabel.implicitWidth + 24
                            height: 30
                            radius: 15
                            color: active ? Qt.tint(shell.surface, Qt.rgba(shell.accent.r, shell.accent.g, shell.accent.b, 0.25))
                                          : (srcMouse.containsMouse ? shell.surfaceHigh : shell.surface)
                            border.color: active ? shell.accent : shell.outline
                            Text {
                                id: srcLabel
                                anchors.centerIn: parent
                                text: parent.modelData.title
                                color: shell.fg
                                font.pixelSize: 12
                            }
                            MouseArea {
                                id: srcMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (shell.sourceKey === parent.modelData.key) return
                                    shell.sourceKey = parent.modelData.key
                                    shell.online = []
                                    filterField.text = ""
                                    shell.search("")
                                }
                            }
                        }
                    }
                  }

                GridView {
                    id: onlineGrid
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    readonly property int cols: Math.max(1, Math.floor(width / 300))
                    cellWidth: Math.floor(width / cols)
                    cellHeight: 262
                    ScrollBar.vertical: ScrollBar {}
                    model: {
                        const q = filterField.text.trim().toLowerCase()
                        if (shell.remoteSearch || q.length === 0) return shell.online
                        const words = q.split(/\s+/)
                        return shell.online.filter(r => words.every(w => r.name.toLowerCase().indexOf(w) >= 0))
                    }

                    delegate: Item {
                        id: ocell
                        required property var modelData
                        readonly property bool busy: shell.busyRepo === modelData.source + ":" + modelData.id
                        readonly property var pal: modelData.preview ? null : shell.colorCache[modelData.raw]
                        Component.onCompleted: if (!modelData.preview) shell.loadColors(modelData.raw, modelData.format)
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
                                    color: ocell.pal ? ocell.pal.bg : shell.surfaceHigh
                                    Text {
                                        anchors.centerIn: parent
                                        visible: !ocell.pal && preview.status !== Image.Ready
                                        text: (ocell.modelData.preview ? preview.attempt < preview.names.length : ocell.pal !== false)
                                              ? "lädt …" : "keine Vorschau"
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
                                        source: ocell.modelData.preview && attempt < names.length
                                                ? ocell.modelData.preview.replace(/preview\.png$/, names[attempt])
                                                : ""
                                        onStatusChanged: if (status === Image.Error) attempt++
                                        sourceSize.width: 560
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }
                                    // Schemata ohne Bild: Mini-Terminal in den Farben des Schemas
                                    Rectangle {
                                        visible: !!ocell.pal
                                        anchors.centerIn: parent
                                        width: parent.width * 0.7
                                        height: parent.height * 0.62
                                        radius: 6
                                        color: ocell.pal ? ocell.pal.bg : "transparent"
                                        border.color: ocell.pal ? ocell.pal.accent : "transparent"
                                        border.width: 2
                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 9
                                            spacing: 6
                                            Repeater {
                                                model: [[1, 0.5], [4, 0.8], [2, 0.35], [5, 0.65], [3, 0.45]]
                                                Rectangle {
                                                    required property var modelData
                                                    height: 5
                                                    radius: 2
                                                    width: parent.width * modelData[1]
                                                    color: ocell.pal && ocell.pal.colors[modelData[0]] ? ocell.pal.colors[modelData[0]] : "gray"
                                                }
                                            }
                                        }
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
                                    Text { visible: ocell.modelData.stars !== null && ocell.modelData.stars !== undefined; text: "★ " + ocell.modelData.stars; color: shell.muted; font.pixelSize: 12 }
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    text: ocell.modelData.description || (shell.sources.find(x => x.key === ocell.modelData.source) || {}).hint || ""
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
                                                    if (a === "apply") shell.applyTheme(shell.slug(ocell.modelData.name))
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
                        text: shell.searching ? "Lade …" : (shell.onlineError || (shell.online.length ? "Nichts passt zum Filter." : ""))
                        color: shell.muted
                        font.pixelSize: 15
                    }
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
                          : (shell.searching ? "Suche …" : onlineGrid.count + " Einträge · farbiger Rahmen = schon vorhanden"))
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
