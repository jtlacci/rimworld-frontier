# Mission: Feed the Colony

## Objective
Establish a cooking pipeline and keep all colonists fed for 3 in-game days. You start with ZERO survival packs — every calorie must come from hunting, gathering, and cooking.

## Success Criteria
- Meals produced within the first game day
- No colonist food need drops below 0.25 for more than 2 hours
- Zero starvation alerts
- At least 5 meals in stockpile at end of run
- Cooking bills active throughout the run

## Strategy Priorities

### If wood is available (campfire path)
1. **Immediately** hunt all wildlife — every animal is food AND removes food competition
2. **Immediately** harvest all berry bushes
3. Build campfire + butcher spot within first 30 minutes game time
4. Set cooking bills as soon as campfire is built
5. Store food INDOORS (animals steal from open stockpiles)
6. Assign best cook to Cooking priority 1
7. Keep hunting designated — new animals may wander in

### If NO wood (electric path — v0.7+)
1. **Immediately** hunt all wildlife — same urgency as above
2. Build ButcherSpot (free, no materials)
3. Build **WindTurbine** (100 steel + 2 comp) in open area with 7-tile east/west exclusion zone clear — NOT SolarGenerator (solar produces 0W at night; no Battery research = no stored power)
4. Lay **PowerConduit** tiles (~10 tiles, 1 steel each) from turbine to stove location — conduit CAN pass through walls
5. Build **ElectricStove** (80 steel + 2 comp), connected to conduit network
6. Add CookMealSimple bills immediately
7. Assign best cook to Cooking priority 1

**Power grid sequencing matters**: stove before generator = "No Power", no cooking. Always build generator → conduit → stove in that order.

## What Doesn't Matter
- Room impressiveness — eat on the ground if you must
- Research — don't waste colonist-hours researching (Electricity is pre-completed in v0.7+)
- Beauty — survival first
- Storage rooms — a stockpile zone indoors is enough

## Scoring (custom rubric)
| Metric | Weight | How |
|--------|--------|-----|
| meals_produced | 30 | Total meals cooked during the run |
| food_sustained | 30 | % of snapshots where all colonists have food > 0.25 |
| no_starvation | 20 | 1.0 if no starvation alerts, 0.0 if any |
| food_stockpile | 10 | Meals in stockpile at end (5+ = 1.0) |
| all_alive | 10 | Everyone alive at end |
