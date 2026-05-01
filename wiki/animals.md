# Animals

Animals provide food (hunting), labor (hauling/rescuing), and materials (leather, wool). Managing them correctly is important.

## Wild Animals

Wild animals spawn on the map and can be hunted, tamed, or ignored.

- `hunt(animal=)` — designate for hunting. Colonist with hunting priority will shoot.
- `tame(animal)` — designate for taming. Colonist with handling skill attempts.
- Hunting yields a corpse that must be butchered for meat + leather.

## Hunting Tips

- Assign your best Shooting skill colonist to Hunting priority 1-2
- Predators (wolves, bears) will fight back — use ranged weapons
- Small animals (rabbits, squirrels) have low meat yield — not worth hunting individually
- Large animals (muffalo, elk, deer) give 70-140 meat + leather
- Designate multiple animals at once for efficiency
- Hunted corpses must be butchered FAST — meat rots in ~2 days

## Taming

- Requires Animal Handling skill
- Tamed animals consume colony food — only tame what you can feed
- Useful animals: muffalo (hauling + wool), husky (hauling + rescue), horse (caravan speed)
- Failed taming attempts can trigger animal revenge (dangerous with large animals)

## Butchering

- Use `ButcherSpot` (no building needed) or `Butcher table` (no research required, available from start)
- Add "butcher creature" bill to the workbench
- Yields: meat (for cooking) + leather (for crafting)
- Butcher corpses IMMEDIATELY — they rot fast outdoors

## Animal Zones

Animals can be restricted to zones to keep them out of food storage:
- Create an "animal zone" that excludes freezer/food storage
- Prevents pets from eating all your meals

## Grazing

Tamed herbivores (muffalo, horses) can graze on grass/haygrass outdoors:
- No food cost if there's enough vegetation
- In winter or barren biomes, they need colony food (hay, kibble)

## Dangerous Wildlife

Some wild animals are aggressive:
- **Manhunter packs**: event where all animals of a type go berserk
- **Predators**: may hunt your colonists or pets
- **Boomalopes/Boomrats**: explode on death — don't hunt near flammable buildings

