# Early Game Strategy

The first 3 in-game days are critical. Establishing food, shelter, and production quickly determines colony survival.

## Day 1 Priorities (in order)

1. **Unforbid all items** — some items may start forbidden. Call `unforbid_all()`.
2. **Dismiss naming dialog** — `Dialog_NamePlayerFactionAndSettlement` blocks time.
3. **Set manual priorities** — `set_manual_priorities(True)`.
4. **Assign roles** — cook, builder, researcher based on skills.
5. **Hunting + harvesting** — designate animals for hunting, wild berries for harvest.
6. **Chop trees** — wood is needed for everything early (radius=45).
7. **Build campfire + butcher spot** — cooking infrastructure.
8. **Build table + chairs** — prevents "ate without table" debuff (-3 mood).
9. **Set up grow zones** — rice for fast food, potatoes if soil is poor.
10. **Create stockpiles** — main storage, food storage, chunk dump.

## Day 2-3 Priorities

1. **Build shelter** — barracks first (shared sleeping), then individual bedrooms
2. **Build storage room** — keep resources organized and indoors
3. **Set up research** — assign research bench + researcher
4. **Add production** — tailoring bench for clothes before cold weather
5. **Recreation** — horseshoes pin prevents joy deprivation

## Resource Management

Starting resources are limited. Prioritize:
- **Wood**: campfire fuel, construction, furniture. Chop aggressively.
- **Steel**: walls (if wood is scarce), stoves, production buildings.
- **Survival meals**: DON'T eat these. Save as emergency backup.
- **Components**: scarce. Don't waste on non-essential buildings.

## Common Day 1 Mistakes

- Not unforbidding items → colonists ignore supplies
- Not dismissing naming dialog → game clock frozen
- Building walls before table/chairs → "ate without table" debuff
- Setting cook priority but not Growing → wild berries never harvested
- Using "do forever" cook bills → overproduction + waste
- Not setting manual priorities → everyone at priority 3, nothing gets done efficiently
