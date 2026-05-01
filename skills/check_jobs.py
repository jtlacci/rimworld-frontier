#!/usr/bin/env python3
import sys
sys.path.insert(0, sys.argv[1])
from rimworld import RimClient

r = RimClient()
try:
    colonists = r.colonists().get('colonists', [])
    for c in colonists:
        name = c.get("name", "?")
        job = c.get("job", "no job")
        print(f'{name}: {job}')
except Exception as e:
    print(f"Error: {e}")
finally:
    r.close()