
### Run 2
1. **Per-bush harvest tracking**: Timeline doesn't track individual berry bush state (growth %, harvested vs. cut vs. remaining). Can't tell if bushes were at harvestable maturity (≥65%) or if some were immature. Need `designate_harvest` to return count of actually-harvestable plants found.

2. **CutPlant target disambiguation**: `score_timeline.jsonl` shows `CutPlant` as the job but doesn't distinguish "clearing wild plants from grow zone" from "cutting designated plants." Need job metadata: target position or target plant type, so we can determine if colonists are clearing the grow zone vs. doing something useful.

3. **Raw food consumption tracking**: No data on which colonist ate raw food vs. who ate a meal. The `Ingest` job appears but we can't see what they ingested. Would clarify how much nutrition was wasted on raw eating.

4. **Cookable threshold visibility**: `food_pipeline.cookable_meals=0` doesn't distinguish "no raw food" from "raw food exists but below 10-unit threshold." A `sub_cookable` status would enable targeted detection of this deadlock.

---

### Run 3
1. **Berry bush growth telemetry**: `designate_harvest` returns only `ok: true` — no count of plants designated or their growth states. `after.json` has no wild plant data. **I cannot verify H3 (bush growth) without this.** Request: `designate_harvest` should return `{"ok": true, "plants_designated": 17, "avg_growth": 0.85}` or similar. Alternatively, `score_timeline.jsonl` should track wild berry bush count + avg growth.

2. **Raw food eating events by colonist**: Currently tracked only through kitchen mood debuffs, which are invisible for Ascetics and for berries (no penalty). Request: add a `raw_food_eaten` counter per colonist to snapshots, or a `food_events` log showing who ate what and when.

3. **Cookable vs raw consumption breakdown**: `food_pipeline.cookable_meals` tracks what CAN be cooked at snapshot time, but not what WAS cooked vs eaten raw between snapshots. Request: cumulative counters `total_meals_cooked` and `total_raw_eaten` in the pipeline data.

4. **`designate_harvest` plant count return**: The command returns no info about how many plants were actually designated. On a map with variable bush growth, this is critical for diagnosing harvest shortfalls.

---
