#!/usr/bin/env bash
# Installiert themectl für den aktuellen Benutzer (ohne Root).
set -euo pipefail
cd "$(dirname "$0")"

if command -v pipx >/dev/null; then
  pipx install --force --editable .
else
  echo "pipx nicht gefunden – installiere über einen Starter in ~/.local/bin"
  mkdir -p "$HOME/.local/bin"
  cat > "$HOME/.local/bin/themectl" <<EOS
#!/usr/bin/env bash
PYTHONPATH="$PWD\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m theme_switcher "\$@"
EOS
  chmod +x "$HOME/.local/bin/themectl"
fi

mkdir -p "$HOME/.config/theme-switcher"
[ -f "$HOME/.config/theme-switcher/config.toml" ] || cp examples/config.toml "$HOME/.config/theme-switcher/config.toml"
# DMS-Launcher-Plugin verlinken (Super+Space, dann "~")
mkdir -p "$HOME/.config/dms/plugins"
ln -sfn "$PWD/dms-plugin/ThemeSwitcher" "$HOME/.config/dms/plugins/ThemeSwitcher"
echo "✓ DMS-Plugin verlinkt. In DMS: Einstellungen → Plugins → Scan → 'Theme Switcher' aktivieren"

echo "✓ Fertig. Probier: themectl --help"
