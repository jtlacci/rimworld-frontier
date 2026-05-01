# Terrain and Movement

Terrain determines movement speed, buildability, and fertility. Understanding terrain is critical for base placement.

## Natural Terrain

| Terrain | Move Speed | Fertility | Beauty | Heavy Build? | Notes |
|---------|-----------|-----------|--------|-------------|-------|
| Soil | 87% | 100% | 0 | Yes | Standard farmable ground |
| Rich Soil | 87% | 140% | 0 | Yes | +40% crop growth speed |
| Stony Soil | 87% | 70% | 0 | Yes | Reduced fertility |
| Marshy Soil | 48% | 100% | 0 | Light only | No heavy structures |
| Sand | 76% | 10% | 0 | Yes | Nearly infertile |
| Soft Sand | 48% | 0% | 0 | Light only | No farming, slow |
| Mud | 48% | 0% | 0 | None | Cannot build anything |
| Marsh | 30% | 0% | 0 | Bridge only | Bridge required |
| Ice | 48% | 0% | 0 | Yes | Buildable but infertile |
| Gravel | 87% | 70% | 0 | Yes | Same as stony soil |
| Rough Stone | 87% | 0% | -1 | Yes | Smoothable for free |
| Smooth Stone | 100% | 0% | +2 | Yes | Best free floor |

Movement speed formula: `13 / (13 + pathCost)`

## Water Terrain

| Terrain | Move Speed | Passable | Bridge? |
|---------|-----------|----------|---------|
| Shallow Water | 30% | Yes | Yes |
| Shallow Moving Water | 30% | Yes | Yes |
| Chest-deep Moving Water | 24% | Yes | Yes |
| Deep Water | 0% | **No** | No |
| Deep Ocean Water | 0% | **No** | No |

## Constructed Floors

All constructed floors: **100% move speed**, 0% fertility, support heavy structures.

| Floor | Beauty | Cleanliness | Cost | Work | Special |
|-------|--------|------------|------|------|---------|
| Wood Floor | 0 | 0 | 3 wood | 85 | 22% flammable |
| Flagstone | 0 | 0 | 4 stone blocks | 500 | Cheapest non-flammable stone floor |
| Stone Tile | +2 | 0 | 4 stone blocks | 1,100 | Best value beauty |
| Carpet | +2 | 0 | 7 cloth | 800 | 32% flammable, 200% clean time |
| Fine Carpet | +4 | 0 | 35 cloth | 4,000 | 32% flammable |
| Steel Tile | 0 | +0.2 | 7 steel | 800 | Hospital viable |
| Sterile Tile | -1 | +0.6 | 3 steel + 12 silver | 1,600 | Best for hospital/kitchen |
| Smooth Stone | +2 | 0 | FREE (labor only) | varies | Best early-game floor |

**Key insights**:
- Smooth stone is free materials, +2 beauty — always smooth mountain floors first
- Sterile tile (+0.6 cleanliness) mandatory for hospitals and kitchens
- Stone tile (+2 beauty) is the best cost-effective beauty floor
- Carpet: +2 beauty but 200% clean time and fire risk — avoid in critical rooms

## Bridges

| Property | Value |
|----------|-------|
| Cost | 6 wood |
| HP | 100 |
| Move speed | 100% |
| Supports | **Light structures only** (no stone walls) |
| Flammability | 80% |

Essential in swamp biomes. Cannot place stone walls on bridges — use wood.

## Mountain Mechanics

### Terrain Elevation (world map)

| Type | Mountains | Minerals | Infestation Risk |
|------|-----------|----------|-----------------|
| Flat | None | Fewest | None |
| Small Hills | Some | Moderate | Low |
| Large Hills | Significant | Many | Moderate |
| Mountainous | Dominant | Most | High |

### Mineable Resources

| Resource | Vein Size | Rarity |
|----------|----------|--------|
| Steel | 20-40 tiles | Common |
| Components | 3-6 tiles | Common |
| Silver | 4-12 tiles | Uncommon |
| Plasteel | 10-50 tiles | Uncommon |
| Gold | 1-6 tiles | Rare |
| Jade | 1-6 tiles | Rare |
| Uranium | 1-6 tiles | Very Rare |

### Mountain Base Pros
- Overhead mountain blocks mortars and drop pods
- Natural temperature regulation
- Free stone walls and smooth stone floors (+2 beauty)
- Abundant mining resources
- Natural defensive chokepoints

### Mountain Base Cons
- **Infestation risk** (spawns under overhead mountain)
- Limited farmland (need hydroponics)
- Slower expansion (mining takes time)
- Overhead mountain collapse = 99,999 damage (instant death)

## Roof Types

| Property | Constructed | Thin Rock | Overhead Mountain |
|----------|-----------|-----------|------------------|
| Removable | Yes | Yes | **No** |
| Blocks mortars | No | No | **Yes** |
| Blocks drop pods | No | No | **Yes** |
| Collapse damage | 15-30 | 15-30 | **99,999 (instant death)** |
| Infestation risk | No | No | **Yes** |

Roofs extend up to **6 tiles** from any wall or column. Buildings up to 12 tiles wide can be fully roofed without columns.

## Infestation Prevention

1. **Don't build under overhead mountain** (100% prevention)
2. Freeze overhead areas to below -17C (100% prevention)
3. Keep overhead areas well-lit (reduces spawn preference)
4. Create a designated "bait room" far from base (redirects spawns)
5. Fill gaps between mountain sections with walls
