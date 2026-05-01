# Work Priorities

Work priorities determine what colonists do and in what order. Proper priority assignment is critical for colony efficiency.

## Priority System

- Must call `set_manual_priorities(True)` after game start — defaults to Simple mode where all priorities = 3
- **Priority 1** = highest urgency (do first)
- **Priority 2** = high
- **Priority 3** = normal (default)
- **Priority 4** = lowest (do last)
- **Priority 0** = disabled (never do this work)
- **Priority -1** = incapable (pawn cannot do this work type)

**All priority-1 work is exhausted before ANY priority-2 work.** Same-priority ties broken by left-to-right work type order.

## Work Types (exact left-to-right check order)

| # | Work Type | Skill | Description |
|---|-----------|-------|-------------|
| 1 | **Firefight** | — | Extinguish fires |
| 2 | **Patient** | — | Go to bed when injured |
| 3 | **Doctor** | Medical | Tend wounds, surgery |
| 4 | **Bed Rest** | — | Stay in bed resting |
| 5 | **Childcare** | Social | Tend to children |
| 6 | **Basic Worker** | — | Flick switches, haul urgent items |
| 7 | **Warden** | Social | Recruit/feed prisoners |
| 8 | **Handle** | Animals | Tame, train, manage animals |
| 9 | **Cook** | Cooking | Cook meals at stoves/campfires |
| 10 | **Hunt** | Shooting | Hunt designated animals |
| 11 | **Construct** | Construction | Build blueprints, repair |
| 12 | **Grow** | Plants | Sow, harvest crops, harvest wild berries |
| 13 | **Mine** | Mining | Mine designated rocks/ores |
| 14 | **Plant Cut** | Plants | Chop trees, cut designated plants |
| 15 | **Smith** | Crafting | Work at smithy |
| 16 | **Tailor** | Crafting | Work at tailoring bench |
| 17 | **Art** | Artistic | Create sculptures |
| 18 | **Craft** | Crafting | General crafting |
| 19 | **Haul** | — | Move items to stockpiles |
| 20 | **Clean** | — | Clean filth from home area |
| 21 | **Research** | Intellectual | Work at research bench |

### Skill → Work Type Mapping

| Skill | Work Types |
|-------|-----------|
| Shooting | Hunt |
| Medical | Doctor |
| Construction | Construct |
| Mining | Mine |
| Cooking | Cook |
| Plants | **Grow** (sowing + harvesting) + **Plant Cut** (trees + cutting) |
| Animals | Handle |
| Crafting | Smith + Tailor + Craft |
| Artistic | Art |
| Social | Warden + Childcare |
| Intellectual | Research |

## Priority Guidelines

### Don't set everything to 1
Colonists check work types in order and do the first available job at their highest priority. Setting everything to 1 means they always do firefight → patient → doctor → ... in fixed order, ignoring your actual needs.

### Role-based assignment
| Role | Key Priorities | Rationale |
|------|---------------|-----------|
| **Cook** | Cooking=1, Hauling=2-3 | Cook needs ingredients nearby |
| **Builder** | Construct=1, Haul=3 | Build what's queued |
| **Researcher** | Research=1-2, Cleaning=2 | One pawn per bench |
| **Hunter** | Hunt=1, Grow=2 | Hunt is Shooting skill |
| **Doctor** | Doctor=1, Warden=2 | Medical emergencies |
| **Everyone** | Firefight=1, Patient=1, Basic=2 | Safety defaults |

### Important notes
- **Growing** handles berry harvesting + crop sowing/harvesting. Set to 2 for early game foragers.
- **Plant Cut** is for chopping trees and cutting designated plants (NOT berry harvesting).
- **Hauling and Cleaning at 3-4**: low-skill tasks everyone can share.
- **Research**: only one pawn can research per bench, so assign your highest Intellectual pawn.
- **When idle**: colonists check for joy → wander/socialize → eat if hungry → sleep if tired.

## Skill-Speed Relationship

| Skill | Stat | Lvl 0 | Lvl 8 | Lvl 10 | Lvl 20 |
|-------|------|-------|-------|--------|--------|
| Construction | Construction Speed | 30% | 100% | 118% | 205% |
| Cooking | Cooking Speed | 40% | — | 100% | 160% |
| Mining | Mining Speed | 4% | — | 124% | 244% |
| Plants | Plant Work Speed | 8% | 100% | 123% | 238% |
| Intellectual | Research Speed | 8% | 100% | 123% | 238% |
| Medical | Tend Quality | 20% | 100% | 110% | 155% |

## Passions

| Passion | XP Bonus | Mood While Working |
|---------|---------|-------------------|
| None | Baseline (×1.0) | +0 |
| Minor (1 flame) | ~×1.5 (flat bonus per learn tick) | +6 |
| Major (2 flames) | ~×2.5 (larger flat bonus) | +10 |

Assign colonists to work types matching their passions for faster skill growth and mood benefits.

## Common Priority Mistakes

- **Everything at priority 1** → colonists only do first available type, never reach lower ones
- **No Grow priority** → wild berries never harvested, crops never sown
- **Manual priorities not enabled** → must call `set_manual_priorities(True)` after game start
- **Cook at same priority as builder** → cook abandons cooking to build, meals run out
- **Cleaning at 1** → colonist cleans obsessively instead of building/cooking
