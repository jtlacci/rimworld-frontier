# Wealth and Raid Scaling

Colony wealth directly determines raid strength. Understanding this system is critical for survival at higher difficulties.

## Wealth Calculation

```
Storyteller Wealth = Item Wealth (100%) + Creature Wealth (100%) + Building Wealth (100%)
```

| Category | Multiplier | What Counts |
|----------|-----------|-------------|
| Items | 100% market value | All items in stockpiles, on ground, equipped by colonists |
| Creatures | 100% market value | Colonists, slaves, prisoners, tamed animals, friendly mechs |
| Buildings | 100% market value | All constructed buildings, floors, furniture, walls, turrets |

Key rules:
- **Unmined resources = zero wealth** (steel/gold in rock walls don't count until mined)
- **Rotted items** have drastically reduced value
- **Items in active caravans** do NOT count toward colony wealth
- **Floors count as buildings** (100% of market value)
- Typical healthy colonist: ~1,500-3,000 silver market value

## Raid Point Formula

```
Raid Points = (Wealth Points + Pawn Points) * Difficulty * Starting Factor * Adaptation Factor
```

Hard limits: minimum 35, maximum 10,000 points.

### Wealth Points

| Storyteller Wealth | Wealth Points |
|-------------------|---------------|
| 0 - 14,000 | 0 (free zone) |
| 14,000 - 400,000 | Linear to 2,400 (~1 point per 160 silver) |
| 400,000 - 1,000,000 | Linear to 4,200 |
| 1,000,000+ | 4,200 (cap) |

### Pawn Points (per colonist)

| Storyteller Wealth | Points Per Colonist |
|-------------------|-------------------|
| 0 - 10,000 | 15 |
| 10,000 - 400,000 | 15 to ~140 (linear) |
| 400,000 - 1,000,000 | Linear to 200 |
| 1,000,000+ | 200 (cap) |

Pawn modifiers: slave = 75%, cryptosleep = 30%, children scale by age.

### Difficulty Multiplier

| Difficulty | Multiplier |
|-----------|-----------|
| Peaceful | 0.10 |
| Community Builder | 0.30 |
| Adventure Story | 0.60 |
| Strive to Survive | 1.00 |
| Blood and Dust | 1.55 |
| Losing is Fun | 2.20 |

### Starting Factor (early game protection)

| Day | Factor |
|-----|--------|
| 0-10 | 0.7 (30% reduction) |
| 10-40 | Linear 0.7 to 1.0 |
| 40+ | 1.0 |

### Adaptation Factor (0.4 to 1.47)

- Colony doing poorly (losing colonists) → factor drops toward 0.4 → easier raids
- Colony dominating → factor rises toward 1.47 → harder raids
- Colonist death: -20 to -30 AdaptDays
- 30-day grace period at game start

### Raid Points to Raiders (approximate)

| Raider Type | Combat Power | Count at 10,000 points |
|------------|-------------|----------------------|
| Tribals | ~40 | ~250 |
| Pirates | ~100 | ~100 |
| Scythers | ~150 | ~66 |
| Centipedes | ~400 | ~25 |

### Raid Type Minimums

| Raid Type | Min Points |
|-----------|-----------|
| Basic raid | 35 |
| Mechanoid / drop pods | 300 |
| Siege | 500 |
| Sappers / breachers | 700 |

## Wealth Management Strategies

### When It Matters

Minimal impact at Strive to Survive and below. Significant at Blood and Dust (1.55x) and Losing is Fun (2.2x).

### Reduce Wealth

1. **Don't mine until needed** — ore in walls = zero wealth
2. **Let corpses rot** — fresh corpse ~250 silver, rotted ~near zero
3. **Smelt excess weapons** — recovers steel, removes weapon wealth
4. **Gift valuables to factions** — removes wealth AND improves relations
5. **Use cheap floors** — flagstone is much cheaper than carpet
6. **Limit food stockpiles** — only keep what's needed
7. **Set bills to "Do Until X"** — prevents massive stockpile accumulation
8. **Smelt unused weapons** — recovers materials and removes wealth

### Common Wealth Traps

| Trap | Why It's Bad |
|------|-------------|
| Hoarding silver | Pure wealth, no defensive value |
| Gold/jade sculptures | Thousands of silver each |
| Organ harvesting | ~3,100 silver per raider in organs |
| Mass drug production | High value sitting in storage |
| Mining everything | Ore becomes wealth the moment it's mined |
| Keeping every weapon | Dozen unused SMGs = ~4,260 silver dead weight |
| Masterwork/legendary hoarding | 2x+ normal value |

### Spend Wealth on Defense

- **Consumable weapons**: doomsday rockets (used = wealth gone, raid dispersed)
- **Turrets and walls**: directly improve defense
- **Better armor/weapons for colonists**: directly improves raid survivability
- **Artifacts**: psychic lances, animal pulsers (consumed on use)

## Practical Rules of Thumb

- ~160 silver = 1 raid point at Strive to Survive with 3 colonists
- ~20,000 silver ≈ 1 extra raider (rough estimate)
- Below 14,000 storyteller wealth: zero wealth points (free zone)
- Above 1,000,000: wealth cap reached, no point managing further
- **Colonist count scales harder than wealth** at high populations
