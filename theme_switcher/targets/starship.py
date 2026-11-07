"""Starship-Prompt: Farbpalette passend zum Theme.

Starship kennt ``palette = "<name>"`` und ``[palettes.<name>]``. themectl
schreibt einen markierten Block ``[palettes.theme_switcher]`` ans Ende von
``starship.toml`` und setzt ``palette = "theme_switcher"``. Der Block
enthält die Farbnamen der gängigen Presets (Catppuccin-Powerline,
Gruvbox-Rainbow) und allgemeine Namen (red, green, accent …), damit
bestehende Configs ohne Umbau mitfärben. Hart kodierte Hex-Werte in der
Config bleiben dagegen unverändert.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .. import colors as c
from ..config import Config
from ..model import Theme

PALETTE = "theme_switcher"
BEGIN = "# >>> theme-switcher (automatisch erzeugt, nicht bearbeiten) >>>"
END = "# <<< theme-switcher <<<"


def config_path(cfg: Config) -> Path:
    env = os.environ.get("STARSHIP_CONFIG")
    return Path(env).expanduser() if env else cfg.starship_file


def palette_colors(theme: Theme) -> dict[str, str]:
    p = theme.palette
    a = p.colors
    bg, fg = p.background, p.foreground
    dark = c.is_dark(bg)
    shade = (lambda x: c.lighten(bg, x)) if dark else (lambda x: c.lighten(bg, -x))
    out = {
        # allgemein
        "bg": bg, "fg": fg, "accent": p.accent, "cursor": p.cursor, "selection": p.selection,
        "black": a[0], "red": a[1], "green": a[2], "yellow": a[3], "blue": a[4],
        "magenta": a[5], "purple": a[5], "cyan": a[6], "white": a[7],
        "bright_black": a[8], "bright_red": a[9], "bright_green": a[10], "bright_yellow": a[11],
        "bright_blue": a[12], "bright_magenta": a[13], "bright_cyan": a[14], "bright_white": a[15],
        "orange": c.mix(a[1], a[3], 0.5),
        # Catppuccin (Preset "catppuccin-powerline")
        "rosewater": c.mix(a[15], a[13], 0.3), "flamingo": c.mix(a[13], a[15], 0.5),
        "pink": a[13], "mauve": a[5], "maroon": c.mix(a[1], a[9], 0.5),
        "peach": c.mix(a[9], a[11], 0.5), "teal": a[6], "sky": a[14],
        "sapphire": c.mix(a[12], a[14], 0.5), "lavender": a[12],
        "text": fg, "subtext1": c.mix(fg, bg, 0.15), "subtext0": c.mix(fg, bg, 0.3),
        "overlay2": c.mix(fg, bg, 0.45), "overlay1": c.mix(fg, bg, 0.55), "overlay0": c.mix(fg, bg, 0.65),
        "surface2": shade(0.15), "surface1": shade(0.10), "surface0": shade(0.05),
        "base": bg, "mantle": shade(-0.03), "crust": shade(-0.06),
        # Gruvbox-Rainbow-Preset
        "color_fg0": fg, "color_bg1": shade(0.08), "color_bg3": shade(0.18),
        "color_blue": a[4], "color_aqua": a[6], "color_green": a[2], "color_orange": c.mix(a[1], a[3], 0.5),
        "color_purple": a[5], "color_red": a[1], "color_yellow": a[3],
    }
    return out


def render_block(theme: Theme) -> str:
    lines = [BEGIN, f"# Theme: {theme.name}", f"[palettes.{PALETTE}]"]
    lines += [f'{k} = "{v}"' for k, v in palette_colors(theme).items()]
    lines.append(END)
    return "\n".join(lines) + "\n"


_TABLE = re.compile(r"^\s*\[")
_PALETTE_LINE = re.compile(r"^\s*palette\s*=")


def _top_level_lines(lines: list[str]) -> tuple[list[int], int]:
    """Indizes der Zeilen auf oberster Ebene (nicht in mehrzeiligen Strings)
    und den Index der ersten echten [Tabelle]."""
    top: list[int] = []
    delim: str | None = None
    for i, line in enumerate(lines):
        if delim is None:
            if _TABLE.match(line):
                return top, i
            top.append(i)
            for d in ('"""', "'''"):
                if line.count(d) % 2 == 1:
                    delim = d
                    break
        elif line.count(delim) % 2 == 1:
            delim = None
    return top, len(lines)


def update_config(text: str, theme: Theme) -> str:
    # alten Block entfernen
    text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", text, flags=re.S)
    lines = text.splitlines()
    top, first_table = _top_level_lines(lines)
    palette_line = f'palette = "{PALETTE}"'
    palette_idx = [i for i in top if _PALETTE_LINE.match(lines[i])]
    if palette_idx:
        lines[palette_idx[0]] = palette_line
        # doppelte palette-Zeilen (z. B. aus Version 0.1) entfernen
        for i in reversed(palette_idx[1:]):
            del lines[i]
    else:
        lines.insert(first_table, palette_line)
    body = "\n".join(lines).rstrip("\n")
    return body + "\n\n" + render_block(theme)


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    path = config_path(cfg)
    if not path.exists():
        return [f"übersprungen: {path} gibt es nicht"]
    if dry_run:
        return [f'würde palette = "{PALETTE}" in {path} setzen']
    backup = path.with_name(path.name + ".backup-theme-switcher")
    msgs = []
    if not backup.exists():
        shutil.copy2(path, backup)
        msgs.append(f"Sicherung angelegt: {backup}")
    new = update_config(path.read_text(), theme)
    tmp = path.with_name(path.name + ".ts-tmp")
    tmp.write_text(new)
    os.replace(tmp, path)
    msgs.append(f"Starship-Palette gesetzt: {path}")
    return msgs
