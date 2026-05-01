# Crops and Farming

Farming is the primary long-term food source. Crop selection, soil quality, and growing skill all affect output.

## Food Crops

| Crop | Base Days | Real Days | Yield | Nutr/Harvest | Fert. Sens. | Min Skill | Hydro | Sow/Harvest Work |
|------|-----------|-----------|-------|-------------|-------------|-----------|-------|-------------------|
| Rice | 3 | 5.54 | 6 | 0.30 | 1.0 (high) | 0 | Yes | 170/200 ticks |
| Potato | 5.8 | 10.71 | 11 | 0.55 | 0.4 (low) | 0 | Yes | 170/200 ticks |
| Corn | 11.3 | 20.86 | 22 | 1.10 | 1.0 (high) | 0 | **No** | 170/200 ticks |
| Strawberry | 4.6 | 8.49 | 8 | 0.40 | 1.0 (high) | 5 | Yes | 170/200 ticks |
| Nutrifungus | 6 | 11.08 | 11 | 0.55 | 0.15 (very low) | 0 | Yes | 170/200 ticks |

All raw food crops produce items at 0.05 nutrition per unit.
"Base Days" = game XML value. "Real Days" = actual calendar days accounting for plant rest period.

## Drug Crops

| Crop | Base Days | Real Days | Yield | Fert. Sens. | Min Skill | Hydro |
|------|-----------|-----------|-------|-------------|-----------|-------|
| Hop plant | 5 | 9.23 | 8 | 0.7 | 3 | Yes |
| Smokeleaf | 7.5 | 13.85 | 9 | 1.0 | 4 | Yes |
| Psychoid | 9 | 16.62 | 8 | 0.4 | 6 | Yes |

## Textile/Utility Crops

| Crop | Base Days | Real Days | Yield | Fert. Sens. | Min Skill | Hydro | Special |
|------|-----------|-----------|-------|-------------|-----------|-------|---------|
| Cotton | 8 | 14.77 | 10 | 1.0 | 0 | Yes | — |
| Devilstrand | 22.5 | 41.54 | 6 | 1.0 | 10 | **No** | Best textile |
| Healroot | 7 | 12.92 | 1 | 1.0 | 8 | Yes | 800 tick sow, 400 tick harvest |
| Haygrass | 7 | 12.92 | 18 | 0.6 | 0 | **No** | Animal feed only |

## Soil Types and Fertility

| Terrain | Fertility | Notes |
|---------|-----------|-------|
| Hydroponics basin | 280% | Requires power (70W), research |
| Rich soil | 140% | Found naturally, cannot be created |
| Normal soil | 100% | Standard farmland |
| Marshy soil | 100% | Full fertility but slow movement |
| Stony soil / Gravel | 70% | Common in mountainous areas |
| Sand | ~10% | Nearly unusable |
| Mud / Ice / Floors | 0% | Cannot plant |

### Fertility Formula
**Growth Rate Factor** = 1 + (Fertility - 1) × Fertility Sensitivity

### Real Grow Days by Soil Type

| Crop | Gravel (70%) | Soil (100%) | Rich Soil (140%) | Hydroponics (280%) |
|------|-------------|-------------|-------------------|---------------------|
| Rice | 7.91 | 5.54 | 3.96 | 1.98 |
| Potato | 12.17 | 10.71 | 9.23 | 6.23 |
| Corn | 29.80 | 20.86 | 14.90 | N/A |
| Strawberry | 12.13 | 8.49 | 6.06 | 3.03 |
| Healroot | 18.46 | 12.92 | 9.23 | 4.61 |

Examples on rich soil (140%):
- Rice (sens 1.0): **40% faster** → 3.96 days
- Potato (sens 0.4): **16% faster** → 9.23 days
- Nutrifungus (sens 0.15): **6% faster** — almost no benefit

On gravel (70%):
- Rice: **30% slower** → 7.91 days
- Potato: only **12% slower** → 12.17 days (why potatoes are best for poor soil)

**Fertility only affects growth speed, NOT harvest yield.** Yield depends on Growing skill.

## Growth Mechanics

### Plant Rest Period
- Plants rest from **hour 19 (7 PM) to hour 6 (6 AM)** = 11 hours rest
- Active growing: **13 hours/day** = **54.167%** of the day
- Conversion: Real Days = Base Days / 0.5417
- Universal — applies even under sun lamps indoors

### Temperature Thresholds

| Temperature | Growth Effect |
|-------------|--------------|
| ≤ 0C | **Growth stops** |
| 0-6C | Growth slows linearly (at 3C = 50% speed) |
| 6-42C | **Optimal range** (100% speed) |
| 42-58C | Growth slows linearly (at 50C = 50% speed) |
| ≥ 58C | **Growth stops** |
| ≤ -10C | **Most plants die** |

