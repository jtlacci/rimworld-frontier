# SDK: Building Helpers

High-level methods that wrap multiple build calls with collision detection, shared walls, and validation.

## Room Building

### `build_room(x1, z1, x2, z2, stuff=, doors=, floor=)`
Build a rectangular room with walls on all edges, optional doors and flooring.

```python
r.build_room(120, 134, 128, 140,
             stuff="BlocksGranite",
             doors=[(124, 134)],
             floor="TileSandstone")
```

- **Collision detection**: raises `RimError` on ANY collision with existing buildings
- Coordinates are outer wall corners (interior is x1+1 to x2-1, z1+1 to z2-1)
- Doors replace wall segments at specified positions
- Floor is placed inside the walls only

### `build_room_grid(origin_x, origin_z, cols, rows, room_w, room_h, ...)`
Build a grid of rooms sharing walls. Adjacent rooms share wall segments — no double-thick walls.

```python
r.build_room_grid(120, 130, cols=3, rows=2,
                  room_w=5, room_h=5,
                  stuff="BlocksGranite",
                  floor="TileSandstone")
```

- `room_w` / `room_h` = interior dimensions (walls are added around)
- Shared walls: a 3×2 grid uses fewer materials than 6 separate rooms
- Each room gets a door on the south face by default

### `build_room_adjacent(existing_bounds, direction, ...)`
Build a new room sharing an existing wall.

```python
# Build room east of an existing room at bounds (120,130,128,138)
r.build_room_adjacent(
    existing_bounds=(120, 130, 128, 138),
    direction="east",
    room_w=5, room_h=5,
    stuff="BlocksGranite"
)
```

- Reuses the shared wall — no double-wall waste
- `direction`: "north", "south", "east", "west"

### `build_hallway(x1, z1, x2, z2, ...)`
Build a 3-wide corridor connecting two points.

```python
r.build_hallway(120, 138, 140, 138,
                stuff="BlocksGranite",
                floor="TileSandstone")
```

## Pre-Flight Validation

### `check_buildable(cells, stuff=)`
Check if cells are buildable before placing blueprints.

```python
result = r.check_buildable(
    [(120, 135), (121, 135), (122, 135)],
    stuff="BlocksGranite"
)
# Returns: {buildable: True/False, blocked: [(x,z,reason)]}
```

### `cost_check(blueprint, stuff=, count=1)`
Check if you can afford to build something.

```python
cost = r.cost_check("Wall", stuff="BlocksGranite", count=20)
# Returns: {affordable: True/False, needed: {BlocksGranite: 100}, have: {BlocksGranite: 150}}
```

### `verify_room(x1, z1, x2, z2)`
Post-build audit — verify a room is properly enclosed, has a door, correct role, etc.

```python
result = r.verify_room(120, 134, 128, 140)
# Returns: {enclosed: True, role: "Bedroom", impressiveness: 42, issues: []}
```

## Construction Waiting

### `wait_for_construction(x1, z1, x2, z2, timeout=120)`
Block until all blueprints in region are built, or timeout.

```python
r.wait_for_construction(120, 134, 128, 140, timeout=120)
```

- Polls every few seconds
- Raises `RimError` on timeout
- Useful before placing furniture that depends on walls being up

### `build_with_budget(plan, budget=)`
Build as many items from a plan as resources allow.

```python
built, skipped = r.build_with_budget(
    [("Wall", 120, 135, {"stuff": "BlocksGranite"}),
     ("Wall", 121, 135, {"stuff": "BlocksGranite"}),
     ...],
    budget={"BlocksGranite": 50}
)
```

## Colony Setup Helpers

These wrap multiple low-level calls into complete setup operations.

### `day1_setup()`
**The most important helper.** Complete Day 1 initialization:
- Detect food-scarce scenarios (low meals + low wildlife)
- Dismiss naming dialog
- Enable manual priorities
- Assign roles (hunter, cook, researcher) based on skills
- Check for disabled work types and ascetic traits
- Set hunting/harvesting/chopping designations
- Set research project
- Configure cook schedule

Returns: `{center_x, center_z, hunter, cook, researcher, resources, food_scarce, ...}`

### `setup_cooking(cx, cz)`
Place campfire + butcher spot + stove near center. Aggressively retries adding bills.

Returns: `{campfire: (x,z), butcher: (x,z), stove: (x,z)}`

### `setup_dining(cx, cz)`
Place table + chairs. Skipped in food-scarce mode (saves 115+ wood).

### `add_cooking_bills(retry=False, max_retries=8, retry_delay=8)`
Idempotent bill management — adds butcher + cook bills to campfire/stove. Waits for construction if buildings are still blueprints.

### `setup_zones(cx, cz)`
Create main storage, food stockpile, chunk dump, and grow zone.

Returns: `{main: (x,z), food: (x,z), dump: (x,z), grow: (x,z)}`

### `secure_food_stockpile(bx, bz, bx2, bz2)`
Create a Critical-priority food stockpile inside a room. Handles zone cell conflicts by deleting and recreating zones.

### `build_barracks(cx, cz, material="Steel")`
Build a complete 7×6 barracks: walls, door, 3 beds, end tables, dressers, sculpture, flooring.
- Food-scarce mode: uses Steel/concrete to preserve wood for fuel
- Normal mode: uses specified material

Returns: `{x1, z1, x2, z2, built, failed}`

### `build_storage_room(cx, cz, material="WoodLog")`
Build 7×5 storage room with interior stockpile and flooring.

### `setup_recreation(cx, cz)`
Place a horseshoes pin near center.

### `setup_production(cx, cz, bx, bz, sx=, sz=)`
Place research bench + tailoring bench.

## Monitoring

### `colony_health_check()`
Structured diagnostic — checks food supply, shelter, wood reserves, mood, game time. Creates food stockpile if missing, triggers emergency chops if wood is critical.

Returns: `{food, shelter, wood, mood, game_day, alerts}`

### `monitored_sleep(duration, check_interval=5)`
Sleep with periodic health checks. Runs `colony_health_check()` every `check_interval` seconds during the sleep. Emergency chops if wood hits zero.

## Construction Rules

- **BUILDING_GAP = 2**: enforced around standalone buildings. Use `gap=0` for adjacent rooms.
- **Collision detection**: `build_room`/`build_room_grid` raise `RimError` on ANY collision.
- **Share walls**: adjacent rooms MUST share walls (no double-thick between rooms).
- **Interaction spots**: build command rejects placement on interaction cells of existing buildings.
- **Conduits**: can go under walls and buildings (isConduit bypass).
- **Never stack blueprints**: don't place on top of each other (except conduits under walls).
