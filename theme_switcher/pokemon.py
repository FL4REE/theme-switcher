"""Pokémon passend zum Theme aus den Sprites von pokemon-colorscripts auswählen.

pokemon-colorscripts (https://gitlab.com/phoneybadger/pokemon-colorscripts)
legt pro Pokémon eine Datei mit ANSI-Truecolor-Escapes ab, z. B.
``colorscripts/small/regular/bulbasaur``. Aus diesen Escapes werden die
Pixel-Farben gezählt, die bunte Hauptfarbe jedes Pokémon bestimmt und mit dem
Akzent des Themes verglichen. Das Ergebnis wird zwischengespeichert.
"""

from __future__ import annotations

import colorsys
import json
import math
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from . import colors as c

_ESC = re.compile(r"\x1b\[(?:38|48);2;(\d+);(\d+);(\d+)m")

CANDIDATE_DIRS = [
    "/usr/local/opt/pokemon-colorscripts/colorscripts",
    "/opt/pokemon-colorscripts/colorscripts",
    "/usr/share/pokemon-colorscripts/colorscripts",
    "/usr/local/share/pokemon-colorscripts/colorscripts",
    "~/.local/share/pokemon-colorscripts/colorscripts",
    "~/.local/opt/pokemon-colorscripts/colorscripts",
]


def _pokefetch_sprites() -> list[str]:
    """Sprite-Ordner, den pokefetch (Yanzz231/PokeFetch) selbst mitbringt.

    pokefetch liefert die Sprites von pokemon-colorscripts im Paket mit
    (``src/colorscripts``). Der Paketordner wird über das Python aus der
    Shebang-Zeile von ``pokefetch`` ermittelt.
    """
    exe = shutil.which("pokefetch")
    if not exe:
        return []
    try:
        first = Path(exe).read_text(errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return []
    if not first.startswith("#!") or "python" not in first:
        return []
    cmd = first[2:].split() + ["-c", "import pathlib, src.cli; print(pathlib.Path(src.cli.__file__).parent)"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    pkg = res.stdout.strip()
    return [str(Path(pkg) / "colorscripts")] if res.returncode == 0 and pkg else []


def find_colorscripts(override: str | None = None) -> Path | None:
    candidates = [override] if override else []
    exe = shutil.which("pokemon-colorscripts")
    if exe:
        real = Path(exe).resolve()
        candidates += [str(real.parent / "colorscripts"), str(real.parent.parent / "colorscripts")]
    candidates += CANDIDATE_DIRS
    candidates += ["~/.local/share/pokefetch/colorscripts"]
    candidates += _pokefetch_sprites()
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand).expanduser()
        if (p / "small" / "regular").is_dir():
            return p
    return None


def sprite_profile(text: str) -> dict | None:
    """Häufigkeiten der Pixel-Farben -> bunte Hauptfarbe und deren Anteil."""
    counts = Counter(_ESC.findall(text))
    if not counts:
        return None
    hues: Counter = Counter()
    chroma_total = 0
    total = 0
    for (r, g, b), n in counts.items():
        rgb = (int(r) / 255, int(g) / 255, int(b) / 255)
        h, l, s = colorsys.rgb_to_hls(*rgb)
        total += n
        # Umrisse, Schatten und Glanzlichter zählen nicht als Farbe
        if s < 0.25 or l < 0.12 or l > 0.92:
            continue
        hues[c.from_rgb(*rgb)] += n
        chroma_total += n
    if not hues:
        return {"main": None, "colorful": 0.0}
    # Hauptfarbe = gewichteter Mittelwert der häufigsten Farbgruppe (nach Farbton gebündelt)
    buckets: Counter = Counter()
    for hex_, n in hues.items():
        h = colorsys.rgb_to_hls(*c.to_rgb(hex_))[0]
        buckets[int(h * 12) % 12] += n
    top_bucket = buckets.most_common(1)[0][0]
    members = {k: n for k, n in hues.items() if int(colorsys.rgb_to_hls(*c.to_rgb(k))[0] * 12) % 12 == top_bucket}
    weight = sum(members.values())
    r = sum(c.to_rgb(k)[0] * n for k, n in members.items()) / weight
    g = sum(c.to_rgb(k)[1] * n for k, n in members.items()) / weight
    b = sum(c.to_rgb(k)[2] * n for k, n in members.items()) / weight
    return {"main": c.from_rgb(r, g, b), "share": weight / max(chroma_total, 1), "colorful": chroma_total / total}


def analyse(colorscripts: Path, cache_file: Path) -> dict[str, dict]:
    """Profil aller Pokémon (regular, small), mit Cache."""
    src = colorscripts / "small" / "regular"
    stamp = f"{src}:{src.stat().st_mtime_ns}:{len(os.listdir(src))}"
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if cached.get("stamp") == stamp:
                return cached["pokemon"]
        except (json.JSONDecodeError, KeyError):
            pass
    result = {}
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        prof = sprite_profile(f.read_text(errors="ignore"))
        if prof and prof["main"]:
            result[f.name] = prof
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"stamp": stamp, "pokemon": result}))
    return result


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


def color_distance(a: str, b: str) -> float:
    """Farbabstand in Lab, Helligkeit nur halb gewichtet (Sprites sind oft heller als Akzente)."""
    la, aa, ba = _lab(a)
    lb, ab, bb = _lab(b)
    return math.sqrt(0.25 * (la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def matching(profiles: dict[str, dict], accent: str, count: int = 40, max_distance: float = 35.0) -> list[str]:
    """Pokémon, deren Hauptfarbe dem Akzent am nächsten kommt.

    Bevorzugt werden Pokémon, die überwiegend aus dieser einen Farbe bestehen.
    Mindestens 10 Treffer werden geliefert, auch wenn der Abstand größer ist.
    """
    scored = []
    for name, p in profiles.items():
        d = color_distance(accent, p["main"])
        # einfarbige Pokémon (hoher Anteil) leicht bevorzugen
        score = d * (1.3 - 0.5 * p.get("share", 0.5))
        scored.append((score, d, name))
    scored.sort()
    close = [name for score, d, name in scored if d <= max_distance][:count]
    if len(close) < 10:
        close = [name for _, _, name in scored[: max(10, min(count, len(scored)))]]
    return close
