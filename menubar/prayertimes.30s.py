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
import hashlib
import urllib.parse
import urllib.request
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
ADHAN_SOUND_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "sounds", "adhan-jazzi.mp3")
REMOTE_SOUNDS_DIR = os.path.join(CACHE_DIR, "remote-sounds")

PRAYERS = [
    ("Fajr",    "الفجر"),
    ("Dhuhr",   "الظهر"),
    ("Asr",     "العصر"),
    ("Maghrib", "المغرب"),
    ("Isha",    "العشاء"),
]
PRAYER_KEYS = [p[0] for p in PRAYERS]


def is_remote_source(path_or_url):
    return isinstance(path_or_url, str) and path_or_url.startswith(("http://", "https://"))


def _cache_filename_for_url(url, prefix="adhan"):
    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in (".mp3", ".m4a", ".wav", ".aiff", ".aac"):
        ext = ".mp3"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}{ext}"


def resolve_audio_source(path_or_url, prefix="adhan"):
    """Return a local playable file path; download remote URLs to cache if needed."""
    if not path_or_url:
        return ""

    expanded = os.path.expanduser(path_or_url)
    if not is_remote_source(expanded):
        return expanded

    os.makedirs(REMOTE_SOUNDS_DIR, exist_ok=True)
    cached = os.path.join(REMOTE_SOUNDS_DIR, _cache_filename_for_url(expanded, prefix=prefix))
    if os.path.isfile(cached) and os.path.getsize(cached) > 0:
        return cached

    urllib.request.urlretrieve(expanded, cached)
    return cached


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


def play_adhan(config, prayer_key=""):
    """Play adhan sound file in the background if enabled and file exists.
    Uses fajr_adhan_file for Fajr prayer if configured, otherwise adhan_file.
    """
    notifications = config.get("notifications", {})
    if not notifications.get("adhan_enabled", True):
        return

    # Fajr gets its own sound if set
    is_fajr = prayer_key.lower() in ("fajr", "sabah")
    if is_fajr and notifications.get("fajr_adhan_file"):
        sound_path = notifications["fajr_adhan_file"]
    else:
        sound_path = notifications.get("adhan_file") or ADHAN_SOUND_FILE

    try:
        sound_path = resolve_audio_source(sound_path, prefix="fajr" if is_fajr else "adhan")
    except Exception as e:
        logger.warning(f"Failed to resolve adhan source: {e}")
        return

    sound_path = os.path.expanduser(sound_path)
    if not os.path.isfile(sound_path):
        logger.warning(f"Adhan sound file not found: {sound_path}")
        return
    try:
        subprocess.Popen(
            ["afplay", sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning(f"Failed to play adhan: {e}")


def notify(text, play_sound=False, config=None, prayer_key=""):
    safe_text = text.replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{safe_text}" with title "salah-bar" subtitle "Prayer Reminder"'],
        check=False,
        capture_output=True,
        text=True,
    )
    if play_sound and config is not None:
        play_adhan(config, prayer_key=prayer_key)


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
                notify(text, play_sound=True, config=config, prayer_key=next_prayer[0])
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
    display_cfg = config.get("display", {})
    display_size = display_cfg.get("size", "Normal")
    display_theme = display_cfg.get("theme", "Dark")
    display_seconds = display_cfg.get("show_seconds", True)
    seconds_status = "ON ✓" if display_seconds else "OFF"
    print(f"--Display settings  [{display_size} · {display_theme} · sec {seconds_status.split()[0]}]")
    print(
        f"----Open display dialog | bash='{py}' param1='{script}' param2=configure param3=choose-display-settings terminal=false refresh=true"
    )
    print(f"----Widget size ({display_size})")
    for opt in ("Compact", "Normal", "Large"):
        marker = " ✓" if display_size == opt else ""
        action = f"set-display-size-{opt.lower()}"
        print(
            f"------{opt}{marker} | bash='{py}' param1='{script}' param2=configure param3={action} terminal=false refresh=true"
        )
    print(f"----Theme ({display_theme})")
    for opt in ("Light", "Dark"):
        marker = " ✓" if display_theme == opt else ""
        action = f"set-display-theme-{opt.lower()}"
        print(
            f"------{opt}{marker} | bash='{py}' param1='{script}' param2=configure param3={action} terminal=false refresh=true"
        )
    print(
        f"----Show seconds ({seconds_status}) | bash='{py}' param1='{script}' param2=configure param3=toggle-display-seconds terminal=false refresh=true"
    )
    notify_enabled = config.get("notifications", {}).get("enabled", True)
    notify_marker = " ✓" if notify_enabled else ""
    print(
        f"--Toggle notifications{notify_marker} | bash='{py}' param1='{script}' param2=configure param3=toggle-notifications terminal=false refresh=true"
    )
    adhan_enabled = config.get("notifications", {}).get("adhan_enabled", True)
    adhan_file = config.get("notifications", {}).get("adhan_file", "")
    if is_remote_source(adhan_file):
        adhan_name = "remote track"
    else:
        adhan_name = os.path.basename(adhan_file) if adhan_file else "adhan-jazzi.mp3"
    adhan_marker = " ✓" if adhan_enabled else " (silent)"
    fajr_file = config.get("notifications", {}).get("fajr_adhan_file", "")
    if is_remote_source(fajr_file):
        fajr_name = "remote track"
    else:
        fajr_name = os.path.basename(fajr_file) if fajr_file else "same as others"
    print(f"--Adhan sound{adhan_marker}  [{adhan_name}]")
    print(
        f"----Toggle on/off | bash='{py}' param1='{script}' param2=configure param3=toggle-adhan terminal=false refresh=true"
    )
    print(
        f"----Change sound... | bash='{py}' param1='{script}' param2=configure param3=choose-adhan-sound terminal=false refresh=true"
    )
    print(f"--Fajr adhan  [{fajr_name}]")
    print(
        f"----Change Fajr sound... | bash='{py}' param1='{script}' param2=configure param3=choose-fajr-adhan terminal=false refresh=true"
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
