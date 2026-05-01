# Research

Research unlocks new buildings, recipes, and capabilities. Only one project can be active at a time.

## Research Speed

```
Points/tick = 0.00825 × Pawn Research Speed × Bench Factor × Difficulty Factor
```

### Bench Factor

| Setup | Factor |
|-------|--------|
| Simple research bench | ×0.75 |
| Hi-tech research bench | ×1.00 |
| Hi-tech + Multi-analyzer | ×1.10 |
| **Not in a "Laboratory" room** | **×0.80 penalty** |

### Pawn Research Speed by Intellectual Skill

| Skill | 0 | 5 | 8 | 10 | 15 | 20 |
|-------|---|---|---|----|----|-----|
| Speed | 8% | 65.5% | 100% | 123% | 180.5% | 238% |

### Points Per Game Hour (hi-tech bench, normal difficulty)

| Skill | Points/hr |
|-------|----------|
| 0 | 1.7 |
| 5 | 13.5 |
| 8 | 20.6 |
| 10 | 25.4 |
| 15 | 37.2 |
| 20 | 49.1 |

### Key rules
- Multiple researchers + benches contribute simultaneously
- Progress retained when switching projects
- Simple bench can research most things; hi-tech needed for advanced projects
- Multi-analyzer required for all Spacer-tier research
- Tribes pay 1.5× for Medieval, 2× for Industrial+ research

## Early Research Priority Order

1. **Complex Furniture** (300) — beds, end tables, dressers. Massive mood boost.
2. **Electricity** (1,600) — power unlocks everything. The #1 tech gate.
3. **Battery** (400) — store power for night/calm.
4. **Stonecutting** (300) — stone blocks for fireproof walls.
5. **Air Conditioning** (500) — coolers for freezer (food preservation).
6. **Complex Clothing** (600) — dusters, pants for temperature.
7. **Smithing** (700) — steel tile, melee weapons.

## Mid-Game Research

8. **Machining** (1,000) — machining table, path to guns + flak.
9. **Gunsmithing** (500) — bolt-action rifles, revolvers.
10. **Sterile Materials** (600) — sterile tile for hospital/kitchen.
11. **Blowback Operation** (500) → **Gun Turrets** (500) — base defense.
12. **Microelectronics** (3,000) — THE key gate. Hi-tech bench, comms, trade beacons.
13. **Hospital Bed** (1,200) — needs Microelectronics + Sterile Materials + Complex Furniture.

## Late-Game Research

14. **Multi-analyzer** (4,000) — required for all advanced research.
15. **Fabrication** (4,000) — craft components, path to power armor + bionics.
16. **Vitals Monitor** (2,500) — hospital improvement.
17. **Bionic Replacements** (2,000) — all bionic parts.
18. **Precision Rifling** (1,400) — assault rifles, sniper rifles.
19. **Recon Armor** (6,000) → **Marine Armor** (6,000) — power armor.

## Situational Research

| Situation | Research | Why |
|-----------|----------|-----|
| Ice sheet / no growing season | **Hydroponics** (700) | Year-round indoor food |
| Tropical / disease-heavy biome | **Penoxycyline** (500) | Disease prevention |
| Raids getting dangerous | **Flak Armor** (1,200) | Mid-game armor |
| Surface resources depleted | **Deep Drilling** (4,000) | Mine deep deposits |
| Cash crop | **Devilstrand** (800) | Best textile for trade |

## Common Research defNames

| Research | defName | Prerequisites | Cost |
|----------|---------|--------------|------|
| Electricity | Electricity | None | 1,600 |
| Battery | Battery | Electricity | 400 |
| Solar Panel | SolarPanels | Electricity | 600 |
| Air Conditioning | AirConditioning | Electricity | 500 |
| Complex Furniture | ComplexFurniture | None | 300 |
| Stonecutting | Stonecutting | None | 300 |
| Smithing | Smithing | None | 700 |
| Machining | Machining | Electricity + Smithing | 1,000 |
| Gun Turrets | GunTurrets | Blowback + Machining | 500 |
| Sterile Materials | SterileMaterials | Electricity | 600 |
| Microelectronics | Microelectronics | Electricity | 3,000 |
| Hospital Bed | HospitalBed | Micro + Sterile + Complex Furn | 1,200 |
| Multi-analyzer | MultiAnalyzer | Micro + Machining | 4,000 |
| Fabrication | Fabrication | Multi-analyzer | 4,000 |
| Drug Production | DrugProduction | None | 500 |
| Medicine Production | MedicineProduction | Drug Prod + Micro | 1,500 |
| Hydroponics | Hydroponics | Electricity | 700 |

## Research Tips

- Research gets **unset on game reload** — always verify and re-set after loading
- Use `set_research(project)` to assign current research
- Use `research()` to check current project and completed list
- Assign highest Intellectual pawn to research priority 2-3
- Put research bench in a "Laboratory" room to avoid ×0.80 penalty
- Sterile tile in lab gives up to +9% research speed bonus
