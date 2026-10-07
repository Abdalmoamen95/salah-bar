#!/usr/bin/env bash
# Salah Bar — one-line installer for the native macOS app.
#
# Install or update:
#   curl -fsSL https://raw.githubusercontent.com/be-liever95/salah-bar/main/install.sh | bash
#
# Options (pass after `bash -s --` when piping, e.g. `| bash -s -- --uninstall`):
#   (none)            install Salah Bar, or update it to the newest release
#   --force           reinstall even if the newest release is already installed
#   --uninstall       remove the OLD SwiftBar/Übersicht version of salah-bar
#                     (keeps ~/.config/salah-bar/config.json unless --purge)
#   --purge           with --uninstall: also delete the old config.json
#   --uninstall-app   remove the Salah Bar app, its data and its settings
#   -y, --yes         don't ask for confirmation
#   -h, --help        show this help
#
# The old Python version lives in legacy/ and under the git tag v1-python.

set -euo pipefail

REPO_SLUG="be-liever95/salah-bar"
RELEASES_URL="${SALAH_BAR_RELEASES_URL:-https://api.github.com/repos/$REPO_SLUG/releases}"
APP_NAME="Salah Bar"
BUNDLE_ID="io.github.abdalmoamen95.salahbar"
APPS_DIR="${SALAH_BAR_APPS_DIR:-/Applications}"   # override only for testing
APP_PATH="$APPS_DIR/$APP_NAME.app"
MIN_MACOS=14

# The old (Python) version's files, for --uninstall.
OLD_CONFIG_DIR="$HOME/.config/salah-bar"
OLD_CONFIG_FILE="$OLD_CONFIG_DIR/config.json"
OLD_APP_DIR="$OLD_CONFIG_DIR/app"
OLD_PLUGIN_DIR="$OLD_CONFIG_DIR/plugins"
OLD_STATE_FILE="$HOME/.prayertimes_city"
UBERSICHT_WIDGETS="$HOME/Library/Application Support/Übersicht/widgets"
OLD_WIDGET="$UBERSICHT_WIDGETS/prayertimes.widget"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
AGENT_SWIFTBAR="com.salah-bar.launch-swiftbar"
AGENT_UBERSICHT="com.salah-bar.launch-ubersicht"

# ---------------------------------------------------------------- options ---
MODE="install"          # install | uninstall | uninstall-app
ASSUME_YES=0
PURGE=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --uninstall) MODE="uninstall" ;;
    --uninstall-app) MODE="uninstall-app" ;;
    --purge) PURGE=1 ;;
    --force) FORCE=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help)
      cat <<'HELP'
Salah Bar installer

  curl -fsSL https://raw.githubusercontent.com/be-liever95/salah-bar/main/install.sh | bash
  curl -fsSL .../install.sh | bash -s -- [options]

  (no option)       install Salah Bar, or update it to the newest release
  --force           reinstall even if the newest release is already installed
  --uninstall       remove the OLD SwiftBar/Übersicht version of salah-bar
                    (keeps ~/.config/salah-bar/config.json unless --purge)
  --purge           with --uninstall: also delete the old config.json
  --uninstall-app   remove the Salah Bar app, its data and its settings
  -y, --yes         don't ask for confirmation
  -h, --help        show this help
HELP
      exit 0 ;;
    *) printf "Unknown option: %s (try --help)\n" "$arg" >&2; exit 2 ;;
  esac
done
if [ "$PURGE" = 1 ] && [ "$MODE" != "uninstall" ]; then
  printf "%s\n" "--purge only works together with --uninstall." >&2; exit 2
fi

# ---------------------------------------------------------------- output ---
HAS_TTY=0
if { : </dev/tty; } 2>/dev/null; then HAS_TTY=1; fi

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
say()    { printf "%s\n" "$*"; }
die()    { red "✗ $*"; exit 1; }

