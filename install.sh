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
PLUGIN_INSTALL_DIR="$CONFIG_DIR/plugins"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

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

install_launch_agent() {
  local label="$1"
  local app_name="$2"
  local app_path="$3"
  local plist="$LAUNCH_AGENTS_DIR/$label.plist"

  if [ ! -d "$app_path" ]; then
    yellow "Skipping launch agent for $app_name; app not found at $app_path"
    return
  fi

  mkdir -p "$LAUNCH_AGENTS_DIR"
  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>$app_name</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
PLIST

  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  green "✓ Installed launch agent for $app_name."
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

ensure_python_certs() {
  # macOS Python (especially python.org builds) can't verify TLS certificates
  # until a CA bundle is set up, which makes api.aladhan.com fail with
  # "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate".
  # The plugin prefers certifi's bundle, so make sure certifi is importable.
  if python3 -c "import certifi" >/dev/null 2>&1; then
    green "✓ Python TLS certificates present."
    return
  fi

  # python.org framework builds ship an "Install Certificates.command".
  local pyver cert_cmd
  pyver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  cert_cmd="/Applications/Python $pyver/Install Certificates.command"
  if [ -f "$cert_cmd" ]; then
    yellow "Setting up Python CA certificates (python.org)…"
    /bin/bash "$cert_cmd" >/dev/null 2>&1 || true
  fi

  # Fallback: install certifi for whatever python3 is on PATH.
  if ! python3 -c "import certifi" >/dev/null 2>&1; then
    yellow "Installing certifi (Python TLS certificates)…"
    python3 -m pip install --quiet certifi >/dev/null 2>&1 \
      || python3 -m pip install --quiet --user certifi >/dev/null 2>&1 \
      || python3 -m pip install --quiet --break-system-packages certifi >/dev/null 2>&1 \
      || true
  fi

  if python3 -c "import certifi" >/dev/null 2>&1; then
    green "✓ Python TLS certificates ready."
  else
    red "⚠ Python still can't verify TLS certificates."
    red "  Fix: run  \"/Applications/Python $pyver/Install Certificates.command\""
    red "  or:   python3 -m pip install certifi"
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

  ensure_python_certs

  if ! command -v CoreLocationCLI >/dev/null 2>&1; then
    yellow "Installing CoreLocationCLI (accurate Wi-Fi-based location for auto-detection)…"
    ensure_brew
    brew install corelocationcli || yellow "CoreLocationCLI install failed; auto-location will fall back to IP geolocation."
  fi

  chmod +x "$PLUGIN_SRC"
  chmod +x "$CONFIG_TOOL_SRC"
  rm -rf "$REPO_DIR/menubar/__pycache__"

  # Install a wrapper plugin to an internal (always-available) path so SwiftBar
  # can find it at boot even before the external SSD mounts.
  mkdir -p "$PLUGIN_INSTALL_DIR"
  local wrapper="$PLUGIN_INSTALL_DIR/prayertimes.30s.sh"
  cat > "$wrapper" <<WRAPPER
#!/usr/bin/env bash
# Auto-generated by install.sh — delegates to the actual plugin in the repo.
PLUGIN="$PLUGIN_SRC"
if [ -f "\$PLUGIN" ]; then
  exec python3 "\$PLUGIN"
else
  printf "🕌\n---\nDrive not mounted\nConnect the drive with the Prayer Times repo\n"
fi
WRAPPER
  chmod +x "$wrapper"
  defaults write com.ameba.SwiftBar PluginDirectory -string "$PLUGIN_INSTALL_DIR"

  if ! python3 "$PLUGIN_SRC" | head -n 1 >/dev/null; then
    red "SwiftBar plugin self-test failed. Run this to inspect:"
    echo "  python3 \"$PLUGIN_SRC\" | head -n 12"
    exit 1
  fi

  green "✓ Installed SwiftBar wrapper plugin to $PLUGIN_INSTALL_DIR."
}

configure_startup() {
  local ubersicht_app swiftbar_app

  ubersicht_app="$(resolve_app_path "Übersicht")" || ubersicht_app="/Applications/Übersicht.app"
  swiftbar_app="$(resolve_app_path "SwiftBar")" || swiftbar_app="/Applications/SwiftBar.app"

  install_launch_agent "com.salah-bar.launch-ubersicht" "Übersicht" "$ubersicht_app"
  install_launch_agent "com.salah-bar.launch-swiftbar"  "SwiftBar"  "$swiftbar_app"
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
