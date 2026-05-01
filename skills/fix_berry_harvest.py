#!/usr/bin/env python3
"""Fix berry harvesting by preventing sowing/planting jobs."""
import sys, json
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

def main(save_path):
    r = RimClient()
    
    # Get colonists and map info
    colonists_data = r.colonists().get("colonists", [])
    map_info = r.map_info()
    cx, cz = map_info["size"]["x"] // 2, map_info["size"]["z"] // 2
    
    # Process colonists like bootstrap does
    for c in colonists_data:
        name = c.get("name", "")
        short = name.split("'")[1] if "'" in name else name.split()[-1]
        skills_list = c.get("skills", [])
        skills = {s["name"]: s["level"] for s in skills_list if isinstance(s, dict)}
        c["_short"] = short
        c["_skills"] = skills
    
    # Find best cook and best harvester
    best_cook = None
    best_cooking_skill = -1
    best_harvester = None
    best_plants_skill = -1
    
    for c in colonists_data:
        cooking_skill = c["_skills"].get("Cooking", 0)
        plants_skill = c["_skills"].get("Plants", 0)
        
        if cooking_skill > best_cooking_skill:
            best_cooking_skill = cooking_skill
            best_cook = c["_short"]
            
        if plants_skill > best_plants_skill:
            best_plants_skill = plants_skill
            best_harvester = c["_short"]
    
    # Set cooking priority to 1 for best cook
    if best_cook:
        try:
            r.set_priority(best_cook, "Cooking", 1)
            print(f"Set {best_cook} Cooking priority to 1")
        except Exception as e:
            print(f"FAILED set cooking priority: {e}")
    
    # Set Growing priority to 2 for best harvester (harvest berries but minimize sowing)
    if best_harvester:
        try:
            r.set_priority(best_harvester, "Growing", 2)
            print(f"Set {best_harvester} Growing priority to 2")
        except Exception as e:
            print(f"FAILED set growing priority: {e}")
    
    # Redesignate berry harvest to ensure it's active
    try:
        r.harvest(cx, cz, radius=50)
        print("Berry harvest re-designated")
    except Exception as e:
        print(f"FAILED re-designate harvest: {e}")
    
    # Ensure hunting is designated
    try:
        result = r.hunt_all_wildlife()
        print(f"Hunting designated: {result.get('designated', 0)} animals")
    except Exception as e:
        print(f"FAILED hunting designation: {e}")
    
    print("Berry harvest priorities fixed successfully")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: fix_berry_harvest.py <save_path>")
        sys.exit(1)
    main(sys.argv[1])