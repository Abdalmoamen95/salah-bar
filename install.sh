#!/usr/bin/env bash
# Prayer Times — installer for macOS.
# Installs the Übersicht widget and the SwiftBar menu-bar plugin.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIDGET_SRC="$REPO_DIR/prayertimes.widget"
PLUGIN_SRC="$REPO_DIR/menubar/prayertimes.30s.py"
CONFIG_TOOL_SRC="$REPO_DIR/support/configure.py"
CONFIG_SRC="$REPO_DIR/config.example.json"
SUPPORT_DIR="$REPO_DIR/support"
MENUBAR_DIR="$REPO_DIR/menubar"

UBERSICHT_DIR="$HOME/Library/Application Support/Übersicht/widgets"
SWIFTBAR_PLUGINS_DEFAULT="$HOME/Library/Application Support/SwiftBar/Plugins"
CONFIG_DIR="$HOME/.config/salah-bar"
CONFIG_FILE="$CONFIG_DIR/config.json"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

resolve_app_path() {
  local app_name="$1"
  local resolved
  resolved="$(osascript -e "POSIX path of (path to application \"$app_name\")" 2>/dev/null | tr -d '\r')" || true
  if [ -n "$resolved" ] && [ -d "$resolved" ]; then
    printf "%s\n" "${resolved%/}"
    return 0
  fi
  return 1
}

ensure_login_item() {
  local app_name="$1"
  local app_path="$2"

  if [ ! -d "$app_path" ]; then
    yellow "Skipping login item for $app_name; app not found at $app_path"
    return
  fi

  osascript \
    -e 'tell application "System Events"' \
    -e "if exists login item \"$app_name\" then delete login item \"$app_name\"" \
    -e "make login item at end with properties {name:\"$app_name\", path:\"$app_path\", hidden:false}" \
    -e 'end tell' >/dev/null

  green "✓ Added $app_name to login items."
}

clear_quarantine() {
  if ! command -v xattr >/dev/null 2>&1; then
    return
  fi
  xattr -dr com.apple.quarantine "$MENUBAR_DIR" 2>/dev/null || true
  xattr -dr com.apple.quarantine "$SUPPORT_DIR" 2>/dev/null || true
  xattr -dr com.apple.quarantine "$WIDGET_SRC" 2>/dev/null || true
}

ensure_brew() {
  if command -v brew >/dev/null 2>&1; then
    return
  fi

  yellow "Homebrew is not installed."
  printf "Install Homebrew automatically now? [Y/n] "
  read -r reply
  if [[ "${reply:-Y}" =~ ^[Nn]$ ]]; then
    red "Homebrew is required. Install from https://brew.sh, then re-run."
    exit 1
  fi

  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi

  if ! command -v brew >/dev/null 2>&1; then
    red "Homebrew installation did not complete. Please install it manually and re-run."
    exit 1
  fi
}

install_ubersicht() {
  if [ ! -d "/Applications/Übersicht.app" ]; then
    yellow "Installing Übersicht.app via brew…"
    ensure_brew
    brew install --cask ubersicht
    open -a Übersicht
    yellow "Launched Übersicht. If macOS asks for permissions, allow them."
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
    ensure_brew
    brew install --cask swiftbar
  fi
  clear_quarantine

  if ! command -v python3 >/dev/null 2>&1; then
    yellow "Installing python3 via brew (required for SwiftBar plugin)…"
    ensure_brew
    brew install python
  fi

  defaults write com.ameba.SwiftBar PluginDirectory -string "$REPO_DIR/menubar"
  chmod +x "$PLUGIN_SRC"
  chmod +x "$CONFIG_TOOL_SRC"
  rm -rf "$REPO_DIR/menubar/__pycache__"

  if ! python3 "$PLUGIN_SRC" | head -n 1 >/dev/null; then
    red "SwiftBar plugin self-test failed. Run this to inspect:"
    echo "  python3 \"$PLUGIN_SRC\" | head -n 12"
    exit 1
  fi

  green "✓ Configured SwiftBar plugin directory."
}

configure_startup() {
  local ubersicht_app swiftbar_app

  ubersicht_app="$(resolve_app_path "Übersicht")" || ubersicht_app="/Applications/Übersicht.app"
  swiftbar_app="$(resolve_app_path "SwiftBar")" || swiftbar_app="/Applications/SwiftBar.app"

  ensure_login_item "Übersicht" "$ubersicht_app"
  ensure_login_item "SwiftBar" "$swiftbar_app"
}

install_config() {
  mkdir -p "$CONFIG_DIR"
  if [ ! -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_SRC" "$CONFIG_FILE"
    green "✓ Created config file at $CONFIG_FILE"
    yellow "Tip: use the menu bar -> Configure -> Add preset city or Add custom city."
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
  configure_startup
  restart_apps
  echo
  green "Done."
  echo "  • Desktop widget: top-right corner. Drag the header to move; click the chevron to collapse; click city to cycle."
  echo "  • Menu bar:       🕌 Next-prayer countdown. Click to expand; switch city from the submenu."
  echo "  • Config file:    $CONFIG_FILE"
  echo "  • Auto-start:     Übersicht + SwiftBar now launch automatically after login."
}

main "$@"
