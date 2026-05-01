# Colony Layout Design

Good colony layout minimizes travel time, prevents fires from spreading, and maximizes room impressiveness.

## Corridor-First Design

The best colony layout uses corridors as the primary pathways:

- **Rooms are dead-ends off corridors** — doors face corridors, never other rooms
- **No through-traffic** — colonists path through corridors only
- **Room adjacency**: neighboring rooms share SOLID walls (no doors between rooms)
- **Only the corridor-facing wall gets a door**

## Corridor Sizing

- **Main spines**: 2 tiles wide (interior) for high-traffic routes
- **Minor branches**: 1 tile wide for low-traffic areas
- Build corridors with `build_hallway()` helper

## Wall Sharing

Adjacent rooms MUST share walls — never double-wall. When building a room next to an existing one:
- Use the existing wall as a shared boundary
- Only build walls that don't already exist
- `build_room_adjacent()` handles this automatically

## Building Gap

- `BUILDING_GAP = 2` is enforced around new standalone buildings
- Use `gap=0` when intentionally adjoining rooms
- This prevents accidental collision with existing structures

## Recommended Layout Zones

### Central Area
- Dining room + kitchen (colonists eat frequently, minimize travel)
- Storage room adjacent to kitchen and workshops

### Bedroom Wing
- Row of bedrooms off a corridor
- Each 5x5 interior, sharing walls
- Away from noisy workshops

### Production Wing
- Kitchen, workshop, lab along a corridor
- Input stockpiles nearby for materials
- Kitchen should be adjacent to food storage

### Perimeter
- Grow zones outside the base
- Dump zone for chunks/slag (away from base)
- Kill box / defense positions at natural chokepoints

## Temperature Considerations

- **Freezer**: double-walled for insulation, cooler venting outside
- **Cooler placement**: deconstruct wall segment first, then place cooler blueprint. Cooler needs conduit.
- **One cooler per ~16 tiles** of freezer space (rough guide)
- **Batteries**: always indoors under a roof (rain = explosion)

## Construction Order

1. **Walls first** — define the room boundaries
2. **Doors** — make rooms enclosed
3. **Critical furniture** — beds, stoves, research bench
4. **Floors** — room by room, after structure is done
5. **Beauty items** — plant pots, sculptures, lamps last

Don't flood colonists with 150+ blueprints at once. Prioritize critical structures, then add cosmetic items after.
