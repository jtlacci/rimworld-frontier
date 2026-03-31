# Build Requests

Observability gaps identified by auditor investigations. Implemented requests are removed.

*No open requests.*

- **Scenario caloric validation**: The scenario description's "200 berries → 40 simple meals" claim is incorrect (actual: 20). A pre-run validation step should compute theoretical max meals from scenario resources and flag when scoring thresholds exceed the caloric ceiling.

- **Savegen starting_items override**: The savegen needs a mode where `starting_items` replaces (not augments) default crashlanded items. Without this, scenarios that depend on resource scarcity cannot function as designed.

- **No tool_calls.jsonl generated**: This run has `overseer_raw.jsonl` instead of `tool_calls.jsonl`. The auditor protocol references `tool_calls.jsonl` — either generate it or update the protocol.

- **Runner**: Runner: use scenario.json 'mission' field for SCENARIO_*.md file lookup instead of versioned scenario name

- **Runner**: Runner: inject scenario.json 'mission_description' into overseer system prompt

- **SDK**: SDK: add_cooking_bills() should handle ElectricStove (currently only Campfire/FueledStove)

- **SDK**: SDK: setup_cooking() should auto-detect wood=0 and build electric infrastructure

- **SculptureSmall NullReferenceException**: SculptureSmall NullReferenceException: 36 consecutive build failures with identical stack trace — C# Harmony mod bug

- **WindTurbine not tracked in score_timeline building**: WindTurbine not tracked in score_timeline building_defs despite being present on colony map

- **No power grid connectivity telemetry — need power_**: No power grid connectivity telemetry — need power_connected field on cooking stations

- **Log construction failure events in events**: Log construction failure events in events.jsonl (e:construct_fail with colonist, building def, position, skill)

- **Track materials delivered to frames in score_timel**: Track materials delivered to frames in score_timeline to distinguish hauling-wait vs builder-wait vs frame-destroyed

- **Track power grid connected/disconnected status in **: Track power grid connected/disconnected status in score_timeline

- **Flag irrecoverable component shortage in food_pipe**: Flag irrecoverable component shortage in food_pipeline telemetry

- **colony_health_check() should check for berry bush **: colony_health_check() should check for berry bush existence before firing berry emergency (plants filter=Plant_Berry), or skip when uncompleted cooking infrastructure frames exist

- **Score timeline should track construction_priority **: Score timeline should track construction_priority per colonist for priority demotion visibility

- **Timeline**: Timeline: track has_bills transitions with timestamps for easier bill-timing audits

- **Command log**: Command log: add phase field to tag commands by overseer/scoring phase

- **SDK set_priority should auto-call set_manual_prior**: SDK set_priority should auto-call set_manual_priorities(True) or error if manual mode inactive

- **setup_food_wood**: setup_food_wood.py skill should include set_manual_priorities(True) and basic priority assignment

- **SDK batch error isolation**: SDK batch error isolation: per-command error reporting instead of cross-batch bleed

- **SDK set_manual_priorities guard**: SDK set_manual_priorities guard: auto-enable or error when set_priority called without manual mode

- **Wiki mechanic verification**: Wiki mechanic verification: controlled test with Growing=0/PlantCutting=1 vs Growing=1/PlantCutting=0 to definitively resolve which work type handles HarvestDesignated jobs for berry bushes in the mod

- **Timeline should track per-colonist food consumptio**: Timeline should track per-colonist food consumption type (raw vs cooked) to quantify raw eating drain

- **Command log should include work type (PlantCutting**: Command log should include work type (PlantCutting vs Sow) to verify labor allocation

- **Events log should capture 'eat' events with food t**: Events log should capture 'eat' events with food type and nutrition consumed

- **Timeline should track per-plant harvestable status**: Timeline should track per-plant harvestable status

- **Track count of remaining unharvested food sources**: Track count of remaining unharvested food sources

- **Monitor job completion rates for critical food har**: Monitor job completion rates for critical food harvesting designations

- **Timeline should track active cooking bills and the**: Timeline should track active cooking bills and their completion status

- **Events log should include eating events to verify **: Events log should include eating events to verify food consumption patterns

- **Command log should show work priority changes over**: Command log should show work priority changes over time

- **Timeline tracking for individual plant growth stat**: Timeline tracking for individual plant growth states (harvestable vs not)

- **Enhanced job transition logging showing work type **: Enhanced job transition logging showing work type competition

- **Food crisis detection in monitored_sleep**: Food crisis detection in monitored_sleep

- **Timeline telemetry tracking per-plant growth perce**: Timeline telemetry tracking per-plant growth percentage

- **Plant harvest success/failure event logging**: Plant harvest success/failure event logging

- **Scenario validation telemetry**: Scenario validation telemetry: log actual vs. expected resource placement

- **Early plant existence verification via SDK plants(**: Early plant existence verification via SDK plants() call before harvest attempts

- **Timeline should track berry bush count per snapsho**: Timeline should track berry bush count per snapshot

- **Events**: Events.jsonl should include hunt completion events

- **Command log should distinguish designation from jo**: Command log should distinguish designation from job completion

- **Timeline should track berry bush count over time**: Timeline should track berry bush count over time

- **Colonist job queue visibility for detecting race c**: Colonist job queue visibility for detecting race conditions

- **Per-item location tracking for debugging sub_cooka**: Per-item location tracking for debugging sub_cookable

- **Cooking station ingredient availability in telemet**: Cooking station ingredient availability in telemetry

- **sub_cookable_count field in food pipeline**: sub_cookable_count field in food pipeline

- **run_and_monitor**: run_and_monitor.py should check meals_delta and colonist jobs every check_interval, re-asserting cooking priorities if cooks go idle

- **Track weapon/equipment state per colonist in timel**: Track weapon/equipment state per colonist in timeline

- **Add detail to hunting job failure errors in comman**: Add detail to hunting job failure errors in command log