# ask "Question" default(Y|N) -> returns 0 for yes. Reads from the terminal
# even under `curl | bash`; without a terminal (or with --yes) uses the default.
ask() {
  local question="$1" default="$2" reply hint
  if [ "$ASSUME_YES" = 1 ]; then return 0; fi
  if [ "$HAS_TTY" = 0 ]; then [ "$default" = "Y" ]; return; fi
  if [ "$default" = "Y" ]; then hint="[Y/n]"; else hint="[y/N]"; fi
  printf "%s %s " "$question" "$hint" > /dev/tty
  read -r reply < /dev/tty || reply=""
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy] ]]
}

# ------------------------------------------------------------- utilities ---
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/salah-bar.XXXXXX")"
MOUNT_POINT=""
cleanup() {
  if [ -n "$MOUNT_POINT" ]; then
    hdiutil detach -quiet "$MOUNT_POINT" >/dev/null 2>&1 \
      || hdiutil detach -quiet -force "$MOUNT_POINT" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# Runs a command, with sudo only if the target folder isn't writable.
as_needed() {
  if [ -w "$APPS_DIR" ]; then "$@"; else sudo "$@"; fi
}

app_running() { pgrep -x "$APP_NAME" >/dev/null 2>&1; }

quit_app() {
  app_running || return 0
  say "Quitting ${APP_NAME}…"
  osascript -e "quit app \"$APP_NAME\"" >/dev/null 2>&1 || true
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    app_running || return 0
    sleep 1
  done
  pkill -x "$APP_NAME" >/dev/null 2>&1 || true
  sleep 1
}

installed_version() {
  [ -f "$APP_PATH/Contents/Info.plist" ] || return 0
  /usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$APP_PATH/Contents/Info.plist" 2>/dev/null || true
}

check_macos() {
  [ "$(uname -s)" = "Darwin" ] || die "Salah Bar only runs on macOS."
  local version major
  version="$(sw_vers -productVersion 2>/dev/null || echo 0)"
  major="${version%%.*}"
  [ "${major:-0}" -ge "$MIN_MACOS" ] 2>/dev/null \
    || die "Salah Bar needs macOS $MIN_MACOS Sonoma or later (this Mac has $version)."
}

# Prints "<tag>\t<dmg name>\t<dmg url>" for the newest release that has a
# Salah-Bar-*.dmg asset, reading the GitHub releases JSON file at $1. The repo
# also has non-app releases (like tracks-v1), so "latest" can't be trusted.
# JavaScript for Automation (osascript) is built into every Mac; python3 isn't
# (/usr/bin/python3 is a stub that asks to install the developer tools).
pick_release() {
  /usr/bin/osascript -l JavaScript - "$1" <<'JXA'
function run(argv) {
  ObjC.import('Foundation');
  const text = $.NSString.stringWithContentsOfFileEncodingError(argv[0], $.NSUTF8StringEncoding, null);
  if (!text || text.isNil()) throw new Error('unreadable');
  const releases = JSON.parse(text.js);
  if (!Array.isArray(releases)) throw new Error('not a list');
  releases.sort((a, b) => (b.published_at || b.created_at || '').localeCompare(a.published_at || a.created_at || ''));
  for (const r of releases) {
    if (r.draft || r.prerelease) continue;
    for (const a of r.assets || []) {
      const name = a.name || '';
      if (name.startsWith('Salah-Bar-') && name.endsWith('.dmg')) {
        return [r.tag_name || '', name, a.browser_download_url].join('\t');
      }
    }
  }
  throw new Error('no release');
}
JXA
}

# ------------------------------------------------------------- install ---
do_install() {
  check_macos
  say "Looking for the newest Salah Bar release…"
  curl -fsSL --max-time 30 -H "Accept: application/vnd.github+json" "$RELEASES_URL" -o "$TMP_DIR/releases.json" \
    || die "Couldn't reach GitHub. Check your internet connection and try again."
  local picked tag dmg_name dmg_url version current
  picked="$(pick_release "$TMP_DIR/releases.json" 2>/dev/null)" \
    || die "No Salah Bar release was found. See https://github.com/$REPO_SLUG/releases"
  IFS=$'\t' read -r tag dmg_name dmg_url <<< "$picked"
  version="${dmg_name#Salah-Bar-}"; version="${version%.dmg}"

  current="$(installed_version)"
  if [ -n "$current" ] && [ "$current" = "$version" ] && [ "$FORCE" = 0 ]; then
    green "✓ $APP_NAME $current is already installed and up to date."
    open -a "$APP_PATH" >/dev/null 2>&1 || true
    return
  fi

  say "Downloading $dmg_name ($tag)…"
  curl -fL --progress-bar --max-time 600 "$dmg_url" -o "$TMP_DIR/$dmg_name" \
    || die "Download failed. Check your internet connection and try again."

  MOUNT_POINT="$TMP_DIR/mnt"
  mkdir -p "$MOUNT_POINT"
  hdiutil attach -nobrowse -readonly -noautoopen -quiet -mountpoint "$MOUNT_POINT" "$TMP_DIR/$dmg_name" \
    || { MOUNT_POINT=""; die "Couldn't open $dmg_name."; }
  [ -d "$MOUNT_POINT/$APP_NAME.app" ] || die "$dmg_name doesn't contain $APP_NAME.app."

  quit_app
  say "Installing to ${APP_PATH}…"
  [ -w "$APPS_DIR" ] || yellow "Your Mac password is needed to write to $APPS_DIR."
  # Copy next to the old app first, so a failed copy leaves the old one in place.
  local staged="$APPS_DIR/.$APP_NAME.app.installing"
  as_needed rm -rf "$staged"
  as_needed ditto "$MOUNT_POINT/$APP_NAME.app" "$staged" || die "Couldn't copy $APP_NAME into $APPS_DIR."
  as_needed rm -rf "$APP_PATH"
  as_needed mv "$staged" "$APP_PATH"

  hdiutil detach -quiet "$MOUNT_POINT" >/dev/null 2>&1 || true
  MOUNT_POINT=""

  open -a "$APP_PATH" >/dev/null 2>&1 || yellow "Open $APP_NAME from your Applications folder."

  echo
  if [ -n "$current" ] && [ "$current" = "$version" ]; then
    green "✓ $APP_NAME $version was reinstalled."
  elif [ -n "$current" ]; then
    green "✓ $APP_NAME was updated from $current to $version."
    # The welcome tour came in 2.11; earlier installs never saw it.
    if [ "$(printf '%s\n' "$current" 2.11.0 | sort -V | head -1)" != "2.11.0" ]; then
      say "  • New: a short welcome tour. Click 🕌 in the menu bar, then Take the Tour."
    fi
  else
    green "✓ $APP_NAME $version is installed."
    say "  • A short welcome tour opens to set it up: language, location and the adhan."
    say "    (Behind this window? Look for 🕌 at the top of your screen.)"
    say "  • Optional: add the desktop widget (right-click the desktop → Edit Widgets…)."
  fi
  # curl doesn't add the com.apple.quarantine flag that browsers add, so
  # Gatekeeper's "can't check this app" prompt doesn't appear. Nothing else
  # is touched: we never remove quarantine from other files.
  say "  • Downloaded with curl, so macOS doesn't show the first-launch warning."
  say "  • Future updates install from inside the app (Check for Updates…)."
  if [ -d "$OLD_APP_DIR" ] || [ -e "$OLD_PLUGIN_DIR/prayertimes.30s.sh" ] \
     || [ -e "$OLD_WIDGET" ] || [ -L "$OLD_WIDGET" ]; then
    echo
    yellow "The old SwiftBar/Übersicht version is still installed, so you'd get"
    yellow "every adhan twice. Remove it (your settings are kept) with:"
    say "  curl -fsSL https://raw.githubusercontent.com/$REPO_SLUG/main/install.sh | bash -s -- --uninstall"
  fi
}

# ------------------------------------------- uninstall the old version ---
remove_launch_agent() {
  local plist="$LAUNCH_AGENTS_DIR/$1.plist"
  [ -f "$plist" ] || return 0
  launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 \
    || launchctl unload "$plist" >/dev/null 2>&1 || true
  rm -f "$plist"
}

# Lists a folder's entries, ignoring hidden files like .DS_Store.
visible_entries() {
  [ -d "$1" ] || return 0
  find "$1" -mindepth 1 -maxdepth 1 ! -name '.*' 2>/dev/null
}

do_uninstall() {
  say "Removing the old SwiftBar/Übersicht version of salah-bar…"
  pkill -f 'adhan_fad[e]\.js' >/dev/null 2>&1 || true

  # SwiftBar plugin. Remove only ours: this folder may hold other plugins.
  rm -f "$OLD_PLUGIN_DIR"/prayertimes.*.sh "$OLD_PLUGIN_DIR"/prayertimes.*.py
  local other_plugins=0
  if [ -n "$(visible_entries "$OLD_PLUGIN_DIR")" ]; then
    other_plugins=1
  elif [ -d "$OLD_PLUGIN_DIR" ]; then
    rm -f "$OLD_PLUGIN_DIR/.DS_Store"
    rmdir "$OLD_PLUGIN_DIR" 2>/dev/null || true
    if [ "$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)" = "$OLD_PLUGIN_DIR" ]; then
      defaults delete com.ameba.SwiftBar PluginDirectory >/dev/null 2>&1 || true
    fi
  fi
  if [ "$other_plugins" = 1 ]; then
    open -g "swiftbar://refreshallplugins" >/dev/null 2>&1 || true
  else
    remove_launch_agent "$AGENT_SWIFTBAR"
    osascript -e 'quit app "SwiftBar"' >/dev/null 2>&1 || true
  fi

  # Übersicht widget. It may be a symlink into a git checkout (--dev
  # installs), so remove the link itself and never what it points to.
  if [ -L "$OLD_WIDGET" ]; then
    rm -f "$OLD_WIDGET"
  elif [ -e "$OLD_WIDGET" ]; then
    rm -rf "$OLD_WIDGET"
  fi
  local other_widgets=0
  [ -n "$(visible_entries "$UBERSICHT_WIDGETS")" ] && other_widgets=1
  if [ "$other_widgets" = 0 ]; then
    remove_launch_agent "$AGENT_UBERSICHT"
    osascript -e 'quit app "Übersicht"' >/dev/null 2>&1 || true
  fi

  rm -rf "$OLD_APP_DIR" "$HOME/Library/Caches/prayertimes" "$HOME/Library/Logs/salah-bar"
  rm -f "$OLD_STATE_FILE"
  if [ "$PURGE" = 1 ]; then
    rm -f "$OLD_CONFIG_FILE" "$OLD_CONFIG_DIR/.DS_Store"
    # The folder goes too, unless the user keeps other files (plugins) in it.
    rmdir "$OLD_CONFIG_DIR" 2>/dev/null || true
  fi

  echo
  green "✓ The old version of salah-bar has been removed."
  [ "$PURGE" = 1 ] || say "  • Your settings are kept in $OLD_CONFIG_FILE (use --purge to delete them)."
  [ "$other_plugins" = 1 ] && say "  • SwiftBar keeps running for your other plugins in $OLD_PLUGIN_DIR."
  [ "$other_widgets" = 1 ] && say "  • Übersicht keeps running for your other widgets."
  say "  • SwiftBar and Übersicht themselves were left installed; remove them from"
  say "    Applications if you don't use them for anything else."
}

# ---------------------------------------------------- uninstall the app ---
do_uninstall_app() {
  local data="$HOME/Library/Application Support/$APP_NAME"
  local logs="$HOME/Library/Logs/$APP_NAME"
  say "This removes:"
  say "  • $APP_PATH"
  say "  • $data"
  say "  • its settings ($BUNDLE_ID)"
  if ! ask "Remove $APP_NAME?" N; then
    if [ "$HAS_TTY" = 0 ]; then
      yellow "No terminal to ask for confirmation; run again with -y to remove it."
    else
      say "Nothing was removed."
    fi
    exit 1
  fi
  quit_app
  if [ -d "$APP_PATH" ]; then
    as_needed rm -rf "$APP_PATH"
  fi
  rm -rf "$data" "$logs"
  defaults delete "$BUNDLE_ID" >/dev/null 2>&1 || true
  echo
  green "✓ $APP_NAME has been removed."
}

case "$MODE" in
  install) do_install ;;
  uninstall) do_uninstall ;;
  uninstall-app) do_uninstall_app ;;
esac
