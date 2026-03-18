# Mission: Build a Home

## Objective
Build the most impressive colony possible in 3 in-game days. Survival is trivially easy — you have 12 survival packs, abundant resources, and pre-researched furniture. Focus entirely on construction quality.

## Success Criteria
- At least 3 enclosed rooms (bedroom per colonist or barracks + dining + workshop)
- Average room impressiveness >= 30
- Every room has: flooring, lighting, furniture
- At least 2 sculptures placed
- No room with negative impressiveness

## Strategy Priorities
1. Plan room layout BEFORE building — shared walls save materials
2. Build walls + doors first to enclose rooms
3. Floor EVERY room (bare soil = negative impressiveness)
4. Light EVERY room (TorchLamp minimum)
5. Furniture: beds need end tables + dressers, dining needs table + chairs
6. Sculptures are the highest-impact beauty item — place one per room
7. Keep rooms CLEAN — assign cleaning priority 2+
8. Use Steel for walls (better looking than wood)

## What Doesn't Matter
- Food production — you have 12 packs, just eat those
- Research — ComplexFurniture and Stonecutting already done
- Hunting — only if colonists have nothing to build

## Scoring (custom rubric)
| Metric | Weight | How |
|--------|--------|-----|
| avg_impressiveness | 30 | Average across all rooms (30+ = 1.0) |
| room_count | 20 | Enclosed rooms with role (3+ = 1.0) |
| avg_beauty | 15 | Colony beauty average (1.0+ = 1.0) |
| sculptures | 15 | Sculptures placed (2+ = 1.0) |
| flooring | 10 | % of rooms with flooring |
| no_negative_rooms | 10 | 1.0 if no room has impressiveness < 0 |
