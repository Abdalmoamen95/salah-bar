#!/usr/bin/env python3
# <bitbar.title>Prayer Times</bitbar.title>
# <bitbar.version>v1</bitbar.version>
# <bitbar.author>mumin</bitbar.author>
# <bitbar.desc>Live countdown to the next Islamic prayer.</bitbar.desc>
# <bitbar.dependencies>python3</bitbar.dependencies>
# <swiftbar.refreshOnOpen>true</swiftbar.refreshOnOpen>

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CITIES = {
    "izmir": (38.4192, 27.1287, "Europe/Istanbul", "İzmir"),
    "doha":  (25.2854, 51.5310, "Asia/Qatar",      "Doha"),
    "cairo": (30.0444, 31.2357, "Africa/Cairo",    "Cairo"),
}

METHOD = 13
SCHOOL = 0

STATE_FILE = os.path.expanduser("~/.prayertimes_city")
CACHE_DIR  = os.path.expanduser("~/Library/Caches/prayertimes")
os.makedirs(CACHE_DIR, exist_ok=True)

PRAYERS = [
    ("Fajr",    "الفجر"),
    ("Dhuhr",   "الظهر"),
    ("Asr",     "العصر"),
    ("Maghrib", "المغرب"),
    ("Isha",    "العشاء"),
]


def load_city():
    try:
        v = open(STATE_FILE).read().strip()
        return v if v in CITIES else "izmir"
    except Exception:
        return "izmir"


def save_city(c):
    try:
        with open(STATE_FILE, "w") as f:
            f.write(c)
    except Exception:
        pass


def fetch_timings(city):
    lat, lon, tz, _label = CITIES[city]
    tzinfo = ZoneInfo(tz)
    now = datetime.now(tzinfo)
    date_str = now.strftime("%d-%m-%Y")
    cache = os.path.join(CACHE_DIR, f"{city}_{date_str}.json")
    if not os.path.exists(cache) or os.path.getsize(cache) < 100:
        url = (
            f"https://api.aladhan.com/v1/timings/{date_str}"
            f"?latitude={lat}&longitude={lon}&method={METHOD}&school={SCHOOL}"
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

    city = load_city()
    try:
        data, now, tzinfo = fetch_timings(city)
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
    label = CITIES[city][3]

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
    for k, (_lat, _lon, _tz, lbl) in CITIES.items():
        check = " ✓" if k == city else ""
        print(
            f"--{lbl}{check} | bash='{py}' param1='{script}' param2=set param3={k} terminal=false refresh=true"
        )
    print("---")
    print("Refresh | refresh=true")


if __name__ == "__main__":
    main()
