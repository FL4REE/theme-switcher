import json
import os
import tempfile
import unittest
from pathlib import Path

from theme_switcher import cli
from theme_switcher.model import Theme

POIMANDRES = {
    "id": "poimandres",
    "name": "Poimandres",
    "dark": {
        "primary": "#89DDFF", "primaryText": "#1B212E", "primaryContainer": "#506477",
        "secondary": "#5DE4C7", "surface": "#1B1E28", "surfaceText": "#E4F0FB",
        "background": "#0F1018", "outline": "#3C5170", "error": "#F087BD",
        "warning": "#FFFAC2", "info": "#add7ff",
    },
}

ANSI = ["#1b1e28", "#d0679d", "#5de4c7", "#fffac2", "#89ddff", "#fcc5e9", "#add7ff", "#e4f0fb",
        "#506477", "#d0679d", "#5de4c7", "#fffac2", "#add7ff", "#f087bd", "#89ddff", "#ffffff"]


class Env:
    """Baut ein Fake-Home mit DMS-, Hypr- und Aether-Ordnern."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        (root / "dms/themes/poimandres").mkdir(parents=True)
        (root / "dms/themes/poimandres/theme.json").write_text(json.dumps(POIMANDRES))
        (root / "dms/settings.json").write_text(json.dumps({
            "currentThemeName": "custom",
            "customThemeFile": str(root / "dms/themes/poimandres/theme.json"),
            "otherSetting": 42,
        }))
        (root / "aether/blueprints").mkdir(parents=True)
        (root / "aether/blueprints/forest.json").write_text(json.dumps({
            "name": "Forest", "palette": {"colors": ANSI, "extendedColors": {"accent": "#5de4c7"}, "mode": "dark"},
            "timestamp": 1,
        }))
        (root / "aether/theme").mkdir(parents=True)
        toml = 'mode = "dark"\naccent = "#ff00aa"\nbackground = "#101010"\nforeground = "#eeeeee"\n'
        toml += "".join(f'color{i} = "{c}"\n' for i, c in enumerate(ANSI))
        (root / "aether/theme/colors.toml").write_text(toml)
        (root / "hypr").mkdir()
        cfg = root / "config.toml"
        cfg.write_text(f"""
