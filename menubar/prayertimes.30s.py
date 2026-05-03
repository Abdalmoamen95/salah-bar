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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Add support directory to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "support"))

from config import load_config, load_city, save_city, CACHE_DIR, STATE_FILE, logger
from api import APIClient
from refresh import calculate_optimal_refresh_interval, get_refresh_hint_comment

PRAYER_NAMES = {
    "en": ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"],
    "tr": ["Sabah", "Öğle", "İkindi", "Akşam", "Yatsı"],
}

CONFIG_TOOL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "support", "configure.py")
NOTIFY_STATE_FILE = os.path.join(CACHE_DIR, "notify_state.json")
PYCACHE_DIR = os.path.join(os.path.dirname(__file__), "__pycache__")

PRAYERS = [
    ("Fajr",    "الفجر"),
    ("Dhuhr",   "الظهر"),
    ("Asr",     "العصر"),
    ("Maghrib", "المغرب"),
    ("Isha",    "العشاء"),
]
PRAYER_KEYS = [p[0] for p in PRAYERS]


def fetch_timings(config, city):
    """Fetch prayer times using resilient API client."""
    city_config = config["cities"][city]
    tz = city_config["tz"]
    tzinfo = ZoneInfo(tz)
    now = datetime.now(tzinfo)
    
    api_client = APIClient()
    data, is_fresh, error_msg = api_client.fetch_timings(config, city, tzinfo)
    
    if data is None:
        logger.error(f"Failed to fetch timings for {city}: {error_msg}")
        raise RuntimeError(error_msg or "API fetch failed")
    
    return data, now, tzinfo, is_fresh, error_msg


def parse_hhmm(t):
    return t.split(" ")[0]


def build_schedule(timings, now, tzinfo, lang="en"):
    names = PRAYER_NAMES.get(lang, PRAYER_NAMES["en"])
    out = []
    for (key, ar), local_name in zip(PRAYERS, names):
        hh, mm = parse_hhmm(timings[key]).split(":")
        d = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        out.append((key, local_name, ar, d))
    return out


def fmt_countdown(delta):
    total = max(0, int(delta.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_notify_state():
    try:
        with open(NOTIFY_STATE_FILE) as f:
            raw = json.load(f)
        notified = raw.get("notified", [])
        if isinstance(notified, list):
            return {"notified": set(str(v) for v in notified)}
    except Exception:
        pass
    return {"notified": set()}


def save_notify_state(state):
    payload = {"notified": sorted(state["notified"])}
    with open(NOTIFY_STATE_FILE, "w") as f:
        json.dump(payload, f)


def notify(text):
    safe_text = text.replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe_text}" with title "salah-bar"'],
        check=False,
        capture_output=True,
        text=True,
    )


def cleanup_plugin_artifacts():
    # SwiftBar may pick up compiled .pyc files under menubar/ as separate plugins.
    try:
        if os.path.isdir(PYCACHE_DIR):
            for name in os.listdir(PYCACHE_DIR):
                path = os.path.join(PYCACHE_DIR, name)
                try:
                    os.remove(path)
                except Exception:
                    pass
            try:
                os.rmdir(PYCACHE_DIR)
            except Exception:
                pass
    except Exception:
        pass


def maybe_notify(config, city_label, next_prayer, now):
    notifications = config.get("notifications", {})
    if not notifications.get("enabled", True):
        return

    offsets = notifications.get("offsets_minutes", [10, 5, 0])
    if not offsets:
        return

    remaining = (next_prayer[3] - now).total_seconds()
    if remaining < 0:
        return

    state = load_notify_state()
    prayer_time = next_prayer[3].strftime("%Y-%m-%dT%H:%M")
    for offset in sorted(set(offsets), reverse=True):
        trigger = offset * 60
        # Plugin refreshes every 30s; include a forward window for 0-minute alerts
        # so we don't miss exact prayer-time notifications between refresh ticks.
        if offset == 0:
            in_window = 0 <= remaining <= 30
        else:
            in_window = trigger - 30 <= remaining <= trigger

        if in_window:
            key = f"{city_label}:{next_prayer[0]}:{prayer_time}:{offset}"
            if key in state["notified"]:
                continue
            if offset == 0:
                text = f"{next_prayer[1]} / {next_prayer[2]} time in {city_label}"
            else:
                text = f"{next_prayer[1]} / {next_prayer[2]} in {offset} min ({city_label})"
            notify(text)
            state["notified"].add(key)
            save_notify_state(state)


