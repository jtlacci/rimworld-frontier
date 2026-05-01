#!/usr/bin/env python3
import sys
import time
sys.path.insert(0, sys.argv[1])
from rimworld import RimClient

def main():
    sdk_path = sys.argv[1]
    target_day = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
    with RimClient() as r:
        # Check current berry count
        resources = r.get_resources()
        raw_berries = resources.get("RawBerries", 0)
        print(f"Current RawBerries: {raw_berries}")
        
        # If we have enough berries, we can proceed
        if raw_berries >= 180:
            print("Berry harvesting complete! Ready for next phase.")
            return
        
        # Otherwise, ensure Growing priority is set for berry harvesting
        colonists = r.get_colonists()
        for colonist in colonists:
            name = colonist["name"]
            if name == "Benjamin":  # Our best harvester
                r.set_priority(name, "Growing", 1)
                print(f"Set Benjamin Growing priority to 1 for berry harvesting")
            elif name == "Gabs":  # Keep cooking priority
                r.set_priority(name, "Cooking", 1)
                print(f"Set Gabs Cooking priority to 1")
        
        # Also ensure no grow zones exist that would compete with harvesting
        # This is handled by not creating any grow zones in our strategy

if __name__ == "__main__":
    main()