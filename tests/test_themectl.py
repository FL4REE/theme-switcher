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
