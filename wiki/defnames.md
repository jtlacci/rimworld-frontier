# DefNames Reference

DefNames are the internal identifiers used by RimWorld for all items, buildings, floors, and materials. The SDK uses these for all build/place/zone commands.

## Walls and Doors
- `Wall` — generic wall (requires stuff material)
- `Door` — generic door (requires stuff material)

## Tables
- `Table1x2c` — 1x2 table
- `Table2x2c` — 2x2 table
- `Table2x4c` — 2x4 table
- `Table3x3c` — 3x3 table

## Chairs and Seating
- `DiningChair` — standard chair (beauty 8, comfort 0.7)
- `Armchair` — armchair (beauty 4, comfort 0.8)
- `Stool` — stool (beauty 0, comfort 0.5)

## Bedroom Furniture
- `Bed` — single bed (1x2)
- `DoubleBed` — double bed (2x2)
- `EndTable` — end table (1x1, +0.05 rest effectiveness when adjacent to bed head)
- `Dresser` — dresser (2x1, bedroom impressiveness bonus when adjacent to bed head)

## Kitchen and Cooking
- `FueledStove` — wood-burning stove (3x1)
- `ElectricStove` — electric stove (3x1)
- `ButcherSpot` — butchering spot (1x1, no construction needed)
- `Campfire` — campfire (1x1, cooking + heating + light)

## Joy/Recreation
- `HorseshoesPin` — horseshoes (joy activity)
- `ChessTable` — chess table (joy activity)
- `BilliardsTable` — pool table (joy activity)

## Production
- `SimpleResearchBench` — research bench (1x3)
- `HiTechResearchBench` — advanced research bench
- `HandTailoringBench` — tailoring bench
- `ElectricTailoringBench` — powered tailoring bench
- `FueledSmithy` — smithing bench
- `ElectricSmithy` — powered smithing bench
- `StonecutterTable` — stonecutting bench

## Power
- `SolarGenerator` — solar panel (4x4)
- `WindTurbine` — wind turbine (5x2 + 7-tile exclusion on wind sides)
- `WatermillGenerator` — watermill (5x6, river required)
- `Battery` — power storage (1x2)
- `PowerConduit` — power conduit (can go under walls)

## Medical
- `MedicalBed` — hospital bed
- `VitalsMonitor` — vitals monitor (improves surgery)

## Lighting
- `StandingLamp` — floor lamp
- `SunLamp` — grow light (large radius)
- `TorchLamp` — torch (no power, uses wood)

## Storage
- `Shelf` — storage shelf (holds items, counts as "inside" for stockpile)

## Decoration
- `PlantPot` — plant pot (beauty varies by plant)
- `Column` — decorative column

## Stuff Materials (for build commands)
- `WoodLog` — wood
- `Steel` — steel
- `BlocksGranite` — granite blocks
- `BlocksSandstone` — sandstone blocks
- `BlocksSlate` — slate blocks
- `BlocksLimestone` — limestone blocks
- `BlocksMarble` — marble blocks
- `Plasteel` — plasteel
- `Silver` — silver
- `Gold` — gold

## Floor defNames
- `WoodPlankFloor` — wood plank floor
- `TileGranite` — granite tile
- `TileSandstone` — sandstone tile
- `TileSlate` — slate tile
- `TileLimestone` — limestone tile
- `TileMarble` — marble tile
- `PavedTile` — paved tile floor
- `SterileTile` — sterile tile
- `CarpetRed` / `CarpetBlue` / `CarpetBeige` / `CarpetDark` — carpet (specify color)

## Plants (for grow zones)
- `Plant_Rice` — rice (fastest growing)
- `Plant_Potato` — potatoes (grows in poor soil)
- `Plant_Corn` — corn (slow but high yield)
- `Plant_Strawberry` — strawberries
- `Plant_Cotton` — cotton (for cloth)
- `Plant_Devilstrand` — devilstrand (best textile, very slow)
- `Plant_Healroot` — healroot (medicine ingredient)
- `Plant_Haygrass` — haygrass (animal feed)

## Food Items
- `MealSimple` — simple meal
- `MealFine` — fine meal
- `MealSurvivalPack` — packaged survival meal (never spoils)
- `RawBerries` — raw berries
- `Meat_Human` — human meat (mood debuff if eaten)
