using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RimWorld;
using Verse;
using Verse.AI;
using static CarolineConsole.Helpers;

namespace CarolineConsole
{
    /// <summary>
    /// Mutation command handlers for game state changes: building, drafting, zoning,
    /// designations, bills, pawn orders, research, and dev/testing tools.
    /// </summary>
    public static class WriteCommands
    {
        private static Pawn FindColonist(string name)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            var pawn = map.mapPawns.FreeColonists.FirstOrDefault(p =>
                p.Name.ToStringFull.Equals(name, StringComparison.OrdinalIgnoreCase) ||
                p.Name.ToStringShort.Equals(name, StringComparison.OrdinalIgnoreCase));
            if (pawn == null) throw new Exception($"Colonist not found: {name}");
            return pawn;
        }

        /// <summary>
        /// Sets a colonist's work priority for a given work type.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - colonist (string, required): colonist name
        /// - work (string, required): work type defName (e.g. "Mining", "Construction")
        /// - priority (int, optional): priority level 0-4, default 3
        /// </param>
        /// <returns>Dictionary with: ok (bool), colonist (string), work (string), priority (int)</returns>
        public static object SetPriority(Dictionary<string, object> req)
        {
            var colonistName = S(req, "colonist");
            var workType     = S(req, "work");
            int priority     = I(req, "priority", 3);

            var pawn = FindColonist(colonistName);
            var workDef = DefDatabase<WorkTypeDef>.AllDefs
                .FirstOrDefault(w => w.defName.Equals(workType, StringComparison.OrdinalIgnoreCase));
            if (workDef == null) throw new Exception($"Unknown work type: {workType}");

            pawn.workSettings.SetPriority(workDef, priority);
            return D("ok", true, "colonist", colonistName, "work", workType, "priority", (object)priority);
        }

        /// <summary>
        /// Sets a colonist's 24-hour schedule (sleep/work/joy/anything per hour).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - colonist (string, required): colonist name
        /// - schedule (List of 24 strings, required): each "sleep", "work", "joy"/"recreation", or "anything"
        /// </param>
        /// <returns>Dictionary with: ok (bool), colonist (string)</returns>
        public static object SetSchedule(Dictionary<string, object> req)
        {
            var colonistName = S(req, "colonist");
            var scheduleRaw  = req.ContainsKey("schedule") ? req["schedule"] as List<object> : null;
            if (scheduleRaw == null || scheduleRaw.Count != 24)
                throw new Exception("Schedule must be an array of 24 entries");

            var pawn = FindColonist(colonistName);
            for (int hour = 0; hour < 24; hour++)
            {
                TimeAssignmentDef assignment;
                switch ((scheduleRaw[hour] as string)?.ToLower())
                {
                    case "sleep":       assignment = TimeAssignmentDefOf.Sleep; break;
                    case "work":        assignment = TimeAssignmentDefOf.Work;  break;
                    case "recreation":
                    case "joy":         assignment = TimeAssignmentDefOf.Joy;   break;
                    default:            assignment = TimeAssignmentDefOf.Anything; break;
                }
                pawn.timetable.SetAssignment(hour, assignment);
            }
            return D("ok", true, "colonist", colonistName);
        }

        /// <summary>
        /// Sets the game tick speed (0=paused, 1=normal, 2=fast, 3=superfast, 4=ultrafast).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - speed (int, optional): 0-4, default 1
        /// </param>
        /// <returns>Dictionary with: ok (bool), speed (int)</returns>
        public static object SetSpeed(Dictionary<string, object> req)
        {
            int speed = I(req, "speed", 1);
            switch (speed)
            {
                case 0: Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;     break;
                case 1: Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;     break;
                case 2: Find.TickManager.CurTimeSpeed = TimeSpeed.Fast;       break;
                case 3: Find.TickManager.CurTimeSpeed = TimeSpeed.Superfast;  break;
                case 4: Find.TickManager.CurTimeSpeed = TimeSpeed.Ultrafast;  break;
                default: throw new Exception($"Invalid speed: {speed}. Use 0-4.");
            }
            return D("ok", true, "speed", (object)speed);
        }

        /// <summary>
        /// Drafts a colonist, enabling direct movement and combat orders.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - colonist (string, required): colonist name
        /// </param>
        /// <returns>Dictionary with: ok (bool), colonist (string), drafted (bool)</returns>
        public static object Draft(Dictionary<string, object> req)
        {
            var name = S(req, "colonist");
            FindColonist(name).drafter.Drafted = true;
            return D("ok", true, "colonist", name, "drafted", true);
        }

        /// <summary>
        /// Undrafts a colonist, returning them to normal autonomous behavior.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - colonist (string, required): colonist name
        /// </param>
        /// <returns>Dictionary with: ok (bool), colonist (string), drafted (bool)</returns>
        public static object Undraft(Dictionary<string, object> req)
        {
            var name = S(req, "colonist");
            FindColonist(name).drafter.Drafted = false;
            return D("ok", true, "colonist", name, "drafted", false);
        }

        /// <summary>
        /// Adds a production bill to a workbench (e.g. cook meal, make apparel).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - workbench (string, required): workbench label or defName
        /// - recipe (string, required): recipe defName
        /// - count (int, optional): number to produce (-1 or omit for forever)
        /// </param>
        /// <returns>Dictionary with: ok (bool), workbench (string), recipe (string), count (int)</returns>
        /// <summary>
        /// Adds a crafting bill to a workbench. Supports position-based targeting and broadcasting to all matches.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - workbench (string, required): workbench label or defName
        /// - recipe (string, required): recipe defName (e.g. "CookMealSimple")
        /// - count (int, optional): repeat count (-1 = forever, default)
        /// - x (int, optional): target workbench at this x position
        /// - z (int, optional): target workbench at this z position
        /// - target_all (bool, optional): if true, add bill to ALL matching workbenches
        /// </param>
        /// <returns>Dictionary with: ok (bool), results (list of {workbench, x, z, ok}), count (int)</returns>
        public static object AddBill(Dictionary<string, object> req)
        {
            var workbenchName = S(req, "workbench");
            var recipeDef     = S(req, "recipe");
            int count         = I(req, "count", -1);
            int tx            = I(req, "x", -1);
            int tz            = I(req, "z", -1);
            bool targetAll    = B(req, "target_all", false);

            var map = GetMap() ?? throw new Exception("No active map");
            var matches = map.listerBuildings.allBuildingsColonist
                .OfType<Building_WorkTable>()
                .Where(b =>
                    b.Label.Equals(workbenchName, StringComparison.OrdinalIgnoreCase) ||
                    b.def.defName.Equals(workbenchName, StringComparison.OrdinalIgnoreCase));

            // Position filter
            if (tx >= 0 && tz >= 0)
                matches = matches.Where(b => b.Position.x == tx && b.Position.z == tz);

            var matchList = matches.ToList();
            if (matchList.Count == 0) throw new Exception($"Workbench not found: {workbenchName}" + (tx >= 0 ? $" at ({tx},{tz})" : ""));

            if (!targetAll)
                matchList = new List<Building_WorkTable> { matchList[0] };

            var results = new List<object>();
            foreach (var wb in matchList)
            {
                var recipe = wb.def.AllRecipes
                    .FirstOrDefault(r => r.defName.Equals(recipeDef, StringComparison.OrdinalIgnoreCase));
                if (recipe == null)
                {
                    results.Add((object)D("workbench", wb.Label, "x", (object)wb.Position.x, "z", (object)wb.Position.z, "ok", (object)false, "error", $"Recipe not found: {recipeDef}"));
                    continue;
                }

                var bill = recipe.MakeNewBill();
                if (bill is Bill_Production pb)
                {
                    if (count > 0) { pb.repeatMode = BillRepeatModeDefOf.RepeatCount; pb.repeatCount = count; }
                    else           { pb.repeatMode = BillRepeatModeDefOf.Forever; }
                }
                wb.BillStack.AddBill(bill);
                results.Add((object)D("workbench", wb.Label, "x", (object)wb.Position.x, "z", (object)wb.Position.z, "ok", (object)true));
            }

            // Backward-compatible: if single target, also return flat fields
            if (results.Count == 1)
                return D("ok", true, "workbench", workbenchName, "recipe", recipeDef, "count", (object)count, "results", results);
            return D("ok", true, "results", results, "count", (object)results.Count);
        }

        /// <summary>
        /// Removes a bill from a workbench by index.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - workbench (string, required): workbench label or defName
        /// - billIndex (int, optional): zero-based index of the bill to remove, default 0
        /// </param>
        /// <returns>Dictionary with: ok (bool), workbench (string), removedIndex (int)</returns>
        public static object CancelBill(Dictionary<string, object> req)
        {
            var workbenchName = S(req, "workbench");
            int billIndex     = I(req, "billIndex", 0);

            var map = GetMap() ?? throw new Exception("No active map");
            var workbench = map.listerBuildings.allBuildingsColonist
                .OfType<Building_WorkTable>()
                .FirstOrDefault(b =>
                    b.Label.Equals(workbenchName, StringComparison.OrdinalIgnoreCase) ||
                    b.def.defName.Equals(workbenchName, StringComparison.OrdinalIgnoreCase));
            if (workbench == null) throw new Exception($"Workbench not found: {workbenchName}");
            if (billIndex < 0 || billIndex >= workbench.BillStack.Count)
                throw new Exception($"Invalid bill index {billIndex}");

            workbench.BillStack.Delete(workbench.BillStack.Bills[billIndex]);
            return D("ok", true, "workbench", workbenchName, "removedIndex", (object)billIndex);
        }

        /// <summary>
        /// Places a building blueprint (or instant-places zero-cost items like sleeping spots).
        /// Validates all occupied cells for rock, water, existing blueprints/frames, impassable buildings, and interaction spots.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - blueprint (string, required): ThingDef defName (e.g. "Wall", "Door", "Bed")
        /// - x (int, required): X map coordinate
        /// - y (int, required): Z map coordinate (NOTE: y param maps to the game's Z axis)
        /// - rotation (int, optional): 0=North, 1=East, 2=South, 3=West (default 0)
        /// - stuff (string, optional): material defName (e.g. "WoodLog"); auto-selected if omitted
        /// </param>
        /// <returns>Dictionary with: ok (bool), blueprint (string), x (int), y (int), stuff (string),
        /// instant (bool), warning (string, if under mountain)</returns>
        public static object Build(Dictionary<string, object> req)
        {
            var blueprintDef = S(req, "blueprint");
            int x = I(req, "x"), y = I(req, "y"), rotation = I(req, "rotation", 0);
            var stuffName = S(req, "stuff");

            var map = GetMap() ?? throw new Exception("No active map");
            var thingDef = DefDatabase<ThingDef>.GetNamedSilentFail(blueprintDef);
            if (thingDef == null) throw new Exception($"Unknown blueprint: {blueprintDef}");

            ThingDef stuff = null;
            if (!string.IsNullOrEmpty(stuffName))
            {
                stuff = DefDatabase<ThingDef>.GetNamedSilentFail(stuffName);
                if (stuff == null) throw new Exception($"Unknown stuff: {stuffName}");
            }
            else if (thingDef.MadeFromStuff)
            {
                stuff = GenStuff.DefaultStuffFor(thingDef);
            }

            var pos = new IntVec3(x, 0, y);
            var rot = new Rot4(rotation);

            // Conduits and other thin buildings can coexist with walls
            bool isConduit = thingDef.defName == "PowerConduit" || thingDef.IsEdifice() == false;

            // Validate all cells the building would occupy
            var occupiedRect = GenAdj.OccupiedRect(pos, rot, thingDef.size);
            var rockCells = new List<string>();
            var waterCells = new List<string>();
            var oobCells = new List<string>();
            var impassableCells = new List<string>();
            var interactionCells = new List<string>();
            var blueprintCells = new List<string>();
            var zoneCells = new List<string>();
            bool underMountain = false;

            // Build set of cells this building will occupy for interaction spot checks
            var occupiedSet = new HashSet<IntVec3>(occupiedRect);

