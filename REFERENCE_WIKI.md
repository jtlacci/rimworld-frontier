# RimWorld Wiki Reference (Pre-cached)

Sourced from https://rimworldwiki.com/ so agents don't need to browse mid-session.

---

## Room Impressiveness Thresholds

| Range | Level | Bedroom/Dining/Rec Mood |
|-------|-------|------------------------|
| < 20 | Awful | −2 |
| 20–29 | Dull | 0 |
| 30–39 | Mediocre | 0 |
| 40–49 | Decent | +2 |
| 50–64 | Slightly Impressive | +3 |
| 65–84 | Somewhat Impressive | +4 |
| 85–119 | Very Impressive | +5 |
| 120–169 | Extremely Impressive | +6 |
| 170–239 | Unbelievably Impressive | +7 |
| ≥ 240 | Wondrously Impressive | +8 |

**Key formula note**: Impressiveness is a weighted geometric mean of space, beauty, wealth, and cleanliness. The lowest stat is weighted at 51.25% — one bad stat tanks the whole score. Cleanliness is the easiest to tank (dirt, blood, chunks).

## Room Size Categories

| Category | Tile Count |
|----------|-----------|
| Cramped | < 12.5 |
| Rather Tight | 12.5–29 |
| Average | 29–55 |
| Quite Spacious | 55–70 |

A 5×5 interior = 25 tiles (average). A 4×4 interior = 16 tiles (rather tight).

## Room Role Scores

| Role | Trigger | Score |
|------|---------|-------|
| Bedroom | Non-medical bed assigned to colonist | 100,000 |
| Hospital | Medical bed | 100,000 |
| Dining Room | Per table | 12 |
| Rec Room | Per entertainment item | 7 |
| Kitchen | Per stove | 28 |
| Laboratory | Per research bench | 60 |

Highest score wins. Tied → earlier priority.

---

## Wall Stats by Material

| Material | HP | Work (ticks) | Beauty | Cost |
|----------|-----|-------------|--------|------|
| Wood | 195 | 95 | 0 | 5 WoodLog |
| Steel | 300 | 135 | 0 | 5 Steel |
| Sandstone | 420 | 815 | 0 | 5 BlocksSandstone |
| Slate | 390 | 950 | 0 | 5 BlocksSlate |
| Limestone | 465 | 950 | 0 | 5 BlocksLimestone |
| Granite | 510 | 950 | 0 | 5 BlocksGranite |
| Marble | 360 | 883 | +1 | 5 BlocksMarble |
| Plasteel | 840 | 297 | 0 | 5 Plasteel |

**Takeaway**: Wood is fast but fragile/flammable. Granite is toughest stone. Marble adds beauty. Stone takes 8-10x longer to build than wood.

## Door Stats by Material

| Material | HP | Work (ticks) | Open Speed | Cost |
|----------|-----|-------------|------------|------|
| Wood | 104 | 595 | 120% | 25 WoodLog |
| Steel | 160 | 850 | 100% | 25 Steel |
| Sandstone | 224 | 4,390 | 45% | 25 BlocksSandstone |
| Granite | 272 | 5,240 | 45% | 25 BlocksGranite |
| Plasteel | 448 | 1,870 | 100% | 25 Plasteel |

**Takeaway**: Stone doors are SLOW to open (45% speed) — causes traffic jams. Use wood or steel doors even in stone buildings. Autodoors (post-research) eliminate the slowdown.

---

## Floor Types

| Floor | defName | Beauty | Cost | Work (ticks) | Flammable | Cleanliness |
|-------|---------|--------|------|-------------|-----------|-------------|
| Wood plank | WoodPlankFloor | 0 | 3 Wood | 85 | Yes (22%) | 0 |
| Stone tile | (varies by stone) | +2 | 4 Blocks | 1,100 | No | 0 |
| Flagstone | (varies by stone) | 0 | 4 Blocks | 500 | No | 0 |
| Sterile tile | SterileTile | −1 | 3 Steel + 12 Silver | 1,600 | No | +0.6 |
| Carpet | CarpetRed (etc.) | +2 | 7 Cloth | 800 | Yes (32%) | 0 |

**Takeaway**: Wood floors are fast + cheap (use for early builds). Stone tile for permanent rooms (+1 beauty, fireproof). Sterile tile for hospitals/labs only (cleanliness bonus). Carpet for beauty but fire risk.

---

## Common Furniture

| Item | defName | Size | Beauty | Comfort | Has Interaction Spot |
|------|---------|------|--------|---------|---------------------|
| Bed | Bed | 1×2 | 1 | 0.75 | Yes (foot) |
| Double Bed | DoubleBed | 2×2 | 2 | 0.75 | Yes (foot) |
| End Table | EndTable | 1×1 | 3 | — | No |
| Dresser | Dresser | 2×1 | 5 | — | No |
| Dining Chair | DiningChair | 1×1 | 8 | 0.7 | No |
| Armchair | Armchair | 1×1 | 4 | 0.8 | No |
| Stool | Stool | 1×1 | 0 | 0.5 | No |
| Table (1×2) | Table1x2c | 1×2 | 0.5 | — | No |
| Table (2×2) | Table2x2c | 2×2 | 1 | — | No |
| Table (2×4) | Table2x4c | 2×4 | 2 | — | No |
| Plant Pot | PlantPot | 1×1 | varies | — | No |
| Standing Lamp | StandingLamp | 1×1 | 0 | — | No |
| Campfire | Campfire | 1×1 | 0 | — | Yes |
| Simple Research Bench | SimpleResearchBench | 1×3 | 0 | — | Yes (front) |
| Butcher Spot | ButcherSpot | 1×1 | 0 | — | Yes |
| Electric Stove | ElectricStove | 3×1 | 0 | — | Yes (front) |
| Fueled Stove | FueledStove | 3×1 | 0 | — | Yes (front) |

**End table + dresser bonus**: When placed adjacent to a bed's head, end table gives +1 comfort; dresser gives +1 beauty to room. Both are essential for bedroom impressiveness.

---

## Material Properties (Stuff)

| Material | Flammable | Beauty Factor | Market Value Factor | Notes |
|----------|-----------|--------------|---------------------|-------|
| Wood | Yes | ×1 | Low | Fast to build, burns |
| Granite | No | ×1 | Low | Toughest stone, slow to build |
| Sandstone | No | ×1 | Low | Weakest stone, slightly faster |
| Limestone | No | ×1 | Low | Mid-tier stone |
| Marble | No | ×1.35 | Low | Beauty bonus, weakest stone HP |
| Slate | No | ×1 | Low | Mid-tier stone |
| Steel | No | ×1 | Medium | Fast to build, versatile |
| Silver | No | ×1.4 | High | Beauty bonus, expensive |
| Gold | No | ×2 | Very High | Highest beauty, very expensive |
| Plasteel | No | ×1 | High | Strongest, expensive |

**Takeaway**: For impressive rooms, marble gives beauty bonus on walls/furniture. Gold for wealth-boosting accent pieces. Stone is always preferred over wood for permanent structures (fireproof).
