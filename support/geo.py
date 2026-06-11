#!/usr/bin/env python3
"""
IP-based geolocation for the 'auto' city.
Returns lat/lon/timezone/label, cached on disk so we don't hit a free
API on every plugin tick. Used to drive prayer-time calculation for
wherever the user currently is.
"""

import json
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from zoneinfo import available_timezones

from config import CACHE_DIR, logger

GEO_CACHE_FILE = os.path.join(CACHE_DIR, "geo_location.json")
GEO_CACHE_TTL = 6 * 3600  # 6 hours — long enough to avoid hammering free APIs, short enough to follow travel


def _parse_ipapi_co(d):
    if not d.get("latitude") or not d.get("timezone"):
        return None
    label_parts = [p for p in (d.get("city"), d.get("country_code")) if p]
    return {
        "lat": float(d["latitude"]),
        "lon": float(d["longitude"]),
        "tz": d["timezone"],
        "label": ", ".join(label_parts) or "Auto",
    }


def _parse_ip_api_com(d):
    if d.get("status") != "success":
        return None
    label_parts = [p for p in (d.get("city"), d.get("countryCode")) if p]
    return {
        "lat": float(d["lat"]),
        "lon": float(d["lon"]),
        "tz": d["timezone"],
        "label": ", ".join(label_parts) or "Auto",
    }


PROVIDERS = [
    ("https://ipapi.co/json/", _parse_ipapi_co),
    ("http://ip-api.com/json/?fields=status,lat,lon,timezone,city,countryCode", _parse_ip_api_com),
]


def _load_cached(ignore_ttl=False):
    try:
        with open(GEO_CACHE_FILE) as f:
            entry = json.load(f)
        if ignore_ttl or (time.time() - entry.get("ts", 0) < GEO_CACHE_TTL):
            return entry["data"]
    except Exception:
        pass
    return None


def _save_cached(data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(GEO_CACHE_FILE, "w") as f:
            json.dump({"ts": time.time(), "data": data}, f)
    except Exception as e:
        logger.warning(f"Failed to cache geo: {e}")


def get_cached_location():
    """Fast, non-blocking: return cached location regardless of TTL, or None."""
    return _load_cached(ignore_ttl=True)


def _detect_corelocation():
    """Use CoreLocationCLI (Wi-Fi-based, accurate). Returns dict or None.

    Requires `brew install corelocationcli` and macOS Location Services permission.
    """
    cli = shutil.which("CoreLocationCLI")
    if not cli:
        return None
    try:
        result = subprocess.run(
            [cli, "-once", "-format", "%latitude\t%longitude\t%timezone\t%locality\t%country"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0 or not result.stdout.strip():
            logger.debug(f"CoreLocationCLI failed: {result.stderr.strip()}")
            return None
        parts = result.stdout.strip().split("\t")
        if len(parts) < 2:
            return None
        lat = float(parts[0])
        lon = float(parts[1])
        tz = parts[2] if len(parts) > 2 and parts[2] else None
        locality = parts[3] if len(parts) > 3 else ""
        country = parts[4] if len(parts) > 4 else ""
        if not tz:
            tz = _system_timezone()
        if tz not in available_timezones():
            return None
        label_parts = [p for p in (locality, country) if p]
        return {
            "lat": lat,
            "lon": lon,
            "tz": tz,
            "label": ", ".join(label_parts) or "Auto",
        }
    except Exception as e:
        logger.debug(f"CoreLocationCLI error: {e}")
        return None


def _system_timezone():
    try:
        result = subprocess.run(
            ["systemsetup", "-gettimezone"], capture_output=True, text=True, timeout=5
        )
        if "Time Zone:" in result.stdout:
            return result.stdout.split("Time Zone:")[1].strip()
    except Exception:
        pass
    return None


def detect_ip_location(force_refresh=False):
    """Return {lat, lon, tz, label} for the user's location, or None.

    Tries CoreLocationCLI first (Wi-Fi-based, accurate), then falls back to
    IP-based lookup. Hits the network unless a fresh cache entry exists.
    Use get_cached_location() on hot paths where you don't want to risk a
    network call.
    """
    if not force_refresh:
        cached = _load_cached()
        if cached:
            return cached

    cl = _detect_corelocation()
    if cl:
        _save_cached(cl)
        logger.info(f"CoreLocation: {cl['label']} ({cl['tz']})")
        return cl

    valid_tzs = available_timezones()
    for url, parse in PROVIDERS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "salah-bar/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.load(resp)
            result = parse(data)
            if result and result["tz"] in valid_tzs:
                _save_cached(result)
                logger.info(f"IP location: {result['label']} ({result['tz']})")
                return result
        except Exception as e:
            logger.debug(f"Geo provider {url} failed: {e}")

    stale = _load_cached(ignore_ttl=True)
    if stale:
        logger.warning("All geo providers failed; using stale cache")
        return stale
    return None


def clear_cache():
    try:
        os.remove(GEO_CACHE_FILE)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    import sys
    force = "--refresh" in sys.argv
    loc = detect_ip_location(force_refresh=force)
    if loc:
        print(json.dumps(loc, indent=2, ensure_ascii=False))
    else:
        print("Could not detect location", file=sys.stderr)
        sys.exit(1)
