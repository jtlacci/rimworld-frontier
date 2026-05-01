# Shooting and Accuracy

Ranged combat accuracy is determined by a chain of multipliers. Small differences compound exponentially over distance.

## Core Formula

```
Hit Chance = Shooter Accuracy x Weapon Accuracy x Target Size x Cover Modifier x Weather Modifier
```

## Shooter Accuracy (Per-Tile Exponential Decay)

```
Effective Accuracy = (Per-Tile Accuracy) ^ Distance
```

| Shooting Skill | Per-Tile Accuracy |
|---------------|-------------------|
| 0 | 89.0% |
| 5 | 94.5% |
| 10 | 97.0% |
| 15 | 98.2% |
| 20 | 99.0% |

Small per-tile differences are massive at range:
- 99% at 32 tiles = 0.99^32 = **72.5%**
- 97% at 32 tiles = 0.97^32 = **38.0%**
- 89% at 32 tiles = 0.89^32 = **2.6%**

### Skill Modifiers

| Modifier | Effect |
|----------|--------|
| Careful Shooter trait | +5 effective skill |
| Trigger-Happy trait | -5 effective skill (but fires 50% faster) |
| Gunlink (Royalty) | +3 |
| Shoot Frenzy inspiration | +8 |
| Shooting Specialist (Ideology) | +7 |

## Cover Mechanics

| Cover Type | Cover % |
|-----------|---------|
| Walls / Doors | **75%** |
| Sandbags / Barricades | **55%** |
| Stone Chunks | **50%** |
| Trees | **25%** |
| Bushes | **20%** |

### Directional Cover
Cover effectiveness depends on angle between shooter and cover:
- < 15 degrees: **100%** effective
- 15-40 degrees: 80-60% effective
- 40-65 degrees: 40-20% effective
- > 65 degrees: **0%** (flanked — cover useless)

## Weather Modifiers

| Weather | Accuracy |
|---------|---------|
| Clear | 100% |
| Rain / Snow | 80% |
| Fog | **50%** |
| Blind Fog | 50% + range capped to 23 tiles |

Darkness does NOT affect accuracy (removed in early development).

## Miss Mechanics

- Missed shots: 50% hit nothing, 50% hit another target in the area
- **Friendly fire safe zone**: pawns within 5 tiles cannot be hit by friendly fire
- Lower accuracy = wider miss radius (up to 10 tiles at 2% accuracy)

## Target Size

- Humans: 1.0 (clamped range: 0.5 to 2.0)
- Small animals: 0.5
- Elephants/Thrumbos: 2.0

## Turret Stats

### Mini-Turret
- Damage: 12/shot, 2-burst, DPS 4.86
- Range: 28.9, Accuracy: 77/70/45/24%
- Cost: 70 steel + 30 stuff + 3 comp, 80W
- Barrel: 60 rounds (rearm: 80 steel)
- Explodes at low HP (50 dmg, 3.9 tile radius)

### Autocannon Turret
- Damage: 27/shot, 3-burst, DPS 19.92
- Range: 32.9 (min 8.9), HP: 380
- Cost: 350 steel + 40 plasteel + 6 comp, 150W
- Barrel: 90 rounds (rearm: 180 steel)

### Uranium Slug Turret
- Damage: 55/shot, DPS 13.75, **82% AP**
- Range: 45.9, **95% long-range accuracy**
- Cost: 300 steel + 30 plasteel + 60 uranium + 6 comp

### Turret Spacing
Keep **4+ tiles apart** to prevent chain explosions. Place walls around back/sides.

## Traps

### Spike Trap Damage by Material

| Material | Total Damage | AP |
|----------|-------------|-----|
| Wood | 40 | 12% |
| Granite | 65 | 19.5% |
| Steel | 100 | 30% |
| Uranium | 110 | 33% |
| Plasteel | 110 | 33% |

Trigger chances: enemies 100%, colonists 0.5%, visitors 0%.

Single-use — destroyed after triggering. Place in single-file corridors where raiders can't path around them.

## Mortar

- Range: 29.9-500 tiles, Miss radius: 9 tiles base
- Cooldown: 28 sec, Barrel: 20 shots
- **HE shell**: 50 bomb damage, 2.9 blast radius
- **Incendiary**: 10 flame, 2.9 radius (2 mortars shut down a siege camp)
- **EMP**: 50 EMP, 8.9 radius (stuns mechs)
- **Antigrain**: 550 damage, 14.9 radius (extremely rare)
