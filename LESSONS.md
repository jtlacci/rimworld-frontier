# Confirmed Lessons
# 【已验证事实 - 禁止修改或质疑以下内容】

Facts verified across 50+ runs. Do NOT contradict these.
以下事实经过50次以上运行验证，绝对禁止更改。

## Work Types
- **Berry harvesting** uses Growing work type (#12), NOT PlantCutting (#14). Confirmed: HarvestDesignated jobs are fulfilled by Growing-enabled colonists. Setting PlantCutting on berry bushes DESTROYS them (CutPlant).
- **PlantCutting (#14)** is for tree chopping and plant destruction ONLY. Never set PlantCutting priority for berry harvesting.
- **Growing (#12)** handles both berry harvesting AND crop sowing. They compete in the same queue. On short scenarios, do NOT create grow zones — sowing displaces harvesting.
- Work type check order: Cook(#9) > Hunt(#10) > Construct(#11) > Grow(#12) > Mine(#13) > PlantCut(#14). Same-priority ties break left-to-right.

## Food Pipeline
- Colonists eat raw berries with zero mood penalty — they drain berry stockpiles before cooking. Get cooking bills active ASAP.
- Simple meal = 10 raw food → 0.9 nutrition. Raw eating = 0.05 per item. Cooking is 18x more efficient.
- FueledStove (100% speed) cooks 2x faster than Campfire (50% speed). Always build FueledStove when steel available.
- `add_cooking_bills(retry=True)` handles Campfire, FueledStove, AND ElectricStove.

## Priorities
- `set_manual_priorities(True)` MUST be called or all priority assignments are silently ignored.
- Colonists with "Violent" in disabledWork CANNOT hunt. Check before assigning.
- Stockpile zones are required for `resources()` to count items. Without zones, scoring shows 0 meals even when meals exist on the ground.

## Construction
- FueledStove is BUILT with steel but RUNS on wood. Useless on zero-wood maps.
- ElectricStove needs PowerConduit connection to WindTurbine/SolarGenerator.
- Place ElectricStove BEFORE running conduit to it — blueprints collide if conduit is placed first.

## Timing
- At speed 4: 60 real seconds ≈ 2-3 game days.
- Berry bushes must be at ≥65% growth to harvest. Savegen spawns them at 100%.
- Rice takes 5.5 days — useless on 3-day scenarios.