[paths]
themes_dir = "{root}/themes"
state_dir = "{root}/state"
dms_dir = "{root}/dms"
hypr_dir = "{root}/hypr"
aether_dir = "{root}/aether"
ghostty_dir = "{root}/ghostty"
starship_file = "{root}/starship.toml"
[targets]
wallpaper = false
hyprland = true
ghostty = true
""")
        self.cfg = cfg
        os.environ["PATH"] = str(root / "nobin")  # keine echten hyprctl/dms-Aufrufe

    def run(self, *args):
        return cli.main(["--config", str(self.cfg), *args])


class ThemectlTest(unittest.TestCase):
    def setUp(self):
        self._path = os.environ.get("PATH", "")
        self.env = Env()

    def tearDown(self):
        os.environ["PATH"] = self._path
        self.env.tmp.cleanup()

    def test_save_current_dms_theme(self):
        self.assertEqual(self.env.run("save", "Mein Poimandres"), 0)
        t = Theme.load(self.env.root / "themes/mein-poimandres")
        self.assertEqual(t.palette.accent, "#89ddff")
        self.assertEqual(t.dms["dark"]["primary"], "#89DDFF")
        self.assertEqual(t.dms_colors()["dark"]["primary"], "#89DDFF")

    def test_aether_blueprint_import_and_apply(self):
        self.assertEqual(self.env.run("aether", "import", "forest", "--apply"), 0)
        root = self.env.root
        dms_theme = json.loads((root / "dms/themes/ts-forest/theme.json").read_text())
        self.assertEqual(dms_theme["dark"]["primary"], "#5de4c7")
        settings = json.loads((root / "dms/settings.json").read_text())
        self.assertEqual(settings["customThemeFile"], str(root / "dms/themes/ts-forest/theme.json"))
        self.assertEqual(settings["otherSetting"], 42)
        self.assertTrue((root / "dms/settings.json.backup-theme-switcher").exists())
        self.assertIn("rgb(5de4c7)", (root / "hypr/theme-switcher.lua").read_text())
        self.assertIn("palette = 15=#ffffff", (root / "ghostty/themes/theme-switcher").read_text())
        self.assertEqual((root / "state/current").read_text().strip(), "forest")

    def test_aether_current_colors_toml(self):
        self.assertEqual(self.env.run("aether", "import", "--current", "--name", "jetzt"), 0)
        t = Theme.load(self.env.root / "themes/jetzt")
        self.assertEqual(t.palette.accent, "#ff00aa")
        self.assertEqual(t.palette.background, "#101010")

    def test_create_and_cycle(self):
        self.assertEqual(self.env.run("create", "hell", "--bg", "#fafafa", "--accent", "#3366ff"), 0)
        self.assertEqual(self.env.run("create", "dunkel", "--bg", "#101014", "--accent", "#ff8800"), 0)
        hell = Theme.load(self.env.root / "themes/hell")
        self.assertEqual(hell.mode, "light")
        self.assertEqual(len(hell.palette.colors), 16)
        self.assertEqual(self.env.run("next"), 0)
        first = (self.env.root / "state/current").read_text().strip()
        self.assertEqual(self.env.run("next"), 0)
        second = (self.env.root / "state/current").read_text().strip()
        self.assertNotEqual(first, second)

    def test_list_json(self):
        import contextlib, io
        self.env.run("create", "x", "--bg", "#101014", "--accent", "#ff8800")
        self.env.run("apply", "x", "--only", "ghostty")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(self.env.run("list", "--json"), 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data[0]["id"], "x")
        self.assertTrue(data[0]["current"])
        self.assertEqual(data[0]["accent"], "#ff8800")

    def test_light_variant_is_light(self):
        self.env.run("create", "x", "--bg", "#101014", "--accent", "#ff8800")
        t = Theme.load(self.env.root / "themes/x")
        from theme_switcher.colors import is_dark
        cols = t.dms_colors()
        self.assertTrue(is_dark(cols["dark"]["background"]))
        self.assertFalse(is_dark(cols["light"]["background"]))

    def test_export_import_roundtrip(self):
        self.env.run("create", "x", "--bg", "#101014", "--accent", "#ff8800")
        out = self.env.root / "x.tar.gz"
        self.assertEqual(self.env.run("export", "x", "-o", str(out)), 0)
        self.env.run("delete", "x")
        self.assertEqual(self.env.run("import", str(out)), 0)
        self.assertTrue((self.env.root / "themes/x/theme.json").exists())


if __name__ == "__main__":
    unittest.main()


class StarshipTest(unittest.TestCase):
    def setUp(self):
        self._path = os.environ.get("PATH", "")
        self.env = Env()
        self.cfg = self.env.root / "starship.toml"
        self.cfg.write_text(
            "\"$schema\" = 'https://starship.rs/config-schema.json'\n"
            'format = "[](red)$os[](bg:peach fg:red)"\n'
            "palette = 'catppuccin_mocha'\n\n"
            '[os]\nstyle = "bg:red fg:crust"\n\n'
            '[palettes.catppuccin_mocha]\nred = "#f38ba8"\n'
        )

    def tearDown(self):
        os.environ["PATH"] = self._path
        self.env.tmp.cleanup()

    def test_palette_switch_and_idempotent(self):
        import tomllib
        self.env.run("aether", "import", "forest")
        self.assertEqual(self.env.run("apply", "forest", "--only", "starship"), 0)
        self.env.run("create", "zwei", "--bg", "#101014", "--accent", "#ff8800")
        self.assertEqual(self.env.run("apply", "zwei", "--only", "starship"), 0)
        text = self.cfg.read_text()
        data = tomllib.loads(text)  # muss gültiges TOML bleiben
        self.assertEqual(data["palette"], "theme_switcher")
        self.assertEqual(text.count("[palettes.theme_switcher]"), 1)
        self.assertIn("catppuccin_mocha", data["palettes"])  # Original bleibt erhalten
        pal = data["palettes"]["theme_switcher"]
        for key in ("red", "peach", "yellow", "green", "sapphire", "lavender", "crust", "color_bg1"):
            self.assertIn(key, pal)
        self.assertEqual(pal["accent"], "#ff8800")
        self.assertTrue((self.env.root / "starship.toml.backup-theme-switcher").exists())

    def test_no_palette_line_inserted_before_tables(self):
        import tomllib
        self.cfg.write_text('# Kommentar\n[character]\nsuccess_symbol = "[>](green)"\n')
        self.env.run("create", "x", "--bg", "#101014", "--accent", "#ff8800")
        self.env.run("apply", "x", "--only", "starship")
        data = tomllib.loads(self.cfg.read_text())
        self.assertEqual(data["palette"], "theme_switcher")
        self.assertIn("character", data)


class OmarchyTest(unittest.TestCase):
    def setUp(self):
        self._path = os.environ.get("PATH", "")
        self.env = Env()
        os.environ["PATH"] = self._path  # git wird hier nicht gebraucht, schadet aber nicht
        self.src = self.env.root / "omarchy-nebel-theme"
        (self.src / "backgrounds").mkdir(parents=True)
        (self.src / "backgrounds/01-a.png").write_bytes(b"png")
        (self.src / "backgrounds/02-b.jpg").write_bytes(b"jpg")

    def tearDown(self):
        os.environ["PATH"] = self._path
        self.env.tmp.cleanup()

    def test_alacritty_fallback_and_hypr_accent(self):
        (self.src / "alacritty.toml").write_text(
            '[colors.primary]\nbackground = "#222222"\nforeground = "#c2c2b0"\n'
            '[colors.normal]\nblack = "#222222"\nred = "#685742"\ngreen = "#5f875f"\nyellow = "#b36d43"\n'
            'blue = "#78824b"\nmagenta = "#bb7744"\ncyan = "#c9a554"\nwhite = "#c2c2b0"\n'
            '[colors.bright]\nblack = "#666666"\n'
        )
        (self.src / "hyprland.conf").write_text("$akzent = rgb(aabbcc)\ngeneral {\n  col.active_border = $akzent rgb(000000) 45deg\n}\n")
        self.assertEqual(self.env.run("omarchy", "import", str(self.src), "--wallpaper", "2"), 0)
        t = Theme.load(self.env.root / "themes/nebel")
        self.assertEqual(t.palette.accent, "#aabbcc")
        self.assertEqual(t.palette.colors[8], "#666666")
        self.assertEqual(t.palette.colors[9], "#685742")  # fehlende Bright-Farbe = normale
        self.assertEqual(t.wallpaper, "wallpaper.jpg")
        self.assertTrue((t.path / "wallpaper.jpg").exists())

    def test_colors_toml_semantic(self):
        (self.src / "colors.toml").write_text(
            'accent = "#78824b"\nbackground = "#222222"\nforeground = "#c2c2b0"\n'
            'bg = "#222222"\nfg = "#c2c2b0"\nred = "#685742"\ngreen = "#5f875f"\nyellow = "#b36d43"\n'
            'blue = "#78824b"\npurple = "#bb7744"\ncyan = "#c9a554"\nmuted = "#8a8a7e"\n'
        )
        self.assertEqual(self.env.run("omarchy", "import", str(self.src), "--name", "Miasma"), 0)
        t = Theme.load(self.env.root / "themes/miasma")
        self.assertEqual(t.palette.accent, "#78824b")
        self.assertEqual(t.palette.colors[5], "#bb7744")
        self.assertEqual(t.palette.colors[8], "#8a8a7e")
        self.assertEqual(t.wallpaper, "wallpaper.png")

    def test_github_tree_url(self):
        from theme_switcher.omarchy import _GITHUB_TREE
        m = _GITHUB_TREE.match("https://github.com/OldJobobo/omarchy-miasma-theme/tree/master")
        self.assertEqual(m.group(1), "https://github.com/OldJobobo/omarchy-miasma-theme")
        self.assertEqual(m.group(2), "master")
