#!/usr/bin/env python3
"""Check food status and inventory."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
try:
    # Get all items/things in the world
    things = r.things()
    
    # Count food items
    meals = 0
    raw_food = 0
    
    for thing in things:
        if hasattr(thing, 'defName'):
            if thing.defName == 'MealSimple':
                meals += 1
            elif thing.defName in ['RawPotatoes', 'RawBerries', 'Meat_Hare']:
                raw_food += 1
    
    print(f"Food inventory:")
    print(f"  Simple meals: {meals}")
    print(f"  Raw food: {raw_food}")
    
    # Check if cooking is still active
    bills = r.bills()
    cooking_bills = [b for b in bills if 'Cook' in str(b)]
    print(f"Cooking bills active: {len(cooking_bills)}")
    
except Exception as e:
    print(f"FAILED: {e}")
r.close()