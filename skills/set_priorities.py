#!/usr/bin/env python3
"""Set work priorities for colonists."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
try:
    # Set Gabs to cooking priority (best cook, can't hunt due to disability)
    r.set_priority("Gabs", "Cooking", 1)
    
    # Set Benjamin to hunting priority (good shooting skills, can hunt)
    r.set_priority("Benjamin", "Hunting", 2)
    
    # Set Donut to plant cutting for berry harvesting
    r.set_priority("Donut", "PlantCutting", 1)
    
    print("Priorities set: Gabs=Cooking(1), Benjamin=Hunting(2), Donut=PlantCutting(1)")
except Exception as e:
    print(f"FAILED: {e}")
r.close()