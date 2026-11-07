"""Import von Omarchy-Themes (Git-Repo oder lokaler Ordner).

Ein Omarchy-Theme ist ein Ordner mit App-Configs, zum Beispiel
``colors.toml``, ``alacritty.toml``, ``kitty.conf``, ``hyprland.conf`` und
``backgrounds/``. Die Farben werden in dieser Reihenfolge gesucht:

1. ``colors.toml`` (neues Omarchy-Format, ``color0`` … ``color15`` oder
   semantische Namen wie ``red`` und ``bright_red``)
2. ``alacritty.toml`` (``[colors.normal]`` / ``[colors.bright]``)
3. ``kitty.conf`` (``color0`` … ``color15``)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import tomllib
import urllib.error
from pathlib import Path

from . import colors as c
from .model import Palette, Theme

ANSI_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_GITHUB_TREE = re.compile(r"^(https://github\.com/[^/]+/[^/]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$")


# ---------------------------------------------------------------------------
# Quelle holen
# ---------------------------------------------------------------------------
class Source:
    """Lokaler Ordner oder temporärer Git-Klon (als Context-Manager nutzen)."""

    def __init__(self, spec: str):
        self.spec = spec
        self._tmp: tempfile.TemporaryDirectory | None = None
        self.path: Path
        self.repo_name: str | None = None

    def __enter__(self) -> "Source":
        local = Path(self.spec).expanduser()
        if local.is_dir():
            self.path = local
            return self
        url, branch, subdir = self.spec, None, None
        m = _GITHUB_TREE.match(self.spec)
        if m:
            url, branch, subdir = m.group(1), m.group(2), m.group(3)
        elif re.fullmatch(r"[\w.-]+/[\w.-]+", self.spec):
            url = f"https://github.com/{self.spec}"
        if not re.match(r"^(https://|git@)", url):
            raise FileNotFoundError(f"'{self.spec}' ist weder ein Ordner noch eine Git-URL")
        if shutil.which("git") is None:
            raise FileNotFoundError("git ist nicht installiert")
        self._tmp = tempfile.TemporaryDirectory(prefix="themectl-omarchy-")
        cmd = ["git", "clone", "--quiet", "--depth", "1"]
        if branch:
            cmd += ["--branch", branch]
        dest = Path(self._tmp.name) / "repo"
        res = subprocess.run([*cmd, url, str(dest)], capture_output=True, text=True)
        if res.returncode != 0:
            raise FileNotFoundError(f"Klonen fehlgeschlagen: {res.stderr.strip()}")
        self.path = dest / subdir if subdir else dest
        self.repo_name = url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
        return self

    def __exit__(self, *exc) -> None:
        if self._tmp:
            self._tmp.cleanup()


def default_name(theme_dir: Path, repo_name: str | None) -> str:
    name = repo_name or theme_dir.name
    name = re.sub(r"^omarchy-", "", name, flags=re.I)
    name = re.sub(r"-theme$", "", name, flags=re.I)
    return name or "omarchy"


# ---------------------------------------------------------------------------
# Farben lesen
# ---------------------------------------------------------------------------
def _hex(v) -> str | None:
    if isinstance(v, str):
        v = v.strip().strip("'\"")
        if v.startswith("0x"):
            v = "#" + v[2:]
        try:
            return c.normalize(v)
        except ValueError:
            return None
    return None


def palette_from_colors_toml(data: dict) -> tuple[list[str], dict[str, str]] | None:
    ansi = [_hex(data.get(f"color{i}")) for i in range(16)]
    if not all(ansi):
        sem = [data.get("bg") or data.get("background"), data.get("red"), data.get("green"), data.get("yellow"),
               data.get("blue"), data.get("magenta") or data.get("purple"), data.get("cyan"),
               data.get("fg") or data.get("foreground")]
        sem = [_hex(x) for x in sem]
        if not all(sem):
            return None
        bright = [_hex(data.get(k)) for k in ("muted", "bright_red", "bright_green", "bright_yellow",
                                               "bright_blue", "bright_magenta", "bright_cyan", "bright_fg")]
        ansi = sem + [b or s for b, s in zip(bright, sem)]
    ext = {}
    for key, src in (("background", "background"), ("foreground", "foreground"), ("accent", "accent"),
                     ("cursor", "cursor"), ("selection", "selection_background")):
        h = _hex(data.get(src))
        if h:
            ext[key] = h
    return ansi, ext  # type: ignore[return-value]


def palette_from_alacritty(data: dict) -> tuple[list[str], dict[str, str]] | None:
    cols = data.get("colors", {})
    normal, bright = cols.get("normal", {}), cols.get("bright", {})
    ansi = [_hex(normal.get(n)) for n in ANSI_NAMES] + [_hex(bright.get(n)) for n in ANSI_NAMES]
    if not all(ansi[:8]):
        return None
    ansi = [b or n for b, n in zip(ansi, ansi[:8] * 2)]
    ext = {}
    prim = cols.get("primary", {})
    for key, val in (("background", prim.get("background")), ("foreground", prim.get("foreground")),
                     ("cursor", cols.get("cursor", {}).get("cursor")),
                     ("selection", cols.get("selection", {}).get("background"))):
        h = _hex(val)
        if h:
            ext[key] = h
    return ansi, ext  # type: ignore[return-value]


def palette_from_kitty(text: str) -> tuple[list[str], dict[str, str]] | None:
    vals: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and (h := _hex(parts[1])):
            vals[parts[0]] = h
    ansi = [vals.get(f"color{i}") for i in range(16)]
    if not all(ansi):
        return None
    ext = {k: vals[k2] for k, k2 in (("background", "background"), ("foreground", "foreground"),
                                     ("cursor", "cursor"), ("selection", "selection_background")) if k2 in vals}
    return ansi, ext  # type: ignore[return-value]


def hypr_accent(theme_dir: Path) -> str | None:
    """Erste Farbe aus col.active_border in hyprland.conf (Variablen werden aufgelöst)."""
    f = theme_dir / "hyprland.conf"
    if not f.exists():
        return None
    text = f.read_text(errors="ignore")
    variables = dict(re.findall(r"^\s*\$(\w+)\s*=\s*(.+?)\s*$", text, flags=re.M))
    m = re.search(r"col\.active_border\s*=\s*(.+)", text)
    if not m:
        return None
    first = m.group(1).split()[0]
    if first.startswith("$"):
        first = variables.get(first[1:], "")
    rgb = re.search(r"rgba?\(([0-9a-fA-F]{6})", first)
    return "#" + rgb.group(1).lower() if rgb else None


def find_wallpapers(theme_dir: Path) -> list[Path]:
    d = theme_dir / "backgrounds"
    if not d.is_dir():
        return []
    def natural(p: Path):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]

    return sorted((p for p in d.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES), key=natural)


def pick_wallpaper(images: list[Path], choice: str | None) -> Path | None:
    if not images:
        return None
    if choice is None:
        return images[0]
    if choice.isdigit():
        idx = int(choice) - 1
        if not 0 <= idx < len(images):
            raise ValueError(f"Es gibt nur {len(images)} Hintergründe (1–{len(images)})")
        return images[idx]
    for img in images:
        if choice.lower() in img.name.lower():
            return img
    raise ValueError(f"Kein Hintergrund passt zu '{choice}'")


def theme_from_dir(theme_dir: Path, name: str, wallpaper: str | None = None) -> Theme:
    result = None
    used = None
    if (theme_dir / "colors.toml").exists():
        result, used = palette_from_colors_toml(tomllib.loads((theme_dir / "colors.toml").read_text())), "colors.toml"
    if result is None and (theme_dir / "alacritty.toml").exists():
        result, used = palette_from_alacritty(tomllib.loads((theme_dir / "alacritty.toml").read_text())), "alacritty.toml"
    if result is None and (theme_dir / "kitty.conf").exists():
        result, used = palette_from_kitty((theme_dir / "kitty.conf").read_text(errors="ignore")), "kitty.conf"
    if result is None:
        raise ValueError(f"Keine Farbpalette gefunden in {theme_dir} (colors.toml, alacritty.toml oder kitty.conf)")
    ansi, ext = result
    if "accent" not in ext and (acc := hypr_accent(theme_dir)):
        ext["accent"] = acc
    palette = Palette.from_ansi(ansi, ext)
    mode = "light" if (theme_dir / "light.mode").exists() or not c.is_dark(palette.background) else "dark"
    wp = pick_wallpaper(find_wallpapers(theme_dir), wallpaper)
    icons_file = theme_dir / "icons.theme"
    icon_theme = icons_file.read_text().strip().splitlines()[0].strip() if icons_file.exists() and icons_file.read_text().strip() else None
    return Theme(
        name=name,
        palette=palette,
        mode=mode,
        wallpaper=str(wp) if wp else None,
        icon_theme=icon_theme,
        source=f"omarchy:{used}",
    )


# ---------------------------------------------------------------------------
# Suche auf GitHub
# ---------------------------------------------------------------------------
_THEME_REPO = re.compile(r"^omarchy-.+-theme$", re.I)


def search(query: str = "", limit: int = 30) -> list[dict]:
    """Sucht Omarchy-Themes auf GitHub (Repos namens omarchy-<name>-theme).

    Nutzt die öffentliche Such-API. Ohne Token sind etwa 10 Suchen pro Minute
    erlaubt; mit GITHUB_TOKEN (oder ``gh auth token``) deutlich mehr.
    """
    import json
    import os
    import urllib.parse
    import urllib.request

    terms = " ".join(query.split())
    q = f"{terms} omarchy theme in:name fork:true".strip()
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": q, "sort": "stars", "order": "desc", "per_page": 100}
    )
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "themectl"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and shutil.which("gh"):
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = res.stdout.strip() if res.returncode == 0 else None
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:  # type: ignore[attr-defined]
        if e.code in (403, 429):
            raise ValueError("GitHub-Limit erreicht, bitte eine Minute warten (oder 'gh auth login')") from None
        raise ValueError(f"GitHub-Suche fehlgeschlagen: HTTP {e.code}") from None
    except OSError as e:
        raise ValueError(f"GitHub nicht erreichbar: {e}") from None

    results = []
    for item in data.get("items", []):
        if not _THEME_REPO.match(item.get("name", "")):
            continue
        results.append({
            "repo": item["full_name"],
            "name": default_name(Path(item["name"]), item["name"]),
            "stars": item.get("stargazers_count", 0),
            "description": (item.get("description") or "").strip(),
            "url": item["html_url"],
            "branch": item.get("default_branch", "main"),
        })
        if len(results) >= limit:
            break
    return results
