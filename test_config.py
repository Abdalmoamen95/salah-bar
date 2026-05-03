#!/usr/bin/env python3
"""
Test suite for Prayer Times widget configuration and API resilience.
Run with: python3 test_config.py
"""

import json
import os
import sys
import tempfile
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

# Add support directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "support"))

from config import (
    DEFAULT_CONFIG, normalize_config, validate_config_schema,
    load_config, save_config
)
from api import APIClient


class TestConfig:
    """Test config loading and validation."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.temp_dir = None

    def setup(self):
        """Create temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown(self):
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_default_config_valid(self):
        """Test that DEFAULT_CONFIG is valid."""
        valid, errors = validate_config_schema(DEFAULT_CONFIG)
        if valid:
            self.passed += 1
            print("✓ DEFAULT_CONFIG is valid")
        else:
            self.failed += 1
            print(f"✗ DEFAULT_CONFIG is invalid: {errors}")

    def test_normalize_empty_config(self):
        """Test that normalizing empty config returns defaults."""
        result = normalize_config({})
        valid, errors = validate_config_schema(result)
        if valid and result["default_city"] == "izmir":
            self.passed += 1
            print("✓ normalize_config({}) returns valid defaults")
        else:
            self.failed += 1
            print(f"✗ normalize_config(empty dict) failed: {errors}")

    def test_normalize_partial_config(self):
        """Test normalizing config with partial overrides."""
        raw = {
            "method": 5,
            "language": "tr",
            "cities": {
                "istanbul": {
                    "label": "Istanbul",
                    "lat": 41.0082,
                    "lon": 28.9784,
                    "tz": "Europe/Istanbul"
                }
            }
        }
        result = normalize_config(raw)
        valid, errors = validate_config_schema(result)
        
        checks = (
            valid and
            result["method"] == 5 and
            result["language"] == "tr" and
            "istanbul" in result["cities"]
        )
        if checks:
            self.passed += 1
            print("✓ normalize_config() correctly merges overrides")
        else:
            self.failed += 1
            print(f"✗ normalize_config() merge failed: {errors}")

    def test_invalid_config_detection(self):
        """Test that validate_config_schema detects invalid configs."""
        invalid_configs = [
            None,
            "not a dict",
            {},  # missing cities
            {"cities": {}, "default_city": "x"},  # no cities, missing required keys
        ]
        
        all_caught = True
        for invalid in invalid_configs:
            valid, _ = validate_config_schema(invalid)
            if valid:
                all_caught = False
                break
        
        if all_caught:
            self.passed += 1
            print("✓ validate_config_schema() detects invalid configs")
        else:
            self.failed += 1
            print("✗ validate_config_schema() failed to detect invalid config")

    def test_config_city_override(self):
        """Test that cities can be overridden."""
        raw = {
            "cities": {
                "custom": {
                    "label": "Custom City",
                    "lat": 0,
                    "lon": 0,
                    "tz": "UTC"
                }
            },
            "default_city": "custom"
        }
        result = normalize_config(raw)
        if "custom" in result["cities"] and result["default_city"] == "custom":
            self.passed += 1
            print("✓ Custom cities are preserved in config")
        else:
            self.failed += 1
            print("✗ Custom cities override failed")

    def run(self):
        """Run all tests."""
        self.setup()
        try:
            print("\n=== Config Tests ===\n")
            self.test_default_config_valid()
            self.test_normalize_empty_config()
            self.test_normalize_partial_config()
            self.test_invalid_config_detection()
            self.test_config_city_override()
        finally:
            self.teardown()

        print(f"\nPassed: {self.passed}, Failed: {self.failed}")
        return self.failed == 0