            foreach (var cell in occupiedRect)
            {
                if (!cell.InBounds(map))
                {
                    oobCells.Add($"({cell.x},{cell.z})");
                    continue;
                }

                var terrain = cell.GetTerrain(map);
                if (terrain != null && terrain.IsWater && !isConduit)
                    waterCells.Add($"({cell.x},{cell.z})");

                // Check for mineable natural rock (null-guarded — run 008 SculptureSmall NullRef)
                bool hasRock = false;
                foreach (var t in map.thingGrid.ThingsListAt(cell))
                {
                    if (t?.def != null && t.def.mineable)
                    {
                        rockCells.Add($"({cell.x},{cell.z})");
                        hasRock = true;
                        break;
                    }
                }

                // Check for existing blueprints or frames (skip for conduits)
                if (!isConduit)
                {
                    foreach (var t in map.thingGrid.ThingsListAt(cell))
                    {
                        if (t is Blueprint || t is Frame)
                        {
                            blueprintCells.Add($"({cell.x},{cell.z}) has {t.def.defName}");
                            break;
                        }
                    }
                }

                // Check for zones (skip for conduits)
                if (!isConduit)
                {
                    var zone = map.zoneManager.ZoneAt(cell);
                    if (zone != null)
                        zoneCells.Add($"({cell.x},{cell.z}) in {zone.label}");
                }

                // Check for existing impassable buildings (skip for conduits, skip rock already caught)
                if (!hasRock && !isConduit)
                {
                    var building = cell.GetFirstBuilding(map);
                    if (building?.def != null && building.def.passability == Traversability.Impassable)
                        impassableCells.Add($"({cell.x},{cell.z})");
                }

                // Check if this cell is the interaction spot of an existing building
                if (!isConduit)
                {
                    foreach (var b in map.listerBuildings.allBuildingsColonist)
                    {
                        if (b?.def != null && b.def.hasInteractionCell)
                        {
                            try
                            {
                                if (b.InteractionCell == cell)
                                {
                                    interactionCells.Add($"({cell.x},{cell.z}) used by {b.def.defName}");
                                    break;
                                }
                            }
                            catch (NullReferenceException) { /* skip buildings with broken interaction cells */ }
                        }
                    }
                }

                if (map.roofGrid.RoofAt(cell) == RoofDefOf.RoofRockThick)
                    underMountain = true;
            }

            // Also check if THIS building's interaction spot would be blocked by an impassable building
            if (thingDef.hasInteractionCell)
            {
                var myInteraction = ThingUtility.InteractionCellWhenAt(thingDef, pos, rot, map);
                if (myInteraction.InBounds(map))
                {
                    var blocker = myInteraction.GetFirstBuilding(map);
                    if (blocker != null && blocker.def.passability == Traversability.Impassable)
                        interactionCells.Add($"({myInteraction.x},{myInteraction.z}) blocks own interaction spot ({blocker.def.defName} in the way)");
                }
            }

            if (oobCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): cells out of bounds at {string.Join(", ", oobCells)}");
            if (rockCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): cells blocked by natural rock at {string.Join(", ", rockCells)}");
            if (waterCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): cells blocked by water at {string.Join(", ", waterCells)}");
            if (blueprintCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): existing blueprint/frame at {string.Join(", ", blueprintCells)}");
            if (zoneCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): zone overlap at {string.Join(", ", zoneCells)}");
            if (impassableCells.Count > 0)
            {
                // Return what's at the blocked cells so SDK can decide whether to skip
                var blockedInfo = new List<object>();
                foreach (var cell in occupiedRect)
                {
                    var building = cell.GetFirstBuilding(map);
                    if (building != null && building.def.passability == Traversability.Impassable)
                    {
                        var info = D("x", (object)cell.x, "z", (object)cell.z,
                                     "existing", building.def.defName);
                        if (building.Stuff != null)
                            info["stuff"] = building.Stuff.defName;
                        blockedInfo.Add(info);
                    }
                }
                throw new Exception($"Cell blocked|{SimpleJson.Serialize(D("cells", blockedInfo))}");
            }
            if (interactionCells.Count > 0)
                throw new Exception($"Cannot build {blueprintDef} at ({x},{y}): blocked interaction spot at {string.Join(", ", interactionCells)}");

            // No-cost items (spots etc.) placed directly with player faction
            bool noCost = thingDef.costList == null && !thingDef.MadeFromStuff && thingDef.costStuffCount == 0;
            if (noCost)
            {
                var thing = ThingMaker.MakeThing(thingDef);
                thing.SetFactionDirect(Faction.OfPlayer);
                GenSpawn.Spawn(thing, pos, map, rot);
            }
            else
            {
                // Ensure stuff is set for MadeFromStuff items (SculptureSmall NullRef fix)
                if (thingDef.MadeFromStuff && stuff == null)
                    stuff = GenStuff.DefaultStuffFor(thingDef);
                if (thingDef.MadeFromStuff && stuff == null)
                    throw new Exception($"Cannot build {blueprintDef}: MadeFromStuff=true but no valid stuff material found (tried '{stuffName}')");
                GenConstruct.PlaceBlueprintForBuild(thingDef, pos, map, rot, Faction.OfPlayer, stuff);
            }

            var result = D("ok", true, "blueprint", blueprintDef, "x", (object)x, "y", (object)y,
                     "stuff", stuff?.defName ?? (object)null, "instant", (object)noCost);
            if (underMountain)
                result["warning"] = "Building is under overhead mountain (thick roof) - collapse risk";
            return result;
        }

        /// <summary>
        /// Places floor blueprints in a single cell or rectangular area. Skips cells that already match.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - floor (string, required): TerrainDef defName or label (e.g. "WoodPlankFloor")
        /// - x/z or x1/z1/x2/z2 (int, required): single cell or rectangular bounds
        /// - stuff (string, optional): material defName for stuff-based floors
        /// </param>
        /// <returns>Dictionary with: ok (bool), floor (string), placed (int), skipped (int)</returns>
        public static object SetFloor(Dictionary<string, object> req)
        {
            var floorName = S(req, "floor");
            if (floorName == null) throw new Exception("Missing 'floor'");

            var map = GetMap() ?? throw new Exception("No active map");
            var floorDef = DefDatabase<TerrainDef>.GetNamedSilentFail(floorName);
            if (floorDef == null)
            {
                floorDef = DefDatabase<TerrainDef>.AllDefsListForReading.FirstOrDefault(t =>
                    t.label != null && t.label.Equals(floorName, StringComparison.OrdinalIgnoreCase));
            }
            if (floorDef == null) throw new Exception($"Unknown floor: {floorName}");

            int x1 = I(req, "x1", I(req, "x", -1));
            int z1 = I(req, "z1", I(req, "z", -1));
            int x2 = I(req, "x2", x1);
            int z2 = I(req, "z2", z1);
            if (x1 < 0 || z1 < 0) throw new Exception("Missing position (x,z or x1,z1,x2,z2)");

            ThingDef stuff = null;
            var stuffName = S(req, "stuff");
            if (!string.IsNullOrEmpty(stuffName))
            {
                stuff = DefDatabase<ThingDef>.GetNamedSilentFail(stuffName);
                if (stuff == null) throw new Exception($"Unknown stuff: {stuffName}");
            }

