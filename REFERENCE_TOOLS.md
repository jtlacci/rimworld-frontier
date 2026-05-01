# Tool Catalog

Auto-generated reference of all available tools. Each agent has different access levels.

## Agent Access Matrix

| Tool Category | Overseer | Auditor | Trainer | Challenger |
|---------------|----------|---------|---------|------------|
| SDK: Game State (read) | ✅ | ❌ | ❌ | ❌ |
| SDK: Game Control (write) | ✅ | ❌ | ❌ | ❌ |
| SDK: Colony Setup Helpers | ✅ | ❌ | ❌ | ❌ |
| SDK: Building Helpers | ✅ | ❌ | ❌ | ❌ |
| File: Read code | ❌ | ✅ | ✅ | ✅ |
| File: Edit code | ❌ | ❌ | ✅ | ❌ |
| File: Write scenarios | ❌ | ❌ | ❌ | ✅ |
| Run scenarios | ❌ | ❌ | ❌ | ❌ |
| Run other agents | ❌ | ❌ | ❌ | ❌ |

### What Each Agent CANNOT Do

**Overseer**: Cannot read/edit source files, run other agents, or modify scoring.
**Auditor**: Cannot edit any files, run scenarios, or call SDK game commands. Read-only investigation.
**Trainer**: Cannot run scenarios, call SDK game commands, or edit scoring thresholds to inflate scores.
**Challenger**: Cannot edit code, run scenarios, or call SDK. Can only write scenario JSON files.

---

## SDK Methods (sdk/rimworld.py — RimClient)

### Connection
| Method | Description |
|--------|-------------|
| `send(command)` | Send a command, return parsed response |
| `send_batch(commands)` | Send multiple commands, return list of results |
| `send_batch_lenient(commands)` | Like send_batch but skips errors |
| `close()` | Close TCP connection |
| `restart_game(save=, timeout=120)` | Kill RimWorld, relaunch, reconnect |

### Game State (Read-Only)
| Method | Returns |
|--------|---------|
| `ping()` | Server status |
| `colonists()` | `{colonists: [{name, mood, currentJob, position, ...}]}` |
| `pawns()` | All pawns on map |
| `animals()` | `{animals: [{name, kind, position, tame, health, ...}]}` |
| `resources()` | `{WoodLog: N, Steel: N, MealSimple: N, ...}` |
| `map_info()` | Map size, biome |
| `weather()` | `{dayOfYear, hour, season, temperature, ...}` |
| `research()` | `{current, completed: [...], ...}` |
| `buildings()` | `{buildings: [{def, position, ...}], rooms: [...]}` |
| `zones()` | `{zones: [{type, cells, ...}]}` |
| `alerts()` | Active game alerts |
| `messages()` | Top-of-screen messages |
| `threats()` | Hostile pawns, fires |
| `work_priorities()` | Per-colonist work priorities |
| `needs(pawn)` | Single pawn's needs |
| `colonist_needs()` | All colonists' needs |
| `thoughts(pawn)` | `{thoughts: [{label, mood, daysLeft}]}` |
| `inventory(pawn)` | Pawn's carried items |
| `bills()` | `{workbenches: [{def, bills: [{recipe, suspended}]}]}` |
| `colony_stats()` | Wealth, beauty, impressiveness, rooms |
| `beauty(x1, z1, x2, z2)` | Beauty values for region |
| `terrain(x1, z1, x2, z2)` | Terrain types for region |
| `roof(x1, z1, x2, z2)` | Roof status for region |
| `costs(blueprint, stuff=)` | Material costs for a building |
| `letters()` | Pending letter stack |
| `dialogs()` | Open dialog windows |
| `visitors()` | Visitors/traders on map |
| `ideology()` | Ideology info |
| `list_saves()` | Available save files |

### Game Control (Write)
| Method | Description |
|--------|-------------|
| `pause()` | Pause game |
| `unpause(speed=4)` | Unpause at speed (default 4 = ultrafast) |
| `speed(n)` | Set game speed 1-4 |
| `save(name=)` | Save game |
| `load_game(name)` | Load save file |
| `camera(x, z)` | Move camera |
| `disable_incidents()` | Disable raids/events |
| `enable_incidents()` | Re-enable incidents |
| `set_storyteller(name=, difficulty=)` | Change storyteller |

