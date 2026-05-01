# Room Size Categories

Room size affects impressiveness and colonist comfort. Measured in interior tiles (not counting walls).

## Space Formula

```
Space = (1.4 × standable_tiles) + (0.5 × passable_only_tiles)
```

- **Standable tiles** (1.4×): empty floor, chairs, party spots
- **Passable-only tiles** (0.5×): lamps, benches, plant pots — walkable but not standable
- **Impassable** (0×): walls, columns, NPD — do not count
- **Net effect of most furniture**: each tile occupied reduces space by 0.9 (from 1.4 to 0.5)
- **Chairs are exempt** — they count as standable (1.4×), no space penalty

## Space Categories

| Space Value | Category |
|------------|----------|
| 0-12 | Cramped |
| 13-28 | Rather tight |
| 29-54 | Average-sized |
| 55-69 | Somewhat spacious |
| 70-129 | Quite spacious |
| 130-349 | Very spacious |
| 350+ | Extremely spacious |

## Tile Count → Space Value (empty rooms)

| Interior | Tiles | Space | Category |
|----------|-------|-------|----------|
| 3×3 | 9 | ~12.6 | Rather tight (barely) |
| 3×4 | 12 | ~16.8 | Rather tight |
| 4×4 | 16 | ~22.4 | Rather tight |
| 4×5 | 20 | ~28 | Rather tight (top end) |
| 5×5 | 25 | ~35 | Average-sized |
| 5×6 | 30 | ~42 | Average-sized |
| 6×6 | 36 | ~50 | Average-sized |
| 7×7 | 49 | ~69 | Somewhat spacious |
| 8×8 | 64 | ~90 | Quite spacious |

Furniture reduces these values. A 5×5 room with bed + dresser + end table + sculpture drops from ~35 to ~30 space.

## Practical Dimensions

- **Bedrooms**: 4×5 interior (20 tiles) is the sweet spot — enough for bed + furniture + sculptures while keeping room compact for impressiveness
- **Kitchens**: 3×5 or 4×5 (small = easier to keep clean = higher cleanliness stat)
- **Labs**: 4×5 or 5×5 with sterile tile (small + clean = cheap impressiveness)
- **Dining/Rec**: 7×7+ (need space for table + chairs + joy items; combined room gives both mood buffs)
- **Hospitals**: 5×6+ (need space for beds + vitals monitor + medicine stockpile)
- **Storage**: as large as needed — impressiveness doesn't matter

## Guidelines

- Don't oversize — bigger rooms need more beauty/wealth to reach the same impressiveness (due to the formula dividing by room size)
- The space soft-cap in the impressiveness formula penalizes large rooms with little content
- Rooms must be **75%+ roofed** to count as indoors
- Maximum room size: ~5,184 tiles (36 map regions)
