# Meals and Cooking

Cooking transforms raw food into meals that prevent mood penalties, stretch nutrition further, and avoid food poisoning from raw consumption.

## Meal Types — Complete Stats

| Meal | Nutr Out | Nutr In | Efficiency | Mood | Min Cook | Work (ticks) | Rot Days | Stack |
|------|----------|---------|------------|------|----------|-------------|----------|-------|
| Simple meal | 0.9 | 0.5 any | 180% | none | 0 | 300 (5s) | 4 | 10 |
| Fine meal | 0.9 | 0.25 meat + 0.25 veg | 180% | +5 | 6 | 450 (7.5s) | 4 | 10 |
| Lavish meal | 1.0 | 0.5 meat + 0.5 veg | 100% | +12 | 8 | 800 (13.3s) | 4 | 10 |
| Packaged survival | 0.9 | 0.3 meat + 0.3 veg | 150% | none | 8 | 450 (7.5s) | NEVER | 10 |
| Pemmican (x16) | 0.05/unit | 0.25 meat + 0.25 veg | 160% | none | 0 | 700 (11.7s) | 70 | 75 |
| Nutrient paste | 0.9 | 0.3 any (hopper) | **300%** | -4 | N/A | 0 (instant) | 0.75 | 10 |
| Kibble (x50) | 0.05/unit | 1.0 meat + 1.0 veg/hay | 125% | -12 | 0 | 450 (7.5s) | NEVER | 75 |

## Nutrition Efficiency Ranking

| Meal | Input | Output | Efficiency | Best For |
|------|-------|--------|-----------|----------|
| Nutrient paste | 0.30 | 0.90 | **300%** | Maximum food stretching, no cook needed |
| Simple meal | 0.50 | 0.90 | **180%** | Early game, single ingredient type |
| Fine meal | 0.50 | 0.90 | **180%** | Same efficiency as simple + mood bonus |
| Pemmican | 0.50 | 0.80 | **160%** | Caravans, long shelf life (70 days) |
| Packaged survival | 0.60 | 0.90 | **150%** | Never spoils, caravan emergency food |
| Lavish meal | 1.00 | 1.00 | **100%** | Maximum mood (+12), expensive |

**Key insight**: Fine meals are strictly better than simple meals if you have both meat and vegetables — same efficiency but +5 mood. Always cook fine when possible.

## Vegetarian/Carnivore Variants (Base Game)

These exist in vanilla for pawns with dietary restrictions. They use MORE ingredients for the same output.

| Variant | Input | Efficiency | vs Standard |
|---------|-------|-----------|-------------|
| Standard fine | 0.25 meat + 0.25 veg = 0.50 | 180% | — |
| Carnivore fine | 0.75 meat | 120% | 50% more input |
| Vegetarian fine | 0.75 veg | 120% | 50% more input |
| Standard lavish | 0.5 meat + 0.5 veg = 1.00 | 100% | — |
| Carnivore lavish | 1.25 meat | 80% | 25% more input |
| Vegetarian lavish | 1.25 veg | 80% | 25% more input |

**Always prefer standard mixed meals** — single-category variants waste food.

## Cooking Speed

### Formula
Cooking speed uses a score system based on skill, converted via post-process curve.

| Cooking Skill | Cooking Speed | Time for Simple Meal |
|---------------|--------------|---------------------|
| 0 | 40% | 12.5s |
| 5 | 70% | 7.1s |
| 10 | 100% | 5.0s |
| 15 | 130% | 3.8s |
| 20 | 160% (cap) | 3.1s |

Speed is also affected by manipulation (very high importance) and sight.
Global Work Speed modifiers apply (Industrious +35%, tool cabinets +6% each).

## Cooking Stations

| Station | defName | Power | Recipes | Speed | Research | Cost |
|---------|---------|-------|---------|-------|----------|------|
| Campfire | Campfire | None | Simple, pemmican | **50% cook speed** | None | 2 Wood (refuel) |
| Fueled stove | FueledStove | None | All meals | 100% | None | Wood-fueled |
| Electric stove | ElectricStove | 350W | All meals + survival meals | 100% | Electricity | 80 Steel + 2 Comp |

### Campfire vs Stove