### Building
| Method | Description |
|--------|-------------|
| `build(blueprint, x, z, stuff=, rotation=)` | Place a building blueprint |
| `bulk_build(ops)` | Multiple builds in one request |
| `wall(x, z, stuff='BlocksGranite')` | Place wall |
| `door(x, z, stuff='BlocksGranite')` | Place door |
| `floor(floor_def, x1, z1, x2=, z2=, stuff=)` | Place flooring |
| `cancel_build(x, z)` | Cancel blueprint |
| `deconstruct(x, z)` | Designate deconstruction |
| `place(thing_def, x, z, stuff=, rotation=)` | Place item |
| `plan(x1, z1, x2=, z2=)` | Place planning markers |
| `remove_plan(x1, z1, x2=, z2=)` | Remove planning markers |

### Zones
| Method | Description |
|--------|-------------|
| `grow_zone(x1, z1, x2, z2, plant=, check_soil=True)` | Create grow zone |
| `stockpile(x1, z1, x2, z2, priority=)` | Create stockpile |
| `delete_zone(x=, z=)` | Delete zone at position |
| `set_plant(zone=, plant=)` | Set plant type for grow zone |
| `set_stockpile_filter(x=, z=, allow=, disallow=, ...)` | Modify stockpile filter |
| `fishing_zone(x1, z1, x2=, z2=)` | Create fishing zone |

### Colonist Management
| Method | Description |
|--------|-------------|
| `draft(colonist)` | Draft colonist |
| `undraft(colonist)` | Undraft colonist |
| `move_pawn(pawn, x, z)` | Move pawn to position |
| `attack(pawn, target=, x=, z=)` | Order attack |
| `rescue(pawn, target)` | Rescue downed pawn |
| `tend(pawn, target=)` | Tend injured pawn |
| `equip(pawn, thing=, x=, z=)` | Equip item |
| `haul(pawn, x, z)` | Haul to position |
| `prioritize(pawn, work_type)` | Force prioritize a task |
| `set_priority(colonist, work, level)` | Set work priority (1-4) |
| `set_priorities(colonist, priorities)` | Set multiple priorities |
| `set_schedule(colonist, schedule)` | Set daily schedule |
| `set_manual_priorities(enabled=True)` | Toggle manual priority mode |
| `assign_role(pawn, role)` | Assign ideology role |

### Designations
| Method | Description |
|--------|-------------|
| `chop(x, z, radius=)` | Designate trees for chopping |
| `harvest(x, z, radius=, def_filter=)` | Designate plants for harvest |
| `mine(x1=, z1=, x2=, z2=)` | Designate mining |
| `hunt(animal=)` | Designate animal for hunting |
| `tame(animal)` | Designate animal for taming |
| `slaughter(animal)` | Designate animal for slaughter |
| `forbid(x=, z=, thing_def=)` | Forbid items |
| `unforbid(x=, z=, thing_def=)` | Unforbid items |
| `unforbid_all()` | Unforbid all items on map |
| `cancel_designation(x, z)` | Cancel single designation |
| `cancel_designations(x1, z1, x2, z2, kind=)` | Cancel designations in area |

### Production
| Method | Description |
|--------|-------------|
| `add_bill(workbench, recipe, count=)` | Add crafting bill |
| `cancel_bill(workbench, bill_index)` | Cancel bill |
| `suspend_bill(workbench, bill_index, suspended=True)` | Suspend/resume bill |
| `set_research(project)` | Set current research project |

### UI / Letters
| Method | Description |
|--------|-------------|
| `open_letter(index)` | Open a letter |
| `dismiss_letter(index)` | Dismiss a letter |
| `choose_option(index)` | Choose dialog option |
| `close_dialog(dialog_type=)` | Close dialog window |

### Survey / Map Inspection
| Method | Description |
|--------|-------------|
| `scan(x1, z1, x2, z2)` | Read map tiles with decoded grids |
| `scan_items(x1, z1, x2, z2, kind)` | Scan for specific item types |
| `survey_composite_ascii(x1=, z1=, x2=, z2=, scale=)` | ASCII map view |
| `survey_terrain_ascii(...)` | Terrain-only ASCII |
| `survey_things_ascii(...)` | Things-only ASCII |
| `survey_beauty_ascii(...)` | Beauty heatmap ASCII |
| `survey_blueprint_ascii(...)` | Blueprint overlay ASCII |
| `find_water()` | Find nearest water cells |
| `find_grow_spot(size=, radius=, cx=, cz=)` | Find fertile ground |
| `find_clear_rect(width=9, height=7, cx=, cz=, radius=30)` | Find buildable area |