### Light Requirements
- Standard crops: minimum **51% light** to grow
- Nutrifungus: grows in **complete darkness**, dies on any light exposure

### Growth Stages and Early Harvest
- Plants start at **5% growth** when sown
- Harvestable at **65% growth** — but yield scales linearly from 50% (at 65%) to 100% (at 100%)
- Always wait for 100% growth unless desperate

## Growing Skill Effects

### Plant Work Speed (sowing and harvesting)
Formula: 8% base + 11.5% per skill level

| Skill | Speed | Skill | Speed |
|-------|-------|-------|-------|
| 0 | 10% (floor) | 10 | 123% |
| 2 | 31% | 12 | 146% |
| 4 | 54% | 15 | 180.5% |
| 6 | 77% | 18 | 215% |
| 8 | 100% | 20 | 238% |

### Plant Harvest Yield

| Skill | Yield | Skill | Yield |
|-------|-------|-------|-------|
| 0 | 60% | 8 | 100% |
| 2 | 75% | 10 | 102% |
| 4 | 85% | 15 | 107% |
| 5 | 90% | 20 | 113% |

Also affected by manipulation (30% importance) and sight (20% importance). Bionic arms help.

### Minimum Sow Skill by Crop

| Skill | Crops |
|-------|-------|
| 0 | Rice, potato, corn, cotton, haygrass, nutrifungus |
| 3 | Hops |
| 4 | Smokeleaf |
| 5 | Strawberry |
| 6 | Psychoid, most trees |
| 8 | Healroot |
| 10 | Devilstrand |

## Blight

- Random event targeting domesticated crops
- Starts at **20% severity** on a random plant, spreads when reaching **28% severity**
- Spreads to same-species crops within **4-tile radius**
- Spread interval: ~12-24 hours
- **Cannot be blocked by walls** — only distance prevents spread
- Immune: trees, devilstrand, wild plants

### Prevention
- Leave **4+ tile gaps** between fields of the same crop type
- Mix different crop species in adjacent fields
- Cut blighted plants immediately — they cannot be saved
- Short-cycle crops (rice) have less exposure time than long-cycle (corn)

## Optimal Crop Selection

| Situation | Best Crop | Why |
|-----------|-----------|-----|
| Early game / emergency | Rice | Fastest harvest (5.54 days) |
| Stable colony | Corn | Highest yield/tile, least labor |
| Poor soil (gravel) | Potatoes | Low fertility sensitivity (0.4) |
| Hydroponics | Rice | Full benefit from 280% fertility |
| No freezer | Corn | 60-day raw shelf life |
| Short growing season | Rice | Fits in 6-day window vs corn's 21 |
| Drug production | Psychoid | Flake is most profitable |
| Medicine | Healroot | 1 herbal medicine per harvest, skill 8 |
| Textiles | Cotton (early), Devilstrand (late) | Devilstrand = best textile, 42-day grow |
| Animal feed | Haygrass | 18 yield per tile, dedicated animal food |

### Nutrition per Day per Tile (normal soil)

| Crop | Nutr/day/tile (raw) | Via Simple Meal | Labor Frequency |
|------|---------------------|-----------------|-----------------|
| Rice | 0.054 | 0.097 | Every 5.5 days |
| Corn | 0.053 | 0.095 | Every 20.9 days |
| Potato | 0.051 | 0.092 | Every 10.7 days |
| Strawberry | 0.047 | 0.085 | Every 8.5 days |

Rice and corn are nearly identical in nutrition/day/tile. **Corn wins on labor** (one harvest per 21 days vs 5.5). **Rice wins on risk** (shorter exposure to blight/cold snaps).

### Rich Soil Priority
1. **Corn** or **Rice** (sensitivity 1.0 = full 40% bonus)
2. **Cotton/Devilstrand** if textiles needed (sensitivity 1.0)
3. **Never waste rich soil on potatoes** (only 16% bonus)

## Colonist Food Math

- Adults consume **1.6 nutrition/day**
- Plan **~20 crop tiles per colonist** with year-round growing
- Plan **30-40 tiles** for seasonal growing (winter stockpiling)
- 25 tiles of rice on normal soil ≈ 1.36 raw nutrition/day → ~2.44 via simple meals → feeds ~1.5 colonists

## Growing Seasons by Biome

| Biome | Growing Period | Notes |
|-------|---------------|-------|
| Tropical Rainforest | Year-round | Disease risk high |
| Temperate Forest | Year-round to 20/60 days | Best beginner biome |
| Arid Shrubland | Year-round to 40/60 | Limited arable soil |
| Boreal Forest | 30/60 to 10/60 | Short seasons — use rice |
| Tundra | 20/60 to 0/60 | May have no outdoor growing |
| Ice Sheet / Sea Ice | **Never** | Indoor farming only |