def main():
    cleanup_plugin_artifacts()

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
        data, now, tzinfo, is_fresh, error_msg = fetch_timings(config, city)
        timings = data["data"]["timings"]
    except Exception as e:
        error_display = "🕌 ⚠" if str(e) == "API fetch failed" else "🕌 ✗"
        print(error_display)
        print("---")
        print(f"Prayer times error: {e}")
        print("---")
        print("Open config | terminal=false")
        return

    lang = config.get("language", "en")
    schedule = build_schedule(timings, now, tzinfo, lang)
    upcoming = [s for s in schedule if s[3] > now]
    if upcoming:
        next_p = upcoming[0]
    else:
        # Tomorrow's Fajr (close enough until next refresh)
        first = schedule[0]
        next_p = (first[0], first[1], first[2], first[3] + timedelta(days=1))

    countdown = fmt_countdown(next_p[3] - now)
    remaining_s = max(0, int((next_p[3] - now).total_seconds()))
    label = config["cities"][city]["label"]
    maybe_notify(config, label, next_p, now)
    
    # Calculate optimal refresh interval based on proximity to next prayer
    refresh_interval, refresh_mode = calculate_optimal_refresh_interval(remaining_s)
    
    flash_warning = config.get("flash_warning", {})
    flash_enabled = flash_warning.get("enabled", True)
    flash_minutes = flash_warning.get("minutes", 5)

    # Menu bar line — first line shown
    # Add warning indicator if using fallback cache
    fallback_indicator = " (cached)" if not is_fresh else ""
    if flash_enabled and 0 < remaining_s <= flash_minutes * 60:
        # Flash effect: color toggles every plugin refresh (30s).
        flash_on = (remaining_s // 30) % 2 == 0
        if flash_on:
            print(f"🕌 {next_p[1]} {countdown[:5]}{fallback_indicator} | color=#22c55e")
        else:
            print(f"🕌 {next_p[1]} {countdown[:5]}{fallback_indicator}")
    else:
        print(f"🕌 {next_p[1]} {countdown[:5]}{fallback_indicator}")

    # Dropdown
    print("---")
    if not is_fresh and error_msg:
        print(f"⚠ {error_msg} | color=#f59e0b")
        print("---")
    
    print(f"City: {label} | size=12")
    next_display = f"{next_p[1]} / {next_p[2]}"
    print(f"Next: {next_display} at {next_p[3].strftime('%H:%M')} | size=12")
    print("---")
    for key, local_name, ar, d in schedule:
        marker = "→" if key == next_p[0] and d.date() == next_p[3].date() else " "
        passed = d < now
        opacity = " color=#888888" if passed and not (key == next_p[0]) else ""
        print(f"{marker} {local_name} / {ar}  {d.strftime('%H:%M')} | font=Menlo size=13{opacity}")
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
    notify_enabled = config.get("notifications", {}).get("enabled", True)
    notify_marker = " ✓" if notify_enabled else ""
    print(
        f"--Toggle notifications{notify_marker} | bash='{py}' param1='{script}' param2=configure param3=toggle-notifications terminal=false refresh=true"
    )
    flash_marker = " ✓" if flash_enabled else ""
    print(
        f"--Toggle green flash{flash_marker} | bash='{py}' param1='{script}' param2=configure param3=toggle-flash-warning terminal=false refresh=true"
    )
    print(f"--Green flash window ({flash_minutes} min)")
    for option in (1, 3, 5, 10, 15):
        option_marker = " ✓" if flash_minutes == option else ""
        print(
            f"----{option} min{option_marker} | bash='{py}' param1='{script}' param2=configure param3=set-flash-minutes-{option} terminal=false refresh=true"
        )
    lang = config.get("language", "en")
    LANG_LABELS = {"en": "English", "tr": "Turkish"}
    print(f"--Language ({LANG_LABELS.get(lang, lang)})")
    for lang_key, lang_label in (("en", "English"), ("tr", "Turkish")):
        lang_marker = " ✓" if lang == lang_key else ""
        print(
            f"----{lang_label}{lang_marker} | bash='{py}' param1='{script}' param2=configure param3=set-language-{lang_key} terminal=false refresh=true"
        )
    print(
        f"--Reset to defaults | bash='{py}' param1='{script}' param2=configure param3=reset-defaults terminal=false refresh=true"
    )
    print(
        f"--Open config file | bash='{py}' param1='{script}' param2=configure param3=open-config terminal=false refresh=false"
    )
    print("---")
    print("Refresh | refresh=true")


if __name__ == "__main__":
    main()