### Colony Setup Helpers (high-level, wrap multiple calls)
| Method | Returns | Description |
|--------|---------|-------------|
| `day1_setup()` | `{center_x, center_z, hunter, cook, researcher, resources, ...}` | Full Day 1 init |
| `setup_cooking(cx, cz)` | `{campfire, butcher, stove}` | Campfire + butcher + stove |
| `setup_dining(cx, cz)` | `{table, chairs}` | Table + chairs |
| `add_cooking_bills()` | `{campfire_bill, butcher_bill, stove_bill}` | Idempotent bill management |
| `setup_zones(cx, cz)` | `{main, food, dump, grow}` | All stockpiles + grow zone |
| `secure_food_stockpile(bx, bz, bx2, bz2)` | `{food: (x,z)}` | Move food inside room |
| `build_barracks(cx, cz, material='Steel')` | `{x1, z1, x2, z2, built, failed}` | 7x5 barracks with furniture + sculpture |
| `build_storage_room(cx, cz, material='WoodLog')` | `{x1, z1, x2, z2, built, failed}` | 7x5 storage with flooring |
| `setup_recreation(cx, cz)` | `{horseshoes}` | Horseshoes pin |
| `setup_production(cx, cz, bx, bz)` | `{research_bench, tailoring_bench}` | Research + tailoring |
| `colony_health_check()` | `{food, shelter, wood, mood, game_day, alerts}` | Structured diagnostic |

### Advanced Building Helpers
| Method | Description |
|--------|-------------|
| `build_room(x1, z1, x2, z2, stuff=, doors=, floor=)` | Build rectangular room |
| `build_room_grid(origin_x, origin_z, cols, rows, ...)` | Grid of shared-wall rooms |
| `build_hallway(x1, z1, x2, z2, ...)` | 3-wide hallway |
| `build_room_adjacent(existing_bounds, direction, ...)` | Room sharing existing wall |
| `check_buildable(cells, stuff=)` | Pre-flight buildability check |
| `cost_check(blueprint, stuff=, count=1)` | Affordability check |
| `verify_room(x1, z1, x2, z2)` | Post-build room audit |
| `build_with_budget(plan, budget=)` | Build as many as affordable |
| `wait_for_construction(x1, z1, x2, z2, timeout=120)` | Wait for completion |

---

## Scoring (sdk/snapshot.py + sdk/timeline_scoring.py)

Agents should know what's being measured but NEVER edit thresholds.

| Metric | Weight | Threshold for 1.0 |
|--------|--------|-------------------|
| alive | 5 | all colonists alive |
| food_safety | 6 | no starvation, worst food > 0.4 |
| shelter | 10 | enclosed rooms >= colonist count |
| self_sufficiency | 15 | survival packs 90%+ remaining |
| building_progress | 15 | building wealth >= 1500 |
| avg_impressiveness | 20 | room impressiveness >= 40 |
| avg_beauty | 8 | home beauty >= 1.0 |
| need_sustained | 10 | no prolonged need deprivation |
| food_trajectory | 5 | food stable throughout run |
| progress_pace | 5 | steady construction growth |

---

## Scenario Config (frontier/scenario.py)

Available parameters for scenario JSON files:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| name | str | required | Scenario identifier |
| map_size | int | 50 | Map dimensions |
| terrain | str | "Soil" | Soil, SoilRich, Gravel, Sand, Mud |
| mountains | str | "none" | none, corners, random, ring, border |
| water | str | "none" | none, river, lake, corners, border |
| trees | bool | true | Enable tree generation |
| tree_density | float | 0.08 | Tree coverage (0.0-0.25) |
| temperature | float | 20.0 | Starting temperature (C) |
| berry_bushes | int | 0 | Berry bush count |
| keep_wildlife | bool | false | Keep template wildlife |
| wildlife_count | int | 0 | Spawned wild animals |
| starting_packs | int | null | Survival meal count |
| starting_items | dict | null | Override item quantities: {"Steel": 500} |
| completed_research | list | null | Pre-completed research: ["Electricity"] |
| seed | int | 42 | Random seed |
