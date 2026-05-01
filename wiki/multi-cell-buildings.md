# Multi-Cell Buildings

Some buildings occupy more than one tile. You must account for their full footprint when planning layouts. Never place furniture or hoppers on tiles occupied by the building itself.

## Building Footprints

| Building | Size | Notes |
|----------|------|-------|
| NutrientPasteDispenser | 3x4 | Anchor + 2 east, + 3 south (rotation 0). Input side = north. Output = 1 tile south of south face. |
| Hopper | 1x1 | Must be adjacent to NPD input side. Fill with raw food. |
| Table2x2c | 2x2 | Place chairs on all 4 sides for max seating. |
| Table2x4c | 2x4 | 8 interaction spots around perimeter. |
| Table3x3c | 3x3 | Largest table, 12 interaction spots. |
| Bed | 1x2 | Head at wall, foot toward door. End tables at head. |
| DoubleBed | 2x2 | For couples. Same head/foot convention. |
| SolarGenerator | 4x4 | Large footprint, needs open sky (no roof). |
| WindTurbine | 5x2 | Plus 7-tile exclusion zone on each wind side (no buildings/trees). |
| ElectricStove | 3x1 | Interaction spot at front. |
| FueledStove | 3x1 | Interaction spot at front. |
| SimpleResearchBench | 1x3 | Interaction spot at front. |

## Nutrient Paste Dispenser (NPD)

The NPD is one of the trickiest buildings to place correctly:

- **Size**: 3 wide x 4 deep at rotation 0
- **Input side** (north at rotation 0): place 2+ hoppers here, adjacent to the input face
- **Output side** (south at rotation 0): colonists collect paste from interaction spot 1 tile south of south face
- **Hoppers go ADJACENT to the dispenser, not on top of it**
- **Place hoppers on the input side (opposite the interaction spot)**
- Requires power (conduit connection to grid)
- Produces paste on-demand — no spoilage, no cook needed, no food poisoning
- -4 mood debuff ("ate nutrient paste") but completely reliable

## Verification After Placement

Always verify multi-cell buildings after placing them:

```python
# Check actual footprint
items = r.scan_items(x-2, z-2, x+5, z+5, kind="building")
for item in items:
    if item.get("def") == "NutrientPasteDispenser":
        print(f"NPD at ({item['x']},{item['z']})")
```

## Power Buildings

- **Solar generator** (4x4): needs unroofed area (no roof above). ~1700W during daylight.
- **Wind turbine** (5x2 + exclusion): 7-tile clear zone on wind sides. ~3460W max but variable.
- **Battery**: 1x2. MUST be indoors under roof — unroofed battery + rain = Zzztt short circuit + fire.
- **Conduit**: can be placed through walls (isConduit bypass). Goes under other buildings.
- **Watermill**: 5x6, must be on river. Constant 1100W.
