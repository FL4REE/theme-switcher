"""Eigene Hyprland-Farbdatei (Lua-Config).

Standardmäßig AUS, weil DMS über seinen Matugen-Hook schon
``hypr/dms/colors.lua`` erzeugt. Einschalten, wenn du die Rahmenfarben
selbst steuern willst, und in ``hyprland.lua`` nach ``require("dms.colors")``
ergänzen::

    pcall(require, "theme-switcher")
"""

from __future__ import annotations

from ..colors import bare
from ..config import Config
from ..model import Theme

FILENAME = "theme-switcher.lua"


def render(theme: Theme) -> str:
    h = theme.hypr_colors()
    a, i, l = bare(h["active_border"]), bare(h["inactive_border"]), bare(h["locked_active"])
    return f"""-- Erzeugt von theme-switcher, Theme: {theme.name}. Nicht von Hand bearbeiten.
hl.config({{
\tgeneral = {{ col = {{ active_border = "rgb({a})", inactive_border = "rgb({i})" }} }},
\tgroup = {{
\t\tcol = {{
\t\t\tborder_active = "rgb({a})",
\t\t\tborder_inactive = "rgb({i})",
\t\t\tborder_locked_active = "rgb({l})",
\t\t\tborder_locked_inactive = "rgb({i})",
\t\t}},
\t\tgroupbar = {{ col = {{ active = "rgb({a})", inactive = "rgb({i})", locked_active = "rgb({l})", locked_inactive = "rgb({i})" }} }},
\t}},
}})
"""


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    from . import run

    target = cfg.hypr_dir / FILENAME
    if dry_run:
        return [f"würde {target} schreiben und hyprctl reload ausführen"]
    target.write_text(render(theme))
    msgs = [f"Hyprland-Farben geschrieben: {target}"]
    err = run(["hyprctl", "reload"])
    if err:
        msgs.append(err)
    return msgs
