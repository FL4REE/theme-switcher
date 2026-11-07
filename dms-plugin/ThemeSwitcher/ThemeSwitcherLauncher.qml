import QtQuick
import Quickshell
import Quickshell.Io
import qs.Services

// Launcher-Plugin für themectl: im DMS-Launcher (Super+Space) "~" tippen,
// dann ein Theme auswählen und mit Enter anwenden.
Item {
    id: root

    property var pluginService: null
    property string pluginId: "themeSwitcher"
    property string trigger: "~"

    // Pfad zu themectl; install.sh legt den Starter in ~/.local/bin an
    readonly property string themectl: Quickshell.env("HOME") + "/.local/bin/themectl"

    property var themes: []
    property bool loaded: false
    property double lastRefresh: 0

    signal itemsChanged()

    Component.onCompleted: {
        if (pluginService)
            trigger = pluginService.loadPluginData(pluginId, "trigger", "~")
        refresh()
    }

    onTriggerChanged: {
        if (pluginService)
            pluginService.savePluginData(pluginId, "trigger", trigger)
    }

    Process {
        id: listProc
        command: [root.themectl, "list", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.themes = JSON.parse(this.text)
                } catch (e) {
                    console.warn("ThemeSwitcher: konnte themectl-Ausgabe nicht lesen:", e)
                    root.themes = []
                }
                root.loaded = true
                root.lastRefresh = Date.now()
                root.notifyUpdate()
            }
        }
        onExited: exitCode => {
            if (exitCode !== 0) {
                console.warn("ThemeSwitcher: themectl list beendet mit", exitCode)
                root.loaded = true
                root.notifyUpdate()
            }
        }
    }

    function refresh() {
        if (!listProc.running)
            listProc.running = true
    }

    function notifyUpdate() {
        itemsChanged()
        if (pluginService && pluginService.requestLauncherUpdate)
            pluginService.requestLauncherUpdate(pluginId)
    }

    function getItems(query) {
        // Liste beim Öffnen auffrischen (neue Aether-Imports usw.)
        if (Date.now() - lastRefresh > 3000)
            refresh()

        if (!loaded)
            return [{ name: "Lade Themes …", icon: "material:hourglass_empty", comment: "", action: "noop:", categories: ["Themes"] }]

        if (themes.length === 0)
            return [{
                name: "Keine Themes gefunden",
                icon: "material:info",
                comment: "themectl save <name> oder themectl aether import --all",
                action: "noop:",
                categories: ["Themes"]
            }]

        const q = (query || "").toLowerCase().trim()
        const items = []
        for (const t of themes) {
            const hay = (t.name + " " + t.id + " " + t.source).toLowerCase()
            if (q.length > 0 && !hay.includes(q))
                continue
            items.push({
                name: t.name,
                icon: t.current ? "material:check_circle" : (t.mode === "light" ? "material:light_mode" : "material:palette"),
                comment: (t.current ? "aktiv · " : "") + t.mode + " · Akzent " + t.accent,
                action: "apply:" + t.id,
                categories: ["Themes"],
                keywords: [t.id, t.source]
            })
        }
        // aktives Theme nach unten, damit Enter direkt ein anderes nimmt
        items.sort((a, b) => (a.icon === "material:check_circle") - (b.icon === "material:check_circle"))
        return items
    }

    function executeItem(item) {
        if (!item || !item.action)
            return
        const idx = item.action.indexOf(":")
        const type = item.action.slice(0, idx)
        const data = item.action.slice(idx + 1)
        if (type !== "apply")
            return

        Quickshell.execDetached([root.themectl, "apply", data])
        for (const t of themes)
            t.current = (t.id === data)
        if (typeof ToastService !== "undefined")
            ToastService.showInfo("Theme", item.name + " wird angewendet")
    }
}
