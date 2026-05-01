# Indoor Farming

Indoor farming enables year-round food production regardless of biome or season. Essential for cold biomes, toxic fallout, and food security.

## Sun Lamp

| Stat | Value |
|------|-------|
| Light radius | 11.72 tiles (100% within ~5.5 tiles) |
| Effective growing area | ~100 tiles |
| Power | 2,900W |
| Operating hours | 06:00 to 19:12 (matches plant active period) |
| Avg daily power | ~1,595 Wd (off at night) |
| Heat output | 3 heat/sec (may require cooling in warm biomes) |
| Cost | 40 Steel |
| Research | Electricity |
| Size | 1x1 |

Place centrally with growing zone radiating outward. Area must be roofed. Requires heating in cold biomes to keep crops above 0C (growth stops) and definitely above -10C (plants die).

## Hydroponics Basin

| Stat | Value |
|------|-------|
| Fertility | **280%** |
| Power | 70W (constant, day and night) |
| Size | 1x4 tiles |
| Cost | 100 Steel + 1 Component |
| Construction skill | 4 |
| Research | Hydroponics |
| HP | 180 |
| Cleanliness | -3 (dirty!) |

### Compatible Crops (13)
Rice, Potato, Strawberry, Cotton, Healroot, Hop, Smokeleaf, Psychoid, Nutrifungus, Tinctoria, Toxipotato, Fibercorn

### Incompatible
**Corn, Devilstrand, Haygrass, Trees, Decorative plants**

### Critical Warning
**Plants die IMMEDIATELY if power is cut** — no grace period. Requires uninterrupted power supply. Regular soil indoor farms are safer (crops survive power loss, just stop growing).

## Hydroponics Math

### Rice per Basin (4 tiles)
- 280% fertility × rice (1.0 sensitivity) = 2.8× growth rate
- Real grow time: 5.54 / 2.8 = **~1.98 days per harvest**
- Yield per basin: 4 tiles × 6 rice = 24 rice per harvest
- Nutrition/day per basin: 24 × 0.05 / 1.98 = **0.61 nutrition/day**
- Via simple meals (180% efficiency): 0.61 × 1.8 = **1.10 nutrition/day**
- **~1.5 basins feed one colonist** (via simple meals at 1.6 nutrition/day)

### Potato per Basin (4 tiles)
- 280% fertility × potato (0.4 sensitivity) = 1.72× growth rate
- Real grow time: 10.71 / 1.72 = **~6.23 days per harvest**
- Yield: 4 × 11 = 44 potatoes per harvest
- Nutrition/day: 44 × 0.05 / 6.23 = **0.35 nutrition/day**
- Rice is **74% more productive** in hydroponics — always prefer rice

### Hydroponics Priority
1. **Rice** — best synergy with 280% fertility (1.0 sensitivity)
2. **Strawberries** — edible raw, no mood penalty
3. **Healroot** — if medicine needed (skill 8 required)
4. **Never corn** — incompatible with hydroponics

## Standard Layouts

### Sun Lamp Farm (soil, roofed)
- 1 sun lamp: 2,900W
- ~100 growing tiles (on natural soil)
- 1-2 heaters (cold biomes): 100-200W each
- 1 cooler (warm biomes): 200W
- **Total**: ~3,100-3,500W
- **Feeds**: ~5-6 colonists (rice or corn on regular soil)
- **Advantage**: crops survive power outages (just stop growing)

### Hydroponics Bay
- 1 sun lamp: 2,900W
- 24 hydroponics basins: 24 × 70W = 1,680W
- 96 growing tiles (24 basins × 4 tiles)
- **Total**: ~4,580W
- **Feeds**: ~8-10 colonists (rice)
- **Cost**: 2,400 Steel + 24 Components + 40 Steel (lamp)
- **Risk**: total crop loss on power failure

### Hybrid Setup (recommended)
- 1 sun lamp over natural soil (backup food, can grow corn)
- 1 sun lamp over hydroponics (high-output rice)
- If power fails, soil crops survive while hydroponics die
- Redundancy prevents total food collapse

## Power Failure Risk

| Setup | On Power Loss |
|-------|--------------|
| Regular indoor (sun lamp + soil) | Crops survive, stop growing |
| Hydroponics | **ALL CROPS DIE instantly** |

### Mitigation
- Maintain battery bank (600 Wd per battery)
- 4,580W hydroponics bay → one battery lasts ~3.1 hours
- Keep 4+ charged batteries for overnight coverage
- Backup wood-fired generator (1,000W, no research needed)
- Consider a switch-isolated battery bank dedicated to food production

## Temperature Management

### Cold Biomes
- Roofed area + heaters keep indoor farms warm
- Heaters: 100W each, target 10-42C (optimal growth range)
- Double-wall the growing room for insulation
- Sun lamp produces 3 heat/sec — helps in cold

### Warm Biomes
- Sun lamp heat can overheat enclosed growing rooms
- Add cooler(s) if temp exceeds 42C (growth slows) or 58C (growth stops)
- Consider leaving growing room unroofed if biome allows (no rain damage to crops, just to basins)

## When to Use Indoor Farming

| Situation | Setup |
|-----------|-------|
| Cold biomes (tundra, ice sheet) | Mandatory — no outdoor growing season |
| Boreal forest | Sun lamp farm for winter months |
| Toxic fallout | Indoor crops are unaffected |
| Volcanic winter | Reduced light kills outdoor crops; indoor is fine |
| Year-round food security | Supplement outdoor farming for winter stockpiling |
| Blight protection | Indoor crops can still get blight, but isolation helps |
| Maximum output | Hydroponics rice: highest nutrition/tile/day in the game |
