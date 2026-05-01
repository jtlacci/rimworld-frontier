#!/usr/bin/env python3
"""Set Growing priority for berry harvesting."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
try:
    colonists = r.colonists().get("colonists", [])
    
    # Find colonists who can do growing work
    for c in colonists:
        name = c.get("name", "")
        short = name.split("'")[1] if "'" in name else name.split()[-1]
        disabled = c.get("disabledWork", "")
        
        # Skip if Growing is disabled
        if "Growing" in disabled:
            continue
            
        # Set Growing priority to 2 for all available colonists
        # This ensures berries get harvested
        try:
            r.set_priority(short, "Growing", 2)
            print(f"Set Growing=2 for {short}")
        except Exception as e:
            print(f"FAILED to set Growing for {short}: {e}")
            
except Exception as e:
    print(f"FAILED: {e}")
r.close()