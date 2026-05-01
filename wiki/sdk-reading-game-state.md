# SDK: Reading Game State

All read methods are cached (2s TTL). Write commands auto-invalidate relevant caches.

## Colony State

| Method | Returns | Key Fields |
|--------|---------|------------|
| `ping()` | Server status | `status`, `gameState`, `colonistCount`, `speed` |
| `colonists()` | All colonists | `{colonists: [{name, mood, currentJob, position, health, skills, traits, disabledWork}]}` |
| `pawns()` | All pawns on map | Colonists + visitors + prisoners |
| `animals()` | Wild + tamed animals | `{animals: [{name, def, position, tame, health}]}` |
| `resources()` | Resource counts | `{WoodLog: N, Steel: N, MealSimple: N, ...}` |
| `colony_stats()` | Colony metrics | Wealth, beauty, impressiveness, room breakdown |

### Colonist Detail

| Method | Signature | Returns |
|--------|-----------|---------|
| `needs(pawn)` | `needs("Gabs")` | Single pawn's need levels (food, rest, joy, comfort, beauty) |
| `colonist_needs()` | `colonist_needs()` | All colonists' needs in one call |
| `thoughts(pawn)` | `thoughts("Gabs")` | `{thoughts: [{label, mood, daysLeft}]}` — current mood modifiers |
| `inventory(pawn)` | `inventory("Gabs")` | Items carried by pawn |

## Map & Environment

| Method | Returns | Notes |
|--------|---------|-------|
| `map_info()` | Map size, biome, avg fertility, season, hour | Cached |
| `weather()` | Temperature, condition, season, day, hour | Cached |
| `terrain(x1, z1, x2, z2)` | `{(x,z): {terrain, fertility, isWater, isRock}}` | Max 50x50 per call |
| `roof(x1, z1, x2, z2)` | `{(x,z): {roof}}` | Roof types: None, Constructed, ThinRock, OverheadMountain |
| `beauty(x1, z1, x2, z2)` | Beauty values per cell | Max 50x50 |
| `interaction_spots(x1, z1, x2, z2)` | Interaction cells for buildings in region | Useful for placement validation |

## Plants

| Method | Signature | Returns |
|--------|-----------|---------|
| `plants(filter=)` | `plants(filter="Plant_Berry")` | `{plants: [{def, position, growth, harvestable, yieldDef, yieldCount}], count: N}` |

Returns harvestable plants on the map. Filter by comma-separated defNames. Without filter, returns all plants that have a harvest yield.

## Food Consumption Log

| Method | Signature | Returns |
|--------|-----------|---------|
| `food_log()` | `food_log()` | `{events: [{tick, hour, pawn, food, nutrition, foodNeedBefore}], count: N}` |

Ring buffer of last 50 food consumption events. Always active (no `set_event_log` needed). Tracks what each colonist ate, nutrition value, and their food need level before eating.

## Buildings & Zones

| Method | Returns | Key Fields |
|--------|---------|------------|
| `buildings()` | Buildings + rooms | `{buildings: [{def, position, stuff, quality}], rooms: [{role, cellCount, impressiveness, beauty, cleanliness, contents, flooredPct, bounds}]}` |
| `zones()` | All zones | `{zones: [{type, cells, bounds, plant (grow), priority (stockpile)}]}` |
| `bills()` | Workbench bills | `{workbenches: [{def, position, bills: [{recipe, suspended, count}]}]}` |
| `costs(blueprint, stuff=)` | Build costs | Material requirements + work amount |

## Research & Production

| Method | Returns | Key Fields |
|--------|---------|------------|
| `research()` | Research state | `{current, progress, completed: [...], available: [...]}` |
| `work_priorities()` | Priority assignments | Per-colonist work type priorities |

## Notifications & UI

| Method | Returns | Cached |
|--------|---------|--------|
| `alerts()` | Active game alerts (NeedColonistBeds, etc.) | Yes |
| `messages()` | Ephemeral top-of-screen messages | **No** (always fresh) |
| `threats()` | Hostile pawns, active fires | Yes |
| `letters()` | Pending letter stack | **No** |
| `dialogs()` | Open dialog windows (blocking!) | **No** |
| `visitors()` | Visitors, traders, incoming caravans | Yes |

## Survey & Exploration

### ASCII Maps (visual overview)

| Method | Shows |
|--------|-------|
| `survey_composite_ascii(x1=, z1=, x2=, z2=, scale=)` | Combined terrain + roof + things |
| `survey_terrain_ascii(...)` | Terrain types only |
| `survey_things_ascii(...)` | Items and buildings |
| `survey_beauty_ascii(...)` | Beauty heatmap |
| `survey_temperature_ascii(...)` | Temperature map |
| `survey_blueprint_ascii(...)` | Blueprint overlay |
| `survey_power_ascii(...)` | Power grid |
| `survey_task_ascii(...)` | Work task overlay |
| `survey_detailed_ascii(...)` | Multi-layer detailed view |
| `survey_fertility_ascii(...)` | Fertility heatmap |
| `survey_roof_ascii(...)` | Roof coverage |

All survey methods accept optional `x1, z1, x2, z2` (defaults to full map) and `scale` (downsampling).

### Tile-Level Scanning

| Method | Description |
|--------|-------------|
| `scan(x1, z1, x2, z2)` | Read map tiles with decoded grids. Auto-pages if > 50x50. Returns terrain, items, roofs. |
| `scan_items(x1, z1, x2, z2, kind)` | Scan for specific item types (e.g., `kind="building"`) |
| `survey_region(x1, z1, x2, z2)` | Aggregate stats: terrain counts, avg fertility, roof coverage |

### Finding Locations

| Method | Description |
|--------|-------------|
| `find_water()` | Find nearest water cells on map |
| `find_grow_spot(size=, radius=, cx=, cz=)` | Find fertile ground for a grow zone |
| `find_clear_rect(width=9, height=7, cx=, cz=, radius=30)` | Find buildable rectangular area |
