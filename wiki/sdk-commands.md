# SDK: Game Commands (Write)

All write commands auto-invalidate relevant read caches.

## Game Control

| Method | Signature | Description |
|--------|-----------|-------------|
| `pause()` | `pause()` | Pause game clock |
| `unpause(speed=4)` | `unpause(speed=4)` | Resume at speed (default 4 = ultrafast) |
| `speed(n)` | `speed(3)` | Set game speed 1-4 |
| `save(name=)` | `save("my_save")` | Save game to file |
| `load_game(name)` | `load_game("my_save")` | Load save (connection drops, must reconnect) |
| `camera(x, z)` | `camera(120, 135)` | Move camera to position |
| `disable_incidents()` | | Block all storyteller events (raids, etc.) |
| `enable_incidents()` | | Re-enable events |
| `set_storyteller(name=, difficulty=)` | | Change storyteller or difficulty |

## Building

| Method | Signature | Description |
|--------|-----------|-------------|
| `build(blueprint, x, z, stuff=, rotation=)` | `build("Wall", 120, 135, stuff="BlocksGranite")` | Place building blueprint |
| `bulk_build(ops)` | `bulk_build([("Wall", 120, 135, {"stuff": "BlocksGranite"}), ...])` | Multiple builds in one request |
| `wall(x, z, stuff=)` | `wall(120, 135, stuff="BlocksGranite")` | Shorthand: place wall |
| `door(x, z, stuff=)` | `door(124, 135, stuff="BlocksGranite")` | Shorthand: place door |
| `floor(floor_def, x1, z1, x2=, z2=)` | `floor("TileSandstone", 121, 136, 127, 139)` | Place flooring over rectangle |
| `place(thing_def, x, z, stuff=, rotation=)` | `place("Bed", 122, 138, stuff="WoodLog")` | Place item/furniture |
| `plan(x1, z1, x2=, z2=)` | `plan(120, 135, 128, 140)` | Place planning designations |
| `remove_plan(x1, z1, x2=, z2=)` | | Remove planning marks |
| `cancel_build(x, z)` | `cancel_build(120, 135)` | Cancel blueprint at cell |
| `deconstruct(x, z)` | `deconstruct(120, 135)` | Designate for deconstruction |

### Build Gotchas
- `build(blueprint, x, z)` — use `z=` keyword, **NOT** `y=`
- Build rejects placement on interaction spots of existing buildings
- Cooler placement: deconstruct wall first, wait for removal, then place cooler
- Conduits can go under walls and buildings (isConduit bypass)
- Never stack blueprints on same cell (except conduits under walls)

## Zones

| Method | Signature | Description |
|--------|-----------|-------------|
| `grow_zone(x1, z1, x2, z2, plant=, check_soil=True)` | `grow_zone(100, 120, 110, 130, plant="Plant_Rice")` | Create grow zone with soil validation |
| `stockpile(x1, z1, x2, z2, priority=)` | `stockpile(115, 130, 120, 135, priority="Important")` | Create stockpile zone |
| `delete_zone(x=, z=)` | `delete_zone(x=100, z=120)` | Delete zone containing cell |
| `remove_zone_cells(x1, z1, x2=, z2=)` | | Remove cells from zone (auto-deletes if empty) |
| `set_plant(zone=, plant=)` | `set_plant(plant="Plant_Corn")` | Change crop type on grow zone |
| `set_stockpile_filter(x=, z=, allow=, disallow=, priority=)` | See below | Modify stockpile filters |

### Stockpile Filter Examples
```python
# Allow only raw food in a stockpile
r.set_stockpile_filter(x=115, z=130, disallow_all=True, allow=["Foods"])

# Set priority
r.set_stockpile_filter(x=115, z=130, priority="Critical")
```

## Colonist Management

