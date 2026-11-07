"""Icon-Theme passend zum Theme setzen (GTK über gsettings, Qt über qt5ct/qt6ct).

Hat ein Theme kein ``icon_theme``, wird – wie bei Omarchy – die
Yaru-Farbvariante gewählt, die dem Akzent am nächsten kommt, sofern Yaru
installiert ist (``yaru-icon-theme``).
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


def nearest_yaru(accent: str, available: list[str] | None = None) -> str | None:
    available = installed() if available is None else available
    candidates = {k: v for k, v in YARU.items() if k in available}
    if not candidates:
        return None
    ar, ag, ab = c.to_rgb(accent)

    def dist(hex_: str) -> float:
        r, g, b = c.to_rgb(hex_)
        # "Redmean"-Näherung: grob wahrnehmungsgerecht, ohne Lab-Umrechnung
        rm = (ar + r) / 2
        return (2 + rm) * (ar - r) ** 2 + 4 * (ag - g) ** 2 + (3 - rm) * (ab - b) ** 2

    return min(candidates, key=lambda k: dist(candidates[k]))


def resolve(theme: Theme, available: list[str] | None = None) -> tuple[str | None, str]:
    available = installed() if available is None else available
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

    name, why = resolve(theme)
    if name is None:
        return [f"übersprungen: {why}"]
    if dry_run:
        return [f"würde Icon-Theme {name} setzen ({why})"]
    msgs = [f"Icon-Theme {name} ({why})"]
    err = run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", name])
    if err:
        msgs.append(err)
    # qt5ct/qt6ct liegen neben dem DMS-Ordner (~/.config)
    msgs += _set_qt(name, cfg.dms_dir.parent)
    return msgs