            int placed = 0, skipped = 0;
            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) { skipped++; continue; }
                // Skip if floor already matches
                if (cell.GetTerrain(map) == floorDef) { skipped++; continue; }
                try
                {
                    GenConstruct.PlaceBlueprintForBuild(
                        floorDef, cell, map, Rot4.North, Faction.OfPlayer, stuff);
                    placed++;
                }
                catch { skipped++; }
            }

            return D("ok", true, "floor", floorDef.defName,
                     "placed", (object)placed, "skipped", (object)skipped);
        }

        /// <summary>
        /// Designates up to 5 wild animals of a species for hunting. Never targets tame animals.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - animal (string, required): species defName (e.g. "Deer", "Boar")
        /// </param>
        /// <returns>Dictionary with: ok (bool), designated (int), animal (string), targets (string)</returns>
        public static object Hunt(Dictionary<string, object> req)
        {
            var animalKind = S(req, "animal");
            var map = GetMap() ?? throw new Exception("No active map");

            // If animal is null or empty, list available species for diagnostics
            if (string.IsNullOrEmpty(animalKind))
            {
                var species = map.mapPawns.AllPawnsSpawned
                    .Where(p => p.RaceProps.Animal && !p.Downed && !p.Dead)
                    .Select(p => p.def.defName)
                    .Distinct()
                    .ToList();
                throw new Exception($"No animal species specified. Available: {string.Join(", ", species)}");
            }

            var targets = map.mapPawns.AllPawnsSpawned
                .Where(p => p.RaceProps.Animal && !p.Downed && !p.Dead
                    && p.Faction != Faction.OfPlayer  // Never hunt tame animals
                    && p.def.defName.Equals(animalKind, StringComparison.OrdinalIgnoreCase))
                .Take(5).ToList();

            if (targets.Count == 0)
            {
                // Return available species so caller knows what's on the map
                var available = map.mapPawns.AllPawnsSpawned
                    .Where(p => p.RaceProps.Animal && !p.Downed && !p.Dead)
                    .Select(p => p.def.defName)
                    .Distinct()
                    .ToList();
                throw new Exception($"No huntable '{animalKind}' found. Available species: {string.Join(", ", available)}");
            }

            int count = 0;
            var names = new List<string>();
            foreach (var animal in targets)
            {
                var desig = map.designationManager.DesignationOn(animal, DesignationDefOf.Hunt);
                if (desig == null)
                {
                    map.designationManager.AddDesignation(new Designation(animal, DesignationDefOf.Hunt));
                    count++;
                    names.Add(animal.LabelShort);
                }
            }
            return D("ok", true, "designated", (object)count, "animal", animalKind,
                     "targets", string.Join(", ", names));
        }

        /// <summary>
        /// Designates trees for cutting within a radius of a center point.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): center X coordinate
        /// - z (int, required): center Z coordinate
        /// - radius (int, optional): search radius in tiles, default 20
        /// </param>
        /// <returns>Dictionary with: ok (bool), designated (int)</returns>
        public static object DesignateChop(Dictionary<string, object> req)
        {
            int x = I(req, "x"), z = I(req, "z"), radius = I(req, "radius", 20);
            var map = GetMap() ?? throw new Exception("No active map");
            var center = new IntVec3(x, 0, z);

            var trees = map.listerThings.ThingsInGroup(ThingRequestGroup.Plant)
                .OfType<Plant>()
                .Where(p => p.def.plant.IsTree && !p.Position.Fogged(map)
                    && (radius <= 0 || p.Position.InHorDistOf(center, radius))
                    && map.designationManager.DesignationOn(p, DesignationDefOf.CutPlant) == null)
                .ToList();

            int count = 0;
            foreach (var tree in trees)
            {
                if (map.designationManager.DesignationOn(tree, DesignationDefOf.CutPlant) == null)
                {
                    map.designationManager.AddDesignation(new Designation(tree, DesignationDefOf.CutPlant));
                    count++;
                }
            }
            return D("ok", true, "designated", (object)count);
        }

        /// <summary>
        /// Designates harvestable non-tree plants within a radius, optionally filtered by defName.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): center X coordinate
        /// - z (int, required): center Z coordinate
        /// - radius (int, optional): search radius in tiles, default 20
        /// - def (string, optional): comma-separated defNames to filter (e.g. "Plant_Berry,Plant_HealrootWild")
        /// </param>
        /// <returns>Dictionary with: ok (bool), designated (int)</returns>
        public static object DesignateHarvest(Dictionary<string, object> req)
        {
            int x = I(req, "x"), z = I(req, "z"), radius = I(req, "radius", 20);
            var map = GetMap() ?? throw new Exception("No active map");
            var center = new IntVec3(x, 0, z);

            // Optional defName filter (comma-separated, e.g. "Plant_Berry,Plant_HealrootWild")
            string filterDef = S(req, "def");
            HashSet<string> filterDefs = null;
            if (filterDef != null)
                filterDefs = new HashSet<string>(filterDef.Split(','), StringComparer.OrdinalIgnoreCase);

            var plants = map.listerThings.ThingsInGroup(ThingRequestGroup.Plant)
                .OfType<Plant>()
                .Where(p => !p.def.plant.IsTree
                    && p.HarvestableNow
                    && (radius <= 0 || p.Position.InHorDistOf(center, radius))
                    && (filterDefs == null || filterDefs.Contains(p.def.defName)))
                .ToList();

            int count = 0;
            foreach (var plant in plants)
            {
                if (map.designationManager.DesignationOn(plant, DesignationDefOf.HarvestPlant) == null)
                {
                    map.designationManager.AddDesignation(new Designation(plant, DesignationDefOf.HarvestPlant));
                    count++;
                }
            }
            float avgGrowth = plants.Count > 0 ? plants.Average(p => p.Growth) : 0f;
            int harvestable = plants.Count;
            int totalOnMap = map.listerThings.ThingsInGroup(ThingRequestGroup.Plant)
                .OfType<Plant>()
                .Count(p => !p.def.plant.IsTree
                    && (filterDefs == null || filterDefs.Contains(p.def.defName))
                    && (radius <= 0 || p.Position.InHorDistOf(center, radius)));
            return D("ok", true, "designated", (object)count,
                     "harvestable", (object)harvestable,
                     "total_plants", (object)totalOnMap,
                     "avg_growth", (object)Math.Round(avgGrowth, 3));
        }

        /// <summary>
        /// Creates a growing zone in a rectangular area, skipping rock, water, mountain, and existing zones.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle corner X
        /// - z1 (int, required): rectangle corner Z
        /// - x2 (int, required): opposite corner X
        /// - z2 (int, required): opposite corner Z
        /// - plant (string, optional): plant defName to grow, default "PlantPotato"
        /// </param>
        /// <returns>Dictionary with: ok (bool), cells (int), skipped (int), plant (string)</returns>
        public static object CreateGrowZone(Dictionary<string, object> req)
        {
            int x1 = I(req, "x1"), z1 = I(req, "z1"), x2 = I(req, "x2"), z2 = I(req, "z2");
            var plant = S(req, "plant") ?? "PlantPotato";
            var map = GetMap() ?? throw new Exception("No active map");

            var cells = new List<IntVec3>();
            int skipped = 0;
            for (int x = Math.Min(x1,x2); x <= Math.Max(x1,x2); x++)
                for (int z = Math.Min(z1,z2); z <= Math.Max(z1,z2); z++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(map)) { skipped++; continue; }

                    var terrain = cell.GetTerrain(map);
                    if (terrain.fertility <= 0f) { skipped++; continue; }
                    if (terrain.IsWater) { skipped++; continue; }
                    if (map.roofGrid.RoofAt(cell) == RoofDefOf.RoofRockThick) { skipped++; continue; }

                    // Skip cells with impassable things (natural rock walls)
                    bool hasImpassable = false;
                    foreach (var t in map.thingGrid.ThingsListAt(cell))
                    {
                        if (t.def.passability == Traversability.Impassable)
                        { hasImpassable = true; break; }
                    }
                    if (hasImpassable) { skipped++; continue; }

                    if (map.zoneManager.ZoneAt(cell) != null) { skipped++; continue; }

                    cells.Add(cell);
                }

            if (cells.Count == 0)
                throw new Exception("No valid cells for grow zone - all cells blocked by rock, water, mountain, or existing zones");

            var zone = new Zone_Growing(map.zoneManager);
            map.zoneManager.RegisterZone(zone);
            foreach (var cell in cells)
                zone.AddCell(cell);

            var plantDef = DefDatabase<ThingDef>.GetNamedSilentFail(plant);
            if (plantDef != null) zone.SetPlantDefToGrow(plantDef);

            return D("ok", true, "cells", (object)cells.Count, "skipped", (object)skipped, "plant", plant);
        }

        /// <summary>
        /// Creates a stockpile zone in a rectangular area. Steals cells from existing zones if needed.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle corner X
        /// - z1 (int, required): rectangle corner Z
        /// - x2 (int, required): opposite corner X
        /// - z2 (int, required): opposite corner Z
        /// - priority (string, optional): storage priority e.g. "Critical", "Preferred", "Normal" (default "Normal")
        /// </param>
        /// <returns>Dictionary with: ok (bool), cells (int), skipped (int), priority (string), label (string)</returns>
        public static object CreateStockpileZone(Dictionary<string, object> req)
        {
            int x1 = I(req, "x1"), z1 = I(req, "z1"), x2 = I(req, "x2"), z2 = I(req, "z2");
            var priority = S(req, "priority") ?? "Normal";
            var map = GetMap() ?? throw new Exception("No active map");

            var cells = new List<IntVec3>();
            int skipped = 0;
            int totalCells = 0;
            for (int x = Math.Min(x1,x2); x <= Math.Max(x1,x2); x++)
                for (int z = Math.Min(z1,z2); z <= Math.Max(z1,z2); z++)
                {
                    totalCells++;
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(map) || !cell.Standable(map) || cell.GetTerrain(map).IsWater)
                    {
                        skipped++;
                        continue;
                    }
                    // Steal cells from existing zones (matches standard RimWorld behavior)
                    var existingZone = map.zoneManager.ZoneAt(cell);
                    if (existingZone != null)
                    {
                        existingZone.RemoveCell(cell);
                        if (existingZone.Cells.Count == 0)
                            existingZone.Deregister();
                    }
                    cells.Add(cell);
                }

            if (cells.Count == 0) throw new Exception("No valid cells for stockpile in specified area");

            var zone = new Zone_Stockpile(StorageSettingsPreset.DefaultStockpile, map.zoneManager);
            map.zoneManager.RegisterZone(zone);
            foreach (var cell in cells)
                zone.AddCell(cell);

            // Set priority
            StoragePriority sp = StoragePriority.Normal;
            if (Enum.TryParse<StoragePriority>(priority, true, out var parsed))
                sp = parsed;
            zone.settings.Priority = sp;

            return D("ok", true, "cells", (object)cells.Count, "skipped", (object)skipped,
                     "priority", zone.settings.Priority.ToString(), "label", zone.label);
        }

        /// <summary>
        /// Cancels a blueprint or construction frame at the given position.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): X map coordinate
        /// - y (int, required): Z map coordinate (NOTE: y param maps to the game's Z axis)
        /// </param>
        /// <returns>Dictionary with: ok (bool), x (int), y (int)</returns>
        public static object CancelBuild(Dictionary<string, object> req)
        {
            int x = I(req, "x"), y = I(req, "y");
            var map = GetMap() ?? throw new Exception("No active map");
            var pos = new IntVec3(x, 0, y);
            var thing = pos.GetThingList(map).FirstOrDefault(t => t is Blueprint)
                     ?? pos.GetThingList(map).FirstOrDefault(t => t is Frame);
            if (thing == null) throw new Exception($"No blueprint or frame at ({x}, {y})");
            thing.Destroy(DestroyMode.Cancel);
            return D("ok", true, "x", (object)x, "y", (object)y);
        }

        /// <summary>
        /// Pauses the game (sets tick speed to 0).
        /// </summary>
        /// <param name="req">Parameters: none required.</param>
        /// <returns>Dictionary with: ok (bool), paused (bool)</returns>
        public static object Pause(Dictionary<string, object> req)
        {
            Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
            return D("ok", true, "paused", true);
        }

        /// <summary>
        /// Unpauses the game and auto-dismisses blocking ImmediateWindow dialogs.
        /// Defaults to speed 4 (Ultrafast) for maximum throughput.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - speed (int, optional): tick speed 1-4, default 4 (Ultrafast)
        /// </param>
        /// <returns>Dictionary with: ok (bool), paused (bool), speed (int), dialogs_dismissed (int)</returns>
        public static object Unpause(Dictionary<string, object> req)
        {
            // Auto-set speed 4 (Ultrafast) on unpause — skips rendering for max throughput
            int speed = I(req, "speed", 4);
            switch (speed)
            {
                case 1: Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;    break;
                case 2: Find.TickManager.CurTimeSpeed = TimeSpeed.Fast;      break;
                case 3: Find.TickManager.CurTimeSpeed = TimeSpeed.Superfast; break;
                case 4: Find.TickManager.CurTimeSpeed = TimeSpeed.Ultrafast; break;
                default: Find.TickManager.CurTimeSpeed = TimeSpeed.Ultrafast; break;
            }

            // Auto-dismiss ImmediateWindow dialogs (always harmless, but slow game 5x)
            int dismissed = 0;
            foreach (var w in Find.WindowStack.Windows.ToList())
            {
                if (w.GetType().Name == "ImmediateWindow")
                {
                    w.Close(true);
                    dismissed++;
                }
            }

            return D("ok", true, "paused", false, "speed", (object)speed,
                     "dialogs_dismissed", (object)dismissed);
        }

        /// <summary>
        /// Saves the game to a .rws file.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - name (string, optional): save file name (defaults to permadeath name or "CarolineSave")
        /// </param>
        /// <returns>Dictionary with: ok (bool), saved (bool)</returns>
        public static object Save(Dictionary<string, object> req)
        {
            var name = S(req, "name");
            GameDataSaveLoader.SaveGame(name ?? Find.GameInfo.permadeathModeUniqueName ?? "CarolineSave");
            return D("ok", true, "saved", true);
        }

        /// <summary>
        /// Loads a saved game by name, queued via LongEventHandler for next frame.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - name (string, required): save file name without .rws extension
        /// </param>
        /// <returns>Dictionary with: ok (bool), loading (string)</returns>
        public static object LoadGame(Dictionary<string, object> req)
        {
            var name = S(req, "name");
            if (name == null) throw new Exception("Need: name (save file name without .rws)");

            var saveDir = GenFilePaths.SaveDataFolderPath + "/Saves";
            var path = System.IO.Path.Combine(saveDir, name + ".rws");
            if (!System.IO.File.Exists(path))
                throw new Exception("Save not found: " + path);

            // Queue the load on the next frame via LongEventHandler
            LongEventHandler.QueueLongEvent(() =>
            {
                GameDataSaveLoader.LoadGame(name);
            }, "LoadingLongEvent", true, null);

            return D("ok", true, "loading", name);
        }

        /// <summary>
        /// Lists all .rws save files sorted by modification date (newest first).
        /// </summary>
        /// <param name="req">Parameters: none required.</param>
        /// <returns>Dictionary with: saves (list of {name, modified, size_mb})</returns>
        public static object ListSaves(Dictionary<string, object> req)
        {
            var saveDir = GenFilePaths.SaveDataFolderPath + "/Saves";
            var saves = new List<object>();
            if (System.IO.Directory.Exists(saveDir))
            {
                foreach (var file in System.IO.Directory.GetFiles(saveDir, "*.rws")
                    .OrderByDescending(f => System.IO.File.GetLastWriteTime(f)))
                {
                    var fi = new System.IO.FileInfo(file);
                    saves.Add(D("name", System.IO.Path.GetFileNameWithoutExtension(file),
                                "modified", fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"),
                                "size_mb", Math.Round(fi.Length / 1048576.0, 1)));
                }
            }
            return D("saves", saves);
        }
        /// <summary>
        /// Orders a drafted pawn to move to a specific map cell.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name
        /// - x (int, required): target X coordinate
        /// - z (int, required): target Z coordinate (also accepts "y")
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), x (int), z (int)</returns>
        public static object MovePawn(Dictionary<string, object> req)
        {
            string name = S(req, "pawn");
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));

            if (name == null || x < 0 || z < 0) throw new Exception("Need: pawn, x, z");
            var pawn = FindPawn(name);
            if (pawn == null) throw new Exception("Pawn '" + name + "' not found");
            if (!pawn.Drafted) throw new Exception("Draft pawn first");

            var map = GetMap();
            var cell = new IntVec3(x, 0, z);
            if (!cell.InBounds(map) || !cell.Walkable(map))
                throw new Exception("Invalid/unwalkable position");

            var job = JobMaker.MakeJob(JobDefOf.Goto, cell);
            pawn.jobs.TryTakeOrderedJob(job);
            return D("ok", true, "pawn", name, "x", (object)x, "z", (object)z);
        }

        /// <summary>
        /// Orders a drafted pawn to attack a target (ranged or melee based on equipped weapon).
        /// Target can be specified by name or by position.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): attacking pawn name
        /// - target (string, optional): target pawn/animal name
        /// - x (int, optional): target X coordinate (if no target name)
        /// - z (int, optional): target Z coordinate (if no target name)
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), target (string)</returns>
        public static object Attack(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            string targetName = S(req, "target");
            int tx = I(req, "x", -1);
            int tz = I(req, "z", -1);

            if (pawnName == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn '" + pawnName + "' not found");
            if (!pawn.Drafted) throw new Exception("Draft pawn first");

            var map = GetMap();
            Thing target = null;

            if (targetName != null)
            {
                target = FindPawn(targetName);
                if (target == null) target = FindAnimal(targetName);
            }
            else if (tx >= 0 && tz >= 0)
            {
                var cell = new IntVec3(tx, 0, tz);
                target = cell.GetFirstPawn(map);
                if (target == null) target = cell.GetFirstBuilding(map);
            }

            if (target == null) throw new Exception("Target not found");

            if (pawn.equipment != null && pawn.equipment.Primary != null && pawn.equipment.Primary.def.IsRangedWeapon)
            {
                var job = JobMaker.MakeJob(JobDefOf.AttackStatic, target);
                pawn.jobs.TryTakeOrderedJob(job);
            }
            else
            {
                var job = JobMaker.MakeJob(JobDefOf.AttackMelee, target);
                pawn.jobs.TryTakeOrderedJob(job);
            }

            return D("ok", true, "pawn", pawnName, "target", target.Label);
        }

        /// <summary>
        /// Orders a pawn to rescue a downed pawn and carry them to an available bed.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): rescuer pawn name
        /// - target (string, required): downed pawn name
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), target (string)</returns>
        public static object Rescue(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            string targetName = S(req, "target");

            if (pawnName == null || targetName == null) throw new Exception("Need: pawn, target");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found");
            var target = FindPawn(targetName);
            if (target == null) throw new Exception("Target '" + targetName + "' not found");
            if (!target.Downed) throw new Exception(targetName + " is not downed");

            var bed = RestUtility.FindBedFor(target, pawn, false);
            if (bed == null) throw new Exception("No available bed");

            var job = JobMaker.MakeJob(JobDefOf.Rescue, target, bed);
            job.count = 1;
            pawn.jobs.TryTakeOrderedJob(job);
            return D("ok", true, "pawn", pawnName, "target", targetName);
        }

        /// <summary>
        /// Orders a pawn to tend (provide medical care to) a target pawn, or self-tend if no target.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): doctor/tender pawn name
        /// - target (string, optional): patient pawn name (defaults to self)
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), target (string)</returns>
        public static object Tend(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            string targetName = S(req, "target");

            if (pawnName == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found");

            Pawn target = pawn;
            if (targetName != null)
            {
                target = FindPawn(targetName);
                if (target == null) throw new Exception("Target '" + targetName + "' not found");
            }

            var job = JobMaker.MakeJob(JobDefOf.TendPatient, target);
            pawn.jobs.TryTakeOrderedJob(job);
            return D("ok", true, "pawn", pawnName, "target", target == pawn ? "self" : target.Name.ToStringShort);
        }

        /// <summary>
        /// Orders a pawn to haul an item at a position to the nearest valid storage.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): hauler pawn name
        /// - x (int, required): item X coordinate
        /// - z (int, required): item Z coordinate (also accepts "y")
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), item (string)</returns>
        public static object Haul(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));

            if (pawnName == null || x < 0 || z < 0) throw new Exception("Need: pawn, x, z");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found");

            var map = GetMap();
            var cell = new IntVec3(x, 0, z);
            var thing = cell.GetFirstItem(map);
            if (thing == null) throw new Exception("No item at (" + x + "," + z + ")");

            var job = HaulAIUtility.HaulToStorageJob(pawn, thing, false);
            if (job == null) throw new Exception("Cannot haul " + thing.Label + " (no valid storage)");

            pawn.jobs.TryTakeOrderedJob(job);
            return D("ok", true, "pawn", pawnName, "item", thing.Label);
        }

        /// <summary>
        /// Orders a pawn to equip a weapon or wear apparel, found by position or defName.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name
        /// - thing (string, optional): item defName to find on map
        /// - x (int, optional): item X coordinate (alternative to thing)
        /// - z (int, optional): item Z coordinate
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), action (string: "equipping"/"wearing"), item (string)</returns>
        public static object Equip(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            string thingDef = S(req, "thing");
            int x = I(req, "x", -1);
            int z = I(req, "z", -1);

            if (pawnName == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found");

            var map = GetMap();
            Thing item = null;

            if (x >= 0 && z >= 0)
            {
                var cell = new IntVec3(x, 0, z);
                item = cell.GetFirstItem(map);
            }
            else if (thingDef != null)
            {
                item = map.listerThings.AllThings.FirstOrDefault(t =>
                    t.def.defName.Equals(thingDef, StringComparison.OrdinalIgnoreCase) &&
                    (t.def.IsWeapon || t.def.IsApparel) &&
                    !t.IsForbidden(Faction.OfPlayer));
            }

            if (item == null) throw new Exception("Item not found");

            if (item.def.IsWeapon)
            {
                var job = JobMaker.MakeJob(JobDefOf.Equip, item);
                pawn.jobs.TryTakeOrderedJob(job);
                return D("ok", true, "pawn", pawnName, "action", "equipping", "item", item.Label);
            }
            else if (item.def.IsApparel)
            {
                var job = JobMaker.MakeJob(JobDefOf.Wear, item);
                pawn.jobs.TryTakeOrderedJob(job);
                return D("ok", true, "pawn", pawnName, "action", "wearing", "item", item.Label);
            }
            else
            {
                throw new Exception(item.Label + " is not equipment or apparel");
            }
        }

        /// <summary>
        /// Forces a pawn to immediately perform a job of the given work type (e.g. Cooking, Hauling).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name
        /// - workType (string, required): WorkTypeDef defName (e.g. "Cooking", "Construction")
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), workType (string)</returns>
        public static object Prioritize(Dictionary<string, object> req)
        {
            string pawnName = S(req, "pawn");
            string workType = S(req, "workType");

            if (pawnName == null || workType == null) throw new Exception("Need: pawn, workType");
            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found");

            var wt = DefDatabase<WorkTypeDef>.GetNamedSilentFail(workType);
            if (wt == null) throw new Exception("Unknown workType: " + workType);

            foreach (var wg in wt.workGiversByPriority)
            {
                var scanner = wg.Worker;
                if (scanner == null) continue;
                try
                {
                    var job = scanner.NonScanJob(pawn);
                    if (job != null)
                    {
                        pawn.jobs.TryTakeOrderedJob(job);
                        return D("ok", true, "pawn", pawnName, "workType", workType);
                    }
                }
                catch { }
            }

            throw new Exception("No available " + workType + " job found for " + pawnName);
        }

        /// <summary>
        /// Designates all mineable rock in a rectangular area for mining.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle start X
        /// - z1 (int, required): rectangle start Z
        /// - x2 (int, optional): rectangle end X (default x1+10)
        /// - z2 (int, optional): rectangle end Z (default z1+10)
        /// </param>
        /// <returns>Dictionary with: ok (bool), designated (int)</returns>
        public static object DesignateMine(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1 = I(req, "x1", 0), z1 = I(req, "z1", 0);
            int x2 = I(req, "x2", x1 + 10), z2 = I(req, "z2", z1 + 10);
            int count = 0;
            for (int x = Math.Min(x1, x2); x <= Math.Max(x1, x2); x++)
            for (int z = Math.Min(z1, z2); z <= Math.Max(z1, z2); z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                foreach (var t in map.thingGrid.ThingsListAt(cell))
                    if (t.def.mineable && map.designationManager.DesignationOn(t, DesignationDefOf.Mine) == null)
                    {
                        map.designationManager.AddDesignation(new Designation(t, DesignationDefOf.Mine));
                        count++;
                        break;
                    }
            }
            return D("ok", true, "designated", (object)count);
        }

        /// <summary>
        /// Designates a wild animal for taming. Matches by defName or kindDef (partial, case-insensitive).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - animal (string, required): species name or partial match
        /// </param>
        /// <returns>Dictionary with: ok (bool), animal (string), kind (string)</returns>
        public static object Tame(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            string kind = S(req, "animal");
            if (kind == null) throw new Exception("Need: animal");

            Pawn target = null;
            foreach (var a in map.mapPawns.AllPawnsSpawned)
                if (a.RaceProps != null && a.RaceProps.Animal && !a.Dead && a.Faction == null &&
                    (a.def.defName.ToLower().Contains(kind.ToLower()) || a.kindDef.defName.ToLower().Contains(kind.ToLower())))
                { target = a; break; }

            if (target == null) throw new Exception("Wild animal not found: " + kind);

            if (map.designationManager.DesignationOn(target, DesignationDefOf.Tame) == null)
                map.designationManager.AddDesignation(new Designation(target, DesignationDefOf.Tame));

            return D("ok", true, "animal", target.LabelShort, "kind", target.def.defName);
        }

        /// <summary>
        /// Designates an animal for slaughter by name, defName, or label.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - animal (string, required): animal name, defName, or short label
        /// </param>
        /// <returns>Dictionary with: ok (bool), animal (string)</returns>
        public static object Slaughter(Dictionary<string, object> req)
        {
            string name = S(req, "animal");
            if (name == null) throw new Exception("Missing 'animal'");

            var animal = FindAnimal(name);
            if (animal == null) throw new Exception("Animal '" + name + "' not found");

            var map = GetMap();
            if (map.designationManager.DesignationOn(animal, DesignationDefOf.Slaughter) == null)
                map.designationManager.AddDesignation(new Designation(animal, DesignationDefOf.Slaughter));

            return D("ok", true, "animal", animal.LabelShort);
        }

        /// <summary>
        /// Designates a building at a position for deconstruction.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): building X coordinate
        /// - z (int, required): building Z coordinate (also accepts "y")
        /// </param>
        /// <returns>Dictionary with: ok (bool), building (string), x (int), z (int)</returns>
        public static object Deconstruct(Dictionary<string, object> req)
        {
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));
            if (x < 0 || z < 0) throw new Exception("Need: x, z");

            var map = GetMap();
            var pos = new IntVec3(x, 0, z);
            var building = pos.GetFirstBuilding(map);
            if (building == null) throw new Exception("No building at (" + x + "," + z + ")");

            if (map.designationManager.DesignationOn(building, DesignationDefOf.Deconstruct) == null)
                map.designationManager.AddDesignation(new Designation(building, DesignationDefOf.Deconstruct));

            return D("ok", true, "building", building.def.defName, "x", (object)x, "z", (object)z);
        }

        /// <summary>
        /// Cancels all designations (mine, chop, hunt, etc.) at a single cell position.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): cell X coordinate
        /// - z (int, required): cell Z coordinate (also accepts "y")
        /// </param>
        /// <returns>Dictionary with: ok (bool), x (int), z (int)</returns>
        public static object CancelDesignation(Dictionary<string, object> req)
        {
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));
            if (x < 0 || z < 0) throw new Exception("Need: x, z");

            var map = GetMap();
            var pos = new IntVec3(x, 0, z);
            bool cancelled = false;

            var desigs = map.designationManager.AllDesignationsAt(pos).ToList();
            foreach (var d in desigs)
            {
                map.designationManager.RemoveDesignation(d);
                cancelled = true;
            }

            var things = pos.GetThingList(map);
            foreach (var thing in things)
            {
                var thingDesigs = map.designationManager.AllDesignationsOn(thing).ToList();
                foreach (var d in thingDesigs)
                {
                    map.designationManager.RemoveDesignation(d);
                    cancelled = true;
                }
            }

            if (!cancelled) throw new Exception("No designations at (" + x + "," + z + ")");
            return D("ok", true, "x", (object)x, "z", (object)z);
        }

        /// <summary>
        /// Bulk-cancels designations in a rectangular area, optionally filtered by kind.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle start X
        /// - z1 (int, required): rectangle start Z
        /// - x2 (int, required): rectangle end X
        /// - z2 (int, required): rectangle end Z
        /// - kind (string, optional): filter — "chop", "harvest", "mine", "deconstruct", "hunt", or "haul" (all if omitted)
        /// </param>
        /// <returns>Dictionary with: ok (bool), cancelled (int), bounds ({x1,z1,x2,z2}), kind (string)</returns>
        public static object CancelDesignations(Dictionary<string, object> req)
        {
            int x1 = I(req, "x1", -1), z1 = I(req, "z1", -1);
            int x2 = I(req, "x2", -1), z2 = I(req, "z2", -1);
            if (x1 < 0 || z1 < 0 || x2 < 0 || z2 < 0) throw new Exception("Need: x1, z1, x2, z2");

            string kind = S(req, "kind"); // optional: "chop", "harvest", "mine", "deconstruct", "hunt", "haul"

            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            // Map kind string to designation def
            DesignationDef targetDef = null;
            if (kind != null)
            {
                switch (kind.ToLower())
                {
                    case "chop": case "cut": targetDef = DesignationDefOf.CutPlant; break;
                    case "harvest": targetDef = DesignationDefOf.HarvestPlant; break;
                    case "mine": targetDef = DesignationDefOf.Mine; break;
                    case "deconstruct": targetDef = DesignationDefOf.Deconstruct; break;
                    case "hunt": targetDef = DesignationDefOf.Hunt; break;
                    case "haul": targetDef = DesignationDefOf.Haul; break;
                    default: throw new Exception("Unknown designation kind: " + kind + ". Valid: chop, harvest, mine, deconstruct, hunt, haul");
                }
            }

            int cancelled = 0;
            int minX = Math.Min(x1, x2), maxX = Math.Max(x1, x2);
            int minZ = Math.Min(z1, z2), maxZ = Math.Max(z1, z2);

            for (int x = minX; x <= maxX; x++)
            for (int z = minZ; z <= maxZ; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;

                // Cancel cell-based designations (e.g. mine)
                var cellDesigs = map.designationManager.AllDesignationsAt(cell).ToList();
                foreach (var d in cellDesigs)
                {
                    if (targetDef == null || d.def == targetDef)
                    {
                        map.designationManager.RemoveDesignation(d);
                        cancelled++;
                    }
                }

                // Cancel thing-based designations (e.g. chop, harvest, hunt)
                var things = cell.GetThingList(map);
                foreach (var thing in things)
                {
                    var thingDesigs = map.designationManager.AllDesignationsOn(thing).ToList();
                    foreach (var d in thingDesigs)
                    {
                        if (targetDef == null || d.def == targetDef)
                        {
                            map.designationManager.RemoveDesignation(d);
                            cancelled++;
                        }
                    }
                }
            }

            return D("ok", true, "cancelled", (object)cancelled, "bounds",
                D("x1", (object)minX, "z1", (object)minZ, "x2", (object)maxX, "z2", (object)maxZ),
                "kind", kind ?? "all");
        }

        /// <summary>
        /// Forbids items at a position, by defName, or all items on the map.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, optional): cell X coordinate
        /// - z (int, optional): cell Z coordinate (also accepts "y")
        /// - thingDef (string, optional): forbid all items of this defName
        /// - all (string, optional): if present, forbid all items on the map
        /// </param>
        /// <returns>Dictionary with: ok (bool), count (int), forbidden (bool)</returns>
        public static object ForbidCmd(Dictionary<string, object> req)
        {
            return SetForbidden(req, true);
        }

        /// <summary>
        /// Unforbids items at a position, by defName, or all items on the map.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, optional): cell X coordinate
        /// - z (int, optional): cell Z coordinate (also accepts "y")
        /// - thingDef (string, optional): unforbid all items of this defName
        /// - all (string, optional): if present, unforbid all items on the map
        /// </param>
        /// <returns>Dictionary with: ok (bool), count (int), forbidden (bool)</returns>
        public static object UnforbidCmd(Dictionary<string, object> req)
        {
            return SetForbidden(req, false);
        }

        private static object SetForbidden(Dictionary<string, object> req, bool forbid)
        {
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));
            string thingDef = S(req, "thingDef");

            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            if (x >= 0 && z >= 0)
            {
                var cell = new IntVec3(x, 0, z);
                var things = cell.GetThingList(map);
                int count = 0;
                foreach (var thing in things)
                {
                    if (thing.def.category == ThingCategory.Item && thing is ThingWithComps twc && twc.GetComp<CompForbiddable>() != null)
                    {
                        thing.SetForbidden(forbid);
                        count++;
                    }
                }
                if (count == 0) throw new Exception("No items at (" + x + "," + z + ")");
                return D("ok", true, "count", (object)count, "forbidden", (object)forbid);
            }
            else if (thingDef != null)
            {
                int count = 0;
                foreach (var thing in map.listerThings.AllThings)
                {
                    if (thing.def.defName.Equals(thingDef, StringComparison.OrdinalIgnoreCase)
                        && thing.def.category == ThingCategory.Item
                        && thing is ThingWithComps twc2 && twc2.GetComp<CompForbiddable>() != null)
                    {
                        thing.SetForbidden(forbid);
                        count++;
                    }
                }
                if (count == 0) throw new Exception("No " + thingDef + " found");
                return D("ok", true, "count", (object)count, "thingDef", thingDef, "forbidden", (object)forbid);
            }
            else if (S(req, "all") != null)
            {
                int count = 0;
                foreach (var thing in map.listerThings.AllThings)
                {
                    if (thing.def.category == ThingCategory.Item ||
                        (thing.def.thingCategories != null && thing.def.thingCategories.Any(c => c?.defName?.Contains("Chunk") == true)))
                    {
                        var comp = thing as ThingWithComps;
                        if (comp != null)
                        {
                            var forbiddable = comp.GetComp<CompForbiddable>();
                            if (forbiddable != null && forbiddable.Forbidden == forbid)
                            {
                                // already in desired state
                            }
                            else if (forbiddable != null)
                            {
                                thing.SetForbidden(forbid);
                                count++;
                            }
                        }
                    }
                }
                return D("ok", true, "count", (object)count, "forbidden", (object)forbid);
            }
            else
            {
                throw new Exception("Need: x,z or thingDef or all");
            }
        }

        /// <summary>
        /// Sets the active research project by defName or label.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - project (string, required): research project defName or label
        /// </param>
        /// <returns>Dictionary with: ok (bool), project (string)</returns>
        public static object SetResearch(Dictionary<string, object> req)
        {
            string project = S(req, "project");
            if (project == null) throw new Exception("Missing 'project'");

            var proj = DefDatabase<ResearchProjectDef>.GetNamedSilentFail(project);
            if (proj == null)
            {
                proj = DefDatabase<ResearchProjectDef>.AllDefsListForReading.FirstOrDefault(r =>
                    r.label.Equals(project, StringComparison.OrdinalIgnoreCase));
            }
            if (proj == null) throw new Exception("Research project '" + project + "' not found");
            if (proj.IsFinished) throw new Exception(project + " already completed");

            Find.ResearchManager.SetCurrentProject(proj);
            return D("ok", true, "project", proj.label);
        }

        /// <summary>
        /// Changes the plant type assigned to a growing zone.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - zone (string, optional): zone label or partial match, default "1"
        /// - plant (string, optional): plant defName, default "Plant_Rice"
        /// </param>
        /// <returns>Dictionary with: ok (bool), zone (string), plant (string)</returns>
        public static object SetPlant(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            string zoneName = S(req, "zone") ?? "1";
            string plantName = S(req, "plant") ?? "Plant_Rice";

            var plantDef = DefDatabase<ThingDef>.GetNamedSilentFail(plantName);
            if (plantDef == null) throw new Exception("Plant not found: " + plantName);

            Zone_Growing zone = null;
            foreach (var z in map.zoneManager.AllZones.OfType<Zone_Growing>())
                if (z.label.ToLower().Contains(zoneName.ToLower())) { zone = z; break; }
            if (zone == null) throw new Exception("Zone not found: " + zoneName);

            zone.SetPlantDefToGrow(plantDef);
            return D("ok", true, "zone", zone.label, "plant", plantName);
        }

        /// <summary>
        /// Deletes a zone at a cell position, or all growing zones if no position given.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, optional): cell X coordinate (omit to delete all growing zones)
        /// - z (int, optional): cell Z coordinate
        /// </param>
        /// <returns>Dictionary with: ok (bool), deleted (int or string)</returns>
        public static object DeleteZone(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x = I(req, "x", -1), z = I(req, "z", -1);

            if (x < 0)
            {
                var zones = map.zoneManager.AllZones.OfType<Zone_Growing>().ToList();
                foreach (var zn in zones) zn.Delete();
                return D("ok", true, "deleted", (object)zones.Count);
            }

            var zone = map.zoneManager.ZoneAt(new IntVec3(x, 0, z));
            if (zone == null) throw new Exception("No zone at cell");
            string label = zone.label;
            zone.Delete();
            return D("ok", true, "deleted", label);
        }

        /// <summary>
        /// Removes cells from zones in a rectangular area, or at a single cell.
        /// Zones that lose all their cells are automatically deleted.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): left bound (or single cell X if x2/z2 omitted)
        /// - z1 (int, required): top bound (or single cell Z if x2/z2 omitted)
        /// - x2 (int, optional): right bound (defaults to x1 for single cell)
        /// - z2 (int, optional): bottom bound (defaults to z1 for single cell)
        /// </param>
        /// <returns>Dictionary with: ok (bool), removed (int cells removed), deleted (int zones fully deleted)</returns>
        public static object RemoveZoneCells(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            int x1 = I(req, "x1"), z1 = I(req, "z1");
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);

            int removed = 0;
            var emptyZones = new HashSet<Zone>();

            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var zone = map.zoneManager.ZoneAt(cell);
                if (zone == null) continue;
                zone.RemoveCell(cell);
                removed++;
                if (zone.Cells.Count == 0)
                    emptyZones.Add(zone);
            }

            foreach (var zone in emptyZones)
                zone.Delete();

            return D("ok", true, "removed", (object)removed, "deleted", (object)emptyZones.Count);
        }

        /// <summary>
        /// Scans the map for water bodies, clustering them into rivers, lakes, and marshes
        /// with bounding boxes and flow direction.
        /// </summary>
        /// <param name="req">Parameters: none required.</param>
        /// <returns>Dictionary with: bodies (list of {type, direction, bounds, cell_count}), total_water_cells (int)</returns>
        public static object FindWater(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            // Sample every 4th cell for water
            var waterCells = new List<IntVec3>();
            var waterTerrain = new Dictionary<IntVec3, string>();
            for (int x = 0; x < map.Size.x; x += 4)
            for (int z = 0; z < map.Size.z; z += 4)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var terrain = cell.GetTerrain(map);
                if (terrain != null && terrain.IsWater)
                {
                    waterCells.Add(cell);
                    waterTerrain[cell] = terrain.defName;
                }
            }

            // Cluster water cells into bodies (cells within 8 tiles = same body)
            const int clusterDist = 8;
            var visited = new HashSet<int>();
            var bodies = new List<object>();
            int totalWater = waterCells.Count;

            for (int i = 0; i < waterCells.Count; i++)
            {
                if (visited.Contains(i)) continue;
                var cluster = new List<int>();
                var queue = new Queue<int>();
                queue.Enqueue(i);
                visited.Add(i);
                while (queue.Count > 0)
                {
                    int cur = queue.Dequeue();
                    cluster.Add(cur);
                    for (int j = 0; j < waterCells.Count; j++)
                    {
                        if (visited.Contains(j)) continue;
                        int dx = Math.Abs(waterCells[cur].x - waterCells[j].x);
                        int dz = Math.Abs(waterCells[cur].z - waterCells[j].z);
                        if (dx <= clusterDist && dz <= clusterDist)
                        {
                            visited.Add(j);
                            queue.Enqueue(j);
                        }
                    }
                }

                // Compute bounding box and classify
                int bx1 = int.MaxValue, bz1 = int.MaxValue, bx2 = int.MinValue, bz2 = int.MinValue;
                int riverCount = 0, marshCount = 0;
                foreach (int ci in cluster)
                {
                    var c = waterCells[ci];
                    if (c.x < bx1) bx1 = c.x;
                    if (c.z < bz1) bz1 = c.z;
                    if (c.x > bx2) bx2 = c.x;
                    if (c.z > bz2) bz2 = c.z;
                    var tn = waterTerrain[c];
                    if (tn.StartsWith("WaterMoving")) riverCount++;
                    else if (tn.Contains("Marsh")) marshCount++;
                }

                string bodyType = riverCount > marshCount && riverCount > cluster.Count / 3 ? "river"
                                : marshCount > riverCount && marshCount > cluster.Count / 3 ? "marsh"
                                : "lake";

                int bw = bx2 - bx1;
                int bh = bz2 - bz1;
                string direction = bodyType == "lake" ? null
                                 : bh > bw ? "N-S" : "E-W";

                var body = D(
                    "type", bodyType,
                    "direction", (object)direction,
                    "bounds", (object)new List<object> { bx1, bz1, bx2, bz2 },
                    "cell_count", (object)cluster.Count
                );
                bodies.Add((object)body);
            }

            return D("bodies", bodies, "total_water_cells", (object)totalWater);
        }

        /// <summary>
        /// Finds the best contiguous fertile area for a grow zone near a center point.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - size (int, optional): side length of the square area, default 12
        /// - radius (int, optional): search radius from center, default 80
        /// - cx (int, optional): center X, default map center
        /// - cz (int, optional): center Z, default map center
        /// </param>
        /// <returns>Dictionary with: x1 (int), z1 (int), x2 (int), z2 (int), cells (int)</returns>
        public static object FindGrowSpot(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int size = I(req, "size", 12), radius = I(req, "radius", 80);
            int cx = I(req, "cx", map.Size.x / 2), cz = I(req, "cz", map.Size.z / 2);
            int bestX = -1, bestZ = -1, bestCount = 0;

            for (int ox = cx - radius; ox < cx + radius - size; ox += 4)
            for (int oz = cz - radius; oz < cz + radius - size; oz += 4)
            {
                int count = 0; bool valid = true;
                for (int x = ox; x < ox + size && valid; x++)
                for (int z = oz; z < oz + size && valid; z++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(map)) { valid = false; break; }
                    var terrain = cell.GetTerrain(map);
                    bool ok = terrain != null && terrain.fertility > 0f && !terrain.IsWater
                              && map.roofGrid.RoofAt(cell) == null && map.zoneManager.ZoneAt(cell) == null;
                    if (ok) count++; else valid = false;
                }
                if (valid && count > bestCount) { bestCount = count; bestX = ox; bestZ = oz; }
            }

            if (bestX < 0) throw new Exception("No grow spot found");
            return D("x1", (object)bestX, "z1", (object)bestZ, "x2", (object)(bestX + size), "z2", (object)(bestZ + size), "cells", (object)bestCount);
        }

        /// <summary>
        /// Finds the closest clear rectangular area (no buildings, water, or rock) near a center point.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - width (int, optional): rectangle width, default 9
        /// - height (int, optional): rectangle height, default 7
        /// - radius (int, optional): search radius from center, default 30
        /// - cx (int, optional): center X, default map center
        /// - cz (int, optional): center Z, default map center
        /// </param>
        /// <returns>Dictionary with: x1 (int), z1 (int), x2 (int), z2 (int)</returns>
        public static object FindClearRect(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int width = I(req, "width", 9), height = I(req, "height", 7);
            int radius = I(req, "radius", 30);
            int cx = I(req, "cx", map.Size.x / 2), cz = I(req, "cz", map.Size.z / 2);
            int bestX = -1, bestZ = -1, bestDist = int.MaxValue;

            for (int ox = cx - radius; ox < cx + radius - width; ox += 2)
            for (int oz = cz - radius; oz < cz + radius - height; oz += 2)
            {
                bool valid = true;
                for (int x = ox; x < ox + width && valid; x++)
                for (int z = oz; z < oz + height && valid; z++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(map)) { valid = false; break; }
                    if (!cell.Walkable(map)) { valid = false; break; }
                    var terrain = cell.GetTerrain(map);
                    if (terrain != null && terrain.IsWater) { valid = false; break; }
                    foreach (var t in cell.GetThingList(map))
                    {
                        if (t.def.category == ThingCategory.Building ||
                            t.def.IsBlueprint || t is Frame ||
                            (t.def.building != null && t.def.building.isNaturalRock))
                        { valid = false; break; }
                    }
                }
                if (valid)
                {
                    int dist = (ox + width/2 - cx) * (ox + width/2 - cx) + (oz + height/2 - cz) * (oz + height/2 - cz);
                    if (dist < bestDist) { bestDist = dist; bestX = ox; bestZ = oz; }
                }
            }

            if (bestX < 0) throw new Exception($"No clear {width}x{height} area found within radius {radius}");
            return D("x1", (object)bestX, "z1", (object)bestZ, "x2", (object)(bestX + width), "z2", (object)(bestZ + height));
        }

        /// <summary>
        /// Jumps the camera to a specific map position.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, optional): target X coordinate, default 125
        /// - z (int, optional): target Z coordinate, default 125
        /// </param>
        /// <returns>Dictionary with: ok (bool), x (int), z (int)</returns>
        public static object CameraJump(Dictionary<string, object> req)
        {
            int x = I(req, "x", 125), z = I(req, "z", 125);
            CameraJumper.TryJump(new IntVec3(x, 0, z), Find.CurrentMap);
            return D("ok", true, "x", (object)x, "z", (object)z);
        }

        /// <summary>
        /// Creates a fishing zone on water cells using reflection to find the modded zone type.
        /// Requires a fishing mod (e.g. Vanilla Fishing Expanded) to be installed.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle start X
        /// - z1 (int, required): rectangle start Z
        /// - x2 (int, optional): rectangle end X (defaults to x1)
        /// - z2 (int, optional): rectangle end Z (defaults to z1)
        /// </param>
        /// <returns>Dictionary with: ok (bool), type (string), cells (int), skipped (int), label (string)</returns>
        public static object CreateFishingZone(Dictionary<string, object> req)
        {
            int x1 = I(req, "x1", -1), z1 = I(req, "z1", -1);
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);
            if (x1 < 0 || z1 < 0) throw new Exception("Need: x1, z1 (and optionally x2, z2)");

            var map = GetMap() ?? throw new Exception("No active map");

            // Find the fishing zone type from mods via reflection
            System.Type fishingZoneType = null;
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    foreach (var type in asm.GetTypes())
                    {
                        if (type.Name.IndexOf("fish", StringComparison.OrdinalIgnoreCase) >= 0
                            && typeof(Zone).IsAssignableFrom(type))
                        {
                            fishingZoneType = type;
                            break;
                        }
                    }
                    if (fishingZoneType != null) break;
                }
                catch { continue; }
            }

            if (fishingZoneType == null)
                throw new Exception("No fishing zone type found. Is a fishing mod installed?");

            var cells = new List<IntVec3>();
            int skipped = 0;
            for (int x = Math.Min(x1,x2); x <= Math.Max(x1,x2); x++)
                for (int z = Math.Min(z1,z2); z <= Math.Max(z1,z2); z++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(map) || map.zoneManager.ZoneAt(cell) != null)
                    {
                        skipped++;
                        continue;
                    }
                    var terrain = cell.GetTerrain(map);
                    if (terrain == null || !terrain.IsWater)
                    {
                        skipped++;
                        continue;
                    }
                    cells.Add(cell);
                }

            if (cells.Count == 0) throw new Exception("No valid water cells for fishing zone");

            // Create the zone via reflection (constructor usually takes ZoneManager)
            Zone zone;
            try
            {
                var ctor = fishingZoneType.GetConstructor(new[] { typeof(ZoneManager) });
                if (ctor != null)
                    zone = (Zone)ctor.Invoke(new object[] { map.zoneManager });
                else
                {
                    ctor = fishingZoneType.GetConstructor(new[] { typeof(ZoneManager), typeof(Map) });
                    if (ctor != null)
                        zone = (Zone)ctor.Invoke(new object[] { map.zoneManager, map });
                    else
                        throw new Exception($"Cannot construct {fishingZoneType.Name}: no suitable constructor");
                }
            }
            catch (Exception ex)
            {
                throw new Exception($"Failed to create {fishingZoneType.Name}: {ex.Message}");
            }

            map.zoneManager.RegisterZone(zone);
            foreach (var cell in cells)
                zone.AddCell(cell);

            return D("ok", true, "type", fishingZoneType.Name, "cells", (object)cells.Count,
                     "skipped", (object)skipped, "label", zone.label);
        }

        /// <summary>
        /// Seeds a water body with fish population via reflection (Odyssey DLC).
        /// Sets population count and enables the shouldHaveFish flag.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, required): water cell X coordinate
        /// - z (int, required): water cell Z coordinate
        /// - population (int, optional): fish population to set, default 100
        /// </param>
        /// <returns>Dictionary with: ok (bool), population (float), shouldHaveFish (bool), cellCount (int), cell (string)</returns>
        public static object SeedFish(Dictionary<string, object> req)
        {
            int x = I(req, "x", -1), z = I(req, "z", -1);
            int population = I(req, "population", 100);
            if (x < 0 || z < 0) throw new Exception("Need: x, z (water cell), optional population (default 100)");

            var map = GetMap() ?? throw new Exception("No active map");
            var cell = new IntVec3(x, 0, z);

            // Find WaterBody at this cell using reflection (Odyssey DLC)
            var tracker = map.GetType().GetProperty("waterBodyTracker")?.GetValue(map)
                       ?? map.GetType().GetField("waterBodyTracker", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(map);
            if (tracker == null)
                throw new Exception("No waterBodyTracker on map — Odyssey DLC required");

            // Get the WaterBody at this cell
            var getBodyMethod = tracker.GetType().GetMethod("GetBodyAt")
                             ?? tracker.GetType().GetMethod("WaterBodyAt");
            object waterBody = null;
            if (getBodyMethod != null)
            {
                waterBody = getBodyMethod.Invoke(tracker, new object[] { cell });
            }
            else
            {
                // Fallback: iterate waterBodies list
                var bodiesField = tracker.GetType().GetField("waterBodies", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (bodiesField != null)
                {
                    var bodies = bodiesField.GetValue(tracker) as System.Collections.IList;
                    if (bodies != null)
                    {
                        foreach (var body in bodies)
                        {
                            var cellCountProp = body.GetType().GetField("cellCount", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                            var rootCellProp = body.GetType().GetField("rootCell", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                            if (cellCountProp != null)
                            {
                                waterBody = body;
                                break;  // Take the first body (or closest)
                            }
                        }
                    }
                }
            }

            if (waterBody == null)
                throw new Exception($"No water body found at ({x},{z}). Is there water here?");

            // Set population
            var popField = waterBody.GetType().GetField("population", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (popField != null)
            {
                popField.SetValue(waterBody, (float)population);
            }

            // Set shouldHaveFish
            var fishField = waterBody.GetType().GetField("shouldHaveFish", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (fishField != null)
            {
                fishField.SetValue(waterBody, true);
            }

            // Try to set common fish species
            var commonField = waterBody.GetType().GetField("commonFish", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (commonField != null)
            {
                var fishList = commonField.GetValue(waterBody) as System.Collections.IList;
                if (fishList != null && fishList.Count == 0)
                {
                    // Add default freshwater fish
                    foreach (var fishName in new[] { "Fish_Bass", "Fish_Tilapia" })
                    {
                        var fishDef = DefDatabase<ThingDef>.GetNamedSilentFail(fishName);
                        if (fishDef != null)
                            fishList.Add(fishDef);
                    }
                }
            }

            // Read back state
            float curPop = popField != null ? (float)popField.GetValue(waterBody) : -1;
            bool hasFish = fishField != null ? (bool)fishField.GetValue(waterBody) : false;
            int cellCount = -1;
            var ccField = waterBody.GetType().GetField("cellCount", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (ccField != null) cellCount = (int)ccField.GetValue(waterBody);

            return D("ok", true, "population", (object)curPop, "shouldHaveFish", (object)hasFish,
                     "cellCount", (object)cellCount, "cell", $"({x},{z})");
        }

        /// <summary>
        /// Instantly places a thing on the map (bypasses construction, sets player faction).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - thingDef (string, required): ThingDef defName to place
        /// - x (int, required): X map coordinate
        /// - z (int, required): Z map coordinate (also accepts "y")
        /// - rotation (int, optional): 0-3, default 0
        /// - stuffDef (string, optional): material defName
        /// </param>
        /// <returns>Dictionary with: ok (bool), thingDef (string), x (int), z (int)</returns>
        public static object Place(Dictionary<string, object> req)
        {
            string thingDefName = S(req, "thingDef");
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));
            int rot = I(req, "rotation", 0);
            string stuffDefName = S(req, "stuffDef");

            if (thingDefName == null || x < 0 || z < 0) throw new Exception("Need: thingDef, x, z");

            var def = DefDatabase<ThingDef>.GetNamedSilentFail(thingDefName);
            if (def == null) throw new Exception("Unknown thingDef: " + thingDefName);

            var map = GetMap();
            var pos = new IntVec3(x, 0, z);
            var rotation = new Rot4(rot);

            if (!pos.InBounds(map)) throw new Exception("Position out of bounds");

            ThingDef stuff = null;
            if (stuffDefName != null)
                stuff = DefDatabase<ThingDef>.GetNamedSilentFail(stuffDefName);
            else if (def.MadeFromStuff)
                stuff = GenStuff.DefaultStuffFor(def);

            Thing thing = ThingMaker.MakeThing(def, stuff);
            thing.SetFactionDirect(Faction.OfPlayer);
            GenSpawn.Spawn(thing, pos, map, rotation, WipeMode.Vanish, false);
            return D("ok", true, "thingDef", thingDefName, "x", (object)x, "z", (object)z);
        }

        /// <summary>
        /// Opens a letter by index, returning its text and any dialog options that appear.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - index (int, required): zero-based letter index (use read_letters to list)
        /// </param>
        /// <returns>Dictionary with: label (string), type (string), text (string),
        /// dialog_opened (bool), dialog_title (string), options (list)</returns>
        public static object OpenLetter(Dictionary<string, object> req)
        {
            int index = I(req, "index", -1);
            var letters = Find.LetterStack.LettersListForReading;

            if (index < 0 || index >= letters.Count)
                throw new Exception("Invalid letter index. Use read_letters to see available.");

            var letter = letters[index];
            var result = D("label", letter.Label, "type", letter.GetType().Name);

            var textField = letter.GetType().GetField("text",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (textField != null)
            {
                var text = textField.GetValue(letter) as string;
                if (text != null) result["text"] = text;
            }

            letter.OpenLetter();

            var dialog = FindTopDialog();
            if (dialog != null)
            {
                result["dialog_opened"] = true;
                result["dialog_title"] = GetDialogTitle(dialog);
                result["options"] = GetDialogOptions(dialog);
            }

            return result;
        }

        /// <summary>
        /// Dismisses (removes) a letter from the letter stack by index.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - index (int, required): zero-based letter index
        /// </param>
        /// <returns>Dictionary with: ok (bool), dismissed (string: letter label)</returns>
        public static object DismissLetter(Dictionary<string, object> req)
        {
            int index = I(req, "index", -1);
            var letters = Find.LetterStack.LettersListForReading;

            if (index < 0 || index >= letters.Count)
                throw new Exception("Invalid letter index");

            var letter = letters[index];
            string label = letter.Label;
            Find.LetterStack.RemoveLetter(letter);
            return D("ok", true, "dismissed", label);
        }

        /// <summary>
        /// Selects a dialog option by index in the topmost Dialog_NodeTree. Navigates to linked
        /// nodes or executes the option's action and optionally closes the dialog.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - index (int, required): zero-based option index
        /// </param>
        /// <returns>Dictionary with: ok (bool), selected (string), result (string),
        /// new_text (string, if navigated), new_options (list, if navigated),
        /// dialog_closed (bool, if action executed)</returns>
        public static object ChooseOption(Dictionary<string, object> req)
        {
            int index = I(req, "index", -1);
            if (index < 0) throw new Exception("Missing 'index'");

            var dialog = FindTopDialog();
            if (dialog == null) throw new Exception("No active dialog. Use read_dialogs to check.");

            var node = GetCurNode(dialog);
            if (node == null || node.options == null)
                throw new Exception("Dialog has no options");

            if (index >= node.options.Count)
                throw new Exception("Option index " + index + " out of range (0-" + (node.options.Count - 1) + ")");

            var option = node.options[index];
            if (option.disabled)
                throw new Exception("Option " + index + " is disabled: " + (option.disabledReason ?? "unknown reason"));

            string optionText = "unknown";
            var textField = typeof(DiaOption).GetField("text",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (textField != null)
            {
                var t = textField.GetValue(option) as string;
                if (t != null) optionText = t;
            }

            if (option.link != null)
            {
                dialog.GotoNode(option.link);
                var result = D("ok", true, "selected", optionText, "result", "navigated");
                var newNode = GetCurNode(dialog);
                if (newNode != null)
                {
                    result["new_text"] = (string)newNode.text;
                    result["new_options"] = GetDialogOptions(dialog);
                }
                return result;
            }
            else
            {
                if (option.action != null) option.action();
                if (option.resolveTree) dialog.Close(true);
                return D("ok", true, "selected", optionText, "result", "action executed", "dialog_closed", (object)option.resolveTree);
            }
        }

        /// <summary>
        /// Closes the topmost dialog window. Supports naming dialogs (faction/settlement name)
        /// by applying names before closing. Falls back to Dialog_NodeTree, then any window.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - type (string, optional): specific window type name to close
        /// - factionName (string, optional): name to apply if closing Dialog_NamePlayerFactionAndSettlement
        /// - settlementName (string, optional): settlement name to apply if closing naming dialogs
        /// </param>
        /// <returns>Dictionary with: ok (bool), closed (string: window type name),
        /// factionName (string, if naming dialog), settlementName (string, if naming dialog)</returns>
        public static object CloseDialog(Dictionary<string, object> req)
        {
            var targetType = S(req, "type");

            // If a specific type is requested, find and close it
            if (targetType != null)
            {
                foreach (var w in Find.WindowStack.Windows.ToList())
                {
                    if (w.GetType().Name == targetType)
                    {
                        // For naming dialogs, apply names directly then close
                        if (w is Dialog_NamePlayerSettlement settDialog)
                        {
                            var sName = S(req, "settlementName") ?? "Settlement";
                            var sObj = Find.WorldObjects.Settlements
                                .FirstOrDefault(s => s.Faction == Faction.OfPlayer);
                            if (sObj != null)
                                sObj.Name = sName;
                            settDialog.Close(true);
                            return D("ok", true, "closed", targetType,
                                     "settlementName", sName);
                        }
                        if (w is Dialog_NamePlayerFactionAndSettlement nameDialog)
                        {
                            var factionName = S(req, "factionName") ?? "Colony";
                            var settlementName = S(req, "settlementName") ?? "Settlement";

                            // Apply faction name directly
                            Faction.OfPlayer.Name = factionName;

                            // Apply settlement name to the first player settlement
                            var settlement = Find.WorldObjects.Settlements
                                .FirstOrDefault(s => s.Faction == Faction.OfPlayer);
                            if (settlement != null)
                                settlement.Name = settlementName;

                            nameDialog.Close(true);
                            return D("ok", true, "closed", targetType,
                                     "factionName", factionName,
                                     "settlementName", settlementName);
                        }
                        w.Close(true);
                        return D("ok", true, "closed", targetType);
                    }
                }
                throw new Exception("No dialog of type: " + targetType);
            }

            // Default behavior: close top Dialog_NodeTree first
            var dialog = FindTopDialog();
            if (dialog != null)
            {
                dialog.Close(true);
                return D("ok", true, "closed", "Dialog_NodeTree");
            }

            // Fallback: close topmost non-ImmediateWindow dialog, or any window
            var allWindows = Find.WindowStack.Windows.ToList();
            // Prefer substantive dialogs over ImmediateWindows
            var substantive = allWindows.FindLast(w => w.GetType().Name != "ImmediateWindow");
            if (substantive != null)
            {
                var typeName = substantive.GetType().Name;
                substantive.Close(true);
                return D("ok", true, "closed", typeName);
            }
            if (allWindows.Count > 0)
            {
                var top = allWindows.Last();
                top.Close(true);
                return D("ok", true, "closed", top.GetType().Name);
            }

            throw new Exception("No dialogs to close");
        }

        /// <summary>
        /// Enables or disables manual work priority mode (the 1-4 priority numbers).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - enabled (bool, optional): true to enable manual priorities, default true
        /// </param>
        /// <returns>Dictionary with: ok (bool), manualPriorities (bool)</returns>
        public static object SetManualPriorities(Dictionary<string, object> req)
        {
            bool enable = B(req, "enabled", true);
            Current.Game.playSettings.useWorkPriorities = enable;
            return D("ok", true, "manualPriorities", (object)enable);
        }

        /// <summary>
        /// Suspends or unsuspends a bill on a workbench by index.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - workbench (string, required): workbench label or defName
        /// - billIndex (int, optional): zero-based bill index, default 0
        /// - suspended (bool, optional): true to suspend, false to unsuspend, default true
        /// </param>
        /// <returns>Dictionary with: ok (bool), workbench (string), billIndex (int), suspended (bool)</returns>
        public static object SuspendBill(Dictionary<string, object> req)
        {
            var workbenchName = S(req, "workbench");
            int billIndex = I(req, "billIndex", 0);
            bool suspend = B(req, "suspended", true);

            var map = GetMap() ?? throw new Exception("No active map");
            var workbench = map.listerBuildings.allBuildingsColonist
                .OfType<Building_WorkTable>()
                .FirstOrDefault(b =>
                    b.Label.Equals(workbenchName, StringComparison.OrdinalIgnoreCase) ||
                    b.def.defName.Equals(workbenchName, StringComparison.OrdinalIgnoreCase));
            if (workbench == null) throw new Exception($"Workbench not found: {workbenchName}");
            if (billIndex < 0 || billIndex >= workbench.BillStack.Count)
                throw new Exception($"Invalid bill index {billIndex}");

            workbench.BillStack.Bills[billIndex].suspended = suspend;
            return D("ok", true, "workbench", workbenchName, "billIndex", (object)billIndex, "suspended", (object)suspend);
        }

        /// <summary>
        /// Configures a stockpile's filter and priority. Supports bulk allow/disallow and
        /// individual ThingDef, ThingCategoryDef, or SpecialThingFilterDef toggles.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x (int, optional): stockpile cell X (alternative to zone name)
        /// - z (int, optional): stockpile cell Z
        /// - zone (string, optional): stockpile label or partial match
        /// - priority (string, optional): "Critical", "Preferred", "Normal", "Low", "Unstored"
        /// - allow_all (bool, optional): enable all filter categories first
        /// - disallow_all (bool, optional): disable all filter categories first
        /// - allow (list of strings, optional): defNames/categories to allow
        /// - disallow (list of strings, optional): defNames/categories to disallow
        /// </param>
        /// <returns>Dictionary with: ok (bool), zone (string), priority (string), allowed (int), disallowed (int)</returns>
        public static object SetStockpileFilter(Dictionary<string, object> req)
        {
            var map = GetMap() ?? throw new Exception("No active map");
            int x = I(req, "x", -1), z = I(req, "z", -1);
            string zoneName = S(req, "zone");

            Zone_Stockpile stockpile = null;
            if (x >= 0 && z >= 0)
            {
                var zone = map.zoneManager.ZoneAt(new IntVec3(x, 0, z));
                stockpile = zone as Zone_Stockpile;
            }
            else if (zoneName != null)
            {
                stockpile = map.zoneManager.AllZones.OfType<Zone_Stockpile>()
                    .FirstOrDefault(sz => sz.label.Equals(zoneName, StringComparison.OrdinalIgnoreCase)
                        || sz.label.ToLower().Contains(zoneName.ToLower()));
            }
            if (stockpile == null) throw new Exception("Stockpile not found");

            var filter = stockpile.settings.filter;

            // Set priority if provided
            var priority = S(req, "priority");
            if (priority != null && Enum.TryParse<StoragePriority>(priority, true, out var sp))
                stockpile.settings.Priority = sp;

            // Bulk operations FIRST so individual allow/disallow can override
            if (B(req, "allow_all", false)) filter.SetAllowAll(null);
            if (B(req, "disallow_all", false)) filter.SetDisallowAll();

            // Allow/disallow specific ThingDefs (runs AFTER bulk operations)
            var allow = req.ContainsKey("allow") ? req["allow"] as List<object> : null;
            var disallow = req.ContainsKey("disallow") ? req["disallow"] as List<object> : null;

            int allowed = 0, disallowed = 0;
            if (allow != null)
            {
                foreach (var item in allow)
                {
                    var name = item?.ToString();
                    if (name == null) continue;
                    var def = DefDatabase<ThingDef>.GetNamedSilentFail(name);
                    if (def != null) { filter.SetAllow(def, true); allowed++; continue; }
                    // Try as category
                    var cat = DefDatabase<ThingCategoryDef>.GetNamedSilentFail(name);
                    if (cat != null) { filter.SetAllow(cat, true); allowed++; continue; }
                    // Try special filters
                    var sf = DefDatabase<SpecialThingFilterDef>.GetNamedSilentFail(name);
                    if (sf != null) { filter.SetAllow(sf, true); allowed++; }
                }
            }
            if (disallow != null)
            {
                foreach (var item in disallow)
                {
                    var name = item?.ToString();
                    if (name == null) continue;
                    var def = DefDatabase<ThingDef>.GetNamedSilentFail(name);
                    if (def != null) { filter.SetAllow(def, false); disallowed++; continue; }
                    var cat = DefDatabase<ThingCategoryDef>.GetNamedSilentFail(name);
                    if (cat != null) { filter.SetAllow(cat, false); disallowed++; continue; }
                    var sf = DefDatabase<SpecialThingFilterDef>.GetNamedSilentFail(name);
                    if (sf != null) { filter.SetAllow(sf, false); disallowed++; }
                }
            }

            return D("ok", true, "zone", stockpile.label,
                     "priority", stockpile.settings.Priority.ToString(),
                     "allowed", (object)allowed, "disallowed", (object)disallowed);
        }

        /// <summary>
        /// Adds plan designations (visual markers) in a rectangular area.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle start X
        /// - z1 (int, required): rectangle start Z
        /// - x2 (int, optional): rectangle end X (defaults to x1)
        /// - z2 (int, optional): rectangle end Z (defaults to z1)
        /// </param>
        /// <returns>Dictionary with: ok (bool), planned (int)</returns>
        public static object AddPlan(Dictionary<string, object> req)
        {
            var map = GetMap() ?? throw new Exception("No active map");
            int x1 = I(req, "x1"), z1 = I(req, "z1");
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);
            int count = 0;
            for (int x = Math.Min(x1, x2); x <= Math.Max(x1, x2); x++)
            for (int z = Math.Min(z1, z2); z <= Math.Max(z1, z2); z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                if (map.designationManager.DesignationAt(cell, DesignationDefOf.Plan) != null) continue;
                map.designationManager.AddDesignation(new Designation(cell, DesignationDefOf.Plan));
                count++;
            }
            return D("ok", true, "planned", (object)count);
        }

        /// <summary>
        /// Removes plan designations in a rectangular area.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, required): rectangle start X
        /// - z1 (int, required): rectangle start Z
        /// - x2 (int, optional): rectangle end X (defaults to x1)
        /// - z2 (int, optional): rectangle end Z (defaults to z1)
        /// </param>
        /// <returns>Dictionary with: ok (bool), removed (int)</returns>
        public static object RemovePlan(Dictionary<string, object> req)
        {
            var map = GetMap() ?? throw new Exception("No active map");
            int x1 = I(req, "x1"), z1 = I(req, "z1");
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);
            int count = 0;
            for (int x = Math.Min(x1, x2); x <= Math.Max(x1, x2); x++)
            for (int z = Math.Min(z1, z2); z <= Math.Max(z1, z2); z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var desig = map.designationManager.DesignationAt(cell, DesignationDefOf.Plan);
                if (desig != null) { desig.Delete(); count++; }
            }
            return D("ok", true, "removed", (object)count);
        }

        /// <summary>
        /// Executes multiple build operations in a single call. Each op is passed to Build().
        /// Errors are captured per-op rather than aborting the batch.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - ops (list, required): list of build operation dicts, each with blueprint/x/y/rotation/stuff
        /// </param>
        /// <returns>Dictionary with: results (list of per-op result dicts with ok/error)</returns>
        public static object BulkBuild(Dictionary<string, object> req)
        {
            var ops = req.ContainsKey("ops") ? req["ops"] as List<object> : null;
            if (ops == null || ops.Count == 0) throw new Exception("Missing 'ops' list");

            var map = GetMap() ?? throw new Exception("No active map");
            var results = new List<object>();

            foreach (var opObj in ops)
            {
                var op = opObj as Dictionary<string, object>;
                if (op == null) { results.Add(D("error", "invalid op")); continue; }

                try
                {
                    var result = Build(op);
                    var rd = result as Dictionary<string, object>;
                    if (rd != null)
                    {
                        rd["ok"] = true;
                        results.Add(rd);
                    }
                    else
                        results.Add(D("ok", true));
                }
                catch (Exception ex)
                {
                    var errResult = D("error", ex.Message,
                                      "x", (object)I(op, "x", 0),
                                      "y", (object)I(op, "y", 0));
                    // Parse blocked cell info from enriched error
                    if (ex.Message.StartsWith("Cell blocked|"))
                    {
                        try
                        {
                            var jsonPart = ex.Message.Substring("Cell blocked|".Length);
                            var parsed = SimpleJson.Deserialize(jsonPart);
                            if (parsed.ContainsKey("cells"))
                                errResult["cells"] = parsed["cells"];
                            errResult["error"] = "Cell blocked";
                        }
                        catch { }
                    }
                    results.Add(errResult);
                }
            }
            return D("results", results);
        }

        /// <summary>
        /// Starts or stops the event logger. Events (job transitions, item pickups, eating)
        /// are written to the specified JSONL file path.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - path (string, optional): file path to write events. Omit or empty to stop logging.
        /// </param>
        /// <returns>Dictionary with: ok (bool), active (bool), path (string)</returns>
        public static object SetEventLog(Dictionary<string, object> req)
        {
            var path = S(req, "path");
            if (string.IsNullOrEmpty(path))
            {
                EventLogger.Stop();
                return D("ok", true, "active", false);
            }
            EventLogger.Start(path);
            return D("ok", true, "active", true, "path", path);
        }

        // ── Dev/Testing Tools ─────────────────────────────────────────

        /// <summary>
        /// Flag that blocks all storyteller incidents when true.
        /// Checked by the IncidentBlocker Harmony patch.
        /// </summary>
        public static bool IncidentsDisabled = true;  // default ON — runner calls enable_incidents() when ready
        public static bool AllowNextAnimalSpawn;       // temporary bypass for spawn_animals command
        public static HashSet<string> AllowedWildlife = new HashSet<string>();  // species allowed to exist on map

        /// <summary>
        /// Toggles random incidents on/off. When disabled, the storyteller
        /// will not fire any events (raids, wanderers, weather, etc.).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - enable (bool, optional): true to disable incidents, toggles if omitted
        /// </param>
        /// <returns>Dictionary with: ok (bool), incidents_disabled (bool)</returns>
        public static object DevToggleIncidents(Dictionary<string, object> req)
        {
            var enable = req.ContainsKey("enable")
                ? System.Convert.ToBoolean(req["enable"])
                : !IncidentsDisabled;
            IncidentsDisabled = enable;
            return D("ok", true, "incidents_disabled", (object)IncidentsDisabled);
        }

        /// <summary>
        /// Changes the active storyteller and/or difficulty level at runtime.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - name (string, optional): storyteller name — "Cassandra", "Phoebe", or "Randy"
        /// - difficulty (string, optional): difficulty — "Peaceful", "Community", "Adventure", "Strive", "Blood"
        /// </param>
        /// <returns>Dictionary with: ok (bool), storyteller (string), difficulty (string)</returns>
        public static object DevSetStoryteller(Dictionary<string, object> req)
        {
            var name = S(req, "name");
            var diff = S(req, "difficulty");

            if (name != null)
            {
                var storytellerDef = DefDatabase<StorytellerDef>.AllDefs
                    .FirstOrDefault(d => d.defName.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0);
                if (storytellerDef == null)
                    throw new Exception("Unknown storyteller: " + name + ". Try Cassandra, Phoebe, or Randy.");
                Current.Game.storyteller.def = storytellerDef;
                Current.Game.storyteller.Notify_DefChanged();
            }

            if (diff != null)
            {
                var diffDef = DefDatabase<DifficultyDef>.AllDefs
                    .FirstOrDefault(d => d.defName.IndexOf(diff, StringComparison.OrdinalIgnoreCase) >= 0);
                if (diffDef == null)
                    throw new Exception("Unknown difficulty: " + diff);
                Current.Game.storyteller.difficultyDef = diffDef;
                Current.Game.storyteller.difficulty = new Difficulty(diffDef);
                Current.Game.storyteller.Notify_DefChanged();
            }

            return D("ok", true,
                "storyteller", Current.Game.storyteller.def.defName,
                "difficulty", Current.Game.storyteller.difficultyDef.defName);
        }

        /// <summary>
        /// Spawns wild animals on the map at runtime (dev/testing tool).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - species (string, required): PawnKindDef defName (e.g. "Boar", "Deer", "Warg")
        /// - count (int, optional): number to spawn, default 1
        /// - x (int, optional): spawn X coordinate (random edge if omitted)
        /// - z (int, optional): spawn Z coordinate (random edge if omitted)
        /// - manhunter (bool, optional): if true, animals spawn in manhunter state, default false
        /// </param>
        /// <returns>Dictionary with: ok (bool), spawned (int), species (string),
        /// details (list of {species, x, z, manhunter})</returns>
        public static object SpawnAnimals(Dictionary<string, object> req)
        {
            var map = Find.CurrentMap;
            if (map == null) throw new Exception("No active map");

            var speciesName = S(req, "species");
            if (speciesName == null) throw new Exception("species required");

            var pawnKind = DefDatabase<PawnKindDef>.AllDefs
                .FirstOrDefault(d => d.defName.Equals(speciesName, StringComparison.OrdinalIgnoreCase)
                    || d.race?.defName?.Equals(speciesName, StringComparison.OrdinalIgnoreCase) == true);
            if (pawnKind == null)
                throw new Exception($"Unknown species: {speciesName}. Use the defName (e.g. Boar, Deer, Megasloth).");

            int count = req.ContainsKey("count") ? System.Convert.ToInt32(req["count"]) : 1;
            bool manhunter = req.ContainsKey("manhunter") && System.Convert.ToBoolean(req["manhunter"]);

            int? targetX = req.ContainsKey("x") ? System.Convert.ToInt32(req["x"]) : (int?)null;
            int? targetZ = req.ContainsKey("z") ? System.Convert.ToInt32(req["z"]) : (int?)null;

            var spawned = new List<object>();
            for (int i = 0; i < count; i++)
            {
                IntVec3 pos;
                if (targetX.HasValue && targetZ.HasValue)
                {
                    // Near the target position
                    pos = new IntVec3(targetX.Value, 0, targetZ.Value);
                    if (!pos.InBounds(map) || !pos.Standable(map))
                    {
                        // Find nearby standable cell
                        if (!CellFinder.TryFindRandomCellNear(pos, map, 10, c => c.Standable(map), out pos))
                            continue;
                    }
                }
                else
                {
                    // Random edge cell
                    if (!CellFinder.TryFindRandomEdgeCellWith(c => c.Standable(map), map, CellFinder.EdgeRoadChance_Animal, out pos))
                        continue;
                }

                var pawn = PawnGenerator.GeneratePawn(pawnKind, null);
                AllowNextAnimalSpawn = true;
                GenSpawn.Spawn(pawn, pos, map);
                AllowNextAnimalSpawn = false;
                AllowedWildlife.Add(pawnKind.defName);

                if (manhunter)
                {
                    pawn.mindState.mentalStateHandler.TryStartMentalState(MentalStateDefOf.Manhunter, forced: true);
                }

                spawned.Add(D("species", pawnKind.defName, "x", pos.x, "z", pos.z,
                    "manhunter", (object)manhunter));
            }

            return D("ok", true, "spawned", (object)spawned.Count,
                "species", speciesName, "details", spawned);
        }
    }
}
