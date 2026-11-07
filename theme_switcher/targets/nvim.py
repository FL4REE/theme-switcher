"""Neovim: eigenes Farbschema aus der Palette erzeugen.

Schreibt ``~/.config/nvim/colors/theme-switcher.lua`` (Base16-Aufteilung mit
Treesitter-, LSP-, Diagnose- und gängigen Plugin-Gruppen) und lädt das
Schema in allen laufenden Neovim-Instanzen neu.

Einmalig in der Neovim-Config setzen::

    vim.cmd.colorscheme("theme-switcher")

Bei LazyVim stattdessen in ``lua/plugins/colorscheme.lua``::

    return { { "LazyVim/LazyVim", opts = { colorscheme = "theme-switcher" } } }
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .. import colors as c
from ..config import Config
from ..model import Theme

SCHEME = "theme-switcher"


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((c.luminance(a), c.luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def base16(theme: Theme) -> dict[str, str]:
    p = theme.palette
    a = p.colors
    bg, fg = p.background, p.foreground
    dark = c.is_dark(bg)
    step = 1 if dark else -1
    comment = a[8] if _contrast(a[8], bg) >= 2.5 else c.mix(fg, bg, 0.5)
    return {
        "base00": bg,
        "base01": c.lighten(bg, 0.04 * step),
        "base02": p.selection if _contrast(p.selection, bg) > 1.15 else c.lighten(bg, 0.10 * step),
        "base03": comment,
        "base04": c.mix(fg, bg, 0.35),
        "base05": fg,
        "base06": c.mix(fg, a[15], 0.5),
        "base07": a[15],
        "base08": a[1],
        "base09": c.mix(a[1], a[3], 0.5),
        "base0A": a[3],
        "base0B": a[2],
        "base0C": a[6],
        "base0D": p.accent,
        "base0E": a[5],
        "base0F": c.mix(a[1], bg, 0.35),
    }


# (Gruppe, Vordergrund, Hintergrund, Zusatz) – Farben als Base16-Schlüssel oder None
_GROUPS: list[tuple[str, str | None, str | None, str]] = [
    ("Normal", "base05", "base00", ""), ("NormalFloat", "base05", "base01", ""), ("NormalNC", "base05", "base00", ""),
    ("FloatBorder", "base03", "base01", ""), ("FloatTitle", "base0D", "base01", "bold=true"),
    ("Cursor", "base00", "base05", ""), ("CursorLine", None, "base01", ""), ("CursorColumn", None, "base01", ""),
    ("ColorColumn", None, "base01", ""), ("CursorLineNr", "base0D", "base01", "bold=true"), ("LineNr", "base03", None, ""),
    ("SignColumn", "base03", "base00", ""), ("FoldColumn", "base03", "base00", ""), ("Folded", "base04", "base01", ""),
    ("VertSplit", "base02", None, ""), ("WinSeparator", "base02", None, ""), ("EndOfBuffer", "base01", None, ""),
    ("Visual", None, "base02", ""), ("VisualNOS", None, "base02", ""), ("Search", "base00", "base0A", ""),
    ("IncSearch", "base00", "base09", ""), ("CurSearch", "base00", "base09", ""), ("Substitute", "base00", "base0A", ""),
    ("MatchParen", "base0A", "base02", "bold=true"), ("NonText", "base03", None, ""), ("Whitespace", "base02", None, ""),
    ("SpecialKey", "base03", None, ""), ("Conceal", "base0D", None, ""), ("Directory", "base0D", None, ""),
    ("Title", "base0D", None, "bold=true"), ("ErrorMsg", "base08", None, ""), ("WarningMsg", "base0A", None, ""),
    ("ModeMsg", "base0B", None, ""), ("MoreMsg", "base0B", None, ""), ("Question", "base0D", None, ""),
    ("Pmenu", "base05", "base01", ""), ("PmenuSel", "base00", "base0D", ""), ("PmenuSbar", None, "base02", ""),
    ("PmenuThumb", None, "base03", ""), ("WildMenu", "base00", "base0D", ""),
    ("StatusLine", "base05", "base01", ""), ("StatusLineNC", "base03", "base01", ""),
    ("TabLine", "base03", "base01", ""), ("TabLineFill", None, "base01", ""), ("TabLineSel", "base0D", "base00", "bold=true"),
    ("WinBar", "base05", None, ""), ("WinBarNC", "base03", None, ""), ("QuickFixLine", None, "base02", ""),
    ("SpellBad", None, None, "undercurl=true, sp=c.base08"), ("SpellCap", None, None, "undercurl=true, sp=c.base0D"),
    ("DiffAdd", "base0B", "base01", ""), ("DiffChange", "base0A", "base01", ""), ("DiffDelete", "base08", "base01", ""),
    ("DiffText", "base0D", "base02", ""), ("Added", "base0B", None, ""), ("Changed", "base0A", None, ""), ("Removed", "base08", None, ""),
    # Syntax
    ("Comment", "base03", None, "italic=true"), ("Constant", "base09", None, ""), ("String", "base0B", None, ""),
    ("Character", "base0B", None, ""), ("Number", "base09", None, ""), ("Boolean", "base09", None, ""), ("Float", "base09", None, ""),
    ("Identifier", "base08", None, ""), ("Function", "base0D", None, ""), ("Statement", "base0E", None, ""),
    ("Conditional", "base0E", None, ""), ("Repeat", "base0E", None, ""), ("Label", "base0A", None, ""),
    ("Operator", "base05", None, ""), ("Keyword", "base0E", None, ""), ("Exception", "base08", None, ""),
    ("PreProc", "base0A", None, ""), ("Include", "base0D", None, ""), ("Define", "base0E", None, ""), ("Macro", "base08", None, ""),
    ("Type", "base0A", None, ""), ("StorageClass", "base0A", None, ""), ("Structure", "base0E", None, ""), ("Typedef", "base0A", None, ""),
    ("Special", "base0C", None, ""), ("SpecialChar", "base0F", None, ""), ("Tag", "base0A", None, ""), ("Delimiter", "base0F", None, ""),
    ("Debug", "base08", None, ""), ("Underlined", "base0D", None, "underline=true"), ("Error", "base08", None, ""),
    ("Todo", "base00", "base0A", "bold=true"),
    # Treesitter
    ("@variable", "base05", None, ""), ("@variable.builtin", "base08", None, ""), ("@variable.parameter", "base08", None, ""),
    ("@variable.member", "base08", None, ""), ("@property", "base08", None, ""), ("@constant", "base09", None, ""),
    ("@constant.builtin", "base09", None, ""), ("@module", "base0A", None, ""), ("@string", "base0B", None, ""),
    ("@string.escape", "base0C", None, ""), ("@string.special", "base0C", None, ""), ("@character", "base0B", None, ""),
    ("@number", "base09", None, ""), ("@boolean", "base09", None, ""), ("@function", "base0D", None, ""),
    ("@function.builtin", "base0C", None, ""), ("@function.call", "base0D", None, ""), ("@function.method", "base0D", None, ""),
    ("@constructor", "base0C", None, ""), ("@keyword", "base0E", None, ""), ("@keyword.function", "base0E", None, ""),
    ("@keyword.return", "base0E", None, ""), ("@keyword.import", "base0D", None, ""), ("@operator", "base05", None, ""),
    ("@punctuation", "base0F", None, ""), ("@punctuation.bracket", "base05", None, ""), ("@punctuation.delimiter", "base05", None, ""),
    ("@type", "base0A", None, ""), ("@type.builtin", "base0A", None, ""), ("@attribute", "base0C", None, ""),
    ("@tag", "base08", None, ""), ("@tag.attribute", "base0A", None, ""), ("@tag.delimiter", "base0F", None, ""),
    ("@comment", "base03", None, "italic=true"), ("@markup.heading", "base0D", None, "bold=true"),
    ("@markup.link", "base0C", None, "underline=true"), ("@markup.raw", "base0B", None, ""), ("@markup.list", "base08", None, ""),
    ("@markup.strong", None, None, "bold=true"), ("@markup.italic", None, None, "italic=true"),
    # LSP / Diagnose
    ("DiagnosticError", "base08", None, ""), ("DiagnosticWarn", "base0A", None, ""), ("DiagnosticInfo", "base0D", None, ""),
    ("DiagnosticHint", "base0C", None, ""), ("DiagnosticOk", "base0B", None, ""),
    ("DiagnosticUnderlineError", None, None, "undercurl=true, sp=c.base08"),
    ("DiagnosticUnderlineWarn", None, None, "undercurl=true, sp=c.base0A"),
    ("DiagnosticUnderlineInfo", None, None, "undercurl=true, sp=c.base0D"),
    ("DiagnosticUnderlineHint", None, None, "undercurl=true, sp=c.base0C"),
    ("LspReferenceText", None, "base02", ""), ("LspReferenceRead", None, "base02", ""), ("LspReferenceWrite", None, "base02", ""),
    ("LspInlayHint", "base03", "base01", "italic=true"),
    # Plugins
    ("GitSignsAdd", "base0B", None, ""), ("GitSignsChange", "base0A", None, ""), ("GitSignsDelete", "base08", None, ""),
    ("TelescopeBorder", "base03", "base01", ""), ("TelescopeNormal", "base05", "base01", ""),
    ("TelescopeSelection", None, "base02", ""), ("TelescopeMatching", "base0D", None, "bold=true"),
    ("NeoTreeNormal", "base05", "base01", ""), ("NeoTreeNormalNC", "base05", "base01", ""),
    ("NeoTreeDirectoryIcon", "base0D", None, ""), ("NeoTreeDirectoryName", "base0D", None, ""),
    ("NvimTreeNormal", "base05", "base01", ""), ("NvimTreeFolderIcon", "base0D", None, ""),
    ("WhichKey", "base0D", None, ""), ("WhichKeyGroup", "base0E", None, ""), ("WhichKeyDesc", "base05", None, ""),
    ("SnacksPickerMatch", "base0D", None, "bold=true"), ("SnacksDashboardHeader", "base0D", None, ""),
    ("BlinkCmpMenu", "base05", "base01", ""), ("BlinkCmpMenuSelection", None, "base02", ""),
    ("BlinkCmpLabelMatch", "base0D", None, "bold=true"),
    ("CmpItemAbbrMatch", "base0D", None, "bold=true"), ("CmpItemKind", "base0E", None, ""),
    ("IblIndent", "base02", None, "nocombine=true"), ("IblScope", "base03", None, "nocombine=true"),
    ("MiniStatuslineModeNormal", "base00", "base0D", "bold=true"), ("MiniStatuslineModeInsert", "base00", "base0B", "bold=true"),
    ("MiniStatuslineModeVisual", "base00", "base0E", "bold=true"),
]


def render(theme: Theme) -> str:
    b = base16(theme)
    bg_mode = "dark" if c.is_dark(theme.palette.background) else "light"
    lines = [
        f"-- Erzeugt von theme-switcher, Theme: {theme.name}. Nicht von Hand bearbeiten.",
        'vim.cmd("highlight clear")',
        'if vim.fn.exists("syntax_on") == 1 then vim.cmd("syntax reset") end',
        f'vim.o.background = "{bg_mode}"',
        f'vim.g.colors_name = "{SCHEME}"',
        "vim.o.termguicolors = true",
        "",
        "local c = {",
    ]
    lines += [f'  {k} = "{v}",' for k, v in b.items()]
    lines += ["}", "", "local hl = function(group, opts) vim.api.nvim_set_hl(0, group, opts) end", ""]
    for group, fg, bg, extra in _GROUPS:
        parts = []
        if fg:
            parts.append(f"fg = c.{fg}")
        if bg:
            parts.append(f"bg = c.{bg}")
        if extra:
            parts.append(extra)
        lines.append(f'hl("{group}", {{ {", ".join(parts)} }})')
    lines.append("")
    lines += [f'vim.g.terminal_color_{i} = "{col}"' for i, col in enumerate(theme.palette.colors)]
    return "\n".join(lines) + "\n"


def _sockets() -> list[str]:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    found: list[Path] = []
    if runtime.is_dir():
        found += runtime.glob("nvim.*")
        found += runtime.glob("nvim/*")
    tmp = Path(os.environ.get("TMPDIR", "/tmp"))
    found += tmp.glob(f"nvim.{os.environ.get('USER', '')}/*/nvim.*")
    return sorted({str(p) for p in found if p.is_socket()})


def apply(theme: Theme, cfg: Config, dry_run: bool = False) -> list[str]:
    target = cfg.nvim_dir / "colors" / f"{SCHEME}.lua"
    if dry_run:
        return [f"würde {target} schreiben und laufende Neovim-Instanzen neu färben"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(theme))
    msgs = [f"Neovim-Farbschema geschrieben: {target}"]
    if shutil.which("nvim"):
        reloaded = 0
        for sock in _sockets():
            res = subprocess.run(
                ["nvim", "--server", sock, "--remote-expr",
                 f'execute("if get(g:, \'colors_name\', \'\') ==# \'{SCHEME}\' | colorscheme {SCHEME} | endif")'],
                capture_output=True, text=True, timeout=5,
            )
            reloaded += res.returncode == 0
        if reloaded:
            msgs.append(f"{reloaded} laufende Neovim-Instanz(en) neu gefärbt")
    return msgs
