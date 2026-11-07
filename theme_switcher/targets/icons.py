"""Icon-Theme passend zum Theme setzen (GTK über gsettings, Qt über qt5ct/qt6ct).

Drei Stile, einstellbar in config.toml unter ``[icons] style``:

* ``adwaita`` (Standard): immer Adwaita, in der Farbe, die dem Akzent am
  nächsten kommt. Nutzt die Varianten von Adwaita-colors
  (https://github.com/dpejoh/Adwaita-colors, z. B. ``Adwaita-teal``) und setzt
  zusätzlich die GNOME-Akzentfarbe (``accent-color``) für libadwaita-Apps.
* ``yaru``: die passende Yaru-Farbvariante (wie Omarchy).
* ``theme``: das ``icon_theme`` aus dem Theme, sonst Yaru.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .. import colors as c
from ..config import DATA_HOME, Config
from ..model import Theme

# Akzentfarben der Yaru-Varianten
YARU = {
    "Yaru": "#e95420",
    "Yaru-blue": "#0073e5",
    "Yaru-bark": "#787859",
    "Yaru-magenta": "#b34cb3",
    "Yaru-olive": "#4b8501",
    "Yaru-prussiangreen": "#308280",
    "Yaru-purple": "#7764d8",
    "Yaru-red": "#da3450",
    "Yaru-sage": "#657b69",
    "Yaru-viridian": "#03875b",
    "Yaru-wartybrown": "#b39169",
}


# Akzentfarben der Adwaita-colors-Varianten (aus deren variants.conf)
ADWAITA = {
    "Adwaita-blue": "#3f8ae5",
    "Adwaita-teal": "#129eb0",
    "Adwaita-green": "#3d9e4f",
    "Adwaita-yellow": "#cb931a",
    "Adwaita-orange": "#f17738",
    "Adwaita-red": "#e84053",
    "Adwaita-pink": "#e64392",
    "Adwaita-purple": "#954ab5",
    "Adwaita-slate": "#637692",
    "Adwaita-brown": "#a5734b",
}
# Werte, die org.gnome.desktop.interface accent-color kennt (kein "brown")
GNOME_ACCENTS = ["blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate"]


def icon_dirs() -> list[Path]:
    dirs = [DATA_HOME / "icons", Path.home() / ".icons"]
    xdg = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    dirs += [Path(d) / "icons" for d in xdg.split(":") if d]
    return dirs


def installed() -> list[str]:
    names = set()
    for d in icon_dirs():
        if d.is_dir():
            names.update(p.name for p in d.iterdir() if (p / "index.theme").exists())
    return sorted(names, key=str.lower)


def _dist(a: str, b: str) -> float:
    """Farbabstand nach der "Redmean"-Näherung (grob wahrnehmungsgerecht, ohne Lab)."""
    ar, ag, ab = c.to_rgb(a)
    r, g, b_ = c.to_rgb(b)
    rm = (ar + r) / 2
    return (2 + rm) * (ar - r) ** 2 + 4 * (ag - g) ** 2 + (3 - rm) * (ab - b_) ** 2


def _nearest(accent: str, table: dict[str, str]) -> str | None:
    return min(table, key=lambda k: _dist(accent, table[k])) if table else None


def nearest_yaru(accent: str, available: list[str] | None = None) -> str | None:
    available = installed() if available is None else available
    return _nearest(accent, {k: v for k, v in YARU.items() if k in available})


def nearest_adwaita(accent: str) -> str:
    """Name der Adwaita-colors-Variante (unabhängig davon, ob installiert)."""
    return _nearest(accent, ADWAITA)  # type: ignore[return-value]


def gnome_accent(accent: str) -> str:
    table = {k: ADWAITA[f"Adwaita-{k}"] for k in GNOME_ACCENTS}
    return _nearest(accent, table)  # type: ignore[return-value]


def resolve(theme: Theme, available: list[str] | None = None, style: str = "theme") -> tuple[str | None, str]:
    available = installed() if available is None else available
    if style == "adwaita":
        variant = nearest_adwaita(theme.palette.accent)
        if variant in available:
            return variant, "Adwaita in Akzentfarbe"
        if "Adwaita" in available or not available:
            return "Adwaita", f"{variant} fehlt (Adwaita-colors installieren), nehme Adwaita"
        return None, "Adwaita ist nicht installiert"
    if style == "yaru":
        auto = nearest_yaru(theme.palette.accent, available)
        return (auto, "Yaru in Akzentfarbe") if auto else (None, "Yaru ist nicht installiert")
    if theme.icon_theme:
        if theme.icon_theme in available:
            return theme.icon_theme, "aus dem Theme"
        fallback = nearest_yaru(theme.palette.accent, available)
        hint = " (yaru-icon-theme installieren?)" if theme.icon_theme.startswith("Yaru") else ""
        if fallback:
            return fallback, f"'{theme.icon_theme}' ist nicht installiert{hint}, nehme {fallback}"
        return None, f"'{theme.icon_theme}' ist nicht installiert{hint}"
    auto = nearest_yaru(theme.palette.accent, available)
    if auto:
        return auto, "passend zum Akzent gewählt"
    return None, "kein Icon-Theme im Theme und Yaru nicht installiert"


def _set_qt(name: str, config_home: Path) -> list[str]:
    msgs = []
    for tool in ("qt5ct", "qt6ct"):
        f = config_home / tool / f"{tool}.conf"
        if not f.exists():
            continue
        text = f.read_text()
        if re.search(r"(?m)^icon_theme=", text):
            text = re.sub(r"(?m)^icon_theme=.*$", f"icon_theme={name}", text)
        elif "[Appearance]" in text:
            text = text.replace("[Appearance]", f"[Appearance]\nicon_theme={name}", 1)
        else:
            text += f"\n[Appearance]\nicon_theme={name}\n"
        f.write_text(text)
        msgs.append(f"{tool} aktualisiert")
    return msgs


def current() -> str | None:
    if shutil.which("gsettings") is None:
        return None
    res = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"], capture_output=True, text=True)
    return res.stdout.strip().strip("'") or None if res.returncode == 0 else None


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    from . import run

    style = cfg.icon_style
    name, why = resolve(theme, style=style)
    if name is None:
        return [f"übersprungen: {why}"]
    accent = gnome_accent(theme.palette.accent) if style == "adwaita" else None
    if dry_run:
        return [f"würde Icon-Theme {name} setzen ({why})" + (f", GNOME-Akzent {accent}" if accent else "")]
    msgs = [f"Icon-Theme {name} ({why})"]
    for err in (
        run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", name]),
        run(["gsettings", "set", "org.gnome.desktop.interface", "accent-color", accent]) if accent else None,
    ):
        if err:
            msgs.append(err)
    if accent:
        msgs.append(f"GNOME-Akzentfarbe: {accent}")
    # qt5ct/qt6ct liegen neben dem DMS-Ordner (~/.config)
    msgs += _set_qt(name, cfg.dms_dir.parent)
    return msgs
