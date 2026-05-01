#!/usr/bin/env python3
import sys
sys.path.insert(0, sys.argv[1])
from rimworld import RimClient

r = RimClient()
try:
    colonists = r.colonists().get('colonists', [])
    print("Colonist Food Status:")
    all_fed = True
    for c in colonists:
        name = c.get("name", "?")
        food_need = c.get("foodNeed", 1.0)
        if food_need < 0.25:
            all_fed = False
            status = "STARVING!"
        elif food_need < 0.5:
            status = "Hungry"
        else:
            status = "Fed"
        print(f'{name}: {food_need:.2f} ({status})')
    
    if all_fed:
        print("All colonists are adequately fed!")
    else:
        print("WARNING: Some colonists are starving!")
        
except Exception as e:
    print(f"Error checking food: {e}")
finally:
    r.close()