"""DankMaterialShell: Theme-Datei schreiben und in settings.json aktivieren.

DMS lädt ein eigenes Theme über ``currentThemeName = "custom"`` und
``customThemeFile = <pfad>/theme.json``. Der Matugen-Hook von DMS erzeugt
danach auch ``~/.config/hypr/dms/colors.lua`` (Rahmenfarben in Hyprland).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from ..config import Config
from ..model import Theme
from ..store import slugify

PREFIX = "ts-"


def theme_json(theme: Theme) -> dict:
    cols = theme.dms_colors()
    slug = PREFIX + slugify(theme.name)
    return {
        "id": slug,
        "name": theme.name,
        "version": "1.0.0",
        "author": "theme-switcher",
        "description": f"Erzeugt von theme-switcher ({theme.source or 'eigenes Theme'})",
        "dark": cols["dark"],
        "light": cols["light"],
        "sourceDir": slug,
    }


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".ts-tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    msgs: list[str] = []
    target_dir = cfg.dms_dir / "themes" / (PREFIX + slugify(theme.name))
    theme_file = target_dir / "theme.json"
    settings_file = cfg.dms_dir / "settings.json"

    if dry_run:
        return [f"würde {theme_file} schreiben", f"würde customThemeFile in {settings_file} setzen"]

    target_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(theme_file, json.dumps(theme_json(theme), indent=2) + "\n")
    msgs.append(f"DMS-Theme geschrieben: {theme_file}")

    if not settings_file.exists():
        msgs.append(f"Warnung: {settings_file} fehlt, DMS-Theme bitte in den DMS-Einstellungen auswählen")
        return msgs

    backup = settings_file.with_name("settings.json.backup-theme-switcher")
    if not backup.exists():
        shutil.copy2(settings_file, backup)
        msgs.append(f"Sicherung angelegt: {backup}")

    settings = json.loads(settings_file.read_text())
    settings["currentThemeName"] = "custom"
    settings["customThemeFile"] = str(theme_file)
    if theme.mode in ("dark", "light") and "isLightMode" in settings:
        settings["isLightMode"] = theme.mode == "light"
    _atomic_write(settings_file, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    msgs.append("DMS auf das Theme umgestellt")
    return msgs


def read_current(cfg: Config) -> dict | None:
    """Liest das aktuell in DMS aktive eigene Theme (für 'themectl save')."""
    settings_file = cfg.dms_dir / "settings.json"
    if not settings_file.exists():
        return None
    settings = json.loads(settings_file.read_text())
    f = settings.get("customThemeFile")
    if settings.get("currentThemeName") == "custom" and f and Path(f).exists():
        return json.loads(Path(f).read_text())
    name = settings.get("currentThemeName")
    candidate = cfg.dms_dir / "themes" / str(name) / "theme.json"
    if name and candidate.exists():
        return json.loads(candidate.read_text())
    return None
