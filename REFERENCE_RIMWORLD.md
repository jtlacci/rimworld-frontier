# RimWorld TCP Bridge SDK Notes

## Storytelling Approach
- Read pawn backstories, traits, passions, incapabilities — build characters with motivations and arcs
- Name and narrate the colony's development: from crash site to settlement to home
- Colony layout tells a story: room assignments reflect personality, shared spaces reflect relationships
- Goals emerge from the characters: a researcher's ambition, a builder's pride, a grower's patience
- Track turning points: first raid, first death, first luxury, harsh winters survived
- Visual evolution matters: early dirt-floor shelters → floored rooms → decorated spaces → coherent base aesthetic

## Connection
- TCP port 9900, JSON line-delimited, BOM-stripped
- `RimClient(host, port, timeout)` — persistent connection, context manager
- Auto-incrementing IDs, raises `RimError` on game errors

## C# Mod Location
- Source: `Source/` (under repo root)
- Build: `cd Source && dotnet build -c Release`
- Deploy to 3 locations:
  - `~/Library/Application Support/Steam/steamapps/common/RimWorld/RimWorldMac.app/Mods/CarolineConsole/Assemblies/`
  - `~/Library/Application Support/Steam/steamapps/common/RimWorld/Mods/CarolineConsole/Assemblies/`
  - `~/Library/Application Support/RimWorld/Mods/CarolineConsole/Assemblies/`
- Requires game restart after DLL changes

## Key DefNames (case-insensitive lookup)
- Walls/Doors: `Wall`, `Door`
- Tables: `Table2x2c`, `Table1x2c`, `Table2x4c`, `Table3x3c`
- Chairs: `DiningChair`
- Bedroom: `Bed`, `EndTable`, `Dresser`
- Joy: `HorseshoesPin`
- Work: `SimpleResearchBench`, `ButcherSpot`, `Campfire`
- Floors: `WoodPlankFloor` (TerrainDef, uses `set_floor` command)
- Stuff: `WoodLog`, `BlocksGranite`, `BlocksSandstone`, `Steel`
- Plants: `Plant_Rice`, `Plant_Potato`, `Plant_Corn`, `Plant_Strawberry`

## SDK Patterns
- `send_batch` / `send_batch_lenient` for bulk operations (walls, floors)
- `_send_cached` with TTL (2s) for read helpers — auto-invalidated on writes
- `_get_occupancy()` uses `buildings()` + `zones()` (compact) NOT `read_map_tiles`
- `read_map_tiles` capped at 50x50 server-side, use `scan()` for auto-paging
- `scan_items(kind=)` filters server-side by kind (item, building, plant, etc.)

## Building Rules (learned from user feedback)
- **Collision detection**: `build_room` / `build_room_grid` raise `RimError` on ANY collision — never skip cells
- **Never stack blueprints**: don't place blueprints on top of each other (except conduits which can go under walls/buildings)
- **BUILDING_GAP = 2**: enforced around new standalone buildings. Use `gap=0` when intentionally adjoining
- **Share walls**: adjacent rooms MUST share walls, not double-wall. Only build walls that don't already exist. If adding a room next to an existing one, use the existing wall as a shared boundary
- **Hallways**: use `build_hallway()` for corridors between separate buildings
- **Queue work in small chunks**: don't flood colonists with 150+ blueprints. Prioritize critical items (cooking, furniture) before cosmetic (floors). Do floors room-by-room after critical stuff is built
- **Soil validation**: `grow_zone()` checks terrain fertility, rejects >50% ungrowable
- **NPD hoppers**: go ADJACENT to the dispenser, not on top of it. Place on the input side (opposite the interaction spot)
- **Interaction spots**: C# Build command now rejects placement on interaction cells of existing buildings AND checks that the new building's own interaction spot isn't blocked by impassable buildings

## Multi-Cell Building Footprints

These buildings occupy more than one tile. **Always verify placement with `r.scan_items()` after building. Never place furniture/hoppers on tiles occupied by the building itself.**

| Building | Size | Notes |
|----------|------|-------|
| NutrientPasteDispenser | 3×4 | Anchor + 2 east, + 3 south (at rotation 0). Input side is north (place hoppers there). Output/interaction is 1 tile south of the south face. Requires 2+ hoppers adjacent to input side. |
| Hopper | 1×1 | Must be adjacent to NPD input side. Fill with raw food (rice, meat, berries). |
| Table2x2c | 2×2 | Place chairs on all 4 sides for max seating. |
| Table2x4c | 2×4 | 8 interaction spots around the perimeter. |
| Table3x3c | 3×3 | Largest table, 12 interaction spots. |
| Bed | 1×2 | Head at wall, foot toward door. End tables go adjacent to head. |
| DoubleBed | 2×2 | For couples. Same head/foot convention. |
| SolarGenerator | 4×4 | Large footprint, needs open sky (no roof). |
| WindTurbine | 2×2 | Plus 5-tile exclusion zone on each side (no buildings/trees). |

**Verification after placement:**
```python
# After building a multi-cell structure, verify its actual footprint
items = r.scan_items(x-2, z-2, x+5, z+5, kind="building")
for item in items:
    if item.get("def") == "NutrientPasteDispenser":
        print(f"NPD at ({item['x']},{item['z']}), size may extend east+south")
```
- **No duplicate floors**: `set_floor` skips cells that already have the requested terrain — don't place same floor on itself

