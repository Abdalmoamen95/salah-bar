#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

CONFIG_FILE = os.path.expanduser("~/.config/salah-bar/config.json")
STATE_FILE = os.path.expanduser("~/.prayertimes_city")
PRESET_CITIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "preset-cities.json")

DEFAULT_CONFIG = {
    "default_city": "izmir",
    "method": 13,
    "school": 0,
    "cities": {
        "izmir": {
            "label": "Izmir",
            "lat": 38.4192,
            "lon": 27.1287,
            "tz": "Europe/Istanbul",
        },
        "doha": {
            "label": "Doha",
            "lat": 25.2854,
            "lon": 51.5310,
            "tz": "Asia/Qatar",
        },
        "cairo": {
            "label": "Cairo",
            "lat": 30.0444,
            "lon": 31.2357,
            "tz": "Africa/Cairo",
        },
    },
}


def normalize_config(raw):
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(raw, dict):
        return config

    if isinstance(raw.get("method"), int):
        config["method"] = raw["method"]
    if raw.get("school") in (0, 1):
        config["school"] = raw["school"]

    cities = raw.get("cities")
    if isinstance(cities, dict):
        normalized = {}
        for key, city in cities.items():
            if not isinstance(city, dict):
                continue
            try:
                normalized[key] = {
                    "label": str(city["label"]),
                    "lat": float(city["lat"]),
                    "lon": float(city["lon"]),
                    "tz": str(city["tz"]),
                }
            except Exception:
                continue
        if normalized:
            config["cities"] = normalized

    default_city = raw.get("default_city")
    if default_city in config["cities"]:
        config["default_city"] = default_city

    return config


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return normalize_config(json.load(f))
    except Exception:
        return normalize_config({})


def load_presets():
    with open(PRESET_CITIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


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
        ["Choose default city", "Add preset city", "Add custom city", "Open config file"],
        "What would you like to configure?",
        "Choose default city",
    )


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        if action == "add-preset-city":
            add_preset_city()
        elif action == "add-custom-city":
            add_custom_city()
        elif action == "choose-default":
            choose_default_city()
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