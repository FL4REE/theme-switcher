"""Hintergrundbild über die DMS-IPC setzen."""

from __future__ import annotations

import shutil
import subprocess

from ..config import Config
from ..model import Theme


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    from . import run

    wp = theme.wallpaper_path()
    if wp is None:
        return ["Kein Hintergrundbild im Theme, bleibt wie es ist"]
    if not wp.exists():
        return [f"Warnung: Hintergrundbild fehlt: {wp}"]
    err = run(["dms", "ipc", "call", "wallpaper", "set", str(wp)], dry_run)
    return [err or f"Hintergrund gesetzt: {wp}"]


def current() -> str | None:
    if shutil.which("dms") is None:
        return None
    res = subprocess.run(["dms", "ipc", "call", "wallpaper", "get"], capture_output=True, text=True)
    out = res.stdout.strip()
    return out if res.returncode == 0 and out.startswith("/") else None
