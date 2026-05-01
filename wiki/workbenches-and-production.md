# Workbenches and Production

Production buildings transform raw materials into useful items. Each workbench has specific recipes and requirements.

## Workbench Summary

| Workbench | Cost | Power | Size | Research | Key Products |
|-----------|------|-------|------|----------|--------------|
| Crafting spot | Free | None | 1x1 | None | Clubs, knives, bows, tribalwear |
| Art bench | 75 stuff + 50 steel | None | 3x1 | None | Sculptures |
| Stonecutter's table | 75 stuff + 30 steel | None | 3x1 | None | Stone blocks (25 per chunk) |
| Brewery | 120 wood + 30 steel | None | 3x1 | None | Wort |
| Fermenting barrel | 30 wood + 10 steel | None | 1x1 | None | Beer (6-day ferment) |
| Fueled stove | Wood-fueled | None | 3x1 | None | Meals, pemmican |
| Butcher table | — | None | 3x1 | None | Butcher creatures |
| Hand tailor bench | 75 stuff + 50 steel | None | 3x1 | None | Apparel (50% speed) |
| Fueled smithy | Wood-fueled | None | 3x1 | None | Melee weapons, bows |
| Electric stove | 80 steel + 2 comp | 350W | 3x1 | Electricity | Meals, survival meals |
| Electric tailor bench | 75 stuff + 50 steel + 2 comp | 120W | 3x1 | Electricity + Complex Clothing | All apparel |
| Electric smithy | 100 steel + 3 comp | 210W | 3x1 | Electricity | Melee weapons, bows |
| Electric smelter | 170 steel + 2 comp | 700W | 3x1 | Electricity | Smelt slag/weapons/apparel |
| Drug lab | 50 stuff + 75 steel + 2 comp | Yes | 3x1 | Drug Production | Drugs, medicine |
| Machining table | 150 steel + 5 comp | 350W | 3x1 | Machining | Guns, shells, flak armor |
| Biofuel refinery | 150 steel + 3 comp | 170W | 3x2 | Biofuel Refining | Chemfuel |
| Fabrication bench | 200 steel + 12 comp + 2 adv comp | 250W | 5x2 | Fabrication | Components, charge weapons, power armor, bionics |

## Work Speed Modifiers

| Modifier | Effect |
|----------|--------|
| Tool cabinet (adjacent) | +6% each, max 2 = **+12%** |
| Crafting/butcher spot | x0.50 (half speed) |
| Unpowered electric bench | Stops working |
| Temperature < 10C | x0.70 |
| Outdoors | x0.90 |

Always place tool cabinets adjacent to workbenches for the free +12% speed.

## Key Production Chains

### Food
```
Raw food → Stove → Simple/Fine/Lavish meal
Corpse → Butcher table → Meat + Leather → Stove → Meals
```

### Beer
```
Hops (harvest) → Brewery (25 hops → 5 wort) → Fermenting barrel (25 wort → 25 beer, 6 days)
Temperature must stay 7-32C during fermentation
```

### Drugs & Medicine
```
Psychoid leaves → Drug lab → Flake (4 leaves) or Yayo (8 leaves)
3 Cloth + 1 Herbal med + 1 Neutroamine → Drug lab → Medicine
```

### Chemfuel
```
70 wood → Biofuel refinery → 35 chemfuel
```

### Smelting & Recycling
```
Steel slag chunk → Smelter → 15 steel
Any weapon/apparel → Smelter → 25% of original materials
```
Items below 60% HP: smelting yields more than selling. Above 90%: selling is better.

### Advanced (Late Game)
```
12 steel → Fabrication bench → Component
1 comp + 50 steel + 20 plasteel → Advanced component
50 plasteel + 2 adv comp → Charge rifle
100 plasteel + 20 uranium + 4 adv comp → Marine armor
```

## Recommended Build Order

1. Butcher table + stove (food security)
2. Stonecutter's table (blocks for walls, floors)
3. Tailor bench (clothing before cold snap)
4. Smithy (melee weapons)
5. Machining table (guns + flak armor)
6. Drug lab (medicine production)
7. Fabrication bench (late-game gear)

## Crafting Skill Assignments

| Task | Min Skill | Why |
|------|-----------|-----|
| Stonecutting | Any | No quality system |
| Drug production | Any | No quality on drugs |
| Simple meals | 6+ Cooking | Food poisoning drops sharply |
| Weapons/armor | 10+ Crafting | 56% Good+, worth the materials |
| Grand sculpture | 15+ Artistic | High material cost, quality matters |
| Marine armor | 15+ Crafting | Can't waste 100 plasteel on Poor quality |

**Bulk (4x) recipes** save 50%+ walking time — always prefer bulk where available.
