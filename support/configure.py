#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Import shared config module
from config import (
    load_config, save_config, load_city, save_city, logger,
    CONFIG_FILE, STATE_FILE, CACHE_DIR, DEFAULT_CONFIG
)

PRESET_CITIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "preset-cities.json")
NOTIFY_STATE_FILE = os.path.join(CACHE_DIR, "notify_state.json")


def applescript_escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def run_osascript(lines):
    result = subprocess.run(
        ["osascript", *sum([["-e", line] for line in lines], [])],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Canceled")
    return result.stdout.strip()


def ask_text(prompt, default_value=""):
    return run_osascript([
        f'set dialogResult to display dialog "{applescript_escape(prompt)}" default answer "{applescript_escape(default_value)}" buttons {{"Cancel", "OK"}} default button "OK"',
        "text returned of dialogResult",
    ])


def ask_yes_no(prompt, yes_label="Yes", no_label="No"):
    answer = run_osascript([
        f'display dialog "{applescript_escape(prompt)}" buttons {{"{applescript_escape(no_label)}", "{applescript_escape(yes_label)}"}} default button "{applescript_escape(yes_label)}"',
        "button returned of result",
    ])
    return answer == yes_label


def choose_from_list(options, prompt, default_value=None):
    quoted = ", ".join(f'"{applescript_escape(option)}"' for option in options)
    lines = [
        f"set choices to {{{quoted}}}",
    ]
    if default_value:
        lines.append(
            f'set picked to choose from list choices with prompt "{applescript_escape(prompt)}" default items {{"{applescript_escape(default_value)}"}}'
        )
    else:
        lines.append(f'set picked to choose from list choices with prompt "{applescript_escape(prompt)}"')
    lines.extend([
        "if picked is false then error number -128",
        "item 1 of picked",
    ])
    return run_osascript(lines)


def slugify(label):
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "city"


def choose_unique_key(config, label):
    base = slugify(label)
    key = base
    counter = 2
    while key in config["cities"]:
        key = f"{base}-{counter}"
        counter += 1
    return key


def save_city_entry(config, key, label, lat, lon, tz):
    config["cities"][key] = {
        "label": label,
        "lat": lat,
        "lon": lon,
        "tz": tz,
    }

    if ask_yes_no(f"Make {label} the default city?", yes_label="Make Default", no_label="Keep Current"):
        config["default_city"] = key
        with open(STATE_FILE, "w") as f:
            f.write(key)

    save_config(config)
    run_osascript([
        f'display notification "Saved {applescript_escape(label)}" with title "salah-bar"'
    ])


def add_custom_city():
    config = load_config()
    label = ask_text("City name shown in the app", "Istanbul").strip()
    if not label:
        raise RuntimeError("City name is required")

    key_default = slugify(label)
    key = ask_text("City key (used internally)", key_default).strip().lower()
    if not key:
        raise RuntimeError("City key is required")

    lat = float(ask_text("Latitude", "41.0082").strip())
    lon = float(ask_text("Longitude", "28.9784").strip())
    tz = ask_text("Timezone (IANA format)", "Europe/Istanbul").strip()
    if not tz:
        raise RuntimeError("Timezone is required")

    if key in config["cities"]:
        overwrite = ask_yes_no(f"{label} already exists. Replace it?", yes_label="Replace", no_label="Cancel")
        if not overwrite:
            return

    save_city_entry(config, key, label, lat, lon, tz)


def add_preset_city():
    config = load_config()
    presets = load_presets()
    country = choose_from_list(sorted(presets.keys()), "Choose a preset country")
    default_query = {
        "Turkey": "Istanbul",
        "Egypt": "Cairo",
        "Qatar": "Doha",
    }.get(country, "")
    query = ask_text(f"Search {country} city names", default_query).strip().lower()
    if len(query) < 2:
        raise RuntimeError("Please enter at least 2 letters to search")

    matches = [
        city for city in presets[country]
        if query in city["label"].lower() or query in city["name"].lower()
    ]
    if not matches:
        raise RuntimeError(f"No matches found in {country}")
    if len(matches) > 250:
        raise RuntimeError(f"Found {len(matches)} matches. Type a more specific search.")

    by_label = {city["label"]: city for city in matches}
    picked_label = choose_from_list(list(by_label.keys()), f"Choose a city in {country}")
    picked = by_label[picked_label]
    key = choose_unique_key(config, picked["label"])
    save_city_entry(config, key, picked["label"], float(picked["lat"]), float(picked["lon"]), picked["tz"])


def choose_default_city():
    config = load_config()
    labels = {city["label"]: key for key, city in config["cities"].items()}
    current_label = config["cities"][config["default_city"]]["label"]
    picked_label = choose_from_list(sorted(labels.keys()), "Choose the default city", current_label)
    key = labels[picked_label]
    config["default_city"] = key
    save_config(config)
    with open(STATE_FILE, "w") as f:
        f.write(key)
    run_osascript([
        f'display notification "Default city set to {applescript_escape(picked_label)}" with title "salah-bar"'
    ])


def open_config():
    config = load_config()
    save_config(config)
    subprocess.run(["open", "-a", "TextEdit", CONFIG_FILE], check=False)


def choose_action():
    return choose_from_list(
        [
            "Choose default city",
            "Add preset city",
            "Add custom city",
            "Toggle notifications",
            "Toggle green flash",
            "Set green flash window",
            "Choose language",
            "Reset to defaults",
            "Open config file",
        ],
        "What would you like to configure?",
        "Choose default city",
    )


def toggle_notifications():
    config = load_config()
    enabled = config["notifications"]["enabled"]
    config["notifications"]["enabled"] = not enabled
    save_config(config)
    state_text = "enabled" if config["notifications"]["enabled"] else "disabled"
    run_osascript([
        f'display notification "Notifications {state_text}" with title "salah-bar"'
    ])


def toggle_flash_warning():
    config = load_config()
    enabled = config.get("flash_warning", {}).get("enabled", True)
    config.setdefault("flash_warning", {"enabled": True, "minutes": 5})
    config["flash_warning"]["enabled"] = not enabled
    save_config(config)
    state_text = "enabled" if config["flash_warning"]["enabled"] else "disabled"
    run_osascript([
        f'display notification "Green flash {state_text}" with title "salah-bar"'
    ])


def set_flash_minutes(minutes):
    if not isinstance(minutes, int) or minutes <= 0:
        raise RuntimeError("Flash window must be a positive integer")
    config = load_config()
    config.setdefault("flash_warning", {"enabled": True, "minutes": 5})
    config["flash_warning"]["minutes"] = minutes
    save_config(config)
    run_osascript([
        f'display notification "Green flash window set to {minutes} min" with title "salah-bar"'
    ])


def choose_flash_minutes():
    config = load_config()
    current = str(config.get("flash_warning", {}).get("minutes", 5))
    picked = choose_from_list(["1", "3", "5", "10", "15"], "Set green flash warning window (minutes)", current)
    set_flash_minutes(int(picked))


def choose_language():
    config = load_config()
    current = config.get("language", "en")
    LANG_LABELS = {"en": "English", "tr": "Turkish"}
    options = ["English", "Turkish"]
    default = LANG_LABELS.get(current, "English")
    picked = choose_from_list(options, "Choose prayer name language", default)
    lang_key = "tr" if picked == "Turkish" else "en"
    config["language"] = lang_key
    save_config(config)
    run_osascript([
        f'display notification "Prayer language set to {picked}" with title "salah-bar"'
    ])


def reset_to_defaults():
    confirmed = ask_yes_no(
        "This will reset cities, default city, method, school, and notifications. Continue?",
        yes_label="Reset",
        no_label="Cancel",
    )
    if not confirmed:
        return

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    save_config(config)
    with open(STATE_FILE, "w") as f:
        f.write(config["default_city"])
    try:
        os.remove(NOTIFY_STATE_FILE)
    except FileNotFoundError:
        pass
    run_osascript([
        'display notification "Configuration reset to defaults" with title "salah-bar"'
    ])


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        if action == "add-preset-city":
            add_preset_city()
        elif action == "add-custom-city":
            add_custom_city()
        elif action == "choose-default":
            choose_default_city()
        elif action == "toggle-notifications":
            toggle_notifications()
        elif action == "toggle-flash-warning":
            toggle_flash_warning()
        elif action and action.startswith("set-flash-minutes-"):
            minutes_text = action.replace("set-flash-minutes-", "", 1)
            set_flash_minutes(int(minutes_text))
        elif action == "choose-language":
            choose_language()
        elif action and action.startswith("set-language-"):
            lang_key = action.replace("set-language-", "", 1)
            if lang_key in ("en", "tr"):
                config = load_config()
                config["language"] = lang_key
                save_config(config)
                LANG_LABELS = {"en": "English", "tr": "Turkish"}
                run_osascript([
                    f'display notification "Prayer language set to {LANG_LABELS[lang_key]}" with title "salah-bar"'
                ])
        elif action == "reset-defaults":
            reset_to_defaults()
        elif action == "open-config":
            open_config()
        else:
            picked = choose_action()
            if picked == "Choose default city":
                choose_default_city()
            elif picked == "Add preset city":
                add_preset_city()
            elif picked == "Add custom city":
                add_custom_city()
            elif picked == "Toggle notifications":
                toggle_notifications()
            elif picked == "Toggle green flash":
                toggle_flash_warning()
            elif picked == "Set green flash window":
                choose_flash_minutes()
            elif picked == "Choose language":
                choose_language()
            elif picked == "Reset to defaults":
                reset_to_defaults()
            else:
                open_config()
    except RuntimeError:
        return
    except Exception as exc:
        run_osascript([
            f'display dialog "{applescript_escape(str(exc))}" buttons {{"OK"}} default button "OK" with title "salah-bar"'
        ])


if __name__ == "__main__":
    main()