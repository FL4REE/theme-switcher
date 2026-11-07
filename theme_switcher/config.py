"""Konfiguration: ~/.config/theme-switcher/config.toml (optional)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _xdg(var: str, default: str) -> Path:
    return Path(os.environ.get(var) or Path.home() / default)


CONFIG_HOME = _xdg("XDG_CONFIG_HOME", ".config")
CACHE_HOME = _xdg("XDG_CACHE_HOME", ".cache")
DATA_HOME = _xdg("XDG_DATA_HOME", ".local/share")
STATE_HOME = _xdg("XDG_STATE_HOME", ".local/state")

DEFAULT_TARGETS = {
    # DMS-Shell: schreibt ein DMS-Theme und aktiviert es (Matugen-Hook färbt dann auch Hyprland)
    "dms": True,
    # Hintergrundbild über die DMS-IPC setzen (nur wenn das Theme eins hat)
    "wallpaper": True,
    # Eigene Hyprland-Farbdatei (nur nötig, wenn du dms.colors NICHT nutzt)
    "hyprland": False,
    # Ghostty-Theme-Datei schreiben (config muss 'theme = theme-switcher' enthalten)
    "ghostty": False,
    # Starship-Prompt: Palette "theme_switcher" in starship.toml setzen
    "starship": True,
    # Icon-Theme (gsettings + qt5ct/qt6ct), Stil siehe [icons] style
    "icons": True,
    # Neovim-Farbschema "theme-switcher" (colors/theme-switcher.lua)
    "nvim": True,
    # pokefetch: fish-Variable pokefetch_farben passend zum Akzent setzen
    "pokefetch": True,
}


@dataclass
class Config:
    themes_dir: Path = DATA_HOME / "theme-switcher" / "themes"
    state_dir: Path = STATE_HOME / "theme-switcher"
    dms_dir: Path = CONFIG_HOME / "dms"
    hypr_dir: Path = CONFIG_HOME / "hypr"
    aether_dir: Path = CONFIG_HOME / "aether"
    ghostty_dir: Path = CONFIG_HOME / "ghostty"
    starship_file: Path = CONFIG_HOME / "starship.toml"
    nvim_dir: Path = CONFIG_HOME / "nvim"
    targets: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_TARGETS))
    # Befehle, die nach dem Anwenden ausgeführt werden ({name}, {dir} werden ersetzt)
    post_apply: list[str] = field(default_factory=list)
    # "adwaita" (Adwaita in Akzentfarbe), "yaru" oder "theme" (icon_theme aus dem Theme)
    icon_style: str = "adwaita"
    # pokefetch: wie viele Pokédex-Farben und wie sie heißen (siehe targets/pokefetch.py)
    pokefetch_count: int = 2
    pokefetch_names: dict[str, str] = field(default_factory=dict)
    pokefetch_pool: int = 40
    pokefetch_colorscripts: str | None = None
    cache_dir: Path = CACHE_HOME / "theme-switcher"

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or Path(os.environ.get("THEME_SWITCHER_CONFIG", CONFIG_HOME / "theme-switcher" / "config.toml"))
        cfg = cls()
        if not path.exists():
            return cfg
        data = tomllib.loads(path.read_text())
        paths = data.get("paths", {})
        for key in ("themes_dir", "state_dir", "dms_dir", "hypr_dir", "aether_dir", "ghostty_dir", "starship_file", "nvim_dir", "cache_dir"):
            if key in paths:
                setattr(cfg, key, Path(paths[key]).expanduser())
        cfg.targets.update({k: bool(v) for k, v in data.get("targets", {}).items()})
        cfg.post_apply = list(data.get("hooks", {}).get("post_apply", []))
        poke = data.get("pokefetch", {})
        if isinstance(poke.get("count"), int) and poke["count"] > 0:
            cfg.pokefetch_count = poke["count"]
        cfg.pokefetch_names.update({str(k): str(v) for k, v in poke.get("names", {}).items()})
        if isinstance(poke.get("pool"), int) and poke["pool"] > 0:
            cfg.pokefetch_pool = poke["pool"]
        if poke.get("colorscripts_dir"):
            cfg.pokefetch_colorscripts = str(poke["colorscripts_dir"])
        style = data.get("icons", {}).get("style")
        if style in ("adwaita", "yaru", "theme"):
            cfg.icon_style = style
        return cfg
