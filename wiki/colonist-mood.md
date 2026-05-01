# Colonist Mood and Needs

Mood is the most important colonist stat. Low mood leads to mental breaks (berserk, wandering, food binge), which can cascade into colony failure.

## Mood Thresholds

- **Extreme break risk**: < 5% mood — mental break imminent
- **Major break risk**: < 15% — frequent breaks
- **Minor break risk**: < 25% — occasional breaks
- **Neutral**: 25-50% — stable, no buffs or debuffs
- **Content**: 50-75% — slight positive effects
- **Happy**: 75-100% — positive effects, inspiration possible

## Key Mood Modifiers

### Positive
| Source | Mood Bonus | How to Get |
|--------|-----------|------------|
| Impressive bedroom | +2 to +8 | Room impressiveness (see room-impressiveness.md) |
| Impressive dining room | +2 to +8 | Eat at table in impressive room |
| Impressive rec room | +2 to +8 | Joy activity in impressive room |
| Ate fine meal | +5 | Cook fine meals (meat + veg) |
| Comfortable | +1 to +6 | Good chairs, beds |
| Beautiful environment | +1 to +6 | Plant pots, sculptures, floors |
| Recreation satisfied | +3 to +10 | Varied joy activities |

### Negative
| Source | Mood Penalty | Cause |
|--------|-------------|-------|
| Ate without table | -3 | No table nearby when eating |
| Ate raw food | -7 | No cooked meals available |
| Ate nutrient paste | -4 | Using NPD (offset by reliability) |
| Disturbed sleep | -3 | Another colonist in bedroom |
| Slept on ground | -4 | No bed assigned |
| Unimpressive bedroom | -2 | Awful bedroom impressiveness |
| Colonist died | -3 (colonist), -10 (friend), -20 (spouse) | Death of colonist |
| Food poisoning | -6 | Dirty kitchen or low cook skill |

## Needs

Colonists have several needs that affect mood:

- **Food**: hunger level. Below 30% = hungry debuff. 0% = starvation damage.
- **Rest**: sleep level. Below 30% = tired debuff. 0% = collapse.
- **Joy/Recreation**: need for entertainment. Variety matters — doing the same joy activity gives diminishing returns.
- **Comfort**: how comfortable their recent seating/sleeping was.
- **Beauty**: average beauty of recently visited areas.
- **Social**: filled by talking to other colonists (automatic).

## Mental Breaks

When mood drops below threshold, colonists may:
- **Wander sad** — waste time walking around (minor)
- **Food binge** — eat all available food (moderate)
- **Hide in room** — refuse to work (moderate)
- **Berserk** — attack colonists/structures (major)
- **Give up/leave** — abandon the colony (extreme)

## Prevention Strategy

1. **Ate without table** is the #1 preventable debuff — build table + chairs BEFORE walls
2. Cook meals ASAP — raw food penalty is -7
3. Floor and furnish bedrooms — impressiveness buffs stack
4. Provide varied recreation (horseshoes, chess, etc.)
5. Keep base clean — beauty from environment matters
6. Don't overwork — leave some joy time in schedules
