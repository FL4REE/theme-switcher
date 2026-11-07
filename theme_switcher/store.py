"""Ablage der Themes unter ~/.local/share/theme-switcher/themes/<name>/."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import Config
from .model import Theme


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-").lower()
    if not slug:
        raise ValueError(f"Ungültiger Theme-Name: {name!r}")
    return slug


class Store:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.root = cfg.themes_dir

    def theme_dir(self, name: str) -> Path:
        return self.root / slugify(name)

    def list(self) -> list[Theme]:
        if not self.root.exists():
            return []
        themes = []
        for d in sorted(self.root.iterdir()):
            if (d / "theme.json").exists():
                try:
                    themes.append(Theme.load(d))
                except (KeyError, ValueError, json.JSONDecodeError) as e:
                    print(f"Warnung: {d.name} übersprungen ({e})")
        return themes

    def exists(self, name: str) -> bool:
        return (self.theme_dir(name) / "theme.json").exists()

    def get(self, name: str) -> Theme:
        d = self.theme_dir(name)
        if not (d / "theme.json").exists():
            raise FileNotFoundError(f"Theme '{name}' nicht gefunden ({d})")
        return Theme.load(d)

    def save(self, theme: Theme, overwrite: bool = False, copy_wallpaper: bool = True) -> Path:
        d = self.theme_dir(theme.name)
        if d.exists() and not overwrite:
            raise FileExistsError(f"Theme '{theme.name}' existiert schon (mit --force überschreiben)")
        d.mkdir(parents=True, exist_ok=True)
        wp = theme.wallpaper_path()
        if copy_wallpaper and wp and wp.is_file() and wp.parent != d:
            target = d / ("wallpaper" + wp.suffix.lower())
            shutil.copy2(wp, target)
            theme.wallpaper = target.name
        theme.path = d
        (d / "theme.json").write_text(json.dumps(theme.to_dict(), indent=2, ensure_ascii=False) + "\n")
        return d

    def delete(self, name: str) -> None:
        d = self.theme_dir(name)
        if not d.exists():
            raise FileNotFoundError(f"Theme '{name}' nicht gefunden")
        shutil.rmtree(d)

    # ---- aktuelles Theme merken -------------------------------------------
    def current(self) -> str | None:
        f = self.cfg.state_dir / "current"
        return f.read_text().strip() if f.exists() else None

    def set_current(self, name: str) -> None:
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True)
        (self.cfg.state_dir / "current").write_text(slugify(name) + "\n")
