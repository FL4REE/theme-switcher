"""Das Theme-Format des Theme-Switchers.

Ein Theme ist ein Ordner mit einer ``theme.json`` und optional einem
Hintergrundbild. Beispiel::

    {
      "name": "poimandres",
      "version": 1,
      "mode": "dark",
      "palette": {
        "colors": ["#1b1e28", ... 16 ANSI-Farben ...],
        "background": "#1b1e28",
        "foreground": "#e4f0fb",
        "accent": "#89ddff",
        "cursor": "#a6accd",
        "selection": "#303340"
      },
      "wallpaper": "wallpaper.png",
      "dms": {"dark": {...}, "light": {...}},
      "hyprland": {"active_border": "#89ddff", "inactive_border": "#3c5170"},
      "source": "aether:Poimandres"
    }

``dms`` und ``hyprland`` sind optional; fehlen sie, werden sie aus der
Palette abgeleitet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import colors as c

SCHEMA_VERSION = 1

# Reihenfolge der DMS-Farbschlüssel, wie sie in ~/.config/dms/themes/*/theme.json vorkommen
DMS_KEYS = [
    "primary",
    "primaryText",
    "primaryContainer",
    "secondary",
    "surface",
    "surfaceText",
    "surfaceVariant",
    "surfaceVariantText",
    "surfaceTint",
    "background",
    "backgroundText",
    "outline",
    "surfaceContainer",
    "surfaceContainerHigh",
    "surfaceContainerHighest",
    "error",
    "warning",
    "info",
]


@dataclass
class Palette:
    colors: list[str]
    background: str
    foreground: str
    accent: str
    cursor: str
    selection: str

    @classmethod
    def from_ansi(cls, ansi: list[str], extended: dict[str, str] | None = None) -> "Palette":
        if len(ansi) < 16:
            raise ValueError(f"Es werden 16 ANSI-Farben benötigt, gefunden: {len(ansi)}")
        ansi = [c.normalize(x) for x in ansi[:16]]
        ext = {k: c.normalize(v) for k, v in (extended or {}).items() if v}
        return cls(
            colors=ansi,
            background=ext.get("background", ansi[0]),
            foreground=ext.get("foreground", ansi[7]),
            accent=ext.get("accent", ansi[4]),
            cursor=ext.get("cursor", ansi[7]),
            selection=ext.get("selection", ext.get("selection_background", ansi[8])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "colors": self.colors,
            "background": self.background,
            "foreground": self.foreground,
            "accent": self.accent,
            "cursor": self.cursor,
            "selection": self.selection,
        }


@dataclass
class Theme:
    name: str
    palette: Palette
    mode: str = "dark"
    wallpaper: str | None = None
    dms: dict[str, dict[str, str]] | None = None
    hyprland: dict[str, str] | None = None
    source: str | None = None
    path: Path | None = field(default=None, compare=False)

    # ---- (De-)Serialisierung ------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path | None = None) -> "Theme":
        p = data["palette"]
        palette = Palette(
            colors=[c.normalize(x) for x in p["colors"]],
            background=c.normalize(p["background"]),
            foreground=c.normalize(p["foreground"]),
            accent=c.normalize(p["accent"]),
            cursor=c.normalize(p.get("cursor", p["foreground"])),
            selection=c.normalize(p.get("selection", p["colors"][8])),
        )
        return cls(
            name=data["name"],
            palette=palette,
            mode=data.get("mode", "dark"),
            wallpaper=data.get("wallpaper"),
            dms=data.get("dms"),
            hyprland=data.get("hyprland"),
            source=data.get("source"),
            path=path,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "version": SCHEMA_VERSION,
            "mode": self.mode,
            "palette": self.palette.to_dict(),
        }
        for key in ("wallpaper", "dms", "hyprland", "source"):
            value = getattr(self, key)
            if value:
                d[key] = value
        return d

    @classmethod
    def load(cls, theme_dir: Path) -> "Theme":
        data = json.loads((theme_dir / "theme.json").read_text())
        return cls.from_dict(data, path=theme_dir)

    # ---- Abgeleitete Werte --------------------------------------------------
    def wallpaper_path(self) -> Path | None:
        if not self.wallpaper:
            return None
        wp = Path(self.wallpaper).expanduser()
        if not wp.is_absolute() and self.path is not None:
            wp = self.path / wp
        return wp

    def dms_colors(self) -> dict[str, dict[str, str]]:
        """Liefert die Farbblöcke 'dark' und 'light' für ein DMS-Theme."""
        generated = {"dark": derive_dms(self.palette, dark=True), "light": derive_dms(self.palette, dark=False)}
        if self.dms:
            for variant in ("dark", "light"):
                generated[variant].update(self.dms.get(variant, {}))
        return generated

    def hypr_colors(self) -> dict[str, str]:
        p = self.palette
        out = {
            "active_border": p.accent,
            "inactive_border": c.mix(p.background, p.colors[8], 0.6),
            "locked_active": p.colors[5],
        }
        out.update(self.hyprland or {})
        return out


def derive_dms(p: Palette, dark: bool = True) -> dict[str, str]:
    """Leitet ein DMS-Farbschema aus einer 16-Farben-Palette ab.

    Für die helle Variante werden Hintergrund und Vordergrund getauscht,
    damit DMS auch im Light-Mode lesbar bleibt.
    """
    bg, fg = (p.background, p.foreground) if dark else (p.foreground, p.background)
    if dark != c.is_dark(bg):
        # Palette passt nicht zur Variante (z. B. helles Aether-Theme) -> tauschen
        bg, fg = fg, bg
    step = 0.05 if dark else -0.05
    surface = c.lighten(bg, step)
    accent = p.accent
    return {
        "primary": accent,
        "primaryText": bg,
        "primaryContainer": p.colors[12],
        "secondary": p.colors[5],
        "surface": surface,
        "surfaceText": fg,
        "surfaceVariant": c.lighten(bg, step * 2),
        "surfaceVariantText": fg,
        "surfaceTint": accent,
        "background": bg,
        "backgroundText": fg,
        "outline": p.colors[8],
        "surfaceContainer": c.lighten(bg, step * 2),
        "surfaceContainerHigh": c.lighten(bg, step * 3),
        "surfaceContainerHighest": c.lighten(bg, step * 4),
        "error": p.colors[1],
        "warning": p.colors[3],
        "info": p.colors[6],
    }
