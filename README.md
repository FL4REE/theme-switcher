# theme-switcher

Themes für **CachyOS + Hyprland + DankMaterialShell (DMS)** anlegen, speichern,
wechseln und aus **[Aether](https://github.com/bjarneo/aether)** übernehmen.
Reines Python (≥ 3.11), keine Abhängigkeiten.

## Installation

```bash
git clone https://github.com/FL4REE/theme-switcher.git ~/Projekte/theme-switcher
cd ~/Projekte/theme-switcher
./install.sh          # nutzt pipx, sonst Starter in ~/.local/bin
themectl --help
```

## Schnellstart

```bash
themectl save mein-setup            # aktuellen Desktop (DMS-Theme + Wallpaper) sichern
themectl aether list                # gespeicherte Aether-Blueprints anzeigen
themectl aether import --all        # alle Blueprints als Themes übernehmen
themectl aether import --current    # das gerade in Aether angewendete Theme übernehmen
themectl list                       # alle Themes mit Farbvorschau
themectl apply forest               # Theme anwenden
themectl apply forest --dry-run     # nur zeigen, was passieren würde
themectl pick                       # Auswahlmenü (fuzzel/rofi/wofi/fzf)
themectl next | prev                # durchschalten
```

Eigenes Theme aus Farben:

```bash
themectl create nachtblau --bg "#0f1018" --accent "#89ddff" --wallpaper ~/Wallpapers/x.png --apply
themectl edit nachtblau             # theme.json im Editor feinjustieren
```

Teilen und sichern: `themectl export <name>` erzeugt ein `.tar.gz`,
`themectl import <datei|ordner|theme.json>` liest es wieder ein.

## Im DMS-Launcher (Super+Space)

`install.sh` verlinkt ein Launcher-Plugin nach `~/.config/dms/plugins/ThemeSwitcher`.
Einmal in DMS unter **Einstellungen → Plugins** auf „Scan for Plugins“ klicken
und **Theme Switcher** einschalten. Danach im Launcher `~` tippen, ein Theme
auswählen und mit Enter anwenden. Mehr dazu in [`dms-plugin/README.md`](dms-plugin/README.md).

## Hotkeys (Hyprland-Lua)

In `~/.config/hypr/dms/binds-user.lua`:

```lua
hl.bind("SUPER + ALT + T", hl.dsp.exec_cmd("dms ipc call spotlight toggleQuery '~'"), { description = "Theme wählen" })
hl.bind("SUPER + ALT + N", hl.dsp.exec_cmd("/home/erik/.local/bin/themectl next"), { description = "Nächstes Theme" })
```

Und in `hyprland.lua`, damit das Auswahlfenster schwebt:

```lua
hl.window_rule({ match = { class = "^(themectl\\.picker)$" }, float = true })
```

Super+Alt+T öffnet damit den DMS-Launcher gleich mit `~`, also die Theme-Liste aus dem Plugin.
Ohne Plugin geht auch `themectl pick`: Es nimmt fuzzel, rofi oder wofi, wenn vorhanden. Sonst öffnet es fzf in
einem schwebenden Ghostty-Fenster. Nach dem Wechsel kommt eine Benachrichtigung.

## Was beim Anwenden passiert

| Ziel        | Standard | Wirkung |
|-------------|----------|---------|
| `dms`       | an       | schreibt `~/.config/dms/themes/ts-<name>/theme.json` und setzt in `settings.json` `currentThemeName = "custom"` und `customThemeFile`. Der Matugen-Hook von DMS erzeugt daraus auch `hypr/dms/colors.lua` (Fensterrahmen). Beim ersten Mal wird `settings.json.backup-theme-switcher` angelegt. |
| `wallpaper` | an       | `dms ipc call wallpaper set <bild>`, falls das Theme ein Bild hat |
| `hyprland`  | aus      | eigene `~/.config/hypr/theme-switcher.lua` + `hyprctl reload`. Nur nötig, wenn du Rahmenfarben unabhängig von DMS willst. Dann in `hyprland.lua` nach `require("dms.colors")` eintragen: `pcall(require, "theme-switcher")` |
| `ghostty`   | aus      | `~/.config/ghostty/themes/theme-switcher`. In der Ghostty-Config einmal `theme = theme-switcher` setzen. |

Ziele schaltest du in `~/.config/theme-switcher/config.toml` (Vorlage:
[`examples/config.toml`](examples/config.toml)) oder einmalig mit
`themectl apply <name> --only dms ghostty`.

> **Hinweis Live-Wallpaper:** Dein Wallpaper-Engine-Hintergrund
> (`~/.local/bin/livewallpaper`) liegt über dem DMS-Hintergrund. Themes ohne
> Bild lassen den Hintergrund in Ruhe.

## Aether-Workflow

1. In Aether ein Bild laden, Palette erzeugen und anpassen.
2. **Als Blueprint speichern** (landet in `~/.config/aether/blueprints/*.json`).
3. `themectl aether import "<Name>" --apply`

Alternativ in Aether direkt *Apply* drücken und dann
`themectl aether import --current --name <name>`. Das liest
`~/.config/aether/theme/colors.toml` und das Bild aus `theme/backgrounds/`.

## Omarchy-Themes

Jedes Omarchy-Theme lässt sich direkt von GitHub übernehmen:

```bash
themectl omarchy import https://github.com/OldJobobo/omarchy-miasma-theme --apply
themectl omarchy import OldJobobo/omarchy-miasma-theme --wallpaper 4 -f   # anderen Hintergrund nehmen
themectl omarchy import ~/Downloads/mein-omarchy-theme                    # lokaler Ordner
```

Die Farben kommen aus `colors.toml`, sonst aus `alacritty.toml` oder `kitty.conf`.
Fehlt ein Akzent, wird die Rahmenfarbe aus `hyprland.conf` genommen. Der Hintergrund
stammt aus `backgrounds/`. Beim Import werden alle Bilder nummeriert aufgelistet,
und mit `--wallpaper` wählst du ein anderes aus.

## Theme-Format

Themes liegen unter `~/.local/share/theme-switcher/themes/<name>/`:

```json
{
  "name": "forest",
  "version": 1,
  "mode": "dark",
  "palette": {
    "colors": ["#1b1e28", "… 16 ANSI-Farben …"],
    "background": "#1b1e28", "foreground": "#e4f0fb",
    "accent": "#5de4c7", "cursor": "#e4f0fb", "selection": "#506477"
  },
  "wallpaper": "wallpaper.png",
  "dms": { "dark": { "primary": "#…" }, "light": { } },
  "hyprland": { "active_border": "#…", "inactive_border": "#…" },
  "source": "aether-blueprint:forest.json"
}
```

`dms` und `hyprland` sind optional. Was fehlt, wird aus der Palette
abgeleitet, und einzelne Werte darin überschreiben die abgeleiteten.

## Entwicklung

```bash
python3 -m unittest discover -s tests -v
python3 -m theme_switcher --help
```

## Ideen für später

- DMS-Plugin mit Theme-Galerie in der Leiste
- Weitere Ziele: GTK/Qt, Kitty, Alacritty, Neovim, Firefox (`dms/firefox.css`)
- `themectl generate <bild>` über `aether --generate`
