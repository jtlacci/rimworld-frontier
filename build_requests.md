# Build Requests

Observability gaps identified by auditor investigations. Each request represents missing data that blocked root cause analysis.

- **Per-bush harvest tracking**: `designate_harvest` returns only `ok: true` — no count of plants designated or their growth states. Need: `{"ok": true, "plants_designated": 17, "avg_growth": 0.85}`. Without this, can't verify if bushes were harvestable.

- **CutPlant target disambiguation**: Timeline shows `CutPlant` as job but doesn't distinguish "clearing wild plants from grow zone" vs "cutting designated plants." Need job metadata: target plant type or position.

- **Raw food consumption tracking**: `Ingest` job appears but doesn't show what was ingested. Can't tell who ate raw food vs meals, or how much nutrition was wasted on raw eating. Need per-colonist `raw_food_eaten` counter or `food_events` log.

- **Cookable threshold visibility**: `food_pipeline.cookable_meals=0` doesn't distinguish "no raw food" from "raw food exists but below 10-unit threshold." Need a `sub_cookable` flag or `raw_food_total` field.
