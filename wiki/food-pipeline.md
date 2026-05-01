# Food Pipeline

Food management is one of the most critical early-game systems. Starvation kills colonists in ~72 hours from full, and food poisoning tanks mood and productivity.

## Colonist Nutrition Needs

- **Adults**: 1.6 nutrition/day
- **Stomach capacity**: 1.0 nutrition max
- **Eating trigger**: colonists eat at ~30% saturation (0.3 nutrition remaining)
- **Daily consumption**: ~2 simple meals OR ~32 raw food units OR ~1.78 nutrient paste meals
- **Overeating waste**: a 0.9-nutrition meal at 0.3 saturation wastes ~0.2 nutrition (max capacity 1.0)

### Starvation Timeline (from 100% saturation)

| Phase | Duration | Cumulative |
|-------|----------|-----------|
| Fed (100% → 25%) | 11.25 hours | 11.25h |
| Hungry (25% → 12.5%) | 3.75 hours | 15h |
| Ravenously Hungry (12.5% → 0%) | 7.5 hours | 22.5h |
| Malnutrition (0% → 100% severity) | ~50 hours | **~72.5h** |
| **Death** | — | **~72.5 hours total** |

### Hunger Mood Effects

| State | Saturation | Mood |
|-------|-----------|------|
| Fed | 25-100% | none |
| Hungry | 12.5-25% | -6 |
| Ravenously Hungry | 0-12.5% | -12 |
| Malnourished | 0% (severity building) | -20 to -44 |

## Food Sources

### Foraging (Day 1)
- **Berry bushes**: harvest wild berries immediately. Use `harvest(cx, cz, radius=50)`. No mood penalty eaten raw.
- **Survival meals**: from crash-landing supplies. Never spoil. Save as emergency backup.
- **Hunting**: designate animals with `hunt(animal=)`. Yields corpses — butcher immediately (meat rots in 2 days).

### Farming (Day 2+)
- **Rice**: fastest food crop (~5.5 real days). Best for early food security. defName: `Plant_Rice`
- **Potatoes**: grows in poor soil (gravel, 70% fertility). Slower but terrain-flexible. defName: `Plant_Potato`
- **Corn**: highest yield per harvest but very slow (~21 real days). Best once food is stable. defName: `Plant_Corn`
- **Strawberries**: edible raw with no mood penalty. Requires Growing skill 5. defName: `Plant_Strawberry`

### Cooking Stations
- **Campfire** (Day 1): free to build, but **50% cook speed** and only makes simple meals + pemmican. Also heats the area.
- **Fueled stove**: full speed, cooks all meal types including fine/lavish. Uses wood fuel.
- **Electric stove**: full speed, all meals + packaged survival meals. 350W, requires Electricity research.
- Campfire **cannot make fine or lavish meals** — upgrade to a stove as soon as practical.

### Cooking
- **Simple meals**: 0.5 nutrition input → 0.9 output (180% efficiency). No mood effect but removes the -7 raw food penalty.
- **Fine meals**: 0.25 meat + 0.25 veg → 0.9 output (180% efficiency). **+5 mood**. Requires Cooking skill 6.
- **Lavish meals**: 0.5 meat + 0.5 veg → 1.0 output (100% efficiency). **+12 mood**. Requires Cooking skill 8.
- **Nutrient paste**: 0.3 input → 0.9 output (**300% efficiency**). -4 mood but zero food poisoning. No cook needed.

### Butchering
- **Butcher spot** (Day 1): free, instant. But **30% yield loss** compared to table.
- **Butcher table**: full yield, no research required. Build one as soon as resources allow.
- **Never butcher in the kitchen** — blood filth tanks cleanliness → food poisoning.

## Spoilage Times (unrefrigerated, >10C)