## RimWorld Room Design & Feng Shui
- **Never mix purposes**: sleeping + working/eating/storage = debuffs
- **Room impressiveness** drives mood buffs: size + beauty + wealth + cleanliness
- **Beauty matters**: place plant pots, sculptures, and quality furniture. Chunks/corpses/filth tank beauty
- **Symmetry and flow**: center tables in dining rooms, beds against walls with matching nightstands, clear walkways to doors
- **Corridor-first layout**: rooms are dead-ends off corridors. Doors face corridors, never other rooms. No through-traffic. Colonists path through corridors only.
- **Room adjacency**: neighboring rooms share SOLID walls (no doors). Only the corridor-facing wall gets a door.
- **Corridor sizing**: 2 tiles wide (interior) for main spines, 1 tile for minor branches

### Room Templates
- **Bedroom (5x5 interior)**: bed centered on back wall, end table on each side of bed head, dresser opposite foot, plant pot or lamp in corner. Floor the whole room. Torch or lamp for light.
- **Dining/Rec (7x7+ interior)**: table centered, chairs on all sides, joy items (horseshoes, chess) along walls away from the eating area. Floor with wood planks.
- **Kitchen**: stove + butcher spot, separate from dining. Keep CLEAN — filth on food gives food poisoning. Small room, easy to clean.
- **Lab**: research bench only, sterile tile floor (after research). No stockpiles. Small + clean = high impressiveness.
- **Workshop**: workbenches along walls, clear center for hauling paths. Can be larger/uglier — colonists don't care as much.
- **Hospital**: beds + medicine stockpile, sterile floors, vitals monitor when available. Cleanliness directly affects infection rates.

### Storage Design
- **Food spoilage planning**: raw crops last ~40 days (store freely), meals ~4 days (cook small batches), meat ~2 days (butcher+cook immediately, never stockpile raw). Use bill limits (e.g., "until 10") not "do forever". NPD produces on-demand with no spoilage — ideal baseline food before refrigeration.
- **Refrigerated food storage** (when available): dedicated room with cooler(s), double-walled for insulation. Target -1°C to 0°C. Meals, raw meat, and medicine here.
- **General storage**: separate room for non-perishables (wood, steel, components, textiles). Priority: Important.
- **Chunk dump**: outdoor low-priority stockpile away from base. Accept only chunks/slag. Colonists auto-haul.
- **Workshop input**: small critical stockpile next to workbenches for ingredients (e.g., steel near smithy). Priority: Preferred.
- **Stockpile filters**: use `set_stockpile_filter` to control what goes where. Don't let food rot in unrefrigerated general storage.
- **Zoning discipline**: every item type should have exactly one valid destination. Prevents hauling loops and lost items.

## Priority System
- Must call `set_manual_priorities(True)` after game start — defaults to Simple mode where all priorities = 3
- Priority 1 = highest, 4 = lowest, 0 = disabled, -1 = incapable
- Differentiate: don't set everything to 1

## Common Pitfalls
- Research gets unset on game reload — always verify and re-set
- Forbidden items at game start — call `unforbid_all()` early
- Campfire is both a building AND a workbench — won't show in `bills()` until fully constructed
- `build()` uses `y` param for z-coordinate (legacy naming in C# handler)
- Multi-cell buildings (Table2x2c, NPD) report position at their anchor cell — verify actual placement location
- Conduits can be placed through walls (isConduit bypass in Build command)
- Floor placement uses `set_floor` command with `x1,z1,x2,z2` region
- Stockpile in lab = ugly room + cluttered. Keep stockpiles in dedicated storage
- **Cooler placement**: Build command rejects coolers on walls (impassable check). Deconstruct the wall first, wait for colonist to remove it, THEN place the cooler blueprint. Cooler needs conduit connection to power grid.
- **Freezer sizing**: one cooler can't freeze a huge storage room. Build a small dedicated freezer (4x4 interior) with double walls for insulation, or partition a corner of storage.
- **Batteries explode in rain**: always place batteries indoors under a roof. Unroofed battery + rain = Zzztt short circuit + fire.
- **Dialogs block game time**: research complete popups, quest dialogs, etc. freeze the game clock. Always check `read_dialogs` and dismiss with `choose_option` when monitoring.
- **Naming dialog**: `Dialog_NamePlayerFactionAndSettlement` appears at game start and blocks time. Close with `r.close_dialog("Dialog_NamePlayerFactionAndSettlement", factionName="Name", settlementName="Name")`. Always check for and dismiss this in session startup.
- **ImmediateWindows regenerate**: calling `close_dialog()` without a type may close an ImmediateWindow that respawns. Use `close_dialog(dialog_type="...")` to target specific dialogs.
- **"idle" is momentary**: colonists briefly show idle between jobs. Check a few seconds later before assuming they're stuck.
- **Colonist job response format**: `colonists()` returns `{'colonists': [...]}`, not a flat list. Same for `buildings()` → `{'buildings': [...], 'rooms': [...]}`.
- **Room data fields**: each room in `buildings().rooms` includes: `role`, `cellCount`, `roofed`, `temperature`, `impressiveness`, `beauty`, `cleanliness`, `contents` (list of furniture defNames inside), `flooredPct` (0-100), `bounds`.

## Notification Types
- **Letters** (bottom right): events, quests, deaths. `read_letters` / `dismiss_letter`
- **Messages** (top center): ephemeral popups like "food rotted", "construction failed". `read_messages`
- **Alerts** (right side): persistent warnings like "need warm clothes". `read_alerts`
- **Dialogs**: modal popups that block game time. `read_dialogs` / `choose_option` / `close_dialog`

## Colony State
- Fresh game — no colony data yet
