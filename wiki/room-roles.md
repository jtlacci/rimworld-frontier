# Room Roles

Every enclosed room in RimWorld gets assigned a "role" based on the furniture inside. The role determines which mood buff the room's impressiveness provides.

## Role Assignment

The game assigns each room the role with the highest score. Ties broken by priority order.

### Role scores

| Role | Points | Triggering Furniture |
|------|--------|---------------------|
| **Bedroom** | 100,000 (flat) | 1 non-medical humanlike bed assigned to a colonist |
| **Barracks** | 100,100 per bed | 2+ non-medical humanlike beds |
| **Hospital** | 100,000 (flat) | Medical beds present |
| **Kitchen** | 28 per stove | Electric stove, fueled stove |
| **Laboratory** | 60 per item | Research bench, hi-tech bench, drug lab, gene assembler |
| **Workshop** | 27 per bench | Art bench, smelter, smithy, tailor bench, fabrication bench, stonecutter |
| **Dining Room** | 12 per table | Tables (1×2, 2×2, 2×4, 3×3) |
| **Rec Room** | 7 per item | Billiards, chess, TV, horseshoes, poker table, telescope |
| **Tomb** | 50 per sarcophagus | Sarcophagi |
| **Barn** | 7.6 per item | Animal beds, animal sleeping spots |
| **Storeroom** | 1 per shelf | Shelves |
| **None** | 0.99 (default) | No qualifying furniture |

### Items that do NOT affect role
Chairs, lamps, sculptures, dressers, end tables, plant pots — these are "neutral" and can go in any room without changing its role.

### Butcher table does NOT trigger Kitchen role
Safe to place a butcher table in a separate room without it competing for kitchen role.

## Critical Rules

- **Never mix sleeping and working**: a bedroom with a research bench → "Laboratory" (60 > 0), loses bedroom mood buff
- **Never put stockpiles in bedrooms**: ugly + cluttered, can change room role
- **Beds always dominate**: 100,000 score overrides almost everything
- **Tables push toward dining room**: even one table (12 pts) outweighs one rec item (7 pts)
- A room with 1 stove (28) + 1 research bench (60) = "Laboratory" (60 > 28)

## Common Room Templates

### Bedroom (4×5 interior)
- Single bed centered on back wall
- End table adjacent to bed head (+0.05 comfort, scales with bed quality)
- Dresser within 6 tiles of bed (+0.05 comfort, scales with bed quality)
- 1-2 large sculptures for beauty
- Floor the whole room (carpet or stone tile)
- One door facing corridor

### Combined Dining + Rec Room (7×7+ interior)
- Table centered, chairs on all sides
- Joy items (horseshoes, chess table, billiards) along walls
- Sculptures for beauty
- Both dining and rec mood buffs apply simultaneously
- At "Somewhat impressive" (65+): +4 dining + +4 rec = **+8 total mood**

### Kitchen (3×5 or 4×5 interior)
- Stove only — **no butcher table** (blood = -10 cleanliness per splat)
- Small room = easy to clean = high cleanliness = low food poisoning
- No stockpiles inside
- Sterile tile if available

### Laboratory (4×5 or 5×5 interior)
- Research bench only
- Sterile tile floor (after Sterile Materials research)
- No stockpiles, no other furniture
- Small + clean = cheap impressiveness
- Must be a "laboratory" room to avoid x0.80 research speed penalty

### Hospital
- Hospital beds + vitals monitor (1 monitor serves up to 8 beds)
- Sterile tile floors (cleanliness directly reduces infection chance: 32% multiplier vs 50% for regular clean floor)
- Well-lit (50%+ light at bed head for surgery)
- Keep separate from bedrooms
- Medicine stockpile nearby (Critical priority)

### Workshop
- Workbenches along walls, clear center for hauling
- Tool cabinets adjacent to benches (+6% speed each, max 2 = +12%)
- Can be larger and uglier — no mood buff for workshop impressiveness
- Input stockpile nearby for materials

## End Table and Dresser Details

### End Table
- Must be **directly adjacent** to bed head
- +0.05 base comfort (scales with BED quality, not table quality)
- Multiple end tables near same bed: **no additional effect**
- 1×1, beauty 3, 30 stuff to build
- Research: Complex Furniture

### Dresser
- Must be within **6 tiles** of bed (not necessarily adjacent)
- +0.05 base comfort (same scaling as end table)
- Multiple dressers near same bed: **no additional effect**
- Stacks with end table: end table + dresser ≈ +0.10 comfort on Normal bed
- 2×1, beauty 5, 50 stuff to build
- Research: Complex Furniture

**Key insight**: Comfort bonus scales with **bed quality**, not table/dresser quality. An awful end table next to a legendary bed gives the same comfort bonus as a legendary end table.
