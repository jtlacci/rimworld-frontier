# Caravans

Caravans let you trade at faction bases, attack settlements, and explore the world map.

## Forming a Caravan

1. Select colony on world map → "Form caravan"
2. Choose pawns, animals, prisoners
3. Select items from stockpiles
4. Colonists gather at hitching spot, pack animals load supplies
5. Travel to map edge and exit

At least one colonist required. No pack animals = fastest formation.

## Carrying Capacity

Formula: Body size x 35 kg

| Carrier | Capacity |
|---------|----------|
| Human | 35 kg |
| Alpaca | 35 kg |
| Donkey | 49 kg |
| Yak | 73.5 kg |
| Dromedary | 73.5 kg |
| Muffalo | 84 kg |
| Bison | 84 kg |
| Horse | 84 kg |
| Elephant | 140 kg |

## Travel Speed

```
Speed = (13.6 x Mount Multiplier x Mass Multiplier) / Terrain Difficulty
```

Schedule: move 06:00-22:00, mandatory rest 22:00-06:00.

### Mount Multipliers (need 1 mount per human)

| Mount | Speed Mult |
|-------|-----------|
| Donkey/Dromedary/Elephant | 1.3x |
| Horse/Thrumbo | 1.6x |

### Terrain Difficulty

| Terrain | Difficulty |
|---------|-----------|
| Forest, Desert, Tundra, Boreal | 1.0 |
| Ice Sheet (flat) | 1.5 |
| Small Hills | +0.5 to 1.0 |
| Large Hills | +1.5 to 2.0 |
| Mountains | +3.0 to 4.5 |
| Swamps | 4.0 |

Roads halve movement difficulty. Below -17C, difficulty increases sharply.

### Reference Speeds

| Setup | Tiles/Day |
|-------|----------|
| No mount, 8hr sleep | 9.07 |
| No mount, no sleep | 13.6 |
| Slow mount (1.3x) | 11.79 |
| Fast mount (1.6x) | 14.51 |

## Food on the Road

- Consumption: **1.6 nutrition/pawn/day**
- Foraging: 0.09 nutrition/day per Plants skill level
- Grazing animals refill hunger in grazable biomes
- Carnivorous/omnivorous animals **cannot hunt** while caravanning

| Food Type | Shelf Life | Best For |
|-----------|-----------|----------|
| Simple meals | 4 days | Short trips |
| Berries | 14 days | Medium trips |
| Pemmican | 70+ days | Long trips |
| Packaged survival meals | Never | Any distance |

## Caravan Events

- **Ambush**: defeat attackers to leave. 24hr loot window after victory.
- **Manhunter ambush**: animal pack, no fleeing.
- **Pirate demand**: surrender items or fight.
- **Friendly encounter**: trade with passing caravans.

## Faction Relations

### Goodwill Thresholds
| Status | Range |
|--------|-------|
| Hostile | Below 0 |
| Neutral | 0 to 75 |
| Allied | Above 75 |

### Improving Relations
| Action | Goodwill |
|--------|---------|
| Fulfill trade request quest | +12 |
| Return prisoners | +12 to +15 |
| Destroy mutual enemy base | +20 |
| Trading (per 500 silver) | +1 |
| Sending gifts | +1 per 40-160 silver |

### Damaging Relations
| Action | Goodwill |
|--------|---------|
| Arrest visitor | Set to -75 (instant hostile) |
| Strip downed pawn | -40 |
| Remove organs | -20 |
| Kill visitor | -5 per death |

Natural goodwill decay: 0.4/day above faction's natural range.

## Caravan Checklist

- Best Social pawn as negotiator
- Enough pemmican/survival meals for round trip
- Pack animals (muffalo 84kg, elephant 140kg)
- Mounts for all humans (horses for 1.6x speed)
- Medicine for emergencies
- Weapons and armor for ambush defense
- High-value, low-weight trade goods (flake, yayo, devilstrand clothes)
- Avoid routes through swamps/mountains (4.0+ difficulty)
