"""Ghostty-Theme schreiben.

Einmalig in ``~/.config/ghostty/config`` eintragen::

    theme = theme-switcher
"""

from __future__ import annotations

from ..config import Config
from ..model import Theme

THEME_NAME = "theme-switcher"


def render(theme: Theme) -> str:
    p = theme.palette
    lines = [f"# Erzeugt von theme-switcher, Theme: {theme.name}"]
    lines += [f"palette = {i}={col}" for i, col in enumerate(p.colors)]
    lines += [
        f"background = {p.background}",
        f"foreground = {p.foreground}",
        f"cursor-color = {p.cursor}",
        f"selection-background = {p.selection}",
        f"selection-foreground = {p.foreground}",
    ]
    return "\n".join(lines) + "\n"


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    from . import run

    target = cfg.ghostty_dir / "themes" / THEME_NAME
    if dry_run:
        return [f"würde {target} schreiben"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(theme))
    msgs = [f"Ghostty-Theme geschrieben: {target}"]
    # Ghostty lädt die Config bei SIGUSR2 neu
    err = run(["pkill", "-USR2", "-x", "ghostty"])
    if err and "Fehler" in err:
        msgs.append("Hinweis: Ghostty lief nicht oder konnte nicht neu laden")
    return msgs
