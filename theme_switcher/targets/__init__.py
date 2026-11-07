"""Ziele, auf die ein Theme angewendet wird.

Jedes Ziel hat eine Funktion ``apply(theme, cfg, dry_run) -> list[str]``,
die eine Liste von Meldungen zurückgibt.
"""

from __future__ import annotations

import shutil
import subprocess

from . import dms, ghostty, hyprland, icons, nvim, starship, wallpaper

TARGETS = {
    "dms": dms.apply,
    "wallpaper": wallpaper.apply,
    "hyprland": hyprland.apply,
    "ghostty": ghostty.apply,
    "starship": starship.apply,
    "icons": icons.apply,
    "nvim": nvim.apply,
}


def run(cmd: list[str], dry_run: bool = False) -> str | None:
    """Führt einen Befehl aus, wenn er installiert ist. Gibt eine Meldung zurück."""
    if dry_run:
        return "würde ausführen: " + " ".join(cmd)
    if shutil.which(cmd[0]) is None:
        return f"übersprungen: '{cmd[0]}' nicht gefunden"
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return f"Fehler bei {' '.join(cmd)}: {(res.stderr or res.stdout).strip()}"
    return None
