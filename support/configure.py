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
    CONFIG_FILE, STATE_FILE, CACHE_DIR, DEFAULT_CONFIG,
    detect_system_timezone, find_matching_city, suggest_timezone_city
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


def load_presets():
    """Load preset cities from preset-cities.json."""
    try:
        with open(PRESET_CITIES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


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


def view_cities():
    """Show a summary of all configured cities with option to remove."""
    config = load_config()
    cities = config.get("cities", {})
    
    if not cities:
        run_osascript(['display dialog "No cities configured yet" buttons {"OK"} default button "OK" with title "salah-bar"'])
        return
    
    city_list = []
    for key, city in sorted(cities.items(), key=lambda x: x[1]["label"]):
        default_mark = " ✓" if key == config["default_city"] else ""
        city_list.append(f"{city['label']} ({city['tz']}){default_mark}")
    
    # Show list with info
    picked = choose_from_list(city_list, "Your cities:", city_list[0] if city_list else None)
    
    # Extract city label from picked string
    city_label = picked.split(" (")[0]
    key = next((k for k, c in cities.items() if c["label"] == city_label), None)
    
    if key and key != config["default_city"]:
        if ask_yes_no(f"Remove {city_label}?", yes_label="Remove", no_label="Keep"):
            del config["cities"][key]
            save_config(config)
            run_osascript([
                f'display notification "Removed {applescript_escape(city_label)}" with title "salah-bar"'
            ])


def remove_city():
    """Remove a configured city."""
    config = load_config()
    cities = config.get("cities", {})
    
    if len(cities) <= 1:
        run_osascript(['display dialog "Cannot remove the only city" buttons {"OK"} default button "OK" with title "salah-bar"'])
        return
    
    removable = {k: c for k, c in cities.items() if k != config["default_city"]}
    if not removable:
        run_osascript(['display dialog "Cannot remove default city. Change default first." buttons {"OK"} default button "OK" with title "salah-bar"'])
        return
    
    city_list = [c["label"] for c in sorted(removable.values(), key=lambda x: x["label"])]
    picked_label = choose_from_list(city_list, "Remove which city?")
    key = next((k for k, c in removable.items() if c["label"] == picked_label), None)
    
    if key:
        del config["cities"][key]
        save_config(config)
        run_osascript([
            f'display notification "Removed {applescript_escape(picked_label)}" with title "salah-bar"'
        ])


def show_settings_summary():
    """Display a summary of current configuration."""
    config = load_config()
    cities = config.get("cities", {})
    
    city_count = len(cities)
    default_city_label = cities.get(config["default_city"], {}).get("label", "Unknown")
    
    METHOD_NAMES = {
        2: "Muslim World League",
        5: "Egyptian General Authority",
        13: "Diyanet (Turkey)",
    }
    method_name = METHOD_NAMES.get(config.get("method", 13), "Custom")
    
    lang_names = {"en": "English", "tr": "Turkish"}
    language = lang_names.get(config.get("language", "en"), "English")
    
    notif_status = "ON" if config.get("notifications", {}).get("enabled", True) else "OFF"
    flash_status = "ON" if config.get("flash_warning", {}).get("enabled", True) else "OFF"
    flash_mins = config.get("flash_warning", {}).get("minutes", 5)
    
    summary = f"""
📍 Default City: {default_city_label}
🌍 Total Cities: {city_count}

⚙️ Settings:
  • Prayer Method: {method_name}
  • Language: {language}
  • Notifications: {notif_status}
  • Green Flash Alert: {flash_status} ({flash_mins}min)
""".strip()
    
    run_osascript([
        f'display dialog "{applescript_escape(summary)}" buttons {{"Close"}} default button "Close" with title "salah-bar Configuration" with icon note'
    ])


def choose_api_method():
    """Let user select calculation method with descriptions."""
    config = load_config()
    
    methods = {
        "Muslim World League": 2,
        "Egyptian Authority": 5,
        "Diyanet (Turkey)": 13,
    }
    
    descriptions = {
        "Muslim World League": "Used in most Arab countries",
        "Egyptian Authority": "Official Egyptian method",
        "Diyanet (Turkey)": "Turkish government method",
    }
    
    current_method = config.get("method", 13)
    current_name = next((k for k, v in methods.items() if v == current_method), "Diyanet (Turkey)")
    
    picked = choose_from_list(list(methods.keys()), "Choose prayer calculation method:", current_name)
    
    if picked:
        config["method"] = methods[picked]
        save_config(config)
        run_osascript([
            f'display notification "Method set to {applescript_escape(picked)}" with title "salah-bar"'
        ])


def choose_school():
    """Let user select Islamic school (Madhab)."""
    config = load_config()
    
    schools = {
        "Shafi'i": 0,
        "Hanafi": 1,
    }
    
    current = config.get("school", 0)
    current_name = "Hanafi" if current == 1 else "Shafi'i"
    
    picked = choose_from_list(list(schools.keys()), "Choose Islamic school (affects Asr time):", current_name)
    
    if picked:
        config["school"] = schools[picked]
        save_config(config)
        run_osascript([
            f'display notification "School set to {applescript_escape(picked)}" with title "salah-bar"'
        ])


def choose_display_settings():
    """Configure display options."""
    config = load_config()
    
    setting = choose_from_list(
        ["Widget Size", "Theme", "Show Seconds in Countdown"],
        "Choose display setting to configure:"
    )
    
    if setting == "Widget Size":
        size = choose_from_list(
            ["Compact", "Normal", "Large"],
            "Select widget size:",
            config.get("display", {}).get("size", "Normal")
        )
        if not config.get("display"):
            config["display"] = {}
        config["display"]["size"] = size
        save_config(config)
        run_osascript([f'display notification "Widget size set to {size}" with title "salah-bar"'])
    
    elif setting == "Theme":
        theme = choose_from_list(
            ["Light", "Dark"],
            "Select theme:",
            config.get("display", {}).get("theme", "Dark")
        )
        if not config.get("display"):
            config["display"] = {}
        config["display"]["theme"] = theme
        save_config(config)
        run_osascript([f'display notification "Theme set to {theme}" with title "salah-bar"'])
    
    elif setting == "Show Seconds in Countdown":
        show_secs = not config.get("display", {}).get("show_seconds", False)
        if not config.get("display"):
            config["display"] = {}
        config["display"]["show_seconds"] = show_secs
        save_config(config)
        state = "enabled" if show_secs else "disabled"
        run_osascript([f'display notification "Seconds in countdown {state}" with title "salah-bar"'])


def main_menu():
    """Main menu with categorized options."""
    config = load_config()
    default_city = config.get("cities", {}).get(config["default_city"], {}).get("label", "Unknown")
    
    menu_items = [
        "📍 Cities",
        "⚙️ Prayer Settings",
        "🎨 Display Settings",
        "🔔 Notifications",
        "📊 View Configuration",
        "↺ Reset All",
        "✏️ Edit Config File",
    ]
    
    picked = choose_from_list(menu_items, "salah-bar Configuration", "📍 Cities")
    
    if picked == "📍 Cities":
        cities_menu()
    elif picked == "⚙️ Prayer Settings":
        prayer_settings_menu()
    elif picked == "🎨 Display Settings":
        choose_display_settings()
    elif picked == "🔔 Notifications":
        notifications_menu()
    elif picked == "📊 View Configuration":
        show_settings_summary()
    elif picked == "↺ Reset All":
        reset_to_defaults()
    elif picked == "✏️ Edit Config File":
        open_config()


def cities_menu():
    """Cities management submenu."""
    cities_items = [
        "Set Default City",
        "Add Preset City",
        "Add Custom City",
        "View All Cities",
        "Remove City",
    ]
    
    picked = choose_from_list(cities_items, "Manage Cities", "Set Default City")
    
    if picked == "Set Default City":
        choose_default_city()
    elif picked == "Add Preset City":
        add_preset_city()
    elif picked == "Add Custom City":
        add_custom_city()
    elif picked == "View All Cities":
        view_cities()
    elif picked == "Remove City":
        remove_city()


def prayer_settings_menu():
    """Prayer calculation settings submenu."""
    prayer_items = [
        "Choose Prayer Method",
        "Choose Islamic School",
        "Choose Language",
    ]
    
    picked = choose_from_list(prayer_items, "Prayer Settings", "Choose Prayer Method")
    
    if picked == "Choose Prayer Method":
        choose_api_method()
    elif picked == "Choose Islamic School":
        choose_school()
    elif picked == "Choose Language":
        choose_language()


def notifications_menu():
    """Notifications settings submenu."""
    config = load_config()
    notif_enabled = config.get("notifications", {}).get("enabled", True)
    flash_enabled = config.get("flash_warning", {}).get("enabled", True)
    
    notif_status = "ON ✓" if notif_enabled else "OFF"
    flash_status = "ON ✓" if flash_enabled else "OFF"
    
    notif_items = [
        f"Prayer Notifications: {notif_status}",
        f"Green Flash Alert: {flash_status}",
        "Flash Alert Window",
    ]
    
    picked = choose_from_list(notif_items, "Notification Settings", notif_items[0])
    
    if picked.startswith("Prayer Notifications"):
        toggle_notifications()
    elif picked.startswith("Green Flash Alert"):
        toggle_flash_warning()
    elif picked == "Flash Alert Window":
        choose_flash_minutes()


def handle_first_run():
    """Offer to detect system timezone and set default city on first run."""
    try:
        suggested_city, system_tz = suggest_timezone_city()
        
        if suggested_city:
            config = load_config()
            city_label = config["cities"][suggested_city]["label"]
            
            if ask_yes_no(
                f"Your system timezone is {system_tz}. Use {city_label} as your default city?",
                yes_label="Use It",
                no_label="Choose Another"
            ):
                config["default_city"] = suggested_city
                save_config(config)
                with open(STATE_FILE, "w") as f:
                    f.write(suggested_city)
                run_osascript([
                    f'display notification "Default city set to {applescript_escape(city_label)}" with title "salah-bar"'
                ])
                return
        
        # If no system TZ match found or user rejected, show normal flow
        choose_default_city()
    except Exception as e:
        logger.warning(f"First-run timezone detection failed: {e}")
        choose_default_city()


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
            main_menu()
    except RuntimeError:
        return
    except Exception as exc:
        run_osascript([
            f'display dialog "{applescript_escape(str(exc))}" buttons {{"OK"}} default button "OK" with title "salah-bar"'
        ])


if __name__ == "__main__":
    main()