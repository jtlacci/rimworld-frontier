# Construction

Construction is how colonies grow from crash sites to functional bases. Understanding build mechanics prevents wasted resources and blocked colonists.

## How Building Works

1. You place a **blueprint** with `build()` or `wall()` or `door()`
2. A colonist with Construction work priority hauls materials to the blueprint
3. The colonist constructs the building (time depends on material + skill)
4. Building appears and becomes functional

## Construction Skill

- Higher Construction skill = faster building + higher quality furniture
- Skill 0 = 0.3x speed, Skill 20 = 2.05x speed (30% + 8.75%/level)
- Low-skill constructors may fail and waste materials
- Assign your best constructor to Construction priority 1

## Build Order Strategy

1. **Critical infrastructure first**: campfire/stove, table + chairs, beds
2. **Walls and doors**: define rooms to get impressiveness bonuses
3. **Flooring**: room by room, after walls are complete
4. **Beauty items**: plant pots, sculptures, lamps — cosmetic, do last

**Don't flood colonists with 150+ blueprints at once.** Queue work in small chunks. Prioritize critical items before cosmetic ones.

## SDK Building Commands

| Command | Use |
|---------|-----|
| `build(blueprint, x, z, stuff=, rotation=)` | Single building |
| `bulk_build(ops)` | Multiple buildings in one request |
| `wall(x, z, stuff='BlocksGranite')` | Place wall |
| `door(x, z, stuff='BlocksGranite')` | Place door |
| `floor(floor_def, x1, z1, x2=, z2=)` | Place flooring region |
| `cancel_build(x, z)` | Cancel blueprint |
| `deconstruct(x, z)` | Designate deconstruction |

## High-Level Building Helpers

| Helper | Description |
|--------|-------------|
| `build_room(x1, z1, x2, z2, stuff=, doors=, floor=)` | Rectangular room with walls, doors, floor |
| `build_room_grid(origin_x, origin_z, cols, rows, ...)` | Grid of rooms sharing walls |
| `build_room_adjacent(existing_bounds, direction, ...)` | Room sharing existing wall |
| `build_hallway(x1, z1, x2, z2, ...)` | 3-wide hallway |
| `build_barracks(cx, cz, material=)` | 7x5 barracks with furniture |
| `build_storage_room(cx, cz, material=)` | 7x5 storage room |
| `check_buildable(cells, stuff=)` | Pre-flight check |
| `cost_check(blueprint, stuff=, count=1)` | Affordability check |
| `verify_room(x1, z1, x2, z2)` | Post-build room audit |
| `wait_for_construction(x1, z1, x2, z2, timeout=120)` | Wait for completion |

## Construction Rules

- **Collision detection**: `build_room`/`build_room_grid` raise `RimError` on ANY collision
- **Never stack blueprints**: don't place on top of each other (except conduits under walls)
- **BUILDING_GAP = 2**: enforced around new standalone buildings. Use `gap=0` for adjacent rooms
- **Share walls**: adjacent rooms MUST share walls (see colony-layout.md)
- **Interaction spots**: build command rejects placement on interaction cells of existing buildings
- **Conduits**: can go under walls and buildings (isConduit bypass)

## Material Cost Check

Always verify you can afford construction before placing blueprints:
```python
cost = r.cost_check("Wall", stuff="BlocksGranite", count=20)
# Returns material requirements and whether you can afford it
```

## Repair

Damaged buildings can be repaired by colonists with Construction priority. Repair is automatic — colonists will repair damaged buildings in the home area without explicit commands.