| Food Type | Shelf Life | Strategy |
|-----------|-----------|----------|
| Corn (raw) | 60 days | Longest-lasting crop — store freely |
| Rice (raw) | 40 days | Store indoors |
| Potatoes (raw) | 30 days | Store indoors |
| Strawberries (raw) | 14 days | Eat early or refrigerate |
| Raw meat (all types) | **2 days** | Butcher + cook IMMEDIATELY |
| Milk | 14 days | Edible raw (no mood penalty) |
| Eggs | 15 days | Cook or refrigerate |
| Simple/Fine/Lavish meals | 4 days | Cook small batches |
| Pemmican | 70 days | Great for caravans and pre-freezer |
| Nutrient paste meal | **0.75 days (18h)** | Consumed on-demand, rarely stored |
| Packaged survival meals | **Never** | Emergency reserve |
| Kibble | **Never** | Animal feed (humans get -12 mood) |

### Temperature and Rot

| Temperature | Rot Rate | Effect |
|-------------|----------|--------|
| ≤ 0C | **Stopped** | Food preserved indefinitely |
| 1C | x0.1 | 10x longer shelf life |
| 5C | x0.5 | 2x longer shelf life |
| 10C+ | x1.0 | Normal rate (heat does NOT accelerate beyond this) |

**Freezing does NOT affect nutrition.** Thawed food is identical to fresh.
Recommended freezer: **-1C to -5C** (saves cooler power; colder is unnecessary).

## Food Poisoning

Two independent checks — if either triggers, the meal is poisoned.

### Cook Skill Check

| Cooking Skill | Poison Chance |
|---------------|---------------|
| 0 | 5.00% |
| 3 | 2.00% |
| 5 | 1.00% |
| 7 | 0.25% |
| 9+ | 0.10% (floor) |

### Room Cleanliness Check

| Cleanliness | Additional Chance |
|-------------|-------------------|
| -5 or worse | ~5% |
| -3.5 | ~2.5% |
| -2 or better | **0%** (check eliminated) |
| Outdoors (no room) | 2% |

### Prevention
- Dedicated small kitchen — easy to clean, keep cleanliness ≥ -2
- **Never butcher in the kitchen** — blood filth = -10 cleanliness per splat
- Assign your best cook (Cooking 9+ = 0.1% base chance)
- Sterile tile floors (+0.6 cleanliness per tile)
- **NPD completely bypasses food poisoning** — 0% always

### Food Poisoning Effects
Lasts ~1 day. Worst phase: 50% consciousness, 50% move speed, periodic vomiting. Vomit creates filth that further dirties rooms.

## Meal Preference Order

Colonists eat the tastiest valid food available:

1. **Lavish meal** (+12 mood)
2. **Fine meal** (+5 mood)
3. **Simple meal** / Packaged survival / Pemmican (no mood effect)
4. **Nutrient paste** (-4 mood)
5. **Raw tasty** — berries, milk, insect jelly (no mood penalty)
6. **Raw food** (-7 mood)
7. **Kibble** (-12 mood)

No variety bonus exists — colonists don't care about eating the same meal type repeatedly.

## Bill Management

- `add_bill(workbench, recipe, count=)` — add a crafting bill
- Use "until X" limits to prevent overproduction and waste
- Butcher bills should be "do forever" — corpses rot in 2 days
- Cook bills should be "until 10" or similar — meals spoil in 4 days
- Bulk (4x) recipes save walking time — always prefer when available
- `add_cooking_bills()` helper manages this automatically

## Storage

- **Pre-refrigeration**: raw crops keep for weeks indoors. Cook meat immediately — never stockpile raw meat unrefrigerated.
- **Post-refrigeration**: dedicated freezer room with cooler(s), double-walled for insulation. Target -1C to -5C. Store meals and raw meat.
- **Medicine does not spoil** — no need to refrigerate.
- Use `set_stockpile_filter` to control what goes where. Don't let food rot in unrefrigerated general storage.

## Planning Rules of Thumb

| Situation | Crop Tiles Per Colonist |
|-----------|------------------------|
| Year-round outdoor growing | ~20 tiles |
| Seasonal growing (winter) | 30-40 tiles |
| Hydroponics (rice) | ~2.6 basins (~10 tiles) |

| Colony Size | Daily Nutrition Need | Simple Meals/Day |
|-------------|---------------------|------------------|
| 3 colonists | 4.8 | 6 |
| 6 colonists | 9.6 | 11 |
| 10 colonists | 16.0 | 18 |
