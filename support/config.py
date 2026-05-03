#!/usr/bin/env python3
"""
Shared configuration module for Prayer Times widget.
Single source of truth for config schema, defaults, and validation.
Eliminates duplication across index.jsx, prayertimes.30s.py, and configure.py
"""

import json
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

# Paths
CONFIG_FILE = os.path.expanduser("~/.config/salah-bar/config.json")
CONFIG_DIR = os.path.dirname(CONFIG_FILE)
STATE_FILE = os.path.expanduser("~/.prayertimes_city")
CACHE_DIR = os.path.expanduser("~/Library/Caches/prayertimes")
LOG_DIR = os.path.expanduser("~/Library/Logs/salah-bar")
LOG_FILE = os.path.join(LOG_DIR, "salah-bar.log")

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger("salah-bar")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)


# Default configuration
DEFAULT_CONFIG = {
    "default_city": "izmir",
    "method": 13,
    "school": 0,
    "language": "en",
    "flash_warning": {
        "enabled": True,
        "minutes": 5,
    },
    "notifications": {
        "enabled": True,
        "offsets_minutes": [10, 5, 0],
    },
    "cities": {
        "izmir": {
            "label": "İzmir",
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
    """Validate and normalize raw config from disk or defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(raw, dict):
        return config

    if isinstance(raw.get("method"), int):
        config["method"] = raw["method"]
    if raw.get("school") in (0, 1):
        config["school"] = raw["school"]
    if raw.get("language") in ("en", "tr"):
        config["language"] = raw["language"]

    flash_warning = raw.get("flash_warning")
    if isinstance(flash_warning, dict):
        if isinstance(flash_warning.get("enabled"), bool):
            config["flash_warning"]["enabled"] = flash_warning["enabled"]
        minutes = flash_warning.get("minutes")
        if isinstance(minutes, int) and minutes > 0:
            config["flash_warning"]["minutes"] = minutes

    notifications = raw.get("notifications")
    if isinstance(notifications, dict):
        if isinstance(notifications.get("enabled"), bool):
            config["notifications"]["enabled"] = notifications["enabled"]
        offsets = notifications.get("offsets_minutes")
        if isinstance(offsets, list):
            valid_offsets = [v for v in offsets if isinstance(v, int) and v >= 0]
            if valid_offsets:
                config["notifications"]["offsets_minutes"] = sorted(set(valid_offsets), reverse=True)

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
            except (ValueError, KeyError, TypeError):
                continue
        if normalized:
            config["cities"] = normalized

    default_city = raw.get("default_city")
    if default_city in config["cities"]:
        config["default_city"] = default_city

    return config


def load_config():
    """Load and validate config from disk, fall back to defaults."""
    try:
        with open(CONFIG_FILE) as f:
            return normalize_config(json.load(f))
    except Exception as e:
        logger.warning(f"Failed to load config from {CONFIG_FILE}: {e}, using defaults")
        return normalize_config({})


def save_config(config):
    """Write validated config to disk."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info(f"Config saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise


def load_city(config):
    """Load last-used city from state file, fallback to default_city."""
    try:
        v = open(STATE_FILE).read().strip()
        return v if v in config["cities"] else config["default_city"]
    except Exception:
        return config["default_city"]


def save_city(city):
    """Save currently-displayed city to state file."""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(city)
    except Exception as e:
        logger.warning(f"Failed to save city: {e}")


def detect_system_timezone():
    """Detect system timezone and find a matching configured city, or suggest one."""
    try:
        # Get system timezone
        import subprocess
        result = subprocess.run(
            ["systemsetup", "-gettimezone"],
            capture_output=True,
            text=True,
            timeout=5
        )
        tz_line = result.stdout.strip()
        if "Time Zone:" in tz_line:
            system_tz = tz_line.split("Time Zone:")[1].strip()
            if system_tz in available_timezones():
                logger.info(f"Detected system timezone: {system_tz}")
                return system_tz
    except Exception as e:
        logger.debug(f"Could not detect system timezone: {e}")
    return None


def validate_config_schema(config):
    """Validate config has required keys and correct types. Returns (is_valid, errors)."""
    errors = []

    if not isinstance(config, dict):
        return False, ["Config is not a dict"]

    # Required top-level keys
    required_keys = ["default_city", "method", "school", "language", "cities"]
    for key in required_keys:
        if key not in config:
            errors.append(f"Missing required key: {key}")

    # Validate cities structure
    if "cities" in config and isinstance(config["cities"], dict):
        if not config["cities"]:
            errors.append("No cities configured")
        for city_key, city_data in config["cities"].items():
            if not isinstance(city_data, dict):
                errors.append(f"City '{city_key}' is not a dict")
                continue
            required_city_keys = ["label", "lat", "lon", "tz"]
            for key in required_city_keys:
                if key not in city_data:
                    errors.append(f"City '{city_key}' missing key: {key}")

    return len(errors) == 0, errors


if __name__ == "__main__":
    # Simple test
    config = load_config()
    valid, errors = validate_config_schema(config)
    print(f"Config valid: {valid}")
    if errors:
        for err in errors:
            print(f"  - {err}")
    else:
        print("✓ Config schema is valid")
