# DMS-Launcher-Plugin

Mit diesem Plugin wählst du Themes direkt im DMS-Launcher (**Super+Space**):
`~` tippen, optional einen Suchbegriff dahinter, dann mit **Enter** anwenden.

Installation (macht `install.sh` automatisch):

```bash
mkdir -p ~/.config/dms/plugins
ln -sfn "$PWD/dms-plugin/ThemeSwitcher" ~/.config/dms/plugins/ThemeSwitcher
```

Danach in DMS: **Einstellungen → Plugins → „Scan for Plugins“**,
**Theme Switcher** einschalten und eventuell `dms restart` ausführen.
