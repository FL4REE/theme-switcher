"""Import aus Aether (https://github.com/bjarneo/aether).

Zwei Quellen werden unterstützt:

* **Blueprints** – gespeicherte Aether-Themes unter ``~/.config/aether/blueprints/*.json``
  (``{"name": ..., "palette": {"colors": [16 Hex], "wallpaper": ..., "extendedColors": {...}}}``)
* **Das gerade angewendete Aether-Theme** – ``~/.config/aether/theme/colors.toml``
  (Omarchy-Format mit ``color0`` … ``color15``, ``accent``, ``background`` …)
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .model import Palette, Theme


def blueprint_files(aether_dir: Path) -> list[Path]:
    d = aether_dir / "blueprints"
    return sorted(d.glob("*.json")) if d.exists() else []


def find_blueprint(aether_dir: Path, name_or_path: str) -> Path:
    p = Path(name_or_path).expanduser()
    if p.is_file():
        return p
    wanted = name_or_path.lower()
    for f in blueprint_files(aether_dir):
        if f.stem.lower() == wanted:
            return f
        try:
            if str(json.loads(f.read_text()).get("name", "")).lower() == wanted:
                return f
        except json.JSONDecodeError:
            continue
    raise FileNotFoundError(f"Aether-Blueprint '{name_or_path}' nicht gefunden in {aether_dir / 'blueprints'}")


def theme_from_blueprint(path: Path, name: str | None = None) -> Theme:
    data = json.loads(path.read_text())
    pal = data.get("palette") or {}
    colors = pal.get("colors") or []
    extended = pal.get("extendedColors") or {}
    mode = pal.get("mode") or ("light" if pal.get("lightMode") else "dark")
    return Theme(
        name=name or data.get("name") or path.stem,
        palette=Palette.from_ansi(colors, extended),
        mode=mode,
        wallpaper=pal.get("wallpaper") or None,
        source=f"aether-blueprint:{path.name}",
    )


def theme_from_colors_toml(path: Path, name: str, wallpaper: str | None = None) -> Theme:
    data = tomllib.loads(path.read_text())
    try:
        ansi = [data[f"color{i}"] for i in range(16)]
    except KeyError as e:
        raise ValueError(f"{path} enthält keine vollständige ANSI-Palette ({e} fehlt)") from None
    extended = {
        k: data[k]
        for k in ("background", "foreground", "accent", "cursor", "selection_background")
        if isinstance(data.get(k), str) and data[k].startswith("#")
    }
    if wallpaper is None:
        bg_dir = path.parent / "backgrounds"
        if bg_dir.is_dir():
            images = sorted(p for p in bg_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
            wallpaper = str(images[0]) if images else None
    return Theme(
        name=name,
        palette=Palette.from_ansi(ansi, extended),
        mode=data.get("mode") or "dark",
        wallpaper=wallpaper,
        source=f"aether-colors:{path}",
    )
