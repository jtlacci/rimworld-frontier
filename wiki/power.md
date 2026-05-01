# Power and Electricity

Power enables stoves, coolers, turrets, research benches, autodoors, and other advanced buildings.

## Power Generators

| Generator | Output | Size | Cost | Research | Fuel |
|-----------|--------|------|------|----------|------|
| Wood-fired | 1,000W constant | 2×2 | 100 Steel + 2 Comp | Electricity | 22 wood/day |
| Solar | 0-1,700W (sunlight) | 4×4 | 100 Steel + 3 Comp | Solar panel | None |
| Wind turbine | 0-3,450W (variable) | 5×2 + exclusion | 100 Steel + 2 Comp | Electricity | None |
| Chemfuel | 1,000W constant | 2×2 | 100 Steel + 3 Comp | Electricity | 4.5 chemfuel/day |
| Watermill | 1,100W constant | 5×6 | 280 Wood + 80 Steel + 3 Comp | Watermill generator | None (river) |
| Geothermal | 3,600W constant | 6×6 | 340 Steel + 8 Comp | Geothermal power | None (geyser) |
| Vanometric cell | 1,000W constant | 1×2 | Quest reward only | None | None (infinite) |

### Solar Generator Detail
- Output scales linearly with world light level. Eclipses = 0W. Weather does NOT reduce output.
- Must be unroofed. Partial roofing proportionally reduces output (half roofed ≈ 850W).
- Daily pattern near equator: ramp up 04:00-08:00, full output 08:00-17:00, ramp down 17:00-20:00, dark 20:00-04:00.
- **Blocks Wind: NO** — can be placed inside wind turbine exclusion zones.

### Wind Turbine Detail
- Average output ~2,200W. Storms/blizzards = ~3,400W. Fog = ~1,200W.
- **Exclusion zone**: 7 wide × 18 long total (8 clear tiles on each wind side of the 7×2 building).
- Each obstruction (tree/building/roof) reduces output by 20%. Five obstructions = 0W.
- Wind direction doesn't matter — turbine works equally in any orientation.

