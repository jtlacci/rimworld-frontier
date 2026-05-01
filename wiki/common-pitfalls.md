# Common Pitfalls

Known issues and gotchas that agents frequently encounter when playing RimWorld through the TCP bridge.

## Game State Issues

- **Research gets unset on game reload** — always verify and re-set research after loading a save
- **Forbidden items at game start** — call `unforbid_all()` early to let colonists haul crashed items
- **"idle" is momentary** — colonists briefly show idle between jobs. Check a few seconds later before assuming they're stuck.
- **Dialogs block game time** — research complete popups, quest dialogs freeze the game clock. Always check `read_dialogs` and dismiss with `choose_option`.

## Naming Dialog

`Dialog_NamePlayerFactionAndSettlement` appears at game start and blocks time. Close with:
```python
r.close_dialog("Dialog_NamePlayerFactionAndSettlement", factionName="Name", settlementName="Name")
```
Always check for and dismiss this in session startup.

## ImmediateWindows

Calling `close_dialog()` without a type may close an ImmediateWindow that respawns immediately. Use `close_dialog(dialog_type="...")` to target specific dialogs.

## Building Issues

- **Never stack blueprints** — don't place blueprints on top of each other (except conduits which can go under walls/buildings)
- **Collision detection** — `build_room` / `build_room_grid` raise `RimError` on ANY collision
- **Cooler placement** — Build command rejects coolers on walls (impassable check). Deconstruct the wall first, wait for colonist to remove it, THEN place the cooler blueprint.
- **Campfire is both a building AND a workbench** — won't show in `bills()` until fully constructed

## SDK Gotchas

- **`build(blueprint, x, z)`** — use positional args or `z=` keyword, NOT `y=`
- **`colonists()` returns `{'colonists': [...]}`** not a flat list
- **`buildings()` returns `{'buildings': [...], 'rooms': [...]}`** not a flat list
- **`read_map_tiles` capped at 50x50 server-side** — use `scan()` for auto-paging

## Layout Mistakes

- **Double walls** — adjacent rooms must share walls, not build double-thick walls between them
- **Zone overlap** — two stockpiles accepting the same item = hauling loops
- **Furniture in bedrooms** — workbenches in bedrooms change the room role and lose bedroom mood buff
- **Stockpiles in labs** — ugly + cluttered, ruins impressiveness

## Food Mistakes

- **Stockpiling raw meat** without refrigeration — rots in 2 days
- **"Do forever" cook bills** — overproduces meals that spoil. Use "until X" limits.
- **No table** — -3 "ate without table" mood debuff. Build table + chairs before walls.
- **Dirty kitchen** — filth where food is cooked = food poisoning chance

## Combat Mistakes

- **Forgetting to draft** — colonists walk into combat zones and get killed
- **Wood perimeter walls** — raiders use fire
- **Unroofed batteries** — rain = Zzztt short circuit explosion

## Priority Mistakes

- **Everything at priority 1** — colonists only do the first available work type, never reach lower ones
- **No Growing priority** — wild berry harvesting uses Growing (Plants work type)
- **Manual priorities not enabled** — must call `set_manual_priorities(True)` after game start
