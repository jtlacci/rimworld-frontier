# Skills and Passions

Every colonist has 12 skills that affect their work speed, quality output, and combat effectiveness.

## The 12 Skills

| Skill | Governs | Key Stats |
|-------|---------|-----------|
| Animals | Taming, training, milking, shearing | Tame chance, train chance |
| Artistic | Sculpture creation | Item quality, work speed |
| Construction | Building, deconstructing, smoothing | Speed, success chance, quality |
| Cooking | Meal prep, butchering | Speed, food poison chance |
| Crafting | Weapons, armor, clothing | Item quality, speed |
| Intellectual | Research, drug synthesis | Research speed |
| Medical | Treatment, surgery | Tend quality, surgery success |
| Melee | Hand-to-hand combat | Hit chance, dodge chance |
| Mining | Mineral extraction | Mining speed, yield |
| Plants | Sowing, harvesting | Work speed, harvest yield |
| Shooting | Ranged weapon accuracy | Per-tile accuracy |
| Social | Trade prices, recruitment | TPI (1.0%/level), conversion |

## Work Speed by Skill Level

| Skill | Stat | Lvl 0 | Lvl 10 | Lvl 20 |
|-------|------|-------|--------|--------|
| Construction | Construction Speed | 30% | 118% | 205% |
| Cooking | Cooking Speed | 40% | 100% | 160% |
| Mining | Mining Speed | 4% | 124% | 244% |
| Plants | Plant Work Speed | 8% | 123% | 238% |
| Medical | Tend Quality | 20% | 120% | 220% |

Formula: Speed = Base Factor + (Level x Per-Level Bonus)

## XP and Leveling

| Level | Cumulative XP | Daily Decay |
|-------|---------------|-------------|
| 0-9 | 0 - 45,000 | 0 |
| 10 | 55,000 | 30/day |
| 12 | 81,000 | 120/day |
| 14 | 115,000 | 360/day |
| 16 | 157,000 | 900/day |
| 18 | 207,000 | 2,160/day |
| 20 | 265,000 | 3,600/day |

Decay starts at level 10 and escalates. Level 20 requires constant work to maintain.

Daily XP cap: 4,000 per skill. Beyond cap, only 20% of XP counts.

## Passion System

| Passion | Icon | XP Multiplier | Mood While Working |
|---------|------|---------------|-------------------|
| None | (blank) | x1.00 (baseline) | +0 |
| Minor | 1 flame | ~x1.50 (with flat XP bonus) | +6 |
| Major | 2 flames | ~x2.50 (with larger flat XP bonus) | +10 |

**Critical**: Passions add a flat XP bonus per learn event on top of the base rate, making passionate colonists learn significantly faster.

## Global Learning Factor

| Source | Effect |
|--------|--------|
| Fast Learner trait | +75% |
| Great Memory trait | x0.50 skill decay |
| Slow Learner trait | -75% |
| Quick Study gene | +50% |
| Neural Supercharger | +25% |

Formula: Final = (100% + sum of offsets) x product of factors

## Construction Success

- Reaches 100% at skill 8+
- Below 8, failed construction wastes 50% of materials

## Harvest Yield (Plants skill)

- Skill 0: **60%** | Skill 5: **90%** | Skill 10: **102%** | Skill 20: **113%**
- Also affected by manipulation (30% weight) and sight (20% weight)
- Also affected by plant harvest yield stat offsets

## Critical Skill Thresholds for Agents

| Threshold | Why |
|-----------|-----|
| Cooking 9+ | Food poison chance significantly reduced (still depends on room cleanliness) |
| Construction 8+ | 100% success rate |
| Crafting 6+ | Average Normal quality (break-even on materials) |
| Crafting 10+ | Majority Good+ quality |
| Shooting 10+ | 97% per-tile accuracy |
| Medical 10+ | Reasonable tend quality for surgery |
| Plants 8+ | ~98% harvest yield (minimal loss) |