**CAN go in exclusion zone** (low-lying, don't block wind):
- Solar generators, shelves, growing zones (any crop), artificial flooring

**CANNOT go in exclusion zone** (block wind):
- Walls, trees, mountains, batteries, most buildings, roof tiles

### Fueled Generators
- **Wood-fired**: 75 wood capacity = 3.27 days runtime. Burns fuel constantly whether or not power is drawn. Generates heat (+6/sec) and light (3.44 tile radius). Heat continues during solar flares.
- **Chemfuel**: 30 capacity = 6.66 days runtime. Same constant burn. Explodes if damaged below 1/3 HP (chemfuel puddles + fire). More fuel-efficient: 4.5 chemfuel/day vs 22 wood/day equivalent.
- Both are auto-refueled by haulers. Refueling is toggleable. Can be switched off to stop fuel burn.
- **Both work as heaters during solar flares** (still burn fuel, still produce heat, but cannot deliver electrical power).

### Watermill
- Overlapping exclusion zones reduce output to 30% (330W). Frozen water halts generation.

## Power Storage (Battery)

| Stat | Value |
|------|-------|
| Capacity | 600 Wd |
| Charge efficiency | **50%** (wastes half of input power) |
| Self-discharge | 5 Wd/day |
| Size | 1×2 |
| Cost | 70 Steel + 2 Components |
| Research | Batteries |
| HP | 100 |
| Beauty | -15 |

- **MUST be indoors under roof** — rain causes Zzzt short circuit.
- Explodes when burning if charged. Loses all energy on breakdown.
- Charge/discharge rate is unlimited. Each tile acts as a conduit.
- Cannot be turned off directly — use a power switch to isolate.
- Excess power is evenly divided between all batteries on a grid.

### Battery Sizing Math

Account for 50% charge efficiency:

| Overnight Load | Stored Power Needed (8h night) | Batteries |
|---------------|-------------------------------|-----------|
| 1,000W | 333 Wd | 1 |
| 2,000W | 667 Wd | 2 |
| 3,000W | 1,000 Wd | 2 |
| 5,000W | 1,667 Wd | 3 |

Formula: batteries = ceil(load_watts × 8/24 / 600)

**Rule of thumb**: 1 battery per ~1,800W of overnight load. Keep batteries to a minimum — each wastes 5W passively and increases Zzzt explosion radius.

## Power Conduits

| Type | Cost | Beauty | Zzzt Immune | Flammable | Build Time |
|------|------|--------|------------|-----------|-----------|
| Regular | 1 Steel/tile | -2 | No | 70% | 0.6s |
| **Hidden** | 2 Steel/tile | 0 | **Yes** | 0% | 4.7s (8× slower) |

- Zero transmission loss over any distance. Branch freely.
- Can go under walls, doors, and any building.
- Cannot be placed on unsmoothed mountain rock or ores.
- Appliances connect to nearest conduit/battery/generator within 6 tiles.

**Always prefer hidden conduits.** The 1 extra steel per tile is negligible. A base using only hidden conduits is completely immune to Zzzt events.

## Power Switch

- 1×1, 15 Steel + 1 Component, 0W power draw
- Toggles power flow — ON acts as conduit, OFF breaks the circuit
- Requires a colonist (Basic work type) to physically toggle
- **Batteries behind an OFF switch are immune to Zzzt discharge**

### Use Cases
- Isolate backup batteries (normally OFF, flip ON when main power fails)
- Separate turret circuits (ON only during raids)
- Disconnect unused generators to prevent fuel waste

## Short Circuit (Zzzt)

- Triggers randomly on powered **regular** conduit tiles (8-day storyteller cooldown)
- Does NOT trigger on hidden conduits or conduit-free networks
- Discharges ALL battery power on the affected grid

### Explosion Scale

| Batteries | Stored Wd | Flame Radius | Bomb? |
|-----------|-----------|-------------|-------|
| 0 | 0 | Fire only | No |
| 1 | 600 | 1.5 tiles | No |
| 4 | 2,400 | 2.5 tiles | No |
| 9 | 5,400 | 3.7 tiles | Yes (1.1 tile) |
| 150 | 90,000 | 14.9 tiles (max) | Yes (4.5 tiles) |

- < 20 Wd: fire only
- ≥ 20 Wd: fiery explosion (10 Flame damage)
- ≥ 4,900 Wd: secondary bomb (50 Bomb damage)
- Radius = clamp(sqrt(Wd) × 0.05, 1.5, 14.9)

### Rain Short Circuits (separate from Zzzt)
Unroofed electrical buildings short circuit from rain/snow — **no cooldown**, bypasses the 8-day timer. Affected: sun lamp, TVs, comms console, stoves, smelters, batteries, research benches, turrets, and most powered workbenches. **Roof all electrical buildings.**

### Prevention
1. **Hidden conduits** (immune to Zzzt) — best solution
2. Isolate batteries with power switches
3. Keep battery count low per grid
4. Roof all electrical buildings (prevents rain shorts)

## Temperature Control

### Cooler
- 200W active / 20W idle. -21 heat/sec. Cost: 90 Steel + 3 Components.
- **Placed in a wall** — blue side = cold (into room), red side = hot exhaust.
- Hot side shuts off at 165°C. Default target 21°C.
- Multiple coolers in same room stack linearly.
- **Stagger targets**: set each cooler 1° lower (-1°C, -2°C, -3°C) so only the warmest stays active; others idle at 20W until needed.

### Heater
- 175W active / 17W idle. +21 heat/sec. Cost: 50 Steel + 1 Component.
- Position in room doesn't matter — corner = center.
- Heats only its own room. Use vents to share heat to adjacent rooms.
- Provides dim light (1.65 tile radius, ~50% — enough for surgery bonus).

### Practical Sizing

| Room Interior | Heaters for 20°C (outdoor -17°C) | Coolers for 0°C (outdoor 30°C) |
|--------------|--------------------------------|-------------------------------|
| 3×3 (9 tiles) | 1 | 1 |
| 5×5 (25 tiles) | 1 | 1 |
| 7×7 (49 tiles) | 1 (barely) | 1-2 |
| 9×9 (81 tiles) | 1-2 | 2 |
| Large freezer (150+ tiles) | N/A | 3-4+ |

**Double walls halve heat transfer** — dramatically improves these numbers. Triple walls give no further benefit.

### Passive Cooler (no power)
- -11 heat/sec (half of electric cooler). Min temp 17°C (cannot freeze food).
- Burns 10 wood/day, 50 capacity = 5 days.
- **Excellent solar flare backup** — keeps rooms livable without power.

### Freezer Design
- Cooler cold side into freezer room, hot side outdoors or into 1×1 unroofed "chimney"
- Double walls for insulation
- Target -2°C to -5°C (buffer against door opening)
- Airlock (double doors in sequence) reduces heat leak from traffic
- Keep 1-2 passive coolers inside as solar flare insurance (won't freeze food, but prevents thaw damage)

### Vent
- 30 Steel, no power. Replaces a wall tile. Rapidly equalizes temperature between rooms when open.
- Heat/cool one central room, vent to surrounding rooms. Don't daisy-chain (efficiency drops per link).

## Solar Flare

- Duration: ~3.6 to 12 hours (15-day cooldown)
- ALL electrical devices disabled
- Batteries retain charge but cannot charge or discharge
- Fueled generators burn fuel but cannot deliver power (still produce heat)

### Still works during flare
Campfires, passive coolers, fueled stove, fueled smithy, all non-electric buildings.

### Critical impacts
- **Hydroponics**: plants die instantly (harvest before they wilt)
- **Freezers**: stop cooling → food spoils
- **Turrets**: offline → vulnerable to raids
- **Heaters/coolers**: offline → temperature danger

## EMP Effects

- Generators/batteries/turrets stunned for 22.5-37.5 seconds
- Batteries do NOT lose charge from EMP (unlike Zzzt)
- Buildings do NOT adapt to EMP — can be chain-stunned indefinitely

## Breakdown Maintenance

- All powered buildings: MTB 3.8 years per building
- Repair costs 1 Component (Construction skill 8+ for 100% success)
- Only powered/functioning buildings break down — turning off makes them immune
- Batteries lose ALL energy on breakdown
- Keep 5-10 spare components stockpiled

## Grid Design for Agents

### Early Game (3-6 colonists, ~500-800W)
1. Research Electricity → Battery
2. 1 wood-fired generator (1,000W)
3. 1-2 batteries (indoors, roofed)
4. Hidden conduits throughout
5. Loads: stove (350W), lights (30-60W), heater/cooler (175-200W)

### Mid Game (6-10 colonists, ~2,000-4,000W)
- 2-3 solar + 1-2 wind turbines + 2-4 batteries
- 1 chemfuel generator as backup
- Add: freezer coolers, more workbenches, turrets, hydroponics

### Late Game (10+ colonists, ~5,000-15,000W)
- Geothermal generators as backbone (3,600W each, constant)
- Solar + wind supplemental
- 4-6 batteries split across isolated circuits
- Chemfuel backup for solar flares

### Recommended Circuit Architecture
1. **Main grid**: all generators → production, lighting, research. 2-4 active batteries.
2. **Freezer circuit**: dedicated coolers + backup battery bank behind switch.
3. **Defense circuit**: turrets behind switch (ON only during raids).
4. **Emergency reserve**: 2-3 batteries behind normally-OFF switch.

## Power Consumer Quick Reference

| Category | Building | Power |
|----------|----------|-------|
| Lighting | Standing/Wall lamp | 30W |
| | Sun lamp | 2,900W |
| Temperature | Heater | 175W / 17W idle |
| | Cooler | 200W / 20W idle |
| Production | Electric stove | 350W |
| | Electric smelter | 700W |
| | Machining table | 350W |
| | Fabrication bench | 250W |
| | Electric smithy | 210W |
| | Electric tailor bench | 120W |
| | Biofuel refinery | 170W |
| Research | Simple research bench | **0W** |
| | Hi-tech research bench | 250W |
| | Multi-analyzer | 200W |
| Infrastructure | NPD | 200W |
| | Autodoor | 50W |
| | Comms console | 200W |
| | Trade beacon | 40W |
| | Vitals monitor | 80W |
| Defense | Mini-turret | 80W |
| | Autocannon/Slug turret | 150W |
| Farming | Hydroponics basin | 70W |
| Recreation | Tube TV | 200W |
| | Flatscreen TV | 330W |
| | Megascreen TV | 450W |