| Method | Signature | Description |
|--------|-----------|-------------|
| `draft(colonist)` | `draft("Gabs")` | Enter combat mode |
| `undraft(colonist)` | `undraft("Gabs")` | Return to work |
| `move_pawn(pawn, x, z)` | `move_pawn("Gabs", 125, 140)` | Move drafted pawn to position |
| `attack(pawn, target=, x=, z=)` | `attack("Gabs", target="Raider1")` | Order attack |
| `rescue(pawn, target)` | `rescue("Gabs", "Dax")` | Rescue downed pawn to bed |
| `tend(pawn, target=)` | `tend("Gabs", target="Dax")` | Tend wounds |
| `equip(pawn, thing=, x=, z=)` | `equip("Gabs", thing="Knife")` | Equip item |
| `haul(pawn, x, z)` | `haul("Gabs", 120, 135)` | Haul item to position |
| `prioritize(pawn, work_type)` | `prioritize("Gabs", "Construction")` | Force prioritize next task |

### Work Priorities

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_manual_priorities(enabled=True)` | | Toggle manual vs simple mode. **Must call after game start.** |
| `set_priority(colonist, work, level)` | `set_priority("Gabs", "Cooking", 1)` | Set single priority (1=highest, 4=lowest, 0=disabled) |
| `set_priorities(colonist, priorities)` | `set_priorities("Gabs", {"Cooking": 1, "Hauling": 3})` | Set multiple at once |
| `set_schedule(colonist, schedule)` | `set_schedule("Gabs", "work")` | Set 24h schedule. Pass string for all-day, or list of 24 entries. |
| `assign_role(pawn, role)` | | Assign ideology role |

## Designations

| Method | Signature | Description |
|--------|-----------|-------------|
| `chop(x, z, radius=)` | `chop(120, 135, radius=20)` | Designate trees for chopping |
| `harvest(x, z, radius=, def_filter=)` | `harvest(120, 135, radius=50)` | Designate plants for harvest |
| `mine(x1=, z1=, x2=, z2=)` | `mine(x1=100, z1=100, x2=110, z2=110)` | Designate mining area |
| `hunt(animal=)` | `hunt(animal="Deer")` | Hunt specific animal |
| `hunt_all_wildlife()` | | Hunt all safe wild animals (skips dangerous species) |
| `tame(animal)` | `tame("Muffalo")` | Designate for taming |
| `slaughter(animal)` | `slaughter("Boomalope")` | Designate for slaughter |
| `forbid(x=, z=, thing_def=)` | | Forbid items at position or by type |
| `unforbid(x=, z=, thing_def=)` | | Unforbid items |
| `unforbid_all()` | | Unforbid all items on map (bulk server-side) |
| `cancel_designation(x, z)` | | Cancel single designation at cell |
| `cancel_designations(x1, z1, x2, z2, kind=)` | | Cancel designations in area |
| `spawn_animals(species, count=, x=, z=, manhunter=)` | | Spawn animals (dev/testing) |

## Production

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_bill(workbench, recipe, count=, x=, z=, target_all=)` | `add_bill("ElectricStove", "MakeMealSimple", count=10)` | Add crafting bill. Use x/z for position targeting, target_all=True to broadcast. |
| `cancel_bill(workbench, bill_index)` | | Cancel bill by index |
| `suspend_bill(workbench, bill_index, suspended=True)` | | Suspend or resume bill |
| `set_research(project)` | `set_research("Electricity")` | Set current research project |

### Common Recipe defNames
- `MakeMealSimple`, `MakeMealSimpleBulk` (4x)
- `MakeMealFine`, `MakeMealFineBulk`
- `MakeMealLavish`, `MakeMealLavishBulk`
- `ButcherCorpseFlesh`
- `MakePemmican`, `MakePemmicanBulk`
- `MakePackagedSurvivalMeal`

## UI & Notifications

| Method | Signature | Description |
|--------|-----------|-------------|
| `open_letter(index)` | `open_letter(0)` | Open letter for details |
| `dismiss_letter(index)` | `dismiss_letter(0)` | Dismiss letter |
| `choose_option(index)` | `choose_option(0)` | Choose dialog option |
| `close_dialog(dialog_type=, **kwargs)` | `close_dialog("Dialog_NamePlayerFactionAndSettlement", factionName="Colony")` | Close specific dialog |

### Critical: Naming Dialog
The naming dialog blocks game time at start. Always close it:
```python
r.close_dialog("Dialog_NamePlayerFactionAndSettlement",
               factionName="Colony", settlementName="Base")
```

## Event Logging

| Method | Description |
|--------|-------------|
| `set_event_log(path=)` | Start/stop game-side event logger (job transitions, eating, pickups) |
