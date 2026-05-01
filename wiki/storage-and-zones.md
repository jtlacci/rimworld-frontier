# Storage and Zones

Proper zone management prevents hauling loops, item loss, and food spoilage.

## Zone Types

### Stockpile
General storage zone. Configure with filters to control what goes where.

- `stockpile(x1, z1, x2, z2, priority=)` — create stockpile
- `set_stockpile_filter(x, z, allow=, disallow=)` — control allowed items

### Grow Zone
Farming area. Must be on soil with fertility > 0 (includes soil, rich soil, stony soil/gravel).

- `grow_zone(x1, z1, x2, z2, plant=, check_soil=True)` — create grow zone
- `set_plant(zone=, plant=)` — change crop type
- Checks terrain fertility, rejects if >50% ungrowable

## Stockpile Priority Levels

| Priority | Use Case |
|----------|----------|
| Low | Chunk dump, overflow storage |
| Normal | General storage |
| Important | Main storage room |
| Preferred | Workshop input stockpiles |
| Critical | Emergency supplies, medicine |

Higher priority stockpiles are filled first. Colonists will haul items from lower to higher priority zones.

## Recommended Storage Layout

### Food Storage (pre-refrigeration)
- Indoor stockpile for raw crops (varies: rice ~40d, potatoes ~30d, berries ~14d)
- Cook meat immediately — NEVER stockpile raw meat unrefrigerated
- Use bill limits ("until 10") to prevent meal overproduction

### Food Storage (post-refrigeration)
- Dedicated freezer room: 4x4+ interior, double walls, cooler(s)
- Target -1C to 0C
- Store meals and raw meat (medicine doesn't spoil — no need to refrigerate)
- Priority: Important or Preferred

### General Storage
- Separate room for non-perishables: wood, steel, components, textiles
- Priority: Important
- Keep OUT of bedrooms and labs (ruins impressiveness)

### Chunk Dump
- Outdoor, low-priority stockpile away from base
- Accept only stone chunks and slag
- Colonists auto-haul when idle

### Workshop Input
- Small critical stockpile next to workbenches
- Only accept ingredients needed (e.g., steel near smithy)
- Priority: Preferred (higher than general storage)

## Zoning Discipline

**Every item type should have exactly one valid destination.** This prevents:
- Hauling loops (item bouncing between two stockpiles)
- Lost items (no valid stockpile = item stays on ground)
- Food rotting (wrong food in unrefrigerated zone)

Use `set_stockpile_filter` to ensure no overlap between stockpiles for the same item categories.
