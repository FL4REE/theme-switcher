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

    // Löschen in zwei Schritten: "Aktives Theme löschen" merkt sich das Theme
    // und öffnet den Launcher erneut mit der Rückfrage.
    property string pendingDelete: ""
    property string pendingDeleteName: ""
    property double pendingDeleteAt: 0

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

    // Der Launcher schließt sich nach jeder Auswahl; für die Rückfrage
    // öffnen wir ihn kurz danach wieder mit dem Trigger.
    Timer {
        id: reopenTimer
        interval: 250
        onTriggered: Quickshell.execDetached(["dms", "ipc", "call", "spotlight", "openQuery", root.trigger])
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

        // Rückfrage vor dem Löschen (gilt 20 Sekunden)
        if (pendingDelete.length > 0 && Date.now() - pendingDeleteAt < 20000)
            return [{
                name: "Ja, „" + pendingDeleteName + "“ löschen",
                icon: "material:delete_forever",
                comment: "Enter bestätigt · danach wird zum nächsten Theme gewechselt",
                action: "confirmdelete:" + pendingDelete,
                categories: ["Themes"]
            }, {
                name: "Abbrechen",
                icon: "material:close",
                comment: "Theme behalten",
                action: "canceldelete:",
                categories: ["Themes"]
            }]
        pendingDelete = ""

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
                keywords: [t.id, t.source],
                imageUrl: t.wallpaper ? "file://" + t.wallpaper : ""
            })
        }
        // aktives Theme nach unten, damit Enter direkt ein anderes nimmt
        items.sort((a, b) => (a.icon === "material:check_circle") - (b.icon === "material:check_circle"))
        // Zufalls-Eintrag oben (mit Suchtext: nur unter den Treffern)
        const pool = items.filter(i => i.icon !== "material:check_circle")
        if (pool.length > 1 || (pool.length === 1 && q.length === 0))
            items.unshift({
                name: "Zufälliges Theme",
                icon: "material:casino",
                comment: q.length > 0 ? "aus " + pool.length + " Treffern" : "irgendeins außer dem aktiven",
                action: "random:" + q,
                categories: ["Themes"],
                keywords: ["zufall", "random"]
            })
        // Löschen-Eintrag für das aktive Theme (ganz unten, mit Rückfrage)
        const active = themes.find(t => t.current)
        if (active && (q.length === 0 || ("löschen delete entfernen " + active.name + " " + active.id).toLowerCase().includes(q)))
            items.push({
                name: "Aktives Theme löschen",
                icon: "material:delete",
                comment: active.name + " gefällt nicht? Löschen (mit Rückfrage)",
                action: "delete:" + active.id,
                categories: ["Themes"],
                keywords: ["löschen", "delete", "entfernen"]
            })
        return items
    }

    function executeItem(item) {
        if (!item || !item.action)
            return
        const idx = item.action.indexOf(":")
        const type = item.action.slice(0, idx)
        const data = item.action.slice(idx + 1)
        if (type === "random") {
            const words = data.length > 0 ? data.split(/\s+/) : []
            Quickshell.execDetached([root.themectl, "random", ...words])
            lastRefresh = 0
            if (typeof ToastService !== "undefined")
                ToastService.showInfo("Theme", "Zufälliges Theme wird angewendet")
            return
        }
        if (type === "delete") {
            const t = themes.find(x => x.id === data)
            pendingDelete = data
            pendingDeleteName = t ? t.name : data
            pendingDeleteAt = Date.now()
            reopenTimer.restart()
            return
        }
        if (type === "confirmdelete") {
            Quickshell.execDetached([root.themectl, "delete", data])
            pendingDelete = ""
            themes = themes.filter(x => x.id !== data)
            lastRefresh = 0
            if (typeof ToastService !== "undefined")
                ToastService.showInfo("Theme", pendingDeleteName + " wird gelöscht")
            return
        }
        if (type === "canceldelete") {
            pendingDelete = ""
            return
        }
        if (type !== "apply")
            return

        Quickshell.execDetached([root.themectl, "apply", data])
        for (const t of themes)
            t.current = (t.id === data)
        if (typeof ToastService !== "undefined")
            ToastService.showInfo("Theme", item.name + " wird angewendet")
    }
}
