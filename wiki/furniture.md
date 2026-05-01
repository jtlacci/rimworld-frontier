# Furniture

Furniture provides comfort, beauty, and functional bonuses. Placement matters — interaction spots and adjacency bonuses affect usability.

## Common Furniture Stats

| Item | defName | Size | Beauty | Comfort | Has Interaction Spot |
|------|---------|------|--------|---------|---------------------|
| Bed | Bed | 1x2 | 1 | 0.68 | Yes (foot) |
| Double Bed | DoubleBed | 2x2 | 2 | 0.68 | Yes (foot) |
| End Table | EndTable | 1x1 | 3 | — | No |
| Dresser | Dresser | 2x1 | 5 | — | No |
| Dining Chair | DiningChair | 1x1 | 8 | 0.7 | No |
| Armchair | Armchair | 1x1 | 4 | 0.8 | No |
| Stool | Stool | 1x1 | 0 | 0.5 | No |
| Table (1x2) | Table1x2c | 1x2 | 0.5 | — | No |
| Table (2x2) | Table2x2c | 2x2 | 1 | — | No |
| Table (2x4) | Table2x4c | 2x4 | 2 | — | No |
| Table (3x3) | Table3x3c | 3x3 | 3 | — | No |
| Plant Pot | PlantPot | 1x1 | varies | — | No |
| Standing Lamp | StandingLamp | 1x1 | 0 | — | No |
| Campfire | Campfire | 1x1 | 0 | — | Yes |
| Simple Research Bench | SimpleResearchBench | 1x3 | 0 | — | Yes (front) |
| Butcher Spot | ButcherSpot | 1x1 | 0 | — | Yes |
| Electric Stove | ElectricStove | 3x1 | 0 | — | Yes (front) |
| Fueled Stove | FueledStove | 3x1 | 0 | — | Yes (front) |

## Bedroom Furniture Bonuses

- **End table adjacent to bed head**: +0.05 rest effectiveness while sleeping
- **Dresser adjacent to bed head**: bedroom impressiveness bonus
- Both are essential for bedroom impressiveness — always place them

## Interaction Spots

Every building with an interaction spot requires that spot to be walkable and unblocked. The C# build command rejects placement that would block existing interaction spots or place new buildings whose interaction spots are blocked by impassable buildings.

- **Beds**: interaction spot at foot — keep foot of bed clear
- **Stoves**: interaction spot at front — don't place furniture in front
- **Research bench**: interaction spot at front — need clear access
- **Tables**: interaction spots around perimeter — place chairs here

## Table Seating

| Table | Size | Max Seats |
|-------|------|-----------|
| Table1x2c | 1x2 | 6 |
| Table2x2c | 2x2 | 8 |
| Table2x4c | 2x4 | 12 |
| Table3x3c | 3x3 | 12 |

Place dining chairs on all accessible sides for maximum seating.

## Quality Matters

Crafted furniture has quality levels (awful to legendary). Higher quality = more beauty and comfort. Quality is determined by the crafter's skill level. Marble and gold materials multiply the beauty further.
