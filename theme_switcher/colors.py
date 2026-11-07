"""Kleine Farb-Helfer ohne externe Abhängigkeiten."""

from __future__ import annotations

import colorsys
import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")


def normalize(value: str) -> str:
    """Gibt eine Farbe als '#rrggbb' (Kleinbuchstaben) zurück."""
    m = _HEX.match(value.strip())
    if not m:
        raise ValueError(f"Ungültige Farbe: {value!r}")
    return "#" + m.group(1).lower()


def to_rgb(value: str) -> tuple[float, float, float]:
    h = normalize(value)[1:]
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def from_rgb(r: float, g: float, b: float) -> str:
    clamp = lambda x: max(0, min(255, round(x * 255)))  # noqa: E731
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))


def lighten(value: str, amount: float) -> str:
    """Hellt (amount > 0) oder dunkelt (amount < 0) eine Farbe in HLS auf."""
    h, l, s = colorsys.rgb_to_hls(*to_rgb(value))
    l = max(0.0, min(1.0, l + amount))
    return from_rgb(*colorsys.hls_to_rgb(h, l, s))


def mix(a: str, b: str, t: float) -> str:
    ra, rb = to_rgb(a), to_rgb(b)
    return from_rgb(*(x + (y - x) * t for x, y in zip(ra, rb)))


def luminance(value: str) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(c) for c in to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_dark(value: str) -> bool:
    return luminance(value) < 0.4


def bare(value: str) -> str:
    """'#89ddff' -> '89ddff' (für Hyprland rgb()/rgba())."""
    return normalize(value)[1:]