class TestAPI:
    """Test API resilience and caching."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.temp_dir = None

    def setup(self):
        """Create temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        # Mock CACHE_DIR for testing
        self.original_cache_dir = os.environ.get("CACHE_DIR")
        os.environ["CACHE_DIR"] = os.path.join(self.temp_dir, "cache")
        os.makedirs(os.environ["CACHE_DIR"], exist_ok=True)

    def teardown(self):
        """Clean up."""
        if self.original_cache_dir:
            os.environ["CACHE_DIR"] = self.original_cache_dir
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_api_client_init(self):
        """Test APIClient initialization."""
        client = APIClient()
        if hasattr(client, 'last_error') and hasattr(client, 'cache_hit'):
            self.passed += 1
            print("✓ APIClient initializes correctly")
        else:
            self.failed += 1
            print("✗ APIClient initialization failed")

    def test_backoff_calculation(self):
        """Test exponential backoff calculation."""
        client = APIClient()
        backoffs = [client._exponential_backoff(i) for i in range(10)]
        
        # Should increase exponentially then cap at MAX_BACKOFF (10)
        increases = all(backoffs[i] <= backoffs[i+1] for i in range(9))
        # At some point should reach MAX_BACKOFF
        reaches_cap = any(b >= client.MAX_BACKOFF for b in backoffs)
        capped_stable = backoffs[-1] == client.MAX_BACKOFF
        
        if increases and reaches_cap and capped_stable:
            self.passed += 1
            print("✓ Exponential backoff calculation works")
        else:
            self.failed += 1
            print(f"✗ Backoff calculation failed: {backoffs}")

    def run(self):
        """Run all tests."""
        self.setup()
        try:
            print("\n=== API Tests ===\n")
            self.test_api_client_init()
            self.test_backoff_calculation()
        finally:
            self.teardown()

        print(f"\nPassed: {self.passed}, Failed: {self.failed}")
        return self.failed == 0


class TestRefresh:
    """Test smart refresh interval calculation."""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test_refresh_idle_interval(self):
        """Test idle period (>2 hours) returns 300s refresh."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "support"))
        from refresh import calculate_optimal_refresh_interval
        
        # 3 hours away
        interval, mode = calculate_optimal_refresh_interval(3 * 3600)
        if interval == 300 and mode == "idle":
            self.passed += 1
            print("✓ Idle period (>2h) returns 300s refresh")
        else:
            self.failed += 1
            print(f"✗ Idle refresh failed: {interval}s, mode={mode}")

    def test_refresh_approaching_interval(self):
        """Test approaching period (10min-2h) returns 60s refresh."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "support"))
        from refresh import calculate_optimal_refresh_interval
        
        # 30 minutes away
        interval, mode = calculate_optimal_refresh_interval(30 * 60)
        if interval == 60 and mode == "approaching":
            self.passed += 1
            print("✓ Approaching period (10m-2h) returns 60s refresh")
        else:
            self.failed += 1
            print(f"✗ Approaching refresh failed: {interval}s, mode={mode}")

    def test_refresh_imminent_interval(self):
        """Test imminent period (<10min) returns 5s refresh."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "support"))
        from refresh import calculate_optimal_refresh_interval
        
        # 5 minutes away
        interval, mode = calculate_optimal_refresh_interval(5 * 60)
        if interval == 5 and mode == "imminent":
            self.passed += 1
            print("✓ Imminent period (<10m) returns 5s refresh")
        else:
            self.failed += 1
            print(f"✗ Imminent refresh failed: {interval}s, mode={mode}")

    def run(self):
        """Run all tests."""
        print("\n=== Refresh Tests ===\n")
        self.test_refresh_idle_interval()
        self.test_refresh_approaching_interval()
        self.test_refresh_imminent_interval()

        print(f"\nPassed: {self.passed}, Failed: {self.failed}")
        return self.failed == 0


def main():
    """Run all test suites."""
    print("Prayer Times Widget Test Suite")
    print("=" * 40)

    config_tests = TestConfig()
    config_ok = config_tests.run()

    api_tests = TestAPI()
    api_ok = api_tests.run()

    refresh_tests = TestRefresh()
    refresh_ok = refresh_tests.run()

    print("\n" + "=" * 40)
    total_passed = config_tests.passed + api_tests.passed + refresh_tests.passed
    total_failed = config_tests.failed + api_tests.failed + refresh_tests.failed
    print(f"Total: {total_passed} passed, {total_failed} failed")

    if total_failed > 0:
        sys.exit(1)
    else:
        print("✓ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
