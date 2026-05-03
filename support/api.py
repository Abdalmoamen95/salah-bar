#!/usr/bin/env python3
"""
Resilient API module for Prayer Times widget.
Handles network requests with retries, exponential backoff, and fallback caching.
Provides transparent error recovery and health status reporting.
"""

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config import CACHE_DIR, logger


class CacheEntry:
    """Single prayer times cache entry for a city/date."""

    def __init__(self, path):
        self.path = path
        self.data = None
        self.loaded_at = None
        self.is_stale = False

    def load(self):
        """Load cached data from disk."""
        try:
            if os.path.exists(self.path) and os.path.getsize(self.path) >= 100:
                with open(self.path) as f:
                    self.data = json.load(f)
                self.loaded_at = datetime.now()
                self.is_stale = False
                return True
        except Exception as e:
            logger.warning(f"Failed to load cache {self.path}: {e}")
        return False

    def save(self, data):
        """Save data to cache."""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(data, f)
            self.data = data
            self.loaded_at = datetime.now()
            self.is_stale = False
            logger.debug(f"Cache saved: {self.path}")
        except Exception as e:
            logger.error(f"Failed to save cache {self.path}: {e}")

    def mark_stale(self):
        """Mark cache as stale (loaded from old date or fallback)."""
        self.is_stale = True

    def age_hours(self):
        """Return age of cache in hours since load."""
        if self.loaded_at is None:
            return None
        return (datetime.now() - self.loaded_at).total_seconds() / 3600


class APIClient:
    """Resilient prayer times API client with retries and fallback caching."""

    API_BASE = "https://api.aladhan.com/v1/timings"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 0.5  # seconds
    MAX_BACKOFF = 10  # seconds

    def __init__(self):
        self.last_error = None
        self.cache_hit = False
        self.is_fallback = False

    def _exponential_backoff(self, attempt):
        """Calculate backoff time: 0.5s, 1s, 2s, ... capped at MAX_BACKOFF."""
        backoff = self.INITIAL_BACKOFF * (2 ** attempt)
        return min(backoff, self.MAX_BACKOFF)

    def _fetch_live(self, url, timeout=10):
        """Fetch prayer times from live API with retries."""
        for attempt in range(self.MAX_RETRIES):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    data = response.read()
                    logger.debug(f"API fetch succeeded on attempt {attempt + 1}")
                    return json.loads(data)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                self.last_error = str(e)
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self._exponential_backoff(attempt)
                    logger.warning(f"API attempt {attempt + 1}/{self.MAX_RETRIES} failed: {e}. Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"API fetch failed after {self.MAX_RETRIES} retries: {e}")
        return None

    def _get_cache_path(self, city, date_str):
        """Get cache file path for city/date."""
        return os.path.join(CACHE_DIR, f"{city}_{date_str}.json")

    def _find_fallback_cache(self, city):
        """Find the most recent cache for a city (even if older than today)."""
        try:
            pattern = f"{city}_"
            candidates = []
            for name in os.listdir(CACHE_DIR):
                if name.startswith(pattern) and name.endswith(".json"):
                    candidates.append(os.path.join(CACHE_DIR, name))
            if candidates:
                latest = max(candidates, key=os.path.getmtime)
                logger.info(f"Using fallback cache: {latest}")
                with open(latest) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to find fallback cache for {city}: {e}")
        return None

    def prefetch_week_ahead(self, config, city, tz_info):
        """
        Prefetch prayer times for the next 7 days.
        Runs silently in the background; errors don't break the main flow.
        """
        try:
            city_config = config["cities"][city]
            lat = city_config["lat"]
            lon = city_config["lon"]
            now = datetime.now(tz_info)
            
            for days_ahead in range(1, 8):
                future_date = now + timedelta(days=days_ahead)
                date_str = future_date.strftime("%d-%m-%Y")
                cache_path = self._get_cache_path(city, date_str)
                
                # Skip if cache already exists
                if os.path.exists(cache_path) and os.path.getsize(cache_path) >= 100:
                    continue
                
                url = (
                    f"{self.API_BASE}/{date_str}"
                    f"?latitude={lat}&longitude={lon}&method={config['method']}&school={config['school']}"
                )
                data = self._fetch_live(url, timeout=5)
                if data:
                    cache = CacheEntry(cache_path)
                    cache.save(data)
                    logger.debug(f"Prefetched {city} for {date_str}")
                else:
                    logger.warning(f"Failed to prefetch {city} for {date_str}")
                    break  # Stop prefetching if one fails
        except Exception as e:
            logger.warning(f"Prefetch failed for {city}: {e}")

    def fetch_timings(self, config, city, tz_info):
        """
        Fetch prayer times for city.
        Returns: (data, is_fresh, error_msg) tuple.
        - data: parsed prayer times or None
        - is_fresh: True if from live API, False if fallback cache
        - error_msg: None if success, error string if fallback used
        """
        self.cache_hit = False
        self.is_fallback = False
        self.last_error = None

        city_config = config["cities"][city]
        lat = city_config["lat"]
        lon = city_config["lon"]
        now = datetime.now(tz_info)
        date_str = now.strftime("%d-%m-%Y")

        # Try today's cache first
        cache_path = self._get_cache_path(city, date_str)
        cache = CacheEntry(cache_path)
        if cache.load():
            self.cache_hit = True
            logger.debug(f"Cache hit for {city} on {date_str}")
            # Prefetch future dates if we got a fresh cache
            if not hasattr(self, '_prefetch_triggered'):
                try:
                    self.prefetch_week_ahead(config, city, tz_info)
                    self._prefetch_triggered = True
                except Exception:
                    pass
            return cache.data, True, None

        # Try live API
        url = (
            f"{self.API_BASE}/{date_str}"
            f"?latitude={lat}&longitude={lon}&method={config['method']}&school={config['school']}"
        )
        data = self._fetch_live(url)
        if data:
            cache.save(data)
            # Trigger week-ahead prefetch in background
            try:
                self.prefetch_week_ahead(config, city, tz_info)
            except Exception:
                pass
            return data, True, None

        # Fallback to any recent cache
        fallback_data = self._find_fallback_cache(city)
        if fallback_data:
            self.is_fallback = True
            error_msg = f"Using cached times (API unavailable)"
            logger.warning(error_msg)
            return fallback_data, False, error_msg

        # Complete failure
        error_msg = f"API error: {self.last_error} (no cache available)"
        logger.error(error_msg)
        return None, False, error_msg


if __name__ == "__main__":
    # Test the API client
    from config import load_config
    client = APIClient()
    config = load_config()
    city = config["default_city"]
    tz_info = ZoneInfo(config["cities"][city]["tz"])
    
    data, is_fresh, error = client.fetch_timings(config, city, tz_info)
    print(f"Fresh: {is_fresh}, Error: {error}")
    if data:
        print(f"✓ Got prayer times for {city}")
    else:
        print(f"✗ Failed to get prayer times")