| Aspect | Campfire | Fueled Stove | Electric Stove |
|--------|----------|-------------|----------------|
| **Cook speed** | **50%** (half speed) | 100% | 100% |
| **Available meals** | Simple, pemmican | Simple, fine, lavish, pemmican | All + packaged survival |
| **Fine/lavish meals** | **No** | Yes | Yes |
| **Power required** | None | None (wood fuel) | 350W |
| **Research required** | None | None | Electricity |
| **Heat output** | Yes (doubles as heater) | Yes | Minimal |
| **Outdoors** | Yes | Yes | Yes (needs conduit) |
| **Tool cabinet bonus** | Yes (+6% each) | Yes | Yes |

**Key differences**:
- Campfire is a **50% speed penalty** — a meal that takes 5s on a stove takes 10s on a campfire
- Campfire **cannot cook fine or lavish meals** — only simple meals and pemmican
- Fueled stove and electric stove have identical cooking speed — the difference is fuel vs power and that **packaged survival meals require an electric stove**
- Campfire provides significant heating — useful Day 1 before building a dedicated heater
- Both stove types accept tool cabinets (place adjacent for +6% each, max 2 = +12%)

**Day 1 strategy**: Build a campfire immediately for simple meals. Transition to a fueled stove when wood is available for construction, then electric stove after Electricity research.

## Butchering Stations

| Station | defName | Yield | Speed | Kibble/Batch | Cost |
|---------|---------|-------|-------|-------------|------|
| Butcher spot | ButcherSpot | **70%** of table | Same | 35 | Free (no materials) |
| Butcher table | TableButcher | 100% (baseline) | Same | 50 | No research required |

### Butcher Spot vs Table

| Aspect | Butcher Spot | Butcher Table |
|--------|-------------|---------------|
| **Meat/leather yield** | **70% of table** (30% loss) | 100% (baseline) |
| **Butchering speed** | Same | Same |
| **Work amount** | 450 ticks (7.5s) | 450 ticks (7.5s) |
| **Kibble per batch** | 35 | 50 |
| **Construction cost** | Free (instant) | Materials required |
| **Research required** | None | None |
| **Blood filth** | Yes | Yes (-15 cleanliness) |

**The 30% yield loss on the butcher spot is huge.** A muffalo at butcher table yields ~110 meat; at butcher spot only ~77 meat. Build a real table ASAP.

**Never place either in the kitchen** — blood filth tanks cleanliness → food poisoning.

### Effective Cook Times (at 100% cooking speed)

| Meal | Base Work | Time |
|------|-----------|------|
| Simple meal | 300 ticks | 5.0s |
| Fine meal | 450 ticks | 7.5s |
| Lavish meal | 800 ticks | 13.3s |
| Pemmican (x16) | 700 ticks | 11.7s |
| Packaged survival | 450 ticks | 7.5s |
| Butchering | 450 ticks | 7.5s |

## Food Poisoning — Full Formula

Two independent checks per cooked meal. If either triggers, the meal is poisoned.

### Check 1: Cook Skill

| Cooking Skill | Base Poison Chance |
|---------------|-------------------|
| 0 | 5.00% |
| 1 | 4.00% |
| 2 | 3.00% |
| 3 | 2.00% |
| 4 | 1.50% |
| 5 | 1.00% |
| 6 | 0.50% |
| 7 | 0.25% |
| 8 | 0.15% |
| 9-20 | 0.10% (floor) |

### Check 2: Room Cleanliness

| Kitchen Cleanliness | Additional Chance |
|--------------------|-------------------|
| -5 or worse | ~5% |
| -3.5 | ~2.5% |
| -2 or better | **0%** (this check eliminated) |
| Outdoors (no room) | 2% |

### Combined Formula
```
Final_chance = 1 - (1 - skill_chance × difficulty) × (1 - cleanliness_chance × difficulty)
```

### Difficulty Multipliers

| Difficulty | Multiplier |
|-----------|-----------|
| Peaceful | 30% |
| Community Builder | 50% |
| Strive to Survive | 100% |
| Losing is Fun | 120% |

### Food Poisoning Effects (Hediff)
Lasts ~1 day, starts at high severity and decreases:

| Phase | Pain | Consciousness | Movement | Vomit Interval |
|-------|------|---------------|----------|----------------|
| Initial (worst) | +20% | 60% | 80% | ~7.2h |
| Major | +40% | **50%** | **50%** | ~4.8h |
| Recovering | +20% | 60% | 80% | ~9.6h |

Vomiting creates filth that dirties the room further.

### Immune to Food Poisoning
- **Nutrient paste meals**: 0% always
- **Raw food**: flat 2% chance (separate from cooking)

## Butchering

### Yield Formulas
```
Base Meat = 140 × body_size × remaining_body_coverage
Base Leather = 40 × body_size × remaining_body_coverage
```
- Non-slaughtered (hunted/combat killed): ×0.66 yield
- Post-process curve boosts small animals (5 base → 14 actual)

### Butchery Efficiency by Cooking Skill

| Cooking Skill | Efficiency | At Butcher Spot |
|---------------|-----------|-----------------|
| 0 | 75% | 52.5% |
| 5 | 87.5% | 61.3% |
| 10 | 100% | 70% |
| 15 | 112.5% | 78.8% |
| 20 | 125% | 87.5% |

**Butcher spot**: 70% of table yield (30% loss), same speed. Always use a table when available.

### Butchering Speed
40% + 6% per Cooking skill level. Same as cooking speed curve.

### Common Animal Yields (approximate, slaughtered, skill 10)

| Animal | Body Size | Meat | Leather |
|--------|-----------|------|---------|
| Chicken | 0.25 | 14 | 0 |
| Hare | 0.25 | 14 | 14 |
| Deer | 1.30 | ~58 | ~19 |
| Muffalo | 2.40 | ~110 | ~40 |
| Elephant | 5.00 | ~220 | ~75 |
| Thrumbo | 4.00 | ~180 | ~60 |

## Insect Meat and Human Meat Penalties

### Insect Meat Thoughts

| Thought | Mood | Duration |
|---------|------|----------|
| Ate insect meat (raw) | -6 | 1 day |
| Ate cooked insect meat | -3 | 1 day |

Stacks with meal quality thought: fine meal with insect meat = +5 (fine) + -3 (insect) = +2 net.

### Human Meat Thoughts

| Thought | Non-Cannibal | Cannibal Trait |
|---------|-------------|---------------|
| Ate raw human meat | **-20** | **+20** |
| Ate cooked human meat | **-15** | **+15** |

### Butchering Humans

| Thought | Who | Mood | Duration | Stacking |
|---------|-----|------|----------|----------|
| I butchered humanlike | The butcher | -6 | 6 days | Stacks per corpse |
| We butchered humanlike | Colony-wide | -6 | 1 day | Does NOT stack |

**Immune**: Psychopaths, Bloodlust trait, Cannibals.

## All Food Mood Thoughts

| Thought | Mood | Duration |
|---------|------|----------|
| Ate lavish meal | +12 | 1 day |
| Ate fine meal | +5 | 1 day |
| Ate simple meal | none | — |
| Ate awful meal (nutrient paste) | -4 | 1 day |
| Ate raw food | -7 | 1 day |
| Ate kibble | -12 | 1 day |
| Ate without table | -3 | 1 day |
| Ate corpse | -12 | 1 day |
| Ate rotten food | -10 | 1 day |
| Ate insect meat (cooked) | -3 | 1 day |
| Ate insect meat (raw) | -6 | 1 day |
| Ate cooked human meat (non-cannibal) | -15 | 1 day |
| Ate raw human meat (non-cannibal) | -20 | 1 day |

## Cooking XP

| Meal | XP |
|------|-----|
| Simple | 60 |
| Fine | 110 |
| Lavish | 160 |
| Pemmican | 80 |

## Milk and Egg Production

### Milk (raw-tasty, no mood penalty eaten raw)

| Animal | Milk/Day | Nutrition/Day | Rot Days |
|--------|----------|---------------|----------|
| Cow | 14 units | 0.70 | 14 |
| Yak | 11 units | 0.55 | 14 |
| Dromedary | 9 units | 0.45 | 14 |
| Goat | 4 units | 0.20 | 14 |

### Eggs

| Type | Nutrition | Rot Days |
|------|-----------|----------|
| Chicken/Duck | 0.25 | 15 |
| Goose/Turkey/Emu | 0.50 | 15 |
| Ostrich | 0.60 | 15 |
