#!/usr/bin/env python3
"""
Smart refresh interval calculation for battery optimization.
Dynamically adjusts refresh frequency based on proximity to next prayer.
"""

from datetime import timedelta


def calculate_optimal_refresh_interval(seconds_until_next_prayer):
    """
    Calculate optimal refresh interval in seconds based on time until next prayer.
    
    Strategy:
    - Idle period (> 2 hours): 300s (5 min) — minimal battery drain
    - Approaching (10 min - 2 hours): 60s (1 min) — reasonable accuracy
    - Imminent (< 10 min): 5s (very accurate) — per-second countdown accuracy
    
    Args:
        seconds_until_next_prayer: Time in seconds until next prayer
        
    Returns:
        Tuple of (refresh_interval_seconds, description)
    """
    if seconds_until_next_prayer < 0:
        # Past prayer, use default
        return (300, "idle")
    
    if seconds_until_next_prayer < 600:  # < 10 min
        return (5, "imminent")
    elif seconds_until_next_prayer < 7200:  # < 2 hours
        return (60, "approaching")
    else:  # >= 2 hours
        return (300, "idle")


def get_refresh_hint_comment(interval_seconds):
    """
    Get a SwiftBar refresh hint comment for the given interval.
    Used to tell SwiftBar when to next call the plugin.
    
    SwiftBar reads the first line for format directives.
    # <swiftbar.refreshInterval>60</swiftbar.refreshInterval>
    """
    return f"# <swiftbar.refreshInterval>{int(interval_seconds)}</swiftbar.refreshInterval>"


if __name__ == "__main__":
    # Test refresh calculations
    test_cases = [
        0,      # At prayer time
        30,     # 30 seconds away
        300,    # 5 minutes away
        600,    # 10 minutes away (boundary)
        1800,   # 30 minutes away
        3600,   # 1 hour away
        7200,   # 2 hours away (boundary)
        10800,  # 3 hours away
        86400,  # 24 hours away
    ]
    
    print("Refresh Interval Calculations:")
    print("=" * 60)
    for seconds in test_cases:
        interval, desc = calculate_optimal_refresh_interval(seconds)
        hours = seconds / 3600
        print(f"{hours:6.2f}h away → {interval:3}s interval ({desc})")
    
    print("\nSwiftBar hint examples:")
    print(get_refresh_hint_comment(5))
    print(get_refresh_hint_comment(60))
    print(get_refresh_hint_comment(300))
