# Apparel and Armor

Clothing protects against temperature and combat damage. Layer system determines what stacks.

## Outer Layer (Torso)

| Item | Material | Sharp Armor | Cold Insulation | Heat Insulation | Work |
|------|----------|------------|----------------|----------------|------|
| Parka | 80 fabric/leather | mat x100% | mat x**200%** | mat x0% | 8,000 |
| Duster | 80 fabric/leather | mat x60% | mat x50% | mat x50% | 10,000 |
| Jacket | 70 fabric/leather | — | — | — | 7,000 |

**Parka vs Duster**: Parka = best cold insulation (2x factor), zero heat. Duster = balanced cold + heat. Cold biome → parka. Hot/temperate → duster.

## Middle Layer (Armor)

| Item | Sharp | Blunt | Market Value | Notes |
|------|-------|-------|-------------|-------|
| Flak vest | 75% | 75% | 330 | Affordable mid-game armor |
| Flak pants | 55% | 8% | 225 | Leg protection |
| Recon armor | 92% | 40% | 525 | Lighter power armor |
| Marine armor | 106% | 45% | 635 | Standard power armor |
| Cataphract armor | 120% | 50% | 745 | Heaviest armor, slows movement |

Flak gear requires Machining research. Power armor requires Fabrication.

## Headgear

| Item | Sharp | Blunt | Cold Factor | Heat Factor |
|------|-------|-------|------------|------------|
| Tuque | 0% | 0% | 50% | 0% |
| Cowboy hat | 0% | 0% | 10% | 50% |
| Simple helmet | 30% | 10% | 15% | 0% |
| Flak helmet | 70% | 20% | 15% | 0% |
| Recon helmet | 92% | 40% | — | — |
| Cataphract helmet | 120% | 50% | — | — |

Tuque for cold, cowboy hat for heat. Helmets for combat.

## Skin Layer

| Item | Cold Factor | Heat Factor | Work |
|------|------------|------------|------|
| Tribalwear | 55% | 55% | 1,800 |
| Button-down shirt | 26% | 10% | 2,700 |
| T-shirt | — | — | 1,600 |
| Pants | — | — | 1,600 |

## Insulation Formula

```
Final Insulation = Material_Base x Apparel_Factor x Quality_Multiplier
```

Insulation stacks additively across all worn apparel. Quality multipliers: Awful x0.80, Normal x1.00, Excellent x1.20, Masterwork x1.50, Legendary x1.80.

## Tainted Apparel

- Items on a pawn at death become **tainted** (suffix "T")
- Mood penalty: -5 (1 item) to -14 (4+ items)
- Market value reduced by 90%
- Cannot be un-tainted — destroy or smelt

## Best Materials for Clothing

| Material | Best For | Why |
|----------|----------|-----|
| Devilstrand | Combat clothing | 1.4 sharp armor factor, best non-armor protection |
| Cloth | General clothing | Cheap, 36C heat insulation |
| Hyperweave | Everything | Best stats across the board (rare, expensive) |
| Thrumbofur | Cold insulation | Best cold insulation factor |
| Muffalo wool | Cold clothing | Good cold insulation, renewable |
| Camelhair | Hot biomes | Good heat insulation |

## Clothing Priority for Agents

1. **Any clothing** (prevent "naked" debuff) — tribalwear is fastest to make
2. **Parkas/dusters** before first temperature extreme
3. **Flak vests + helmets** before first serious raid
4. **Power armor** when fabrication is available and resources allow
