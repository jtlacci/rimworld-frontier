# Health and Medicine

Injury management prevents colonist death and keeps the workforce active.

## Tend Quality Formula

1. **Base** = Doctor's Medical Tend Quality × Medicine Potency
2. **Offsets**: +10% hospital bed, +7% vitals monitor
3. **Self-tend**: ×0.70
4. **Randomize**: ×0.75 to ×1.25
5. **Clamp** to [0%, medicine max tend quality]

**Does NOT affect tend quality**: light level, room cleanliness, indoors vs outdoors. Those affect surgery and infection instead.

### Doctor Skill → Tend Quality

| Skill | 0 | 3 | 5 | 8 | 10 | 15 | 20 |
|-------|---|---|---|---|----|----|-----|
| Quality | 20% | 50% | 70% | 100% | 110% | 135% | 155% |

## Medicine Types

| Medicine | Potency | Max Tend | Avg Quality (Skill 8) | Cost |
|----------|---------|----------|----------------------|------|
| None (doctor care) | 30% | 70% | ~24% | Free |
| Herbal medicine | 60% | 70% | ~48% | Harvest healroot |
| Industrial medicine | 100% | 100% | ~80% | 3 Cloth + 1 Herbal + 1 Neutroamine |
| Glitterworld medicine | 160% | 130% | ~100% | Trade only |

**Rule of thumb**: Use herbal for minor injuries. Save industrial for surgery and infections. Glitterworld for emergencies only.

## Infection

### When it starts
- Cuts, bites, burns, frostbite can become infected (bruises/cracks cannot)
- Infection roll happens 4-12 minutes after wound
- Base chance: 15-30% depending on wound type

### Infection chance modifiers
- **Tend quality**: 85% multiplier at 0% quality → 5% at 100% quality
- **Room cleanliness**: sterile tile room = 32% multiplier; clean floor = 50%; outdoors = 100%
- Animals: 20% of colonist's infection chance

### Timeline
- **Untreated**: death in ~1.19 days
- **100% immunity gain speed**: immune in ~1.55 days
- **Minimum tend quality to survive**: ~15% (resting colonist)
- Treatment slows severity progression (up to -0.53/day at 100% quality)

### Infection stages

| Stage | Severity | Symptoms |
|-------|----------|----------|
| Minor | 0-32% | Pain +5% |
| Major | 33-77% | Pain +8% |
| Extreme | 78-86% | Pain +12%, Consciousness -5% |
| Critical | 87-99% | Pain +85%, unconscious |
| **Death** | 100% | Pawn dies |

### Emergency options
- Amputate infected body part (instant cure, loses part)
- Cryptosleep casket (freezes progression)
- Healer mech serum (instant cure)

## Surgery Success Chance

```
Success = Surgeon SSC × Bed Factor × Medicine Potency × Operation Multiplier
```
**Hard capped at 98%.**

### Reaching 98% cap
- Medical 8 + lit clean room + Normal hospital bed + industrial medicine = cap
- Medical 11 + lit clean room + regular bed + industrial medicine = cap

### Bed surgery factor

| Bed Type | Base SSC | + Vitals Monitor |
|----------|----------|-----------------|
| Regular bed | ×1.00 | N/A |
| Hospital bed (Normal) | ×1.10 | ×1.15 |
| Hospital bed (Excellent) | ×1.21 | ×1.27 |

### Room modifiers on surgery
- **Cleanliness**: 1.0 at 0, 1.018 for sterile, minimum 0.6 at -5 or outdoors
- **Light**: penalty below 50% light at bed head (×0.75 in darkness)
- **Outdoors**: ×0.85 additional penalty

## Blood Loss

| Stage | Blood Lost | Consciousness |
|-------|-----------|---------------|
| Minor | ≥15% | -10% |
| Moderate | ≥30% | -20% |
| Severe | ≥45% | -40% |
| Extreme | ≥60% | Max 10% (unconscious) |
| **Death** | 100% | — |

- Recovery: 33.3% blood/day (stops while still bleeding)
- Heart wounds bleed ×5, neck wounds ×4
- **Tending immediately stops ALL bleeding** regardless of quality

## Immunity Gain Speed

Multiplicative factors:

| Factor | Effect |
|--------|--------|
| Blood filtration | 50% importance (missing kidney = 75%) |
| Fed/hungry | 100% fed, 90% urgently hungry, 70% starving |
| Rest | 100% rested, 80% exhausted |
| Resting in bed | +10% while sleeping |
| Regular bed | ×1.07 |
| Hospital bed | ×1.11 |
| Hospital bed + vitals monitor | ×1.13 |
| Age 54+ | Decreases (90% at 79, 50% at 120+) |

## Hospital Design

### Sterile Tile
- Cleanliness +0.6/tile (highest non-DLC floor)
- 60% normal cleaning time (faster to clean)
- Beauty -1 (don't use in bedrooms)
- Cost: 3 Steel + 12 Silver per tile
- Research: Sterile Materials (600 pts)

### Hospital Bed
- +10% tend quality offset, +10% surgery SSC
- ×1.11 immunity gain speed, +14 HP/day healing (vs +8 regular bed)
- Research: Hospital Bed (1200 pts, requires Microelectronics + Sterile Materials + Complex Furniture)
- **Metallic materials only** (not wood/stone)

### Vitals Monitor
- +7% tend quality, +5% surgery SSC, +2% immunity gain
- 1 monitor serves up to 8 adjacent hospital beds
- Only works with hospital beds (not regular beds marked medical)
- Power: 80W. Research: Vitals Monitor (2500 pts)

### Optimal hospital room
1. Sterile tile throughout
2. Hospital beds (Normal+ quality)
3. Vitals monitor adjacent (1 per 8 beds)
4. Well-lit (50%+ at bed head for surgery)
5. High-priority cleaning assigned
6. No workbenches (keeps "Hospital" role)

## Healing Rates

| Source | HP/Day |
|--------|--------|
| Base (all pawns) | 8 |
| Sleeping on ground/spot | +4 |
| Sleeping in bed | +8 |
| Sleeping in hospital bed | +14 |
| Tend quality bonus | +4 to +12 (scales with quality) |

Total example: hospital bed + 100% tend = 8 + 14 + 12 = **34 HP/day**

## Chronic Conditions

| Condition | Min Age | Effect | Cures |
|-----------|---------|--------|-------|
| Bad back | 41+ | -30% Moving, -10% Manipulation | Bionic spine, healer serum, luciferium |
| Cataracts | 49+ | -50% per eye | Bionic eye, healer serum |
| Hearing loss | 49+ | -50% per ear | Bionic ear, cochlear implant |
| Frail | 51+ | -30% Moving + Manipulation | Healer serum, luciferium |
| Artery blockage | Progressive | Heart attacks | Replace heart |
| Carcinoma | Progressive | Organ damage | Excise surgery (skill 10) |

## Prosthetics Quick Reference

| Tier | Efficiency | Examples |
|------|-----------|---------|
| Improvised (no research) | 60-80% | Peg leg, wooden hand, denture |
| Prosthetic | 50-85% | Prosthetic arm/leg/heart, cochlear implant |
| Bionic (Fabrication research) | 125% | Bionic arm/leg/eye/ear/heart/spine |
| Archotech (trade/quest only) | 150% | Archotech arm/leg/eye |
