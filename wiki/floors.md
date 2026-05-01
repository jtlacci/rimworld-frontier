# Floor Types

Floors affect beauty, cleanliness, and room impressiveness. Unflooredground (soil, dirt) has 0 beauty and looks rough.

## Floor Comparison

| Floor | defName | Beauty | Cost | Work (ticks) | Flammable | Cleanliness |
|-------|---------|--------|------|-------------|-----------|-------------|
| Wood plank | WoodPlankFloor | 0 | 3 Wood | 85 | Yes (22%) | 0 |
| Stone tile | (varies by stone) | +2 | 4 Blocks | 1,100 | No | 0 |
| Flagstone | (varies by stone) | 0 | 4 Blocks | 500 | No | 0 |
| Sterile tile | SterileTile | -1 | 3 Steel + 12 Silver | 1,600 | No | +0.6 |
| Carpet | CarpetRed (etc.) | +2 | 7 Cloth | 800 | Yes (32%) | 0 |

## Stone Tile defNames

- `TileGranite` — granite blocks
- `TileSandstone` — sandstone blocks
- `TileSlate` — slate blocks
- `TileLimestone` — limestone blocks
- `TileMarble` — marble blocks (same +2 beauty as others)

## Usage Guidelines

- **Wood planks**: Fast and cheap. Use for early builds. Replace later when stone is available.
- **Stone tile**: Best general-purpose permanent floor. +2 beauty, fireproof.
- **Sterile tile**: Hospitals and labs ONLY. The +0.6 cleanliness bonus directly improves surgery success and infection rates. Expensive (silver cost).
- **Carpet**: +2 beauty but flammable (32%). Good for bedrooms where fire risk is low. Bad for kitchens/workshops.
- **Flagstone**: Cheap stone floor with 0 beauty. Use for workshops/storage where beauty doesn't matter.

## Placement Notes

- Use `set_floor` command with `x1, z1, x2, z2` region for bulk placement
- `set_floor` skips cells that already have the requested terrain — safe to call on partially floored rooms
- Floor the entire room for impressiveness — even one unfloored cell hurts the average beauty
- Do floors room-by-room after critical construction (walls, furniture) is done
