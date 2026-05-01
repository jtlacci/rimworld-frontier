#!/usr/bin/env python3
"""Unpause game and run until target day, with periodic health checks.

Usage:
  python3 run_and_monitor.py SDK_PATH                  # run 60s
  python3 run_and_monitor.py SDK_PATH 120              # run 120s
  python3 run_and_monitor.py SDK_PATH --until-day 4    # run until game day 4
"""
import sys, time
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()

# Parse args
target_day = None
duration = 60
i = 2
while i < len(sys.argv):
    if sys.argv[i] == "--until-day":
        target_day = int(sys.argv[i+1]); i += 2
    else:
        duration = int(sys.argv[i]); i += 1

try:
    r.unpause()
    if target_day:
        # Run in 30s chunks, checking game day between each
        total = 0
        while True:
            result = r.monitored_sleep(30, check_interval=5)
            total += 30
            w = r.weather()
            day = w.get("dayOfYear", 0)
            hour = w.get("hour", 0)
            print(f"Day {day} H{hour:.1f} ({total}s elapsed)")
            if day >= target_day:
                print(f"Reached target day {target_day}")
                break
            if total > 600:
                print(f"Safety limit: 600s elapsed, day={day}")
                break
    else:
        result = r.monitored_sleep(duration, check_interval=5)
        print(f"Monitored sleep {duration}s done: {result}")
except Exception as e:
    print(f"FAILED: {e}")

try:
    r.add_cooking_bills(retry=True)
    print("Cooking bills refreshed")
except Exception as e:
    print(f"Bills: {e}")

w = r.weather()
print(f"Final: Day {w.get('dayOfYear',0)} H{w.get('hour',0):.1f}")
r.pause()
r.close()
