"""pokefetch: nur Pokémon in Theme-passenden Farben anzeigen.

Setzt die universelle fish-Variable ``pokefetch_farben``, die die
``fish_greeting``-Funktion an ``pokefetch-color`` weitergibt. Universelle
Variablen gelten sofort in allen offenen fish-Shells.

Die Farben sind die zehn Pokédex-Farbklassen. Die Namen, die übergeben
werden, lassen sich in ``config.toml`` unter ``[pokefetch] names`` anpassen,
falls ``pokefetch-color`` andere Wörter erwartet.
"""

from __future__ import annotations

import colorsys
import math
import shutil
import subprocess

from .. import colors as c
from ..config import Config
from ..model import Theme

# Pokédex-Farbklasse -> typischer Farbton
POKEDEX = {
    "black": "#303030",
    "blue": "#3b6fd8",
    "brown": "#a0703c",
    "gray": "#9a9a9a",
    "green": "#4caf50",
    "pink": "#f2a2c0",
    "purple": "#8e5bc6",
    "red": "#e04040",
    "white": "#f0f0f0",
    "yellow": "#f2d03b",
}
ACHROMATIC = {"black", "gray", "white"}

DEFAULT_NAMES = {
    "black": "schwarz",
    "blue": "blau",
    "brown": "braun",
    "gray": "grau",
    "green": "grün",
    "pink": "rosa",
    "purple": "lila",
    "red": "rot",
    "white": "weiß",
    "yellow": "gelb",
}


def _lab(hex_: str) -> tuple[float, float, float]:
    def lin(x: float) -> float:
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in c.to_rgb(hex_))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _dist(a: str, b: str) -> float:
    """Abstand vor allem nach Farbton (Lab-Hue), Helligkeit nur als Feinsortierung."""
    la, aa, ba = _lab(a)
    lb, ab, bb = _lab(b)
    ha, hb = math.degrees(math.atan2(ba, aa)) % 360, math.degrees(math.atan2(bb, ab)) % 360
    dh = abs(ha - hb)
    return min(dh, 360 - dh) + abs(la - lb) * 0.15


def _saturation(hex_: str) -> float:
    return colorsys.rgb_to_hls(*c.to_rgb(hex_))[2]


def pick_colors(theme: Theme, count: int = 2) -> list[str]:
    """Die Pokédex-Farben, die am besten zum Akzent passen.

    Bei einem bunten Akzent werden nur bunte Klassen genommen, bei einem
    grauen Akzent auch Schwarz/Grau/Weiß.
    """
    accent = theme.palette.accent
    if _saturation(accent) < 0.2:
        # grauer Akzent: nach Helligkeit Schwarz/Grau/Weiß
        lum = _lab(accent)[0]
        ranked = sorted(ACHROMATIC, key=lambda k: abs(_lab(POKEDEX[k])[0] - lum))
        return ranked[:count]
    pool = {k: v for k, v in POKEDEX.items() if k not in ACHROMATIC}
    ranked = sorted(pool, key=lambda k: _dist(accent, pool[k]))
    return ranked[:count]


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    names = {**DEFAULT_NAMES, **cfg.pokefetch_names}
    picked = [names[k] for k in pick_colors(theme, cfg.pokefetch_count)]
    if dry_run:
        return [f"würde pokefetch_farben = {' '.join(picked)} setzen"]
    if shutil.which("fish") is None:
        return ["übersprungen: fish nicht gefunden"]
    quoted = " ".join("'" + n.replace("\\", "\\\\").replace("'", "\\'") + "'" for n in picked)
    res = subprocess.run(["fish", "-c", f"set -U pokefetch_farben {quoted}"], capture_output=True, text=True)
    if res.returncode != 0:
        return [f"Fehler: {res.stderr.strip()}"]
    return [f"pokefetch-Farben: {' '.join(picked)}"]
