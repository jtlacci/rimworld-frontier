# Room Impressiveness

Room impressiveness is the primary driver of colonist mood buffs from rooms. It applies to bedrooms, dining rooms, rec rooms, hospitals, and labs.

## Impressiveness Formula

Four input stats: **Wealth**, **Beauty**, **Space**, **Cleanliness**.

### Step 1: Convert raw stats to base values
```
Wb = wealth / 1500
Bb = beauty / 3
Sb = space / 125
Cb = 1 + (cleanliness / 2.5)
```

### Step 2: Log compression (values outside -1 to 1)
For each base value `b`:
- If `b >= 1`: `m = 1 + ln(b)`
- If `b <= -1`: `m = -(1 + ln(-b))`
- If `-1 < b < 1`: `m = b` (unchanged)

### Step 3: Weighted combination
```
I = 65 * (Wm + Bm + Sm + Cm) / 4  +  35 * min(Wm, Bm, Sm, Cm)
```

### Step 4: Space soft-cap
```
If I > 500 * Sm:  I' = 0.25 * I + 0.75 * 500 * Sm
```
Large rooms with little content get capped hard.

### Weight breakdown
- The **minimum (worst) stat contributes 51.25%** of the final score
- Each of the other three stats contributes 16.25% each
- **One bad stat tanks the entire score.** Bottleneck order in practice: space > cleanliness > beauty > wealth.

## Impressiveness Tiers

### Bedroom mood

| Impressiveness | Tier | Mood |
|---------------|------|------|
| < 20 | Awful | **-4** |
| 20-29 | Dull | 0 |
| 30-39 | Mediocre | 0 |
| 40-49 | Decent | **+2** |
| 50-64 | Slightly impressive | **+3** |
| 65-84 | Somewhat impressive | **+4** |
| 85-119 | Very impressive | **+5** |
| 120-169 | Extremely impressive | **+6** |
| 170-239 | Unbelievably impressive | **+7** |
| 240+ | Wondrously impressive | **+8** |

### Barracks mood (much worse)

| Impressiveness | Tier | Mood |
|---------------|------|------|
| < 20 | Awful | **-7** |
| 20-29 | Dull | -5 |
| 30-39 | Mediocre | -4 |
| 40-49 | Decent | -3 |
| 50-64 | Slightly impressive | -2 |
| 65-84 | Somewhat impressive | -1 |
| 85-119 | Very impressive | **+1** |
| 120-169 | Extremely impressive | +2 |
| 240+ | Wondrously impressive | +4 |

### Dining / Rec room mood (identical scale)

| Impressiveness | Mood |
|---------------|------|
| < 40 | 0 |
| 40-49 | +2 |
| 50-64 | +3 |
| 65-84 | +4 |
| 85-119 | +5 |
| 120-169 | +6 |
| 240+ | +8 |

**Key insight**: A combined dining+rec room gives BOTH moodlets. A "Somewhat impressive" combo room = +4 dining + +4 rec = **+8 total mood**.

## What Tanks Impressiveness

- **Cleanliness**: easiest to tank — blood (-10), vomit (-15), dirt (-5) per filth item
- **Mixing room purposes**: bedroom with workbench → "workshop" role, loses bedroom mood
- **Tiny rooms**: space is the most common bottleneck; rooms under 13 space are "Cramped"
- **Unfloored cells**: 0 beauty, hurts the average
- **Stockpiles**: items on ground are ugly + cluttered

## How to Maximize

### Floor beauty values

| Floor | Beauty | Cleanliness | Cost |
|-------|--------|------------|------|
| Gold tile | +11 | +0.2 | 705 silver |
| Fine carpet | +4 | 0 | 67 silver |
| Fine stone tile | +3 | 0 | 36 silver |
| Carpet | +2 | 0 | 13 silver |
| Smooth stone | +2 | 0 | FREE (labor only) |
| Stone tile | +1 | 0 | 8 silver |
| Steel tile | 0 | +0.2 | 16 silver |
| Sterile tile | -1 | +0.6 | 24 silver |

### Furniture beauty (Normal quality)

| Item | Base Beauty |
|------|-----------|
| Grand sculpture | 400 |
| Large sculpture | 100 |
| Small sculpture | 50 |
| Dining chair | 8 |
| Dresser | 5 |
| Armchair | 4 |
| End table | 3 |
| Bed | 1 per cell |

Quality multiplies beauty: Awful x-0.1, Poor x0.5, Normal x1.0, Good x2.0, Excellent x3.0, Masterwork x5.0, Legendary x8.0.

### Wall beauty

| Material | Beauty |
|----------|--------|
| Smoothed stone | +2 |
| Marble | +1 |
| Gold | +20 |
| Silver | +6 |
| All other stone/wood/steel | 0 |

### Optimization strategy
1. Floor the entire room (stone tile +1, carpet +2, smooth stone +2 free)
2. Add sculptures (large sculptures = best beauty-per-tile ratio)
3. Keep clean — no stockpiles, no through-traffic, assign cleaning priority
4. Use marble walls for bedrooms (+1 beauty per wall segment)
5. Don't oversize — a focused 4x5 room is easier to make impressive than 8x8
6. End table + dresser next to beds for comfort bonuses

## Bedroom Optimization

### Sweet spot: 4x5 interior (20 tiles)
- Space ~28 ("Rather tight" but adequate for formula)
- Room for: bed + end table + dresser + 1-2 large sculptures
- With good+ quality sculptures, easily reaches "Very impressive" (+5 mood)

### Minimum viable bedroom (+2 mood, "Decent" 40+)
- 3x4 interior, any material
- Bed + end table + dresser
- Carpet or stone tile floor, keep clean

### Good bedroom (+5 mood, "Very impressive" 85+)
- 4x5 interior, marble or steel walls
- Good+ quality bed + end table + dresser
- 2 large sculptures (good+ quality)
- Fine carpet or fine stone tile floor
