#!/usr/bin/env python3
# <bitbar.title>Prayer Times</bitbar.title>
# <bitbar.version>v1</bitbar.version>
# <bitbar.author>mumin</bitbar.author>
# <bitbar.desc>Live countdown to the next Islamic prayer.</bitbar.desc>
# <bitbar.dependencies>python3</bitbar.dependencies>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_CONFIG = {
    "default_city": "izmir",
    "method": 13,
    "school": 0,
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

STATE_FILE = os.path.expanduser("~/.prayertimes_city")
CACHE_DIR  = os.path.expanduser("~/Library/Caches/prayertimes")
CONFIG_FILE = os.path.expanduser("~/.config/salah-bar/config.json")
CONFIG_TOOL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "support", "configure.py")
os.makedirs(CACHE_DIR, exist_ok=True)

PRAYERS = [
    ("Fajr",    "الفجر"),
    ("Dhuhr",   "الظهر"),
    ("Asr",     "العصر"),
    ("Maghrib", "المغرب"),
    ("Isha",    "العشاء"),
]


def load_config():
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_FILE) as f:
            raw = json.load(f)
    except Exception:
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


def load_city(config):
    try:
        v = open(STATE_FILE).read().strip()
        return v if v in config["cities"] else config["default_city"]
    except Exception:
        return config["default_city"]


def save_city(c):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(c)
    except Exception:
        pass


def fetch_timings(config, city):
    city_config = config["cities"][city]
    lat = city_config["lat"]
    lon = city_config["lon"]
    tz = city_config["tz"]
    tzinfo = ZoneInfo(tz)
    now = datetime.now(tzinfo)
    date_str = now.strftime("%d-%m-%Y")
    cache = os.path.join(CACHE_DIR, f"{city}_{date_str}.json")
    if not os.path.exists(cache) or os.path.getsize(cache) < 100:
        url = (
            f"https://api.aladhan.com/v1/timings/{date_str}"
            f"?latitude={lat}&longitude={lon}&method={config['method']}&school={config['school']}"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
        with open(cache, "wb") as f:
            f.write(data)
    return json.load(open(cache)), now, tzinfo


def parse_hhmm(t):
    return t.split(" ")[0]


def build_schedule(timings, now, tzinfo):
    out = []
    for key, ar in PRAYERS:
        hh, mm = parse_hhmm(timings[key]).split(":")
        d = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        out.append((key, ar, d))
    return out


def fmt_countdown(delta):
    total = max(0, int(delta.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    # Allow CLI args from SwiftBar to cycle/set city.
    if len(sys.argv) > 1 and sys.argv[1] == "set" and len(sys.argv) > 2:
        save_city(sys.argv[2])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "configure":
        action = sys.argv[2] if len(sys.argv) > 2 else ""
        subprocess.run([sys.executable, "-B", CONFIG_TOOL, action], check=False)
        return

    config = load_config()
    city = load_city(config)
    try:
        data, now, tzinfo = fetch_timings(config, city)
        timings = data["data"]["timings"]
    except Exception as e:
        print(f"🕌 ⚠")
        print("---")
        print(f"Prayer times error: {e}")
        return

    schedule = build_schedule(timings, now, tzinfo)
    upcoming = [s for s in schedule if s[2] > now]
    if upcoming:
        next_p = upcoming[0]
    else:
        # Tomorrow's Fajr (close enough until next refresh)
        first = schedule[0]
        next_p = (first[0], first[1], first[2] + timedelta(days=1))

    countdown = fmt_countdown(next_p[2] - now)
    label = config["cities"][city]["label"]

    # Menu bar line — first line shown
    print(f"🕌 {next_p[0]} {countdown[:5]}")

    # Dropdown
    print("---")
    print(f"City: {label} | size=12")
    print(f"Next: {next_p[0]} ({next_p[1]}) at {next_p[2].strftime('%H:%M')} | size=12")
    print("---")
    for key, ar, d in schedule:
        marker = "→" if key == next_p[0] and d.date() == next_p[2].date() else " "
        passed = d < now
        opacity = " color=#888888" if passed and not (key == next_p[0]) else ""
        print(f"{marker} {key}  {ar}  {d.strftime('%H:%M')} | font=Menlo size=13{opacity}")
    print("---")
    print("Switch city")
    script = os.path.realpath(__file__)
    py = sys.executable
    for k, city_config in config["cities"].items():
        lbl = city_config["label"]
        check = " ✓" if k == city else ""
        print(
            f"--{lbl}{check} | bash='{py}' param1='{script}' param2=set param3={k} terminal=false refresh=true"
        )
    print("---")
    print("Configure")
    print(
        f"--Choose default city | bash='{py}' param1='{script}' param2=configure param3=choose-default terminal=false refresh=true"
    )
    print(
        f"--Add preset city (Turkey/Egypt/Qatar) | bash='{py}' param1='{script}' param2=configure param3=add-preset-city terminal=false refresh=true"
    )
    print(
        f"--Add custom city | bash='{py}' param1='{script}' param2=configure param3=add-custom-city terminal=false refresh=true"
    )
    print(
        f"--Open config file | bash='{py}' param1='{script}' param2=configure param3=open-config terminal=false refresh=false"
    )
    print("---")
    print("Refresh | refresh=true")


if __name__ == "__main__":
    main()
