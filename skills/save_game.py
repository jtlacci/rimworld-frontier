#!/usr/bin/env python3
"""Pause, save, and close."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
name = sys.argv[2] if len(sys.argv) > 2 else "Autosave"
try:
    r.pause()
    r.save(name=name)
    print(f"Saved as '{name}'")
except Exception as e:
    print(f"FAILED: {e}")
r.close()
