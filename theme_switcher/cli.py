"""Kommandozeile: ``themectl``."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, aether, omarchy
from . import colors as c
from .config import Config
from .model import Palette, Theme
from .store import Store
from .targets import TARGETS
from .targets import dms as dms_target
from .targets import icons as icons_target
from .targets import wallpaper as wallpaper_target


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def default_ansi(bg: str, fg: str, accent: str) -> list[str]:
    """Erzeugt 16 ANSI-Farben passend zu Hintergrund/Vordergrund/Akzent."""
    dark = c.is_dark(bg)
    base = ["#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2"]
    hues = [c.mix(h, accent, 0.25) for h in base]
    if not dark:
        hues = [c.lighten(h, -0.15) for h in hues]
    bright = [c.lighten(h, 0.08 if dark else -0.08) for h in hues]
    return [bg, *hues, fg, c.mix(bg, fg, 0.35), *bright, c.lighten(fg, 0.1 if dark else -0.1)]


def palette_from_dms(block: dict[str, str]) -> Palette:
    bg = block["background"]
    fg = block.get("surfaceText", block.get("backgroundText", "#ffffff"))
    accent = block["primary"]
    ansi = default_ansi(bg, fg, accent)
    ansi[1] = ansi[9] = block.get("error", ansi[1])
    ansi[3] = ansi[11] = block.get("warning", ansi[3])
    ansi[4] = accent
    ansi[12] = block.get("primaryContainer", ansi[12])
    ansi[5] = ansi[13] = block.get("secondary", ansi[5])
    ansi[6] = ansi[14] = block.get("info", ansi[6])
    ansi[8] = block.get("outline", ansi[8])
    return Palette.from_ansi(ansi, {"background": bg, "foreground": fg, "accent": accent})


def _colors_only(block: dict) -> dict[str, str]:
    return {k: v for k, v in block.items() if isinstance(v, str) and v.startswith("#")}


def apply_theme(theme: Theme, cfg: Config, store: Store, only: list[str] | None, dry_run: bool) -> int:
    targets = only or [t for t, on in cfg.targets.items() if on]
    failed = 0
    print(f"▶ Wende '{theme.name}' an …")
    for t in targets:
        fn = TARGETS.get(t)
        if fn is None:
            print(f"  ✗ unbekanntes Ziel: {t} (möglich: {', '.join(TARGETS)})")
            failed += 1
            continue
        try:
            for msg in fn(theme, cfg, dry_run):
                print(f"  [{t}] {msg}")
        except Exception as e:  # ein kaputtes Ziel soll die anderen nicht aufhalten
            print(f"  ✗ [{t}] {e}")
            failed += 1
    if not dry_run:
        for hook in cfg.post_apply:
            cmd = hook.format(name=theme.name, dir=theme.path or "")
            subprocess.run(cmd, shell=True)
        store.set_current(theme.name)
    return 1 if failed else 0


def _print_swatch(theme: Theme) -> str:
    if not sys.stdout.isatty():
        return ""
    out = ""
    for col in theme.palette.colors[:8]:
        r, g, b = (round(x * 255) for x in c.to_rgb(col))
        out += f"\033[48;2;{r};{g};{b}m  "
    return out + "\033[0m"


# ---------------------------------------------------------------------------
# Befehle
# ---------------------------------------------------------------------------
def cmd_list(args, cfg, store):
    current = store.current()
    themes = store.list()
    if getattr(args, "json", False):
        print(json.dumps([
            {
                "id": t.path.name if t.path else t.name,
                "name": t.name,
                "mode": t.mode,
                "accent": t.palette.accent,
                "background": t.palette.background,
                "foreground": t.palette.foreground,
                "colors": t.palette.colors,
                "wallpaper": str(t.wallpaper_path()) if t.wallpaper_path() and t.wallpaper_path().exists() else "",
                "source": t.source or "",
                "current": bool(t.path and t.path.name == current),
            }
            for t in themes
        ], ensure_ascii=False))
        return 0
    if not themes:
        print("Noch keine Themes. Lege eins an mit 'themectl save <name>' oder 'themectl aether import --all'.")
        return 0
    for t in themes:
        mark = "●" if t.path and t.path.name == current else " "
        print(f"{mark} {t.path.name if t.path else t.name:<24} {_print_swatch(t)}  {t.mode}")
    return 0


def cmd_show(args, cfg, store):
    t = store.get(args.name)
    print(json.dumps(t.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_current(args, cfg, store):
    print(store.current() or "(keins)")
    return 0


def cmd_apply(args, cfg, store):
    return apply_theme(store.get(args.name), cfg, store, args.only, args.dry_run)


def cmd_save(args, cfg, store):
    """Speichert den aktuellen Desktop-Zustand als Theme."""
    current = dms_target.read_current(cfg)
    if current is None:
        print("Konnte das aktuelle DMS-Theme nicht lesen.", file=sys.stderr)
        return 1
    dark = current.get("dark") or {}
    light = current.get("light") or dark
    missing = [k for k in ("background", "primary") if k not in dark]
    if missing:
        print(f"DMS-Theme unvollständig, es fehlt: {missing}", file=sys.stderr)
        return 1
    wp = args.wallpaper or wallpaper_target.current()
    theme = Theme(
        name=args.name,
        palette=palette_from_dms(dark),
        dms={"dark": _colors_only(dark), "light": _colors_only(light)},
        wallpaper=wp,
        icon_theme=args.icons or icons_target.current(),
        source=f"dms:{current.get('name', 'unbekannt')}",
    )
    d = store.save(theme, overwrite=args.force)
    print(f"✓ Gespeichert: {d}")
    return 0


def cmd_create(args, cfg, store):
    if args.colors:
        ansi = [x for x in args.colors.replace(",", " ").split() if x]
        palette = Palette.from_ansi(ansi, {k: v for k, v in (("accent", args.accent), ("background", args.background), ("foreground", args.foreground)) if v})
    else:
        if not (args.background and args.accent):
            print("Bitte --background und --accent angeben (oder --colors mit 16 Farben).", file=sys.stderr)
            return 1
        bg = c.normalize(args.background)
        fg = c.normalize(args.foreground) if args.foreground else ("#e6e6e6" if c.is_dark(bg) else "#202020")
        palette = Palette.from_ansi(default_ansi(bg, fg, c.normalize(args.accent)), {"accent": args.accent})
    theme = Theme(
        name=args.name,
        palette=palette,
        mode="dark" if c.is_dark(palette.background) else "light",
        wallpaper=args.wallpaper,
        icon_theme=args.icons,
        source="manuell",
    )
    d = store.save(theme, overwrite=args.force)
    print(f"✓ Theme angelegt: {d}\n  Feinschliff: themectl edit {theme.name}")
    if args.apply:
        return apply_theme(store.get(args.name), cfg, store, None, False)
    return 0


def cmd_edit(args, cfg, store):
    import os

    t = store.get(args.name)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "micro"
    return subprocess.call([editor, str(t.path / "theme.json")])


def cmd_delete(args, cfg, store):
    store.delete(args.name)
    print(f"✓ Gelöscht: {args.name}")
    return 0


def cmd_export(args, cfg, store):
    t = store.get(args.name)
    out = Path(args.output or f"{t.path.name}.tar.gz").expanduser()
    base = str(out).removesuffix(".tar.gz")
    shutil.make_archive(base, "gztar", root_dir=t.path.parent, base_dir=t.path.name)
    print(f"✓ Exportiert: {base}.tar.gz")
    return 0


def cmd_import(args, cfg, store):
    src = Path(args.path).expanduser()
    if src.suffixes[-2:] == [".tar", ".gz"]:
        import tarfile

        with tarfile.open(src) as tar:
            tar.extractall(cfg.themes_dir, filter="data")
        print(f"✓ Importiert nach {cfg.themes_dir}")
        return 0
    theme_file = src / "theme.json" if src.is_dir() else src
    theme = Theme.from_dict(json.loads(theme_file.read_text()), path=theme_file.parent)
    if args.name:
        theme.name = args.name
    print(f"✓ Importiert: {store.save(theme, overwrite=args.force)}")
    return 0


def cmd_aether(args, cfg, store):
    if args.aether_cmd == "list":
        files = aether.blueprint_files(cfg.aether_dir)
        if not files:
            print(f"Keine Blueprints in {cfg.aether_dir / 'blueprints'}. In Aether ein Theme als Blueprint speichern.")
        for f in files:
            try:
                name = json.loads(f.read_text()).get("name", f.stem)
            except json.JSONDecodeError:
                name = f"{f.stem} (kaputt)"
            print(f"  {name:<28} {f.name}")
        return 0

    # import
    themes: list[Theme] = []
    if args.current:
        toml = cfg.aether_dir / "theme" / "colors.toml"
        if not toml.exists():
            print(f"{toml} fehlt. In Aether zuerst ein Theme anwenden.", file=sys.stderr)
            return 1
        themes.append(aether.theme_from_colors_toml(toml, args.name or "aether-aktuell"))
    elif args.all:
        themes = [aether.theme_from_blueprint(f) for f in aether.blueprint_files(cfg.aether_dir)]
    elif args.blueprint:
        themes.append(aether.theme_from_blueprint(aether.find_blueprint(cfg.aether_dir, args.blueprint), args.name))
    else:
        print("Gib einen Blueprint-Namen an, oder --all bzw. --current.", file=sys.stderr)
        return 1

    for t in themes:
        try:
            d = store.save(t, overwrite=args.force)
            print(f"✓ {t.name} → {d}")
        except FileExistsError as e:
            print(f"• {e}")
    if args.apply and len(themes) == 1:
        return apply_theme(store.get(themes[0].name), cfg, store, None, False)
    return 0


def _notify(title: str, body: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "themectl", title, body])


def _terminal_cmd(inner: list[str]) -> list[str] | None:
    """Startet inner in einem schwebenden Terminal (für Hotkeys ohne GUI-Menü)."""
    import os

    for term in filter(None, [os.environ.get("TERMINAL"), "ghostty", "kitty", "alacritty", "foot"]):
        if shutil.which(term):
            if term == "ghostty":
                return [term, "--class=themectl.picker", "-e", *inner]
            if term in ("kitty", "foot"):
                return [term, "--app-id" if term == "foot" else "--class", "themectl.picker", *inner]
            return [term, "--class", "themectl.picker", "-e", *inner]
    return None


def cmd_omarchy(args, cfg, store):
    if args.omarchy_cmd == "search":
        return cmd_omarchy_search(args, cfg, store)
    with omarchy.Source(args.source) as src:
        name = args.name or omarchy.default_name(src.path, src.repo_name)
        theme = omarchy.theme_from_dir(src.path, name, args.wallpaper)
        theme.source = f"omarchy:{args.source}"
        images = omarchy.find_wallpapers(src.path)
        chosen = Path(theme.wallpaper).name if theme.wallpaper else "-"
        d = store.save(theme, overwrite=args.force)  # kopiert das Wallpaper, solange der Klon noch existiert
    print(f"✓ {theme.name} → {d}")
    if len(images) > 1:
        print(f"  {len(images)} Hintergründe im Theme, genommen: {chosen}")
        print("  Anderen wählen: --wallpaper <Nummer|Teil des Namens> -f")
        for i, img in enumerate(images, 1):
            print(f"    {i:>2}. {img.name}")
    if args.apply:
        return apply_theme(store.get(theme.name), cfg, store, None, False)
    return 0


GALLERY_QML = Path(__file__).resolve().parent.parent / "app" / "ThemeGallery" / "shell.qml"
DESKTOP_FILE = """[Desktop Entry]
Type=Application
Name=Theme Galerie
GenericName=Theme-Auswahl
Comment=Alle themectl-Themes ansehen, anwenden und Omarchy-Themes online suchen
Exec={exe} gallery
Icon=preferences-desktop-theme
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=theme;themes;farben;wallpaper;omarchy;
"""


def _themectl_exe() -> str:
    exe = shutil.which("themectl")
    return exe or str(Path.home() / ".local/bin/themectl")


def cmd_gallery(args, cfg, store):
    if args.install:
        apps = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "applications"
        apps.mkdir(parents=True, exist_ok=True)
        target = apps / "themectl-gallery.desktop"
        target.write_text(DESKTOP_FILE.format(exe=_themectl_exe()))
        print(f"✓ Starter angelegt: {target}")
        return 0
    qs = shutil.which("qs") or shutil.which("quickshell")
    if not qs:
        print("Quickshell (qs) nicht gefunden, die Galerie braucht es.", file=sys.stderr)
        return 1
    if not GALLERY_QML.exists():
        print(f"Galerie nicht gefunden: {GALLERY_QML}", file=sys.stderr)
        return 1
    env = dict(os.environ, THEMECTL=_themectl_exe())
    if args.online is not None:
        env["THEME_GALLERY_TAB"] = "online"
        env["THEME_GALLERY_QUERY"] = " ".join(args.online)
    subprocess.Popen([qs, "-p", str(GALLERY_QML)], env=env, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_icons(args, cfg, store):
    if args.name:
        t = store.get(args.name)
        t.icon_theme = None if args.theme in ("auto", "") else args.theme
        store.save(t, overwrite=True, copy_wallpaper=False)
        print(f"✓ {t.name}: Icon-Theme = {t.icon_theme or 'automatisch'}")
        return 0
    names = icons_target.installed()
    cur = icons_target.current()
    print("Installierte Icon-Themes:")
    for n in names:
        print(f"  {'●' if n == cur else ' '} {n}")
    return 0


def cmd_omarchy_search(args, cfg, store):
    try:
        results = omarchy.search(" ".join(args.query), args.limit)
    except ValueError as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            return 1
        raise
    if not results and args.json:
        print("[]")
        return 0
    if not results:
        print("Nichts gefunden.")
        return 1
    installed = {t.path.name for t in store.list() if t.path}
    if args.json:
        for r in results:
            r["installed"] = r["name"].lower() in installed
        print(json.dumps(results, ensure_ascii=False))
        return 0

    def line(i: int, r: dict) -> str:
        mark = "✓" if r["name"].lower() in installed else " "
        desc = f" – {r['description'][:60]}" if r["description"] else ""
        return f"{i:>2}. {mark} {r['name']:<22} ★{r['stars']:<5} {r['repo']}{desc}"

    lines = [line(i, r) for i, r in enumerate(results, 1)]
    chosen: list[dict] = []
    if args.install:
        for n in args.install:
            if not 1 <= n <= len(results):
                print(f"Nummer {n} gibt es nicht (1–{len(results)})", file=sys.stderr)
                return 1
            chosen.append(results[n - 1])
    elif args.pick:
        menu = None
        if sys.stdin.isatty() and shutil.which("fzf"):
            menu = ["fzf", "--multi", "--prompt", "Omarchy-Theme> ", "--header", "Tab = mehrere wählen, Enter = importieren"]
        else:
            for tool, cmd in (("fuzzel", ["fuzzel", "--dmenu", "--width", "90"]), ("rofi", ["rofi", "-dmenu", "-multi-select"]), ("wofi", ["wofi", "--dmenu"])):
                if shutil.which(tool):
                    menu = cmd
                    break
        if menu is None:
            print("Kein Auswahlmenü gefunden (fzf, fuzzel, rofi oder wofi).", file=sys.stderr)
            return 1
        res = subprocess.run(menu, input="\n".join(lines), stdout=subprocess.PIPE, text=True)
        for sel in res.stdout.splitlines():
            m = re.match(r"\s*(\d+)\.", sel)
            if m:
                chosen.append(results[int(m.group(1)) - 1])
    else:
        print("\n".join(lines))
        cmd = " ".join(["themectl omarchy search", *args.query, "--install <Nr> [<Nr> …]"])
        print(f"\nImportieren: {cmd}   (✓ = schon vorhanden)")
        return 0

    rc = 0
    for r in chosen:
        print(f"▶ {r['repo']}")
        ns = argparse.Namespace(source=r["url"], name=None, wallpaper=None, apply=args.apply and len(chosen) == 1,
                                force=args.force, omarchy_cmd="import")
        try:
            rc |= cmd_omarchy(ns, cfg, store)
        except (FileNotFoundError, FileExistsError, ValueError) as e:
            print(f"  ✗ {e}")
            rc = 1
    return rc


def cmd_pick(args, cfg, store):
    names = [t.path.name for t in store.list() if t.path]
    if not names:
        print("Keine Themes vorhanden.")
        return 1
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    current = store.current()
    menus = {
        "fuzzel": ["fuzzel", "--dmenu", "--prompt", "Theme: "],
        "rofi": ["rofi", "-dmenu", "-p", "Theme"],
        "wofi": ["wofi", "--dmenu"],
        "fzf": ["fzf", "--prompt", "Theme> ", "--height", "~60%", "--reverse", "--header", f"aktiv: {current or '-'}"],
    }
    order = [args.menu] if args.menu else (["fzf", "fuzzel", "rofi", "wofi"] if interactive else ["fuzzel", "rofi", "wofi"])
    menu = next((menus[m] for m in order if shutil.which(m)), None)

    if menu is None and not interactive and not args.menu and shutil.which("fzf"):
        # Aus einem Hotkey gestartet, aber kein GUI-Menü da: fzf in einem Terminal öffnen
        term = _terminal_cmd([sys.executable, "-m", "theme_switcher", "pick", "--menu", "fzf"])
        if term:
            import os

            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            return subprocess.call(term, env=env)
    if menu is None:
        msg = "Kein Menü gefunden (fuzzel, rofi, wofi oder fzf installieren)."
        print(msg, file=sys.stderr)
        _notify("themectl", msg)
        return 1

    res = subprocess.run(menu, input="\n".join(names), stdout=subprocess.PIPE, text=True)
    choice = res.stdout.strip()
    if not choice:
        return 0
    rc = apply_theme(store.get(choice), cfg, store, None, False)
    _notify("Theme gewechselt" if rc == 0 else "Theme-Wechsel mit Fehlern", choice)
    return rc


def cmd_cycle(args, cfg, store):
    names = [t.path.name for t in store.list() if t.path]
    if not names:
        return 1
    cur = store.current()
    idx = names.index(cur) if cur in names else -1
    nxt = names[(idx + (1 if args.cmd == "next" else -1)) % len(names)]
    rc = apply_theme(store.get(nxt), cfg, store, None, False)
    if not sys.stdout.isatty():
        _notify("Theme gewechselt", nxt)
    return rc


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="themectl", description="Themes für Hyprland + DMS speichern, wechseln und aus Aether importieren.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, help="Pfad zur config.toml")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", aliases=["ls"], help="Gespeicherte Themes anzeigen")
    s.add_argument("--json", action="store_true", help="maschinenlesbar (für das DMS-Plugin)")
    s.set_defaults(fn=cmd_list)
    sub.add_parser("current", help="Aktives Theme anzeigen").set_defaults(fn=cmd_current)

    s = sub.add_parser("show", help="Theme-Inhalt anzeigen")
    s.add_argument("name")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("apply", help="Theme anwenden")
    s.add_argument("name")
    s.add_argument("--only", nargs="+", metavar="ZIEL", help=f"nur diese Ziele ({', '.join(TARGETS)})")
    s.add_argument("-n", "--dry-run", action="store_true", help="nur anzeigen, nichts ändern")
    s.set_defaults(fn=cmd_apply)

    s = sub.add_parser("save", help="Aktuellen Desktop als Theme speichern")
    s.add_argument("name")
    s.add_argument("--wallpaper", help="Hintergrundbild (sonst wird das aktuelle von DMS genommen)")
    s.add_argument("--icons", help="Icon-Theme (sonst das aktuell gesetzte)")
    s.add_argument("-f", "--force", action="store_true", help="vorhandenes Theme überschreiben")
    s.set_defaults(fn=cmd_save)

    s = sub.add_parser("create", help="Neues Theme aus Farben anlegen")
    s.add_argument("name")
    s.add_argument("--background", "--bg")
    s.add_argument("--foreground", "--fg")
    s.add_argument("--accent")
    s.add_argument("--colors", help="16 ANSI-Farben, durch Komma oder Leerzeichen getrennt")
    s.add_argument("--wallpaper")
    s.add_argument("--icons", help="Icon-Theme, z. B. Yaru-blue oder Papirus-Dark (sonst automatisch)")
    s.add_argument("--apply", action="store_true", help="direkt anwenden")
    s.add_argument("-f", "--force", action="store_true")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("edit", help="theme.json im Editor öffnen")
    s.add_argument("name")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("delete", aliases=["rm"], help="Theme löschen")
    s.add_argument("name")
    s.set_defaults(fn=cmd_delete)

    s = sub.add_parser("export", help="Theme als .tar.gz exportieren")
    s.add_argument("name")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("import", help="Theme aus theme.json, Ordner oder .tar.gz importieren")
    s.add_argument("path")
    s.add_argument("--name")
    s.add_argument("-f", "--force", action="store_true")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("aether", help="Themes aus Aether übernehmen")
    asub = s.add_subparsers(dest="aether_cmd", required=True)
    asub.add_parser("list", help="Aether-Blueprints anzeigen")
    ai = asub.add_parser("import", help="Blueprint(s) als Theme speichern")
    ai.add_argument("blueprint", nargs="?", help="Name oder Pfad eines Blueprints")
    ai.add_argument("--all", action="store_true", help="alle Blueprints importieren")
    ai.add_argument("--current", action="store_true", help="das gerade in Aether angewendete Theme übernehmen")
    ai.add_argument("--name", help="Name des neuen Themes")
    ai.add_argument("--apply", action="store_true", help="direkt anwenden")
    ai.add_argument("-f", "--force", action="store_true")
    s.set_defaults(fn=cmd_aether)

    s = sub.add_parser("omarchy", help="Omarchy-Theme importieren")
    osub = s.add_subparsers(dest="omarchy_cmd", required=True)
    oi = osub.add_parser("import", help="aus GitHub-URL, user/repo oder lokalem Ordner")
    oi.add_argument("source", help="z. B. https://github.com/OldJobobo/omarchy-miasma-theme")
    oi.add_argument("--name", help="Name des neuen Themes (Standard: aus dem Repo-Namen)")
    oi.add_argument("--wallpaper", help="welcher Hintergrund aus backgrounds/ (Nummer oder Namensteil)")
    oi.add_argument("--apply", action="store_true", help="direkt anwenden")
    oi.add_argument("-f", "--force", action="store_true")
    osr = osub.add_parser("search", help="Omarchy-Themes auf GitHub suchen")
    osr.add_argument("query", nargs="*", help="Suchbegriff, z. B. 'nord' oder 'dark green' (leer = beliebteste)")
    osr.add_argument("--limit", type=int, default=30, help="maximale Anzahl Treffer")
    osr.add_argument("--install", type=int, nargs="+", metavar="NR", help="Treffer mit diesen Nummern importieren")
    osr.add_argument("--pick", action="store_true", help="Treffer im Menü auswählen und importieren")
    osr.add_argument("--apply", action="store_true", help="bei genau einem Import direkt anwenden")
    osr.add_argument("-f", "--force", action="store_true")
    osr.add_argument("--json", action="store_true", help="Treffer als JSON ausgeben (für die Galerie-App)")
    s.set_defaults(fn=cmd_omarchy)

    s = sub.add_parser("icons", help="Icon-Themes anzeigen oder einem Theme zuweisen")
    s.add_argument("name", nargs="?", help="Theme, dem ein Icon-Theme zugewiesen wird")
    s.add_argument("theme", nargs="?", default="auto", help="Icon-Theme-Name oder 'auto'")
    s.set_defaults(fn=cmd_icons)

    s = sub.add_parser("pick", help="Theme über ein Menü (fuzzel/rofi/wofi/fzf) auswählen")
    s.add_argument("--menu", choices=["fuzzel", "rofi", "wofi", "fzf"])
    s.set_defaults(fn=cmd_pick)

    s = sub.add_parser("gallery", aliases=["app"], help="Theme-Galerie als eigenes Fenster öffnen")
    s.add_argument("--install", action="store_true", help="Starter 'Theme Galerie' fürs App-Menü anlegen")
    s.add_argument("--online", nargs="*", metavar="BEGRIFF", help="gleich den Online-Tab öffnen (optional mit Suchbegriff)")
    s.set_defaults(fn=cmd_gallery)

    sub.add_parser("next", help="Nächstes Theme anwenden").set_defaults(fn=cmd_cycle)
    sub.add_parser("prev", help="Vorheriges Theme anwenden").set_defaults(fn=cmd_cycle)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load(args.config)
    store = Store(cfg)
    try:
        return args.fn(args, cfg, store)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
