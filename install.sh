#!/usr/bin/env bash
# Prayer Times — installer for macOS.
# Installs the Übersicht widget and the SwiftBar menu-bar plugin.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIDGET_SRC="$REPO_DIR/prayertimes.widget"
PLUGIN_SRC="$REPO_DIR/menubar/prayertimes.30s.py"
CONFIG_SRC="$REPO_DIR/config.example.json"

UBERSICHT_DIR="$HOME/Library/Application Support/Übersicht/widgets"
SWIFTBAR_PLUGINS_DEFAULT="$HOME/Library/Application Support/SwiftBar/Plugins"
CONFIG_DIR="$HOME/.config/salah-bar"
CONFIG_FILE="$CONFIG_DIR/config.json"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

require_brew() {
  if ! command -v brew >/dev/null 2>&1; then
    red "Homebrew is required. Install from https://brew.sh, then re-run."
    exit 1
  fi
}

install_ubersicht() {
  if [ ! -d "/Applications/Übersicht.app" ]; then
    yellow "Installing Übersicht.app via brew…"
    require_brew
    brew install --cask ubersicht
    open -a Übersicht
    yellow "Launched Übersicht. Grant any permissions it asks for, then press Enter to continue."
    read -r
  fi
  mkdir -p "$UBERSICHT_DIR"
  if [ -e "$UBERSICHT_DIR/prayertimes.widget" ] || [ -L "$UBERSICHT_DIR/prayertimes.widget" ]; then
    rm -rf "$UBERSICHT_DIR/prayertimes.widget"
  fi
  ln -s "$WIDGET_SRC" "$UBERSICHT_DIR/prayertimes.widget"
  green "✓ Linked widget into Übersicht."
}

install_swiftbar() {
  if [ ! -d "/Applications/SwiftBar.app" ]; then
    yellow "Installing SwiftBar.app via brew…"
    require_brew
    brew install --cask swiftbar
  fi
  defaults write com.ameba.SwiftBar PluginDirectory -string "$REPO_DIR/menubar"
  chmod +x "$PLUGIN_SRC"
  green "✓ Configured SwiftBar plugin directory."
}

install_config() {
  mkdir -p "$CONFIG_DIR"
  if [ ! -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_SRC" "$CONFIG_FILE"
    green "✓ Created config file at $CONFIG_FILE"
  else
    yellow "Keeping existing config at $CONFIG_FILE"
  fi
}

restart_apps() {
  osascript -e 'tell application "Übersicht" to quit' 2>/dev/null || true
  osascript -e 'tell application "SwiftBar" to quit'   2>/dev/null || true
  sleep 1
  open -a Übersicht
  open -a SwiftBar
  green "✓ Launched Übersicht + SwiftBar."
}

main() {
  install_ubersicht
  install_swiftbar
  install_config
  restart_apps
  echo
  green "Done."
  echo "  • Desktop widget: top-right corner. Drag the header to move; click the chevron to collapse; click city to cycle."
  echo "  • Menu bar:       🕌 Next-prayer countdown. Click to expand; switch city from the submenu."
  echo "  • Config file:    $CONFIG_FILE"
}

main "$@"
