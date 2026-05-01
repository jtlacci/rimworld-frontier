# Combat and Defense

Raids are the primary threat to colonies. Preparation and response determine survival.

## Raid Types

- **Tribal raids**: melee-heavy, lower tech, larger numbers
- **Pirate raids**: mixed ranged + melee, moderate tech
- **Mechanoid raids**: high-tech enemies, very dangerous
- **Sappers**: dig through walls to bypass defenses
- **Drop pods**: land inside your base, bypassing perimeter walls

## Defense Basics

### Kill Box
A funnel that forces raiders through a narrow, heavily defended corridor:
1. Wall off most of the base perimeter
2. Leave one opening as the "entrance"
3. Line the entrance corridor with sandbags, turrets, and cover for your colonists
4. Raiders pathfind to the opening and get concentrated fire

### Cover
- **Sandbags**: 55% cover (cheap, fast to build)
- **Walls**: 75% cover (but colonists must peek around corners)
- **Stone chunks**: 50% cover (free, placed by mining)
- Cover only works if the attacker's shot passes through the cover object

### Turrets
- **Mini-turret**: requires Gun Turrets research + power. Automated fire.
- Place behind sandbags for protection
- Need power connection (conduit)
- Have limited barrel life — need steel to rebuild barrel

## Combat Commands

- `draft(colonist)` — put colonist in combat mode
- `undraft(colonist)` — return to normal work
- `move_pawn(pawn, x, z)` — position for combat
- `attack(pawn, target=, x=, z=)` — order attack
- `rescue(pawn, target)` — rescue downed colonist

## Combat Tips

- **Draft all colonists** when raid starts — stop them from wandering into danger
- **Position behind cover** before enemies arrive
- **Focus fire**: order all shooters to attack the same target
- **Melee block**: one melee colonist in a 1-wide doorway blocks all enemies
- **Rescue downed pawns** immediately after combat — bleeding kills
- **Tend injuries** ASAP — infection chance increases with time
- C# mod auto-tends injured colonists every ~10s, but verify with alerts

## Perimeter Walls

- Stone walls for durability (granite = 510 HP)
- Double-thick walls for sapper resistance
- Never wood walls on perimeter (raiders use fire)
- Leave NO gaps — even diagonal gaps allow pathing through

## Fire Response

- Firefighting priority should be 1 for ALL colonists
- Cut firebreaks (clear vegetation around base)
- Stone buildings don't burn — transition from wood ASAP
- Rain extinguishes fires (wait if possible)
- Drafted colonists don't fight fires — undraft them

## Post-Combat

1. Rescue downed colonists
2. Tend all injuries
3. Unforbid dropped weapons/equipment
4. Strip and bury/burn enemy corpses (mood debuff from seeing corpses)
5. Repair damaged buildings
6. Restock defenses
