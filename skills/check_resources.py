#!/usr/bin/env python3
"""Check resource inventory."""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "sdk")
from rimworld import RimClient

r = RimClient()
try:
    # Get all items/things in the world
    things = r.things()
    
    # Count resources
    wood = 0
    steel = 0
    components = 0
    raw_berries = 0
    
    for thing in things:
        if hasattr(thing, 'defName'):
            if thing.defName == 'WoodLog':
                wood += 1
            elif thing.defName == 'Steel':
                steel += 1
            elif thing.defName == 'ComponentIndustrial':
                components += 1
            elif thing.defName == 'RawBerries':
                raw_berries += 1
    
    print(f"Resources:")
    print(f"  WoodLog: {wood}")
    print(f"  Steel: {steel}")
    print(f"  ComponentIndustrial: {components}")
    print(f"  RawBerries: {raw_berries}")
    
    # Count berry bushes
    plants = [t for t in things if hasattr(t, 'defName') and t.defName == 'Plant_Berry']
    print(f"  Berry bushes: {len(plants)}")
    
except Exception as e:
    print(f"FAILED: {e}")
r.close()