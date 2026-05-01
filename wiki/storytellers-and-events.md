# Storytellers and Events

Storytellers control the pacing and type of events that hit your colony. Each has distinct scheduling patterns.

## Storyteller Comparison

| Metric | Cassandra | Randy | Phoebe |
|--------|-----------|-------|--------|
| Major threats/year | ~8.5 | ~8 (avg, highly variable) | ~4-5 |
| Predictability | High | None | High |
| Recovery time | 6 days off-phase | Random (0-13 days) | 8 days off-phase |
| Raid point variance | None | 50-150% per raid | None |

## Cassandra Classic

- **On-phase**: 4.6 days, **Off-phase**: 6 days (10.6-day cycle)
- First on-phase starts Day 11
- 1-2 major threats per on-phase (50/50 chance)
- Minimum 1.9 days between major threats
- Misc events every ~4.8 days
- Grace period: single mad animal, then single raider on Day 5

**Character**: Predictable, consistent pressure. Best for learning the game and preparing defenses on a schedule.

## Randy Random

- Events checked every 1,000 ticks (~60x/day)
- Average 1.35 events per day
- Forced major threat after 13 days without one
- Raid point multiplier: **0.5x to 1.5x** random per event
- Events start after Day 1

Event category weights:
| Category | Weight |
|----------|--------|
| Misc | 3.5 |
| Faction Arrival | 2.4 |
| Big Threat | 1.4 |
| Small Threat | 0.6 |
| Orbital Visitor | 1.1 |

**Character**: Chaotic. Can stack dangerous events or create months of peace. Randy raids can be 50% weaker OR 50% stronger than Cassandra equivalents.

## Phoebe Chillax

- **On-phase**: 8 days, **Off-phase**: 8 days (16-day cycle)
- First on-phase starts Day 13
- 1 major threat per on-phase
- 8-24 day gap between major threats
- Same raid strength as Cassandra — just less frequent

**Character**: Maximum recovery time. 50-60% fewer threats per year. Good for building-focused play.

## Event Categories

1. **Major Threats** — raids, infestations, manhunter packs, mech clusters, sieges
2. **Minor Threats** — mad animals, small raids
3. **Weather Events** — toxic fallout, volcanic winter, cold/heat snaps, flashstorms, eclipses, solar flares
4. **Positive Events** — cargo pods, trader caravans, wanderer joins, ambrosia sprouts
5. **Neutral Events** — transport pod crash, thrumbo passage, ship chunk drops

Major threats and weather events require at least Community Builder difficulty.

## Threat Event Weights

| Threat Type | Weight |
|-------------|--------|
| Standard Raid | 7.40 (42% of all major threats) |
| Infestation | 2.70 |
| Manhunter Pack | 2.00 |
| Poison Ship (Defoliator) | 2.00 |
| Psychic Ship | 2.00 |
| Mass Animal Insanity | 1.30 |

## Infestation Requirements

- Overhead mountain roof within 30 tiles of a colony structure
- Temperature above -17C
- Light levels below threshold increase probability
- **Completely avoidable** by not building under overhead mountain

## Event Cooldowns and Durations

| Event | Cooldown | Duration |
|-------|----------|----------|
| Toxic Fallout | 90 days | 2.5-10.5 days |
| Volcanic Winter | 140 days | 7.5-40 days (-7C, -30% light, -50% wildlife) |
| Flashstorm | 15 days | ~2 hours |
| Eclipse | 15 days | 0.75-1.25 days |
| Heat Wave / Cold Snap | 30 days (shared cooldown) | varies |
| Blight | 30 days | instant (destroys crops) |
| Thrumbo Passage | 13 days | until they leave |

## Solar Flares

- Disable ALL electrical devices (no power, no turrets, no coolers)
- Duration: typically 1-2 days
- Freezer food will start spoiling
- Turrets go offline — vulnerable to raids during flare
- Keep non-electric backup: campfire for cooking, passive cooler for temp
