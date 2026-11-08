"""Weitere Online-Quellen für Themes.

Jede Quelle ist ein Ordner in einem GitHub-Repo. Die Liste kommt über die
GitHub-Contents-API (ein Aufruf pro Quelle, einen Tag lang zwischengespeichert),
die Dateien selbst über raw.githubusercontent.com.

Quellen:

- ``omarchy``         Omarchy-Themes der Community (GitHub-Suche, siehe omarchy.search)
- ``omarchy-core``    die offiziellen Omarchy-Themes aus basecamp/omarchy, mit Hintergründen
- ``iterm2``          iTerm2-Color-Schemes, etwa 450 Terminal-Farbschemata (Ghostty-Format)
- ``base16``          tinted-theming Base16-Schemata
- ``base24``          tinted-theming Base24-Schemata

Schemata ohne Hintergrundbild werden als reine Farbthemes gespeichert.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import colors as c
from . import omarchy
from .model import Palette, Theme


@dataclass(frozen=True)
class SourceDef:
    key: str
    title: str
    description: str
    repo: str = ""
    path: str = ""
    kind: str = ""  # omarchy-dir | ghostty | base16 | base24 | search


SOURCES: dict[str, SourceDef] = {
    s.key: s
    for s in [
        SourceDef("omarchy", "Omarchy Community", "Omarchy-Themes auf GitHub (omarchy-*-theme), mit Wallpaper", kind="search"),
        SourceDef("omarchy-core", "Omarchy Offiziell", "Die mitgelieferten Omarchy-Themes, mit Wallpaper",
                  "basecamp/omarchy", "themes", "omarchy-dir"),
        SourceDef("iterm2", "Terminal-Schemata", "iTerm2-Color-Schemes, über 400 Farbschemata ohne Wallpaper",
                  "mbadolato/iTerm2-Color-Schemes", "ghostty", "ghostty"),
        SourceDef("base16", "Base16", "tinted-theming Base16-Schemata ohne Wallpaper",
                  "tinted-theming/schemes", "base16", "base16"),
        SourceDef("base24", "Base24", "tinted-theming Base24-Schemata ohne Wallpaper",
                  "tinted-theming/schemes", "base24", "base24"),
    ]
}

CACHE_SECONDS = 24 * 3600


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and shutil.which("gh"):
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        token = res.stdout.strip() if res.returncode == 0 else None
    return token


def _get(url: str, api: bool = False) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "themectl"})
    if api:
        req.add_header("Accept", "application/vnd.github+json")
        if tok := _token():
            req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if api and e.code in (403, 429):
            raise ValueError("GitHub-Limit erreicht, bitte etwas warten (oder 'gh auth login')") from None
        raise ValueError(f"Download fehlgeschlagen ({e.code}): {url}") from None
    except OSError as e:
        raise ValueError(f"GitHub nicht erreichbar: {e}") from None


def _contents(repo: str, path: str, cache_dir: Path | None) -> list[dict]:
    """Inhalt eines Repo-Ordners (name, type, download_url), mit Cache."""
    cache = None
    if cache_dir:
        cache = cache_dir / "sources" / (re.sub(r"[^\w.-]+", "_", f"{repo}_{path}") + ".json")
        if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_SECONDS:
            try:
                return json.loads(cache.read_text())
            except json.JSONDecodeError:
                pass
    url = f"https://api.github.com/repos/{repo}/contents/{urllib.parse.quote(path)}"
    data = json.loads(_get(url, api=True))
    if not isinstance(data, list):
        raise ValueError(f"Unerwartete Antwort für {repo}/{path}")
    items = [{"name": d["name"], "type": d["type"], "download_url": d.get("download_url")} for d in data]
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(items))
    return items


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------
def _display_name(kind: str, filename: str) -> str:
    if kind in ("base16", "base24"):
        return filename.rsplit(".", 1)[0]
    return filename


def browse(key: str, query: str = "", limit: int = 0, cache_dir: Path | None = None) -> list[dict]:
    """Einträge einer Quelle, optional nach Begriff gefiltert."""
    src = SOURCES.get(key)
    if not src:
        raise ValueError(f"Unbekannte Quelle '{key}'. Verfügbar: {', '.join(SOURCES)}")
    if src.kind == "search":
        out = []
        for r in omarchy.search(query, limit or 100):
            out.append({"id": r["repo"], "name": r["name"], "source": key, "kind": "omarchy-repo",
                        "description": r["description"], "stars": r["stars"], "url": r["url"],
                        "preview": f"https://raw.githubusercontent.com/{r['repo']}/{r.get('branch') or 'HEAD'}/preview.png",
                        "raw": None})
        return out

    items = _contents(src.repo, src.path, cache_dir)
    words = query.lower().split()
    out = []
    for it in items:
        if src.kind == "omarchy-dir":
            if it["type"] != "dir":
                continue
            base = f"https://raw.githubusercontent.com/{src.repo}/HEAD/{src.path}/{it['name']}"
            entry = {"preview": base + "/preview.png", "raw": base + "/colors.toml", "format": "colors.toml"}
        else:
            if it["type"] != "file" or not it.get("download_url"):
                continue
            if src.kind in ("base16", "base24") and not it["name"].endswith((".yaml", ".yml")):
                continue
            entry = {"preview": None, "raw": it["download_url"], "format": src.kind}
        name = _display_name(src.kind, it["name"])
        if words and not all(w in name.lower() for w in words):
            continue
        out.append({"id": it["name"], "name": name, "source": key, "kind": src.kind, "description": "",
                    "stars": None, "url": f"https://github.com/{src.repo}/tree/HEAD/{src.path}/{it['name']}", **entry})
    out.sort(key=lambda e: e["name"].lower())
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# Farben lesen
# ---------------------------------------------------------------------------
def palette_from_ghostty(text: str) -> tuple[list[str], dict[str, str]]:
    ansi: dict[int, str] = {}
    ext: dict[str, str] = {}
    for line in text.splitlines():
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key == "palette":
            idx, _, col = val.partition("=")
            if idx.strip().isdigit():
                ansi[int(idx)] = c.normalize(col.strip())
        elif key in ("background", "foreground", "cursor-color", "selection-background"):
            name = {"cursor-color": "cursor", "selection-background": "selection"}.get(key, key)
            try:
                ext[name] = c.normalize(val)
            except ValueError:
                pass
    if not all(i in ansi for i in range(16)):
        raise ValueError("Schema hat keine 16 Palettenfarben")
    return [ansi[i] for i in range(16)], ext


def palette_from_base16(text: str, base24: bool = False) -> tuple[list[str], dict[str, str], str, str | None]:
    vals = {k.lower(): v for k, v in re.findall(r"^\s*(base[0-9A-Fa-f]{2})\s*:\s*[\"']?#?([0-9A-Fa-f]{6})", text, flags=re.M)}
    if not all(f"base0{x}" in vals for x in "0123456789abcdef"):
        raise ValueError("Schema hat nicht alle base00–base0F-Farben")
    b = {k: "#" + v.lower() for k, v in vals.items()}
    normal = [b["base00"], b["base08"], b["base0b"], b["base0a"], b["base0d"], b["base0e"], b["base0c"], b["base05"]]
    if base24 and all(f"base1{x}" in b for x in "234567"):
        bright = [b["base03"], b["base12"], b["base14"], b["base13"], b["base16"], b["base17"], b["base15"], b["base07"]]
    else:
        bright = [b["base03"], b["base08"], b["base0b"], b["base0a"], b["base0d"], b["base0e"], b["base0c"], b["base07"]]
    ext = {"background": b["base00"], "foreground": b["base05"], "accent": b["base0d"], "selection": b["base02"],
           "cursor": b["base05"]}
    m = re.search(r"^name:\s*[\"']?(.+?)[\"']?\s*$", text, flags=re.M)
    v = re.search(r"^variant:\s*[\"']?(\w+)", text, flags=re.M)
    return normal + bright, ext, (m.group(1) if m else ""), (v.group(1) if v else None)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
def fetch_theme(key: str, entry_id: str, cache_dir: Path | None = None, wallpaper: str | None = None,
                workdir: Path | None = None) -> Theme:
    """Lädt einen Eintrag und baut daraus ein Theme.

    Bei ``omarchy-core`` werden die Dateien nach ``workdir`` geladen, damit das
    Wallpaper beim Speichern noch kopiert werden kann.
    """
    src = SOURCES.get(key)
    if not src:
        raise ValueError(f"Unbekannte Quelle '{key}'")
    if src.kind == "search":
        raise ValueError("Omarchy-Community-Themes mit 'themectl omarchy import <repo>' übernehmen")

    if src.kind == "omarchy-dir":
        if workdir is None:
            raise ValueError("workdir fehlt")
        files = _contents(src.repo, f"{src.path}/{entry_id}", cache_dir)
        if not files:
            raise ValueError(f"'{entry_id}' gibt es in {src.title} nicht")
        tdir = workdir / entry_id
        tdir.mkdir(parents=True, exist_ok=True)
        wanted = {"colors.toml", "alacritty.toml", "kitty.conf", "hyprland.conf", "icons.theme", "light.mode"}
        for f in files:
            if f["type"] == "file" and f["name"] in wanted and f.get("download_url"):
                (tdir / f["name"]).write_bytes(_get(f["download_url"]))
            elif f["type"] == "dir" and f["name"] == "backgrounds":
                imgs = [b for b in _contents(src.repo, f"{src.path}/{entry_id}/backgrounds", cache_dir)
                        if b["type"] == "file" and Path(b["name"]).suffix.lower() in omarchy.IMAGE_SUFFIXES]
                imgs.sort(key=lambda b: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", b["name"])])
                chosen = omarchy.pick_wallpaper([Path(b["name"]) for b in imgs], wallpaper)
                if chosen:
                    (tdir / "backgrounds").mkdir(exist_ok=True)
                    url = next(b["download_url"] for b in imgs if b["name"] == chosen.name)
                    (tdir / "backgrounds" / chosen.name).write_bytes(_get(url))
        theme = omarchy.theme_from_dir(tdir, entry_id)
        theme.source = f"{key}:{entry_id}"
        return theme

    items = {it["name"]: it for it in _contents(src.repo, src.path, cache_dir)}
    it = items.get(entry_id)
    if it is None:
        # Groß-/Kleinschreibung und fehlende Endung verzeihen
        low = {k.lower(): v for k, v in items.items()}
        it = low.get(entry_id.lower()) or low.get(entry_id.lower() + ".yaml")
    if it is None or not it.get("download_url"):
        raise ValueError(f"'{entry_id}' gibt es in {src.title} nicht")
    text = _get(it["download_url"]).decode("utf-8", errors="replace")
    if src.kind == "ghostty":
        ansi, ext = palette_from_ghostty(text)
        name, variant = it["name"], None
    else:
        ansi, ext, name, variant = palette_from_base16(text, base24=src.kind == "base24")
        name = name or _display_name(src.kind, it["name"])
    palette = Palette.from_ansi(ansi, ext)
    if src.kind == "ghostty":
        palette.accent = pick_accent(palette)
    mode = variant if variant in ("light", "dark") else ("dark" if c.is_dark(palette.background) else "light")
    return Theme(name=name, palette=palette, mode=mode, source=f"{key}:{it['name']}")


def pick_accent(palette: Palette) -> str:
    """Akzent für Terminal-Schemata: das kräftigste Blau/Lila/Cyan, sonst die buntesste Farbe."""
    import colorsys

    def sat(h: str) -> float:
        r, g, b = c.to_rgb(h)
        _, l, s = colorsys.rgb_to_hls(r, g, b)
        return s * (1 - abs(l - 0.55))

    if sat(palette.colors[4]) > 0.25:
        return palette.colors[4]
    candidates = [palette.colors[i] for i in (12, 5, 6)]
    best = max(candidates, key=sat)
    if sat(best) > 0.2:
        return best
    return max(palette.colors[1:7] + palette.colors[9:15], key=sat)


def temp_workdir() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="themectl-source-")
