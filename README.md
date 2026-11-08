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

## Theme-Galerie in der Leiste

`install.sh` verlinkt auch das Widget **Theme Galerie** nach `~/.config/dms/plugins/ThemeGallery`.
Aktivieren mit `dms ipc call plugins enable themeGallery` (oder in DMS unter Einstellungen →
Plugins) und dann in den Leisten-Einstellungen als Widget hinzufügen. In der Leiste stehen
ein Palette-Symbol und der Name des aktiven Themes. Ein Klick öffnet die Galerie mit
Wallpaper, Mini-Fenster und Farben jedes Themes, ein Klick auf eine Karte wendet es an.

## Theme Galerie als eigene App

```bash
themectl gallery                 # Fenster mit allen Themes (ohne Begrenzung, mit Filter)
themectl gallery --online nord   # gleich im Online-Tab nach Omarchy-Themes suchen
themectl gallery --install       # Starter „Theme Galerie“ fürs App-Menü (macht install.sh auch)
```

Das Fenster läuft mit Quickshell (`qs`), das DMS ohnehin mitbringt. Es hat zwei Tabs:

- **Meine Themes**: alle gespeicherten Themes mit Wallpaper, Mini-Fenster und Farben. Klick wendet an,
  Strg+F filtert, Esc schließt.
- **Online (Omarchy)**: bis zu 100 Omarchy-Themes von GitHub mit Vorschaubild, Sternen und Beschreibung.
  Knöpfe *Importieren* und *Import + Anwenden*, schon vorhandene Themes haben einen farbigen Rahmen.

Die Farben des Fensters kommen vom aktiven Theme. Im Leisten-Widget gibt es dafür den Knopf „Alle im Fenster“.

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
| `starship`  | an       | setzt `palette = "theme_switcher"` in `~/.config/starship.toml` und schreibt einen markierten Block `[palettes.theme_switcher]` ans Ende. Er enthält die Farbnamen der Presets Catppuccin-Powerline (`red`, `peach`, `sapphire`, `crust` …) und Gruvbox-Rainbow (`color_bg1` …) sowie `red`, `green`, `accent` usw. Dein bisheriger Palettenblock bleibt stehen. Beim ersten Mal wird `starship.toml.backup-theme-switcher` angelegt. Farben, die in der Config fest als Hex-Wert stehen, ändern sich nicht. |
| `icons`     | an       | setzt das Icon-Theme per `gsettings` (GTK/DMS) und in `qt5ct`/`qt6ct`. Standard: **immer Adwaita in der Farbe, die dem Akzent am nächsten kommt** (Varianten aus [Adwaita-colors](https://github.com/dpejoh/Adwaita-colors)), dazu die passende GNOME-Akzentfarbe. Umstellbar in `config.toml` unter `[icons] style` auf `yaru` oder `theme`. |
| `nvim`      | an       | schreibt das Farbschema `~/.config/nvim/colors/theme-switcher.lua` und färbt laufende Neovim-Fenster sofort um. Einmalig in der Neovim-Config `vim.cmd.colorscheme("theme-switcher")` setzen (LazyVim: siehe unten). |
| `pokefetch` | an       | Findet themectl die Sprites von [pokemon-colorscripts](https://gitlab.com/phoneybadger/pokemon-colorscripts) (eigenständig installiert oder die, die pokefetch selbst mitbringt), wertet themectl die echten Sprite-Farben aller Pokémon aus (einmalig, danach im Cache) und setzt die fish-Variable `pokefetch_pokemon` auf die 40 Pokémon, deren Hauptfarbe dem Akzent am nächsten kommt. Zusätzlich setzt es `pokefetch_farben` auf die zwei passendsten Pokédex-Farbklassen als Rückfall. Einstellbar unter `[pokefetch]` (`pool`, `count`, `names`, `colorscripts_dir`). |

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

## Neovim

Einmalig das Farbschema aktivieren. Bei einer eigenen Config in `init.lua`:

```lua
vim.cmd.colorscheme("theme-switcher")
```

Bei LazyVim als `~/.config/nvim/lua/plugins/theme-switcher.lua`:

```lua
return { { "LazyVim/LazyVim", opts = { colorscheme = "theme-switcher" } } }
```

Danach färbt jeder Theme-Wechsel auch offene Neovim-Fenster sofort um.

## Icons

Für den Standardstil `adwaita` einmal die farbigen Adwaita-Varianten installieren:

```bash
git clone https://github.com/dpejoh/Adwaita-colors /tmp/adwaita-colors
cd /tmp/adwaita-colors && sudo ./setup -i -g   # systemweit nach /usr/share/icons
```

Ohne sie wird normales Adwaita gesetzt, und es ändert sich nur die GNOME-Akzentfarbe.

```bash
themectl icons                       # installierte Icon-Themes, ● = aktiv
themectl icons miasma Papirus-Dark   # festes Icon-Theme für ein Theme
themectl icons miasma auto           # wieder automatisch (Yaru passend zum Akzent)
```

## Weitere Online-Quellen

Neben Omarchy-Themes kennt themectl noch andere Sammlungen:

| Quelle         | Inhalt | Wallpaper |
|----------------|--------|-----------|
| `omarchy`      | Omarchy-Themes der Community (GitHub-Suche `omarchy-*-theme`) | ja |
| `omarchy-core` | die offiziellen Omarchy-Themes aus [basecamp/omarchy](https://github.com/basecamp/omarchy/tree/master/themes) | ja |
| `iterm2`       | [iTerm2-Color-Schemes](https://github.com/mbadolato/iTerm2-Color-Schemes), über 400 Terminal-Farbschemata | nein |
| `base16`       | [tinted-theming](https://github.com/tinted-theming/schemes) Base16-Schemata | nein |
| `base24`       | tinted-theming Base24-Schemata (mit eigenen hellen Farben) | nein |

```bash
themectl online sources                      # Quellen anzeigen
themectl online browse iterm2 gruvbox        # Einträge einer Quelle, optional gefiltert
themectl online import iterm2 "Gruvbox Dark" --apply
themectl online import omarchy-core tokyo-night --wallpaper 2
themectl gallery --source base16             # Galerie gleich mit dieser Quelle öffnen
```

Die Liste einer Quelle wird einen Tag lang in `~/.cache/theme-switcher/sources/` gespeichert.
Themes ohne Wallpaper lassen deinen Hintergrund beim Anwenden in Ruhe. Mit
`themectl edit <name>` kannst du nachträglich ein Bild eintragen.

In der Galerie stehen die Quellen als Knöpfe über dem Online-Tab. Schemata ohne Vorschaubild
werden als Mini-Terminal in ihren eigenen Farben gezeigt.

## Omarchy-Themes

### Suchen

```bash
themectl omarchy search                 # beliebteste Omarchy-Themes auf GitHub
themectl omarchy search nord            # nach Begriff suchen
themectl omarchy search green --pick    # im Menü (fzf/fuzzel) auswählen und importieren
themectl omarchy search --install 1 4   # Treffer 1 und 4 importieren
```

Gesucht werden GitHub-Repos namens `omarchy-<name>-theme`, sortiert nach Sternen. Ein ✓ zeigt
an, dass das Theme schon da ist. Ohne Anmeldung erlaubt GitHub etwa 10 Suchen pro Minute;
ist `gh` angemeldet, wird dessen Token genutzt. Die Suche gibt es auch als Knopf in der
Theme-Galerie und im Desktop-Kontextmenü.

### Importieren

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

- Weitere Ziele: GTK/Qt, Kitty, Alacritty, Neovim, Firefox (`dms/firefox.css`)
- `themectl generate <bild>` über `aether --generate`
