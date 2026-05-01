using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using RimWorld;
using Verse;
using static CarolineConsole.Helpers;

namespace CarolineConsole
{
    public static class ReadCommands
    {
        /// <summary>
        /// Returns detailed info for all free colonists including backstories, traits, skills, and current state.
        /// </summary>
        /// <returns>Dictionary with: colonists (list of {name, position, health, mood, currentJob, mentalState, isDrafted, childhood, childhoodDesc, adulthood, adulthoodDesc, traits, disabledWork, skills})</returns>
        public static object Colonists(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("colonists", new List<object>());

            var colonists = map.mapPawns.FreeColonists.Select(p => {
                // Backstories
                string childhood = null, childhoodDesc = null;
                string adulthood = null, adulthoodDesc = null;
                if (p.story != null)
                {
                    var child = p.story.Childhood;
                    if (child != null) { childhood = child.title; childhoodDesc = child.baseDesc; }
                    var adult = p.story.Adulthood;
                    if (adult != null) { adulthood = adult.title; adulthoodDesc = adult.baseDesc; }
                }

                // Traits
                var traits = p.story?.traits?.allTraits?.Select(t => (object)D(
                    "name", t.LabelCap,
                    "description", t.TipString(p)
                )).ToList() ?? new List<object>();

                // Work incapabilities
                var disabled = p.story?.DisabledWorkTagsBackstoryAndTraits.ToString() ?? "";

                return (object)D(
                    "name",        p.Name?.ToStringFull ?? "Unknown",
                    "position",    D("x", (object)p.Position.x, "z", (object)p.Position.z),
                    "health",      (object)(p.health?.summaryHealth?.SummaryHealthPercent ?? 1f),
                    "mood",        (object)(p.needs?.mood?.CurLevelPercentage ?? 0.5f),
                    "currentJob",  p.CurJobDef?.defName ?? "idle",
                    "jobTarget",   p.CurJob?.targetA.Thing?.def?.defName ?? "",
                    "mentalState", p.MentalStateDef?.defName ?? "none",
                    "isDrafted",   (object)p.Drafted,
                    "childhood",   childhood ?? "",
                    "childhoodDesc", childhoodDesc ?? "",
                    "adulthood",   adulthood ?? "",
                    "adulthoodDesc", adulthoodDesc ?? "",
                    "traits",      (object)traits,
                    "disabledWork", disabled,
                    "skills",      (object)p.skills?.skills?.Select(s => (object)D(
                        "name",    s.def.defName,
                        "level",   (object)s.Level,
                        "passion", s.passion.ToString()
                    )).ToList()
                );
            }).ToList();

            return D("colonists", colonists);
        }

        /// <summary>
        /// Returns a count of every resource the colony has in stockpiles, keyed by defName.
        /// </summary>
        /// <returns>Dictionary with: {defName: count, ...} for all resources with count > 0</returns>
        public static object Resources(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return new Dictionary<string, object>();

            var result = new Dictionary<string, object>();
            var counter = map.resourceCounter;
            foreach (var def in DefDatabase<ThingDef>.AllDefsListForReading)
            {
                int count = counter.GetCount(def);
                if (count > 0)
                    result[def.defName] = count;
            }

            // Also count items NOT in stockpile zones (on the ground)
            var ground = new Dictionary<string, int>();
            foreach (var thing in map.listerThings.AllThings)
            {
                if (thing.def.category != ThingCategory.Item) continue;
                if (thing.IsInAnyStorage()) continue;  // already counted by resourceCounter
                var defName = thing.def.defName;
                if (!ground.ContainsKey(defName))
                    ground[defName] = 0;
                ground[defName] += thing.stackCount;
            }
            if (ground.Count > 0)
                result["_ground"] = ground;

            return result;
        }

        /// <summary>
        /// Returns high-level map metadata including size, biome, season, and home area stats.
        /// </summary>
        /// <returns>Dictionary with: size ({x, z}), biome (string), avgFertility (float), homeCells (int), season (string), hour (float)</returns>
        public static object Map(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return new Dictionary<string, object>();

            var cells = map.areaManager.Home?.ActiveCells?.ToList() ?? new List<IntVec3>();
            float avgFertility = cells.Count > 0 ? cells.Average(c => map.fertilityGrid.FertilityAt(c)) : 0f;

            return D(
                "size",         (object)D("x", (object)map.Size.x, "z", (object)map.Size.z),
                "biome",        map.Biome.defName,
                "avgFertility", (object)avgFertility,
                "homeCells",    (object)cells.Count,
                "season",       GenLocalDate.Season(map).ToString(),
                "hour",         (object)GenLocalDate.HourFloat(map)
            );
        }

        /// <summary>
        /// Returns a compact tile-level map snapshot with base64-encoded terrain, fertility, roof, and fog layers,
        /// plus a sparse list of things. Region is clamped to 50x50 max per request.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - kind (string, optional): comma-separated thing kind filter (e.g. "building,item")
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2 (int), width, height (int), terrainPalette (list of string),
        /// terrain, fertility, roof, fog (base64 strings), things (list of {x, z, kind, def, label, ...}),
        /// cellDesignations (list of {x, z, def})</returns>
        public static object MapTiles(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("error", "no active map");

            // Optional bounds — defaults to full map, clamped to 50×50 max
            const int MAX_REGION = 50;
            int minX = I(req, "x1", 0);
            int minZ = I(req, "z1", 0);
            int maxX = Math.Min(I(req, "x2", map.Size.x - 1), map.Size.x - 1);
            int maxZ = Math.Min(I(req, "z2", map.Size.z - 1), map.Size.z - 1);
            // Clamp to MAX_REGION tiles per axis — caller can page with multiple requests
            if (maxX - minX + 1 > MAX_REGION) maxX = minX + MAX_REGION - 1;
            if (maxZ - minZ + 1 > MAX_REGION) maxZ = minZ + MAX_REGION - 1;
            int regionW = maxX - minX + 1;
            int regionH = maxZ - minZ + 1;
            int total = regionW * regionH;

            // Build terrain palette (defName → byte index)
            var terrainPalette = new List<string>();
            var terrainIndex   = new Dictionary<string, byte>();

            // Layer arrays
            var terrain   = new byte[total];
            var fertility  = new byte[total];
            var roof       = new byte[total]; // 0=none 1=thin 2=thick/overhead
            var fog        = new byte[total]; // 0=visible 1=fogged

            for (int x = minX; x <= maxX; x++)
            {
                for (int z = minZ; z <= maxZ; z++)
                {
                    int idx  = (x - minX) * regionH + (z - minZ);
                    var cell = new IntVec3(x, 0, z);

                    // Terrain
                    var td = map.terrainGrid.TerrainAt(cell);
                    var tn = td?.defName ?? "Unknown";
                    if (!terrainIndex.ContainsKey(tn))
                    {
                        terrainIndex[tn] = (byte)terrainPalette.Count;
                        terrainPalette.Add(tn);
                    }
                    terrain[idx] = terrainIndex[tn];

                    // Fertility (0-255 = 0-100%)
                    fertility[idx] = (byte)Math.Min(255, (int)(map.fertilityGrid.FertilityAt(cell) * 255f));

                    // Roof
                    var r = map.roofGrid.RoofAt(cell);
                    roof[idx] = r == null ? (byte)0
                              : r.isThickRoof    ? (byte)2
                              : (byte)1;

                    // Fog
                    fog[idx] = map.fogGrid.IsFogged(cell) ? (byte)1 : (byte)0;
                }
            }

            // Sparse things list — only within bounds
            // Optional: kind filter (comma-separated) to only return matching kinds
            string filterKind = S(req, "kind");
            HashSet<string> filterKinds = null;
            if (filterKind != null)
                filterKinds = new HashSet<string>(filterKind.Split(','), StringComparer.OrdinalIgnoreCase);
            var things = new List<object>();
            try
            {
                for (int x = minX; x <= maxX; x++)
                for (int z = minZ; z <= maxZ; z++)
                {
                    var cell = new IntVec3(x, 0, z);
                    var list = map.thingGrid.ThingsListAt(cell);
                    if (list == null || list.Count == 0) continue;

                    foreach (var t in list)
                    {
                        try
                        {
                            if (t == null || t.def == null) continue;

                            string kind;
                            if (t is Pawn p)
                            {
                                kind = p.IsColonist ? "colonist"
                                     : (Faction.OfPlayer != null && p.HostileTo(Faction.OfPlayer)) ? "enemy"
                                     : (p.RaceProps?.Animal == true) ? "animal"
                                     : "pawn";
                            }
                            else if (t is Plant) kind = "plant";
                            else if (t is Blueprint) kind = "blueprint";
                            else if (t is Frame) kind = "frame";
                            else if (t is Building) kind = "building";
                            else if (t.def.category == ThingCategory.Item) kind = "item";
                            else if (t.def.thingCategories != null && t.def.thingCategories.Any(c => c?.defName?.Contains("Chunk") == true)) kind = "chunk";
                            else continue; // skip projectiles, motes etc

                            if (filterKinds != null && !filterKinds.Contains(kind)) continue;

                            var entry = D(
                                "x",    (object)cell.x,
                                "z",    (object)cell.z,
                                "kind", kind,
                                "def",  t.def.defName ?? "unknown",
                                "label", t.Label ?? "unknown"
                            );

                            // Extra data per kind
                            if (t is Pawn pawn)
                            {
                                entry["name"]   = pawn.Name?.ToStringShort ?? pawn.Label ?? "unknown";
                                entry["health"] = (object)(pawn.health?.summaryHealth?.SummaryHealthPercent ?? 1f);
                                entry["job"]    = pawn.CurJobDef?.defName ?? "idle";
                            }
                            else if (t is Plant plant)
                            {
                                entry["growth"]      = (object)plant.Growth;
                                entry["harvestable"] = (object)plant.HarvestableNow;
                            }
                            else if (t is Blueprint bp)
                            {
                                entry["building"] = bp.def?.entityDefToBuild?.defName ?? "unknown";
                                entry["buildingLabel"] = bp.def?.entityDefToBuild?.label ?? "unknown";
                            }
                            else if (t is Frame frame)
                            {
                                entry["building"] = frame.def?.entityDefToBuild?.defName ?? "unknown";
                                entry["buildingLabel"] = frame.def?.entityDefToBuild?.label ?? "unknown";
                                entry["workDone"] = (object)frame.WorkToBuild;
                                entry["workTotal"] = (object)frame.def?.entityDefToBuild?.GetStatValueAbstract(StatDefOf.WorkToBuild, null);
                            }
                            else if (t.def.category == ThingCategory.Item || kind == "chunk")
                            {
                                entry["count"] = (object)t.stackCount;
                                entry["hp"]    = (object)t.HitPoints;
                                entry["maxHp"] = (object)t.MaxHitPoints;

                                // Forbidden status
                                if (t.Faction == Faction.OfPlayer || t.Faction == null)
                                    entry["forbidden"] = (object)(t is ThingWithComps twc
                                        && twc.GetComp<CompForbiddable>()?.Forbidden == true);

                                // Rot timer (food, corpses)
                                var rot = t.TryGetComp<CompRottable>();
                                if (rot != null)
                                    entry["rotTicksLeft"] = (object)rot.TicksUntilRotAtCurrentTemp;

                                // Deteriorating (outdoors, no roof)
                                entry["deteriorating"] = (object)(!t.Position.Roofed(t.Map)
                                    && t.def.CanEverDeteriorate);
                            }

                            things.Add(entry);
                        }
                        catch (Exception) { /* skip problematic thing */ }
                    }
                }
            }
            catch (Exception ex)
            {
                return D("error", "things iteration failed: " + ex.Message);
            }

            // Also add cell-level designations within bounds
            var cellDesigs = new List<object>();
            var desigField = map.designationManager.GetType().GetField("allDesignations",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var allDesigs = desigField?.GetValue(map.designationManager) as IEnumerable<Designation>;
            if (allDesigs != null)
            {
                foreach (var d in allDesigs)
                {
                    if (d.target.HasThing) continue;
                    var c = d.target.Cell;
                    if (c.x < minX || c.x > maxX || c.z < minZ || c.z > maxZ) continue;
                    cellDesigs.Add(D(
                        "x",   (object)c.x,
                        "z",   (object)c.z,
                        "def", d.def.defName
                    ));
                }
            }

            return D(
                "x1",             (object)minX,
                "z1",             (object)minZ,
                "x2",             (object)maxX,
                "z2",             (object)maxZ,
                "width",          (object)regionW,
                "height",         (object)regionH,
                "terrainPalette", terrainPalette,
                "terrain",        Convert.ToBase64String(terrain),
                "fertility",      Convert.ToBase64String(fertility),
                "roof",           Convert.ToBase64String(roof),
                "fog",            Convert.ToBase64String(fog),
                "things",         things,
                "cellDesignations", cellDesigs
            );
        }

        /// <summary>
        /// Returns all currently active game alerts (e.g. "colonist needs rescue", "starvation").
        /// </summary>
        /// <returns>Dictionary with: alerts (list of {type, label, priority}), totalChecked (int)</returns>
        public static object Alerts(Dictionary<string, object> req)
        {
            var alertsManager = Find.Alerts;
            if (alertsManager == null) return D("alerts", new List<object>(), "error", "Find.Alerts is null");

            // Try multiple field names and binding flags
            var flags = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
            var type = alertsManager.GetType();
            
            List<Alert> allAlerts = null;
            
            // Try different possible field names
            foreach (var fieldName in new[] { "AllAlerts", "allAlerts", "activeAlerts", "alerts" })
            {
                var field = type.GetField(fieldName, flags);
                if (field != null)
                {
                    allAlerts = field.GetValue(alertsManager) as List<Alert>;
                    if (allAlerts != null) break;
                }
            }
            
            // If no field found, try properties
            if (allAlerts == null)
            {
                foreach (var propName in new[] { "AllAlerts", "ActiveAlerts" })
                {
                    var prop = type.GetProperty(propName, flags);
                    if (prop != null)
                    {
                        allAlerts = prop.GetValue(alertsManager) as List<Alert>;
                        if (allAlerts != null) break;
                    }
                }
            }

            if (allAlerts == null) 
                return D("alerts", new List<object>(), "debug", "Could not find alerts field/property");

            var alerts = allAlerts
                .Where(a => a != null && a.Active)
                .Select(a => {
                    try {
                        return (object)D(
                            "type",     a.GetType().Name,
                            "label",    a.GetLabel() ?? "unknown",
                            "priority", a.Priority.ToString()
                        );
                    } catch { return null; }
                })
                .Where(a => a != null)
                .ToList();

            return D("alerts", alerts, "totalChecked", (object)allAlerts.Count);
        }

        /// <summary>
        /// Returns all player-owned buildings (including spots) and a list of enclosed rooms with stats.
        /// </summary>
        /// <returns>Dictionary with: buildings (list of {def, label, position, hitPoints, maxHitPoints, isSpot}),
        /// rooms (list of {role, cellCount, roofed, openRoofCount, temperature, impressiveness, beauty, cleanliness, contents, flooredPct, bounds})</returns>
        public static object Buildings(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("buildings", new List<object>(), "rooms", new List<object>());

            // Include proper buildings AND spots/workbenches (Things that aren't Building subclass)
            var buildingThings = map.listerBuildings.allBuildingsColonist
                .Select(b => (object)D(
                    "def",         b.def.defName,
                    "label",       b.Label,
                    "position",    D("x", (object)b.Position.x, "z", (object)b.Position.z),
                    "hitPoints",   (object)b.HitPoints,
                    "maxHitPoints",(object)b.MaxHitPoints,
                    "isSpot",      (object)false
                )).ToList();

            // Also grab spots (ButcherSpot, etc.) — may not be in allBuildingsColonist
            var existingPositions = new HashSet<string>(
                map.listerBuildings.allBuildingsColonist.Select(b => $"{b.Position.x},{b.Position.z}"));
            var butcherSpotDef = DefDatabase<ThingDef>.GetNamedSilentFail("ButcherSpot");
            var spotThings = (butcherSpotDef != null ? map.listerThings.ThingsOfDef(butcherSpotDef) : Enumerable.Empty<Thing>())
                .Where(t => t.Faction == Faction.OfPlayer && !existingPositions.Contains($"{t.Position.x},{t.Position.z}"))
                .Select(t => (object)D(
                    "def",      t.def.defName,
                    "label",    t.Label,
                    "position", D("x", (object)t.Position.x, "z", (object)t.Position.z),
                    "hitPoints",(object)t.HitPoints,
                    "maxHitPoints",(object)t.MaxHitPoints,
                    "isSpot",   (object)true
                )).ToList();

            var buildings = buildingThings.Concat(spotThings).ToList();

            var roomsField = map.regionGrid.GetType().GetField("allRooms",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var allRooms = roomsField?.GetValue(map.regionGrid) as List<Room> ?? new List<Room>();
            var rooms = allRooms
                .Where(r => !r.TouchesMapEdge && r.Role != null)
                .Select(r => {
                    var cells = r.Cells.ToList();
                    int rMinX = cells.Count > 0 ? cells.Min(c => c.x) : 0;
                    int rMaxX = cells.Count > 0 ? cells.Max(c => c.x) : 0;
                    int rMinZ = cells.Count > 0 ? cells.Min(c => c.z) : 0;
                    int rMaxZ = cells.Count > 0 ? cells.Max(c => c.z) : 0;

                    // Furniture inside the room (exclude walls/doors)
                    var contents = cells
                        .SelectMany(c => map.thingGrid.ThingsListAtFast(c))
                        .Where(t => t is Building b && b.Faction == Faction.OfPlayer
                            && !t.def.IsSmoothed && !t.def.defName.Equals("Wall")
                            && !t.def.defName.Equals("Door") && !t.def.defName.Equals("Autodoor"))
                        .Select(t => t.def.defName)
                        .Distinct()
                        .ToList();

                    // Floor coverage: count cells with non-natural terrain
                    int flooredCells = cells.Count(c => map.terrainGrid.TerrainAt(c).layerable);

                    return (object)D(
                        "role",          r.Role.defName,
                        "cellCount",     (object)r.CellCount,
                        "roofed",        (object)(r.OpenRoofCount == 0),
                        "openRoofCount", (object)r.OpenRoofCount,
                        "temperature",   (object)r.Temperature,
                        "impressiveness",(object)r.GetStat(RoomStatDefOf.Impressiveness),
                        "beauty",        (object)r.GetStat(RoomStatDefOf.Beauty),
                        "cleanliness",   (object)r.GetStat(RoomStatDefOf.Cleanliness),
                        "contents",      contents,
                        "flooredPct",    (object)(cells.Count > 0 ? Math.Round((double)flooredCells / cells.Count * 100) : 0),
                        "bounds",        D("minX", (object)rMinX, "maxX", (object)rMaxX, "minZ", (object)rMinZ, "maxZ", (object)rMaxZ)
                    );
                }).ToList();

            return D("buildings", buildings, "rooms", rooms);
        }

        /// <summary>
        /// Returns current weather conditions, temperature, season, and time of day.
        /// </summary>
        /// <returns>Dictionary with: temperature (float), condition (string), season (string), dayOfYear (int), dayOfSeason (int), hour (float)</returns>
        public static object Weather(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return new Dictionary<string, object>();

            return D(
                "temperature", (object)map.mapTemperature.OutdoorTemp,
                "condition",   map.weatherManager.curWeather.defName,
                "season",      GenLocalDate.Season(map).ToString(),
                "dayOfYear",   (object)GenLocalDate.DayOfYear(map),
                "dayOfSeason", (object)GenLocalDate.DayOfSeason(map),
                "hour",        (object)GenLocalDate.HourFloat(map)
            );
        }

        /// <summary>
        /// Returns the current research project, completed projects, and available projects with progress.
        /// </summary>
        /// <returns>Dictionary with: current (string or null), currentProgress (float), completed (list of string), available (list of {def, label, cost, progress})</returns>
        public static object Research(Dictionary<string, object> req)
        {
            var current = Find.ResearchManager.GetProject();
            var completed = DefDatabase<ResearchProjectDef>.AllDefs
                .Where(r => r.IsFinished).Select(r => (object)r.defName).ToList();
            var available = DefDatabase<ResearchProjectDef>.AllDefs
                .Where(r => !r.IsFinished && r.CanStartNow)
                .Select(r => (object)D(
                    "def",      r.defName,
                    "label",    r.label,
                    "cost",     (object)r.baseCost,
                    "progress", (object)r.ProgressPercent
                )).ToList();

            return D(
                "current",         current?.defName ?? (object)null,
                "currentProgress", (object)(current?.ProgressPercent ?? 0f),
                "completed",       completed,
                "available",       available
            );
        }

        /// <summary>
        /// Returns all zones on the map with type, label, cell count, bounds, and zone-specific data (plant for growing zones, priority for stockpiles).
        /// </summary>
        /// <returns>Dictionary with: zones (list of {type, label, cellCount, bounds, plant?, priority?})</returns>
        public static object Zones(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("zones", new List<object>());

            var zones = map.zoneManager.AllZones.Select(z =>
            {
                var zCells = z.Cells;
                int zMinX = zCells.Count > 0 ? zCells.Min(c => c.x) : 0;
                int zMaxX = zCells.Count > 0 ? zCells.Max(c => c.x) : 0;
                int zMinZ = zCells.Count > 0 ? zCells.Min(c => c.z) : 0;
                int zMaxZ = zCells.Count > 0 ? zCells.Max(c => c.z) : 0;
                var d = D(
                    "type",      z.GetType().Name,
                    "label",     z.label,
                    "cellCount", (object)zCells.Count,
                    "bounds",    D("minX", (object)zMinX, "maxX", (object)zMaxX, "minZ", (object)zMinZ, "maxZ", (object)zMaxZ)
                );
                if (z is Zone_Growing gz) d["plant"] = gz.GetPlantDefToGrow()?.defName ?? "none";
                else if (z is Zone_Stockpile sz) d["priority"] = sz.settings.Priority.ToString();
                return (object)d;
            }).ToList();

            return D("zones", zones);
        }

        /// <summary>
        /// Returns all player-owned workbenches and their active bills.
        /// </summary>
        /// <returns>Dictionary with: workbenches (list of {def, label, position, bills: [{index, recipe, label, suspended}]})</returns>
        public static object Bills(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("workbenches", new List<object>());

            var workbenches = map.listerBuildings.allBuildingsColonist
                .OfType<Building_WorkTable>()
                .Select(wb => (object)D(
                    "def",      wb.def.defName,
                    "label",    wb.Label,
                    "position", D("x", (object)wb.Position.x, "z", (object)wb.Position.z),
                    "bills",    (object)wb.BillStack.Bills.Select((b, i) => (object)D(
                        "index",     (object)i,
                        "recipe",    b.recipe.defName,
                        "label",     b.Label,
                        "suspended", (object)b.suspended
                    )).ToList()
                )).ToList();

            return D("workbenches", workbenches);
        }
        /// <summary>
        /// Returns all hostile pawns and active fires on the map.
        /// </summary>
        /// <returns>Dictionary with: threats (list of {type, name?, kind?, faction?, position, health?, downed?} for hostiles, {type, position} for fires)</returns>
        public static object Threats(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("threats", new List<object>());

            var list = new List<object>();
            foreach (var pawn in map.mapPawns.AllPawnsSpawned)
            {
                if (!pawn.HostileTo(Faction.OfPlayer)) continue;
                list.Add((object)D(
                    "type",     "hostile",
                    "name",     pawn.Name != null ? pawn.Name.ToStringShort : pawn.def.label,
                    "kind",     pawn.def.defName,
                    "faction",  pawn.Faction != null ? pawn.Faction.Name : "Wild",
                    "position", (object)PosDict(pawn.Position),
                    "health",   (object)RoundF(pawn.health.summaryHealth.SummaryHealthPercent),
                    "downed",   (object)pawn.Downed
                ));
            }
            foreach (var fire in map.listerThings.ThingsOfDef(ThingDefOf.Fire))
            {
                list.Add((object)D(
                    "type",     "fire",
                    "position", (object)PosDict(fire.Position)
                ));
            }
            return D("threats", list);
        }

        /// <summary>
        /// Returns work priority settings for all colonists, including disabled work types (-1).
        /// </summary>
        /// <returns>Dictionary with: colonists (list of {name, priorities: {workTypeDef: int, ...}})</returns>
        public static object WorkPriorities(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("colonists", new List<object>());

            var workTypes = DefDatabase<WorkTypeDef>.AllDefsListForReading;
            var list = new List<object>();
            foreach (var pawn in map.mapPawns.FreeColonists)
            {
                var priorities = new Dictionary<string, object>();
                foreach (var wt in workTypes)
                {
                    if (pawn.WorkTypeIsDisabled(wt))
                        priorities[wt.defName] = -1;
                    else if (pawn.workSettings != null)
                        priorities[wt.defName] = pawn.workSettings.GetPriority(wt);
                    else
                        priorities[wt.defName] = 0;
                }
                list.Add((object)D(
                    "name",       pawn.Name != null ? pawn.Name.ToStringShort : "Unknown",
                    "priorities", (object)priorities
                ));
            }
            return D("colonists", list);
        }

        /// <summary>
        /// Returns all animals on the map with species, position, health, tame/bonded status, and downed state.
        /// </summary>
        /// <returns>Dictionary with: animals (list of {name, kind, position, health, tame, bonded, downed})</returns>
        public static object Animals(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("animals", new List<object>());

            var list = new List<object>();
            foreach (var animal in map.mapPawns.AllPawnsSpawned)
            {
                if (!animal.RaceProps.Animal) continue;
                list.Add((object)D(
                    "name",     animal.Name != null ? animal.Name.ToStringShort : animal.LabelShort,
                    "kind",     animal.def.defName,
                    "position", (object)PosDict(animal.Position),
                    "health",   (object)RoundF(animal.health.summaryHealth.SummaryHealthPercent),
                    "tame",     (object)(animal.Faction == Faction.OfPlayer),
                    "bonded",   (object)(animal.relations != null && animal.relations.GetFirstDirectRelationPawn(PawnRelationDefOf.Bond) != null),
                    "downed",   (object)animal.Downed,
                    "huntDesignated", (object)(map.designationManager.DesignationOn(animal, DesignationDefOf.Hunt) != null)
                ));
            }
            int huntCount = list.Count(a => ((Dictionary<string, object>)a)["huntDesignated"].Equals(true));
            return D("animals", list, "hunt_designated_count", (object)huntCount);
        }

        /// <summary>
        /// Returns harvestable plants on the map (berry bushes, mature crops, etc.).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - filter (string, optional): comma-separated defNames to filter (e.g. "Plant_Berry,Plant_HealrootWild")
        ///   If omitted, returns all harvestable plants.
        /// </param>
        /// <returns>Dictionary with: plants (list of {def, position, growth, harvestable, yieldDef, yieldCount}), count (int)</returns>
        public static object Plants(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("plants", new List<object>(), "count", (object)0);

            string filterStr = S(req, "filter");
            HashSet<string> filters = null;
            if (filterStr != null)
                filters = new HashSet<string>(filterStr.Split(','), StringComparer.OrdinalIgnoreCase);

            var list = new List<object>();
            foreach (var thing in map.listerThings.AllThings)
            {
                var plant = thing as Plant;
                if (plant == null) continue;
                if (plant.def.plant == null) continue;
                if (filters != null && !filters.Contains(plant.def.defName)) continue;
                // Without filter, only return harvestable-type plants (have a yield def)
                if (filters == null && plant.def.plant.harvestedThingDef == null) continue;

                list.Add((object)D(
                    "def",         plant.def.defName,
                    "position",    (object)PosDict(plant.Position),
                    "growth",      (object)RoundF(plant.Growth),
                    "harvestable", (object)plant.HarvestableNow,
                    "yieldDef",    plant.def.plant.harvestedThingDef?.defName ?? "",
                    "yieldCount",  (object)(int)plant.def.plant.harvestYield
                ));
            }
            return D("plants", list, "count", (object)list.Count);
        }

        /// <summary>
        /// Returns a lightweight summary of all pawns on the map: colonists, prisoners, guests, and hostile/animal counts.
        /// </summary>
        /// <returns>Dictionary with: colonists (list of {name, position, health, drafted}), prisoners (list of {name, position, health}),
        /// guests (list of {name, faction, position}), hostile_count (int), animal_count (int)</returns>
        public static object Pawns(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("colonists", new List<object>());

            var colonists = new List<object>();
            foreach (var pa in map.mapPawns.FreeColonists)
            {
                colonists.Add((object)D(
                    "name",     pa.Name != null ? pa.Name.ToStringShort : "Unknown",
                    "position", (object)PosDict(pa.Position),
                    "health",   (object)RoundF(pa.health.summaryHealth.SummaryHealthPercent),
                    "drafted",  (object)pa.Drafted
                ));
            }

            var prisoners = new List<object>();
            foreach (var pa in map.mapPawns.PrisonersOfColony)
            {
                prisoners.Add((object)D(
                    "name",     pa.Name != null ? pa.Name.ToStringShort : "Unknown",
                    "position", (object)PosDict(pa.Position),
                    "health",   (object)RoundF(pa.health.summaryHealth.SummaryHealthPercent)
                ));
            }

            var guests = new List<object>();
            foreach (var pa in map.mapPawns.AllPawnsSpawned)
            {
                if (pa.RaceProps.Animal) continue;
                if (pa.Faction == Faction.OfPlayer) continue;
                if (pa.HostileTo(Faction.OfPlayer)) continue;
                guests.Add((object)D(
                    "name",     pa.Name != null ? pa.Name.ToStringShort : pa.LabelShort,
                    "faction",  pa.Faction != null ? pa.Faction.Name : "None",
                    "position", (object)PosDict(pa.Position)
                ));
            }

            return D(
                "colonists",     (object)colonists,
                "prisoners",     (object)prisoners,
                "guests",        (object)guests,
                "hostile_count", (object)map.mapPawns.AllPawnsSpawned.Count(pa => pa.HostileTo(Faction.OfPlayer)),
                "animal_count",  (object)map.mapPawns.AllPawnsSpawned.Count(pa => pa.RaceProps.Animal)
            );
        }

        /// <summary>
        /// Returns all needs for a specific pawn with current level percentages.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name to look up
        /// </param>
        /// <returns>Dictionary with: needs (list of {name, label, level})</returns>
        public static object Needs(Dictionary<string, object> req)
        {
            string name = S(req, "pawn");
            if (name == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(name);
            if (pawn == null) throw new Exception("Pawn '" + name + "' not found");

            var list = new List<object>();
            if (pawn.needs != null && pawn.needs.AllNeeds != null)
            {
                foreach (var need in pawn.needs.AllNeeds)
                {
                    list.Add((object)D(
                        "name",  need.def.defName,
                        "label", need.def.label,
                        "level", (object)RoundF(need.CurLevelPercentage)
                    ));
                }
            }
            return D("needs", list);
        }

        /// <summary>
        /// Returns a pawn's equipment, worn apparel, and carried inventory items.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name to look up
        /// </param>
        /// <returns>Dictionary with: equipment (list of {def, label, hp, maxHp}), apparel (list of {def, label, hp, maxHp}), inventory (list of {def, label, count})</returns>
        public static object Inventory(Dictionary<string, object> req)
        {
            string name = S(req, "pawn");
            if (name == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(name);
            if (pawn == null) throw new Exception("Pawn '" + name + "' not found");

            var equip = new List<object>();
            if (pawn.equipment != null)
            {
                foreach (var eq in pawn.equipment.AllEquipmentListForReading)
                {
                    equip.Add((object)D(
                        "def",   eq.def.defName,
                        "label", eq.Label,
                        "hp",    (object)eq.HitPoints,
                        "maxHp", (object)eq.MaxHitPoints
                    ));
                }
            }

            var apparel = new List<object>();
            if (pawn.apparel != null)
            {
                foreach (var ap in pawn.apparel.WornApparel)
                {
                    apparel.Add((object)D(
                        "def",   ap.def.defName,
                        "label", ap.Label,
                        "hp",    (object)ap.HitPoints,
                        "maxHp", (object)ap.MaxHitPoints
                    ));
                }
            }

            var inv = new List<object>();
            if (pawn.inventory != null && pawn.inventory.innerContainer != null)
            {
                foreach (var item in pawn.inventory.innerContainer)
                {
                    inv.Add((object)D(
                        "def",   item.def.defName,
                        "label", item.Label,
                        "count", (object)item.stackCount
                    ));
                }
            }

            return D("equipment", (object)equip, "apparel", (object)apparel, "inventory", (object)inv);
        }

        /// <summary>
        /// Returns key need levels (mood, food, rest, joy, beauty, comfort) for all colonists at once.
        /// </summary>
        /// <returns>Dictionary with: colonists (list of {name, mood, food, rest, joy, beauty, comfort}); values are floats 0-1 or -1 if unavailable</returns>
        public static object ColonistNeeds(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("colonists", new List<object>());

            var list = new List<object>();
            foreach (var pawn in map.mapPawns.FreeColonists)
            {
                var beauty = pawn.needs?.TryGetNeed<Need_Beauty>();
                var comfort = pawn.needs?.TryGetNeed<Need_Comfort>();
                list.Add((object)D(
                    "name",    pawn.LabelShort,
                    "mood",    (object)(pawn.needs?.mood != null ? RoundF(pawn.needs.mood.CurLevelPercentage) : -1f),
                    "food",    (object)(pawn.needs?.food != null ? RoundF(pawn.needs.food.CurLevelPercentage) : -1f),
                    "rest",    (object)(pawn.needs?.rest != null ? RoundF(pawn.needs.rest.CurLevelPercentage) : -1f),
                    "joy",     (object)(pawn.needs?.joy != null ? RoundF(pawn.needs.joy.CurLevelPercentage) : -1f),
                    "beauty",  (object)(beauty != null ? RoundF(beauty.CurLevelPercentage) : -1f),
                    "comfort", (object)(comfort != null ? RoundF(comfort.CurLevelPercentage) : -1f)
                ));
            }
            return D("colonists", list);
        }

        /// <summary>
        /// Returns all active mood thoughts for a specific pawn, including mood offset and remaining duration.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name to look up
        /// </param>
        /// <returns>Dictionary with: thoughts (list of {label, mood, daysLeft}); daysLeft is -1 for permanent thoughts</returns>
        public static object Thoughts(Dictionary<string, object> req)
        {
            string name = S(req, "pawn");
            if (name == null) throw new Exception("Missing 'pawn'");
            var pawn = FindPawn(name);
            if (pawn == null) throw new Exception("Pawn not found: " + name);

            var thoughts = new List<object>();
            if (pawn.needs?.mood?.thoughts == null)
                return D("thoughts", thoughts);

            var mem = new List<Thought>();
            pawn.needs.mood.thoughts.GetAllMoodThoughts(mem);
            foreach (var t in mem)
            {
                var tm = t as Thought_Memory;
                thoughts.Add((object)D(
                    "label",    t.LabelCap,
                    "mood",     (object)RoundF(t.MoodOffset()),
                    "daysLeft", (object)(tm != null && t.DurationTicks > 0 ? RoundF((float)(t.DurationTicks - tm.age) / 60000f) : -1f)
                ));
            }
            return D("thoughts", thoughts);
        }

        /// <summary>
        /// Returns all letters (notifications) currently in the letter stack, with text and quest info if available.
        /// </summary>
        /// <returns>Dictionary with: letters (list of {index, label, type, def, text?, has_quest?})</returns>
        public static object Letters(Dictionary<string, object> req)
        {
            var letters = Find.LetterStack.LettersListForReading;
            var list = new List<object>();
            for (int i = 0; i < letters.Count; i++)
            {
                var letter = letters[i];
                var ld = D(
                    "index", (object)i,
                    "label", letter.Label,
                    "type",  letter.GetType().Name,
                    "def",   letter.def != null ? letter.def.defName : "Unknown"
                );

                var textField = letter.GetType().GetField("text",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (textField != null)
                {
                    var text = textField.GetValue(letter) as string;
                    if (text != null)
                        ld["text"] = text.Length > 500 ? text.Substring(0, 500) + "..." : text;
                }

                var questField = letter.GetType().GetField("quest",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (questField != null)
                {
                    var quest = questField.GetValue(letter);
                    if (quest != null)
                        ld["has_quest"] = true;
                }

                list.Add((object)ld);
            }
            return D("letters", list);
        }

        /// <summary>
        /// Returns all open dialog windows, including node-tree dialog text and selectable options.
        /// </summary>
        /// <returns>Dictionary with: dialogs (list of {type, id, title?, text?, options?})</returns>
        public static object Dialogs(Dictionary<string, object> req)
        {
            var windows = Find.WindowStack.Windows;
            var list = new List<object>();

            foreach (var window in windows)
            {
                var wd = D(
                    "type", window.GetType().Name,
                    "id",   (object)window.ID
                );

                if (window.GetType().Name == "Dialog_NodeTree" || window.GetType().IsSubclassOf(typeof(Dialog_NodeTree)))
                {
                    var dnt = window as Dialog_NodeTree;
                    if (dnt != null)
                    {
                        wd["title"] = GetDialogTitle(dnt);
                        var node = GetCurNode(dnt);
                        wd["text"] = node != null ? (string)node.text : "";
                        wd["options"] = GetDialogOptions(dnt);
                    }
                }
                else
                {
                    var titleField = window.GetType().GetField("title",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    if (titleField != null)
                    {
                        var title = titleField.GetValue(window) as string;
                        if (title != null) wd["title"] = title;
                    }
                }

                list.Add((object)wd);
            }
            return D("dialogs", list);
        }

        /// <summary>
        /// Returns per-cell beauty values for a rectangular region (clamped to 50x50 max). Only non-zero cells are included.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default x1+10)
        /// - z2 (int, optional): top bound (default z1+10)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2 (int), avg (float), cells (list of {x, z, b})</returns>
        public static object Beauty(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("error", "no active map");

            const int MAX_REGION = 50;
            int minX = I(req, "x1", 0);
            int minZ = I(req, "z1", 0);
            int maxX = I(req, "x2", minX + 10);
            int maxZ = I(req, "z2", minZ + 10);
            if (maxX - minX + 1 > MAX_REGION) maxX = minX + MAX_REGION - 1;
            if (maxZ - minZ + 1 > MAX_REGION) maxZ = minZ + MAX_REGION - 1;

            int w = maxX - minX + 1;
            int h = maxZ - minZ + 1;
            var cells = new List<object>();
            float total = 0f;
            int count = 0;
            for (int x = minX; x <= maxX; x++)
            for (int z = minZ; z <= maxZ; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                float beauty = BeautyUtility.CellBeauty(cell, map, null);
                total += beauty;
                count++;
                // Only include non-zero cells to keep response compact
                if (beauty != 0f)
                    cells.Add(D("x", (object)x, "z", (object)z, "b", (object)RoundF(beauty)));
            }

            return D(
                "x1", (object)minX, "z1", (object)minZ,
                "x2", (object)maxX, "z2", (object)maxZ,
                "avg", (object)(count > 0 ? RoundF(total / count) : 0f),
                "cells", cells
            );
        }

        /// <summary>
        /// Returns per-cell terrain info (defName, fertility, water/rock flags) for a rectangular region (clamped to 50x50).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default x1)
        /// - z2 (int, optional): top bound (default z1)
        /// </param>
        /// <returns>Dictionary with: cells (list of {x, z, terrain, fertility, isWater, isRock})</returns>
        public static object Terrain(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("error", "no active map");

            int x1 = I(req, "x1", 0), z1 = I(req, "z1", 0);
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);
            // Clamp to 50x50
            if (x2 - x1 + 1 > 50) x2 = x1 + 49;
            if (z2 - z1 + 1 > 50) z2 = z1 + 49;

            var cells = new List<object>();
            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var td = map.terrainGrid.TerrainAt(cell);
                cells.Add(D(
                    "x", (object)x, "z", (object)z,
                    "terrain", td?.defName ?? "Unknown",
                    "fertility", (object)RoundF(map.fertilityGrid.FertilityAt(cell)),
                    "isWater", (object)(td != null && td.IsWater),
                    "isRock", (object)(cell.GetFirstMineable(map) != null)
                ));
            }
            return D("cells", cells);
        }

        /// <summary>
        /// Returns per-cell roof type for a rectangular region (clamped to 50x50).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default x1)
        /// - z2 (int, optional): top bound (default z1)
        /// </param>
        /// <returns>Dictionary with: cells (list of {x, z, roof}) where roof is defName string or null</returns>
        public static object Roof(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("error", "no active map");

            int x1 = I(req, "x1", 0), z1 = I(req, "z1", 0);
            int x2 = I(req, "x2", x1), z2 = I(req, "z2", z1);
            if (x2 - x1 + 1 > 50) x2 = x1 + 49;
            if (z2 - z1 + 1 > 50) z2 = z1 + 49;

            var cells = new List<object>();
            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var r = map.roofGrid.RoofAt(cell);
                cells.Add(D(
                    "x", (object)x, "z", (object)z,
                    "roof", r != null ? r.defName : (object)null
                ));
            }
            return D("cells", cells);
        }

        /// <summary>
        /// Returns the material costs and work amount required to build a given blueprint, optionally with a specific stuff material.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - blueprint (string, required): ThingDef defName of the building
        /// - stuff (string, optional): material defName (defaults to the building's default stuff)
        /// </param>
        /// <returns>Dictionary with: costs (list of {defName, count}), workAmount (float)</returns>
        public static object Costs(Dictionary<string, object> req)
        {
            var blueprintName = S(req, "blueprint");
            if (blueprintName == null) throw new Exception("Missing 'blueprint'");

            var thingDef = DefDatabase<ThingDef>.GetNamedSilentFail(blueprintName);
            if (thingDef == null) throw new Exception($"Unknown blueprint: {blueprintName}");

            var stuffName = S(req, "stuff");
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

            var costs = new List<object>();
            if (thingDef.costList != null)
            {
                foreach (var cost in thingDef.costList)
                    costs.Add(D("defName", cost.thingDef.defName, "count", (object)cost.count));
            }
            if (thingDef.MadeFromStuff && stuff != null)
            {
                costs.Add(D("defName", stuff.defName, "count", (object)thingDef.costStuffCount));
            }

            float work = thingDef.GetStatValueAbstract(StatDefOf.WorkToBuild, stuff);
            return D("costs", costs, "workAmount", (object)RoundF(work));
        }

        /// <summary>
        /// Returns interaction cells for all player buildings with interaction spots within a given region.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default x1+10)
        /// - z2 (int, optional): top bound (default z1+10)
        /// </param>
        /// <returns>Dictionary with: spots (list of {building, bx, bz, ix, iz})</returns>
        public static object InteractionSpots(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("error", "no active map");

            int x1 = I(req, "x1", 0), z1 = I(req, "z1", 0);
            int x2 = I(req, "x2", x1 + 10), z2 = I(req, "z2", z1 + 10);

            var spots = new List<object>();
            foreach (var b in map.listerBuildings.allBuildingsColonist)
            {
                if (!b.def.hasInteractionCell) continue;
                var bp = b.Position;
                var ic = b.InteractionCell;
                // Check if building or its interaction cell is within bounds
                bool inBounds = (bp.x >= x1 && bp.x <= x2 && bp.z >= z1 && bp.z <= z2)
                             || (ic.x >= x1 && ic.x <= x2 && ic.z >= z1 && ic.z <= z2);
                if (!inBounds) continue;
                spots.Add(D(
                    "building", b.def.defName,
                    "bx", (object)bp.x, "bz", (object)bp.z,
                    "ix", (object)ic.x, "iz", (object)ic.z
                ));
            }
            return D("spots", spots);
        }

        /// <summary>
        /// Health-check endpoint returning game/map status, colonist count, game speed, and current time.
        /// </summary>
        /// <returns>Dictionary with: status ("pong"), game (string), map (bool), time (string), colonists? (int), speed? (int)</returns>
        public static object Ping(Dictionary<string, object> req)
        {
            var map = GetMap();
            var d = D(
                "status", "pong",
                "game",   Current.Game != null ? "running" : "no_game",
                "map",    (object)(map != null),
                "time",   DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
            );
            if (map != null)
            {
                d["colonists"] = map.mapPawns.FreeColonistsCount;
                d["speed"] = (int)Find.TickManager.CurTimeSpeed;
            }
            return d;
        }

        /// <summary>
        /// Returns the current on-screen game messages (e.g. "colonist is starving") with age in seconds.
        /// </summary>
        /// <returns>Dictionary with: messages (list of {text, age})</returns>
        public static object LiveMessages(Dictionary<string, object> req)
        {
            // Messages.liveMessages is private — use reflection
            var msgType = typeof(Verse.Messages);
            var field = msgType.GetField("liveMessages", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
            if (field == null)
            {
                // Try alternative field names
                var fields = msgType.GetFields(BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public);
                var fieldNames = fields.Select(f => f.Name).ToList();
                return D("error", "No liveMessages field", "fields", string.Join(", ", fieldNames));
            }
            var messages = field.GetValue(null) as System.Collections.IList;
            if (messages == null) return D("messages", new List<object>());

            var result = new List<object>();
            foreach (var msg in messages)
            {
                var textProp = msg.GetType().GetField("text", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                var tickProp = msg.GetType().GetField("startingTick", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                string text = textProp?.GetValue(msg)?.ToString() ?? "?";
                int tick = tickProp != null ? (int)tickProp.GetValue(msg) : 0;
                float ageSec = (Find.TickManager.TicksGame - tick) / 60f;
                result.Add((object)D("text", text, "age", (object)ageSec));
            }
            return D("messages", result);
        }
        /// <summary>
        /// Returns aggregate statistics for a rectangular map region: terrain counts, water/rock/buildable tiles,
        /// fertility, roof coverage, and thing counts by category.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2 (int), total_tiles (int), terrain_counts ({string: int}),
        /// water_tiles, rock_tiles, buildable_tiles (int), avg_fertility (float), rich_soil_tiles (int),
        /// roof ({open, thin, overhead}), thing_counts ({tree, chunk, building, plant, item, pawn})</returns>
        public static object SurveyRegion(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            int x1 = I(req, "x1", 0);
            int z1 = I(req, "z1", 0);
            int x2 = Math.Min(I(req, "x2", map.Size.x - 1), map.Size.x - 1);
            int z2 = Math.Min(I(req, "z2", map.Size.z - 1), map.Size.z - 1);

            var terrainCounts = new Dictionary<string, int>();
            int waterTiles = 0, rockTiles = 0, buildableTiles = 0, richSoilTiles = 0;
            double fertilitySum = 0;
            int totalTiles = 0;
            int roofOpen = 0, roofThin = 0, roofOverhead = 0;

            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                totalTiles++;

                var td = map.terrainGrid.TerrainAt(cell);
                var tn = td?.defName ?? "Unknown";
                if (terrainCounts.ContainsKey(tn)) terrainCounts[tn]++;
                else terrainCounts[tn] = 1;

                if (td != null && td.IsWater) waterTiles++;

                // Rock: check for mineable things on cell
                bool hasMineable = false;
                var cellThings = map.thingGrid.ThingsListAt(cell);
                if (cellThings != null)
                {
                    foreach (var t in cellThings)
                    {
                        if (t is Mineable) { hasMineable = true; break; }
                    }
                }
                if (hasMineable) rockTiles++;

                // Buildable: not water, not impassable building
                bool impassableBuilding = false;
                if (cellThings != null)
                {
                    foreach (var t in cellThings)
                    {
                        if (t is Building b && b.def.passability == Traversability.Impassable)
                        { impassableBuilding = true; break; }
                    }
                }
                if (td != null && !td.IsWater && !impassableBuilding) buildableTiles++;

                // Fertility
                float fert = map.fertilityGrid.FertilityAt(cell);
                fertilitySum += fert;

                // Rich soil
                if (tn == "SoilRich") richSoilTiles++;

                // Roof
                var roof = map.roofGrid.RoofAt(cell);
                if (roof == null) roofOpen++;
                else if (roof.isThickRoof) roofOverhead++;
                else roofThin++;
            }

            // Count things by kind (reuse MapTiles categorization)
            int trees = 0, chunks = 0, buildings = 0, plants = 0, items = 0, pawns = 0;
            for (int x = x1; x <= x2; x++)
            for (int z = z1; z <= z2; z++)
            {
                var cell = new IntVec3(x, 0, z);
                if (!cell.InBounds(map)) continue;
                var list = map.thingGrid.ThingsListAt(cell);
                if (list == null) continue;
                foreach (var t in list)
                {
                    if (t == null || t.def == null) continue;
                    // Only count at spawn position to avoid double-counting multi-cell things
                    if (t.Position != cell) continue;

                    if (t is Plant pl)
                    {
                        if (pl.def.defName.StartsWith("Plant_Tree")) trees++;
                        else plants++;
                    }
                    else if (t.def.thingCategories != null &&
                             t.def.thingCategories.Any(c => c?.defName?.Contains("Chunk") == true))
                        chunks++;
                    else if (t is Building && !(t is Mineable)) buildings++;
                    else if (t.def.category == ThingCategory.Item) items++;
                    else if (t is Pawn) pawns++;
                }
            }

            double avgFert = totalTiles > 0 ? Math.Round(fertilitySum / totalTiles, 2) : 0;

            return D(
                "x1", (object)x1, "z1", (object)z1, "x2", (object)x2, "z2", (object)z2,
                "total_tiles", (object)totalTiles,
                "terrain_counts", terrainCounts.ToDictionary(kv => kv.Key, kv => (object)kv.Value),
                "water_tiles", (object)waterTiles,
                "rock_tiles", (object)rockTiles,
                "buildable_tiles", (object)buildableTiles,
                "avg_fertility", (object)avgFert,
                "rich_soil_tiles", (object)richSoilTiles,
                "roof", (object)D("open", (object)roofOpen, "thin", (object)roofThin, "overhead", (object)roofOverhead),
                "thing_counts", (object)D("tree", (object)trees, "chunk", (object)chunks, "building", (object)buildings, "plant", (object)plants, "item", (object)items, "pawn", (object)pawns)
            );
        }

        // ── ASCII Survey Lenses ───────────────────────────────────────
        // All accept optional x1,z1,x2,z2 (default full map) and scale (default 1).
        // scale>1 downsamples: each output char represents a scale×scale block.
        // Terrain/roof/fertility use majority vote; things/composite use max priority.

        /// <summary>
        /// Returns an ASCII grid of terrain types for a map region. Each character represents the majority terrain in a scale x scale block.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyTerrainAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                var counts = new Dictionary<char, int>();
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    char c = TerrainToChar(m.terrainGrid.TerrainAt(cell));
                    counts[c] = counts.ContainsKey(c) ? counts[c] + 1 : 1;
                }
                return MajorityChar(counts, '?');
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                ["."] = "Soil", ["R"] = "Rich soil", [","] = "Gravel",
                ["~"] = "Water", ["M"] = "Marsh", ["#"] = "Rock",
                ["S"] = "Sand", ["I"] = "Ice", ["_"] = "Floor", ["?"] = "Unknown"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of roof coverage for a map region. Characters indicate open sky, thin roof, or overhead mountain.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyRoofAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                var counts = new Dictionary<char, int>();
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    var r = m.roofGrid.RoofAt(cell);
                    char c = r == null ? ' ' : r.isThickRoof ? '#' : '.';
                    counts[c] = counts.ContainsKey(c) ? counts[c] + 1 : 1;
                }
                return MajorityChar(counts, ' ');
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "Open sky", ["."] = "Thin roof", ["#"] = "Overhead mountain"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of fertility levels for a map region. Characters range from empty (unfertile) to '#' (rich soil).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyFertilityAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                var counts = new Dictionary<char, int>();
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    char c = FertilityToChar(m.fertilityGrid.FertilityAt(cell));
                    counts[c] = counts.ContainsKey(c) ? counts[c] + 1 : 1;
                }
                return MajorityChar(counts, ' ');
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "0 (unfertile)", ["."] = "0.01-0.49", [","] = "0.50-0.69",
                ["+"] = "0.70-0.99", ["o"] = "1.00-1.09", ["O"] = "1.10-1.39",
                ["#"] = "1.40+ (rich)"
            });
        }

        /// <summary>
        /// Returns an ASCII grid showing things (buildings, pawns, items, etc.) for a map region, with highest-priority thing per cell.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyThingsAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                char best = ' '; int bestPri = -1;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    var things = m.thingGrid.ThingsListAt(cell);
                    if (things == null) continue;
                    foreach (var t in things)
                    {
                        if (t == null || t.def == null) continue;
                        char ch = ThingToChar(t);
                        if (ch == '\0') continue;
                        int pri = ThingCharPriority(ch);
                        if (pri > bestPri) { best = ch; bestPri = pri; }
                    }
                }
                return best;
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "Empty", ["!"] = "Urgent (food/medicine/corpse)",
                ["$"] = "Item", ["W"] = "Wall", ["D"] = "Door",
                ["F"] = "Furniture/building", ["B"] = "Blueprint", ["r"] = "Frame",
                ["T"] = "Tree", ["C"] = "Chunk", ["p"] = "Plant",
                ["P"] = "Colonist", ["A"] = "Animal", ["E"] = "Enemy"
            });
        }

        /// <summary>
        /// Returns a composite ASCII grid overlaying things on terrain for a map region. Things take priority over terrain characters.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyCompositeAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                var terrainCounts = new Dictionary<char, int>();
                char bestThing = '\0'; int bestThingPri = -1;

                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;

                    char tc = TerrainToChar(m.terrainGrid.TerrainAt(cell));
                    terrainCounts[tc] = terrainCounts.ContainsKey(tc) ? terrainCounts[tc] + 1 : 1;

                    var things = m.thingGrid.ThingsListAt(cell);
                    if (things == null) continue;
                    foreach (var t in things)
                    {
                        if (t == null || t.def == null) continue;
                        char ch = ThingToChar(t);
                        if (ch == '\0') continue;
                        int pri = ThingCharPriority(ch);
                        if (pri > bestThingPri) { bestThing = ch; bestThingPri = pri; }
                    }
                }

                return bestThing != '\0' ? bestThing : MajorityChar(terrainCounts, '?');
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                ["."] = "Soil", ["R"] = "Rich soil", [","] = "Gravel",
                ["~"] = "Water", ["M"] = "Marsh", ["#"] = "Rock",
                ["S"] = "Sand", ["I"] = "Ice", ["_"] = "Floor",
                ["!"] = "Urgent (food/medicine/corpse)", ["$"] = "Item",
                ["W"] = "Wall", ["D"] = "Door", ["F"] = "Furniture/building",
                ["B"] = "Blueprint", ["r"] = "Frame",
                ["T"] = "Tree", ["C"] = "Chunk", ["p"] = "Plant",
                ["P"] = "Colonist", ["A"] = "Animal", ["E"] = "Enemy"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of beauty levels for a map region, from '!' (very ugly) to '#' (gorgeous).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyBeautyAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                float sum = 0f; int n = 0;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    sum += BeautyUtility.CellBeauty(cell, m, null);
                    n++;
                }
                if (n == 0) return ' ';
                float avg = sum / n;
                if (avg <= -15f) return '!';
                if (avg < -5f)   return '-';
                if (avg <= 5f)   return '.';
                if (avg <= 15f)  return '+';
                if (avg <= 30f)  return '*';
                return '#';
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                ["!"] = "Very ugly (<= -15)", ["-"] = "Ugly (-15 to -5)",
                ["."] = "Neutral (-5 to 5)", ["+"] = "Pretty (5 to 15)",
                ["*"] = "Beautiful (15 to 30)", ["#"] = "Gorgeous (> 30)"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of temperature zones for a map region, from '*' (freezing) to '#' (hot).
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyTemperatureAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                float sum = 0f; int n = 0;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    sum += GenTemperature.GetTemperatureForCell(cell, m);
                    n++;
                }
                if (n == 0) return ' ';
                float avg = sum / n;
                if (avg < 0f)    return '*';
                if (avg < 10f)   return '-';
                if (avg <= 21f)  return '.';
                if (avg <= 30f)  return '+';
                return '#';
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                ["*"] = "Freezing (< 0C)", ["-"] = "Cold (0-10C)",
                ["."] = "Comfortable (10-21C)", ["+"] = "Warm (21-30C)",
                ["#"] = "Hot (> 30C)"
            });
        }

        /// <summary>
        /// Returns a highly detailed ASCII grid with zones, detailed thing classification, and a named entity legend
        /// listing colonists, animals, and their positions/jobs.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), entities (list of {type, char, name, x, z, ...}), legend ({char: description})</returns>
        public static object SurveyDetailedAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            // Collect named entities for the legend
            var entities = new List<Dictionary<string, object>>();

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                var terrainCounts = new Dictionary<char, int>();
                char bestThing = '\0'; int bestThingPri = -1;
                char zoneChar = '\0';

                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;

                    // Terrain
                    char tc = TerrainToChar(m.terrainGrid.TerrainAt(cell));
                    terrainCounts[tc] = terrainCounts.ContainsKey(tc) ? terrainCounts[tc] + 1 : 1;

                    // Zone (lowest priority, background)
                    if (zoneChar == '\0')
                    {
                        var zone = m.zoneManager.ZoneAt(cell);
                        if (zone != null)
                        {
                            var zn = zone.GetType().Name;
                            if (zn.Contains("Growing")) zoneChar = 'g';
                            else if (zone.label != null && zone.label.ToLower().Contains("food")) zoneChar = 'f';
                            else if (zone.label != null && zone.label.ToLower().Contains("dump")) zoneChar = 'd';
                            else zoneChar = 's'; // stockpile
                        }
                    }

                    // Things
                    var things = m.thingGrid.ThingsListAt(cell);
                    if (things == null) continue;
                    foreach (var t in things)
                    {
                        if (t == null || t.def == null) continue;
                        if (t is Mineable) continue;

                        char ch = '\0'; int pri = -1;
                        try {

                        if (t is Pawn pawn)
                        {
                            if (pawn.HostileTo(Faction.OfPlayer)) { ch = 'E'; pri = 95; }
                            else if (pawn.IsColonist)
                            {
                                var nick = pawn.Name?.ToStringShort ?? "?";
                                ch = char.ToUpper(nick[0]);
                                pri = 100;
                                entities.Add(new Dictionary<string, object> {
                                    ["type"] = "colonist", ["char"] = ch.ToString(),
                                    ["name"] = nick, ["x"] = x, ["z"] = z,
                                    ["job"] = (object)(pawn.CurJobDef?.defName ?? "idle")
                                });
                            }
                            else if (pawn.RaceProps?.Animal == true)
                            {
                                var species = pawn.def?.defName ?? "Unknown";
                                ch = char.ToLower(species[0]);
                                pri = 35;
                                entities.Add(new Dictionary<string, object> {
                                    ["type"] = "animal", ["char"] = ch.ToString(),
                                    ["name"] = species, ["x"] = x, ["z"] = z,
                                    ["tame"] = (object)(pawn.Faction != null && pawn.Faction == Faction.OfPlayer)
                                });
                            }
                            else { ch = '?'; pri = 30; }
                        }
                        else if (t is Blueprint) { ch = 'b'; pri = 50; }
                        else if (t is Frame) { ch = 'r'; pri = 55; }
                        else if (t is Building)
                        {
                            var def = t.def.defName;
                            if (def.Contains("Door")) { ch = 'D'; pri = 70; }
                            else if (def == "Wall" || t.def.IsSmoothed) { ch = 'W'; pri = 70; }
                            else if (def.Contains("Bed")) { ch = '='; pri = 65; }
                            else if (def.Contains("Table") || def.Contains("Chair")) { ch = '+'; pri = 60; }
                            else if (def.Contains("Campfire") || def.Contains("Stove")) { ch = '&'; pri = 65; }
                            else if (def.Contains("Torch") || def.Contains("Lamp")) { ch = '*'; pri = 58; }
                            else if (def.Contains("Sculpture")) { ch = '@'; pri = 62; }
                            else if (def.Contains("Research")) { ch = 'R'; pri = 62; }
                            else if (def.Contains("Butcher")) { ch = '%'; pri = 62; }
                            else if (def.Contains("Horseshoe")) { ch = 'H'; pri = 58; }
                            else if (def.Contains("EndTable") || def.Contains("Dresser")) { ch = 'n'; pri = 57; }
                            else { ch = 'F'; pri = 60; }
                        }
                        else if (t is Plant plant)
                        {
                            if (plant.def.defName.StartsWith("Plant_Tree")) { ch = 'T'; pri = 20; }
                            else if (plant.def.defName.Contains("Berry")) { ch = 'v'; pri = 22; }
                            else { ch = '.'; pri = 0; } // plants don't override terrain
                        }
                        else if (t.def.category == ThingCategory.Item)
                        {
                            var dn = t.def.defName;
                            if (dn.Contains("Corpse")) { ch = 'X'; pri = 90; }
                            else if (dn.Contains("Meal")) { ch = 'm'; pri = 82; }
                            else if (dn.Contains("Meat") || dn.Contains("RawFood")) { ch = '~'; pri = 80; }
                            else if (dn.Contains("Medicine")) { ch = '!'; pri = 85; }
                            else if (dn == "WoodLog") { ch = 'w'; pri = 75; }
                            else if (dn == "Steel") { ch = 'i'; pri = 75; }
                            else if (dn.Contains("Component")) { ch = 'c'; pri = 76; }
                            else { ch = '$'; pri = 74; }
                        }
                        else if (t.def.thingCategories != null &&
                            t.def.thingCategories.Any(c => c?.defName?.Contains("Chunk") == true))
                        { ch = 'C'; pri = 25; }

                        if (pri > bestThingPri) { bestThing = ch; bestThingPri = pri; }
                        } catch { /* skip problematic thing */ }
                    }
                }

                if (bestThing != '\0' && bestThing != '.') return bestThing;
                if (zoneChar != '\0') return zoneChar;
                return MajorityChar(terrainCounts, ' ');
            });

            return new Dictionary<string, object>
            {
                ["x1"] = x1, ["z1"] = z1, ["x2"] = x2, ["z2"] = z2, ["scale"] = scale,
                ["grid"] = rows,
                ["entities"] = entities,
                ["legend"] = new Dictionary<string, object>
                {
                    // Terrain
                    [" "] = "Soil", [","] = "Gravel", ["#"] = "Rock",
                    // Zones (background)
                    ["s"] = "Stockpile zone", ["f"] = "Food stockpile", ["d"] = "Dump zone", ["g"] = "Grow zone",
                    // Structures
                    ["W"] = "Wall", ["D"] = "Door", ["_"] = "Floor",
                    // Furniture
                    ["="] = "Bed", ["+"] = "Table/Chair", ["&"] = "Campfire/Stove",
                    ["*"] = "Torch/Lamp", ["@"] = "Sculpture", ["R"] = "Research bench",
                    ["%"] = "Butcher spot", ["H"] = "Horseshoes", ["n"] = "EndTable/Dresser",
                    ["F"] = "Other furniture",
                    // Construction
                    ["b"] = "Blueprint", ["r"] = "Frame",
                    // Nature
                    ["T"] = "Tree", ["v"] = "Berry bush", ["C"] = "Chunk",
                    // Items
                    ["m"] = "Meal", ["~"] = "Raw meat/food", ["w"] = "Wood", ["i"] = "Steel",
                    ["c"] = "Components", ["$"] = "Other item", ["!"] = "Medicine",
                    ["X"] = "Corpse",
                    // Pawns (colonists use first letter of name, listed in entities)
                    ["a-z"] = "Wild animal (first letter of species)",
                    ["A-Z"] = "Colonist (first letter of name)",
                    ["E"] = "Enemy"
                }
            };
        }

        /// <summary>
        /// Returns an ASCII grid focused on construction progress: blueprints, frames, and completed buildings.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyBlueprintAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                char best = ' '; int bestPri = -1;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    var things = m.thingGrid.ThingsListAt(cell);
                    if (things == null) continue;
                    foreach (var t in things)
                    {
                        if (t == null || t.def == null) continue;
                        char ch = '\0'; int pri = -1;
                        if (t is Blueprint)
                        {
                            var dn = t.def?.entityDefToBuild?.defName ?? "";
                            if (dn == "Wall" || dn.Contains("Door")) { ch = 'B'; pri = 3; }
                            else if (dn.Contains("Conduit"))         { ch = 'b'; pri = 2; }
                            else                                     { ch = 'B'; pri = 3; }
                        }
                        else if (t is Frame)
                        {
                            ch = 'r'; pri = 4;
                        }
                        else if (t is Building)
                        {
                            var dn = t.def.defName;
                            if (dn.Contains("Door")) { ch = 'D'; pri = 1; }
                            else if (dn == "Wall" || t.def.IsSmoothed) { ch = 'W'; pri = 1; }
                            else { ch = '#'; pri = 0; }
                        }
                        if (pri > bestPri) { best = ch; bestPri = pri; }
                    }
                }
                return best;
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "Empty", ["#"] = "Built (other)", ["W"] = "Built wall",
                ["D"] = "Built door", ["b"] = "Blueprint (conduit)",
                ["B"] = "Blueprint (structure)", ["r"] = "Frame (in progress)"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of the power network for a map region, showing generators, consumers, conduits, and batteries.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyPowerAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                char best = ' '; int bestPri = -1;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    var cell = new IntVec3(x, 0, z);
                    if (!cell.InBounds(m)) continue;
                    var things = m.thingGrid.ThingsListAt(cell);
                    if (things == null) continue;
                    foreach (var t in things)
                    {
                        if (t == null || t.def == null) continue;
                        var comp = t.TryGetComp<CompPowerTrader>();
                        var compBat = t.TryGetComp<CompPowerBattery>();
                        char ch = '\0'; int pri = -1;

                        if (comp != null)
                        {
                            if (comp.PowerOutput > 0)
                            {
                                ch = 'G'; pri = 4;  // producing power
                            }
                            else
                            {
                                ch = comp.PowerOn ? 'C' : 'c'; pri = 3;
                            }
                        }
                        else if (compBat != null)
                        {
                            ch = 'B'; pri = 3;
                        }
                        else if (t.def.defName.Contains("Conduit"))
                        {
                            ch = '='; pri = 1;
                        }

                        if (pri > bestPri) { best = ch; bestPri = pri; }
                    }
                }
                return best;
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "No power", ["="] = "Conduit",
                ["B"] = "Battery", ["C"] = "Consumer (powered)",
                ["c"] = "Consumer (unpowered)", ["G"] = "Generator"
            });
        }

        /// <summary>
        /// Returns an ASCII grid of active designations/tasks (mine, cut, hunt, haul, etc.) for a map region.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - x1 (int, optional): left bound (default 0)
        /// - z1 (int, optional): bottom bound (default 0)
        /// - x2 (int, optional): right bound (default map width - 1)
        /// - z2 (int, optional): top bound (default map height - 1)
        /// - scale (int, optional): downsampling factor (default 1)
        /// </param>
        /// <returns>Dictionary with: x1, z1, x2, z2, scale (int), grid (list of string rows), legend ({char: description})</returns>
        public static object SurveyTaskAscii(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No active map");
            int x1, z1, x2, z2, scale;
            ParseAsciiBounds(req, map, out x1, out z1, out x2, out z2, out scale);

            // Build a lookup: cell → highest-priority designation char
            var desigMap = new Dictionary<long, char>();
            Action<int, int, char, int> trySet = (cx, cz, ch, pri) =>
            {
                if (cx < x1 || cx > x2 || cz < z1 || cz > z2) return;
                long key = ((long)cx << 32) | (uint)cz;
                char existing;
                if (!desigMap.TryGetValue(key, out existing) || pri > TaskCharPriority(existing))
                    desigMap[key] = ch;
            };

            // Iterate all designations (both cell and thing targets)
            var desigField = map.designationManager.GetType().GetField("allDesignations",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var allDesigs = desigField?.GetValue(map.designationManager) as IEnumerable<Designation>;
            if (allDesigs != null)
            {
                foreach (var d in allDesigs)
                {
                    IntVec3 pos;
                    if (d.target.HasThing)
                    {
                        if (d.target.Thing == null) continue;
                        pos = d.target.Thing.Position;
                    }
                    else
                    {
                        pos = d.target.Cell;
                    }

                    var dn = d.def.defName;
                    char ch; int pri;
                    if (dn == "Deconstruct")        { ch = 'X'; pri = 5; }
                    else if (dn == "Mine")           { ch = 'M'; pri = 5; }
                    else if (dn == "CutPlant")       { ch = 'C'; pri = 4; }
                    else if (dn == "HarvestPlant")   { ch = 'V'; pri = 4; }
                    else if (dn == "Hunt")           { ch = 'H'; pri = 6; }
                    else if (dn == "Tame")           { ch = 'T'; pri = 3; }
                    else if (dn == "Slaughter")      { ch = 'K'; pri = 6; }
                    else if (dn == "Haul")           { ch = 'h'; pri = 2; }
                    else if (dn == "HaulThing")      { ch = 'h'; pri = 2; }
                    else if (dn == "Strip")          { ch = 'S'; pri = 3; }
                    else if (dn == "Flick")          { ch = 'f'; pri = 1; }
                    else if (dn == "Plan")           { ch = 'p'; pri = 0; }
                    else if (dn == "Uninstall")      { ch = 'U'; pri = 4; }
                    else if (dn == "SmoothFloor")    { ch = 's'; pri = 2; }
                    else if (dn == "SmoothWall")     { ch = 's'; pri = 2; }
                    else if (dn == "RemoveFloor")    { ch = 'R'; pri = 3; }
                    else if (dn == "ClaimBuilding")  { ch = 'c'; pri = 1; }
                    else                             { ch = '?'; pri = 1; }

                    trySet(pos.x, pos.z, ch, pri);
                }
            }

            var rows = BuildAsciiGrid(map, x1, z1, x2, z2, scale, (m, bx, bz, ex, ez) =>
            {
                char best = ' '; int bestPri = -1;
                for (int z = bz; z <= ez; z++)
                for (int x = bx; x <= ex; x++)
                {
                    long key = ((long)x << 32) | (uint)z;
                    char ch;
                    if (desigMap.TryGetValue(key, out ch))
                    {
                        int pri = TaskCharPriority(ch);
                        if (pri > bestPri) { best = ch; bestPri = pri; }
                    }
                }
                return best;
            });

            return AsciiResult(x1, z1, x2, z2, scale, rows, new Dictionary<string, object>
            {
                [" "] = "No task", ["p"] = "Plan", ["f"] = "Flick",
                ["c"] = "Claim", ["h"] = "Haul", ["s"] = "Smooth",
                ["R"] = "Remove floor", ["S"] = "Strip",
                ["T"] = "Tame", ["U"] = "Uninstall",
                ["C"] = "Cut plant", ["V"] = "Harvest",
                ["M"] = "Mine", ["X"] = "Deconstruct",
                ["H"] = "Hunt", ["K"] = "Slaughter", ["?"] = "Other"
            });
        }

        private static int TaskCharPriority(char c)
        {
            switch (c)
            {
                case 'p': return 0;
                case 'f': case 'c': return 1;
                case 'h': case 's': return 2;
                case 'R': case 'S': case 'T': return 3;
                case 'C': case 'V': case 'U': return 4;
                case 'M': case 'X': return 5;
                case 'H': case 'K': return 6;
                default: return 1;
            }
        }

        // ── ASCII helpers ─────────────────────────────────────────────

        private static void ParseAsciiBounds(Dictionary<string, object> req, Map map,
            out int x1, out int z1, out int x2, out int z2, out int scale)
        {
            x1 = I(req, "x1", 0);
            z1 = I(req, "z1", 0);
            x2 = Math.Min(I(req, "x2", map.Size.x - 1), map.Size.x - 1);
            z2 = Math.Min(I(req, "z2", map.Size.z - 1), map.Size.z - 1);
            scale = Math.Max(I(req, "scale", 1), 1);
        }

        private delegate char AsciiBlockFunc(Map map, int bx, int bz, int ex, int ez);

        private static List<string> BuildAsciiGrid(Map map, int x1, int z1, int x2, int z2,
            int scale, AsciiBlockFunc blockFunc)
        {
            var rows = new List<string>();
            for (int bz = z1; bz <= z2; bz += scale)
            {
                int ez = Math.Min(bz + scale - 1, z2);
                var sb = new StringBuilder((x2 - x1) / scale + 2);
                for (int bx = x1; bx <= x2; bx += scale)
                {
                    int ex = Math.Min(bx + scale - 1, x2);
                    sb.Append(blockFunc(map, bx, bz, ex, ez));
                }
                rows.Add(sb.ToString());
            }
            return rows;
        }

        private static Dictionary<string, object> AsciiResult(int x1, int z1, int x2, int z2,
            int scale, List<string> rows, Dictionary<string, object> legend)
        {
            return D(
                "x1", (object)x1, "z1", (object)z1,
                "x2", (object)x2, "z2", (object)z2,
                "scale", (object)scale,
                "grid", rows,
                "legend", (object)legend
            );
        }

        private static char MajorityChar(Dictionary<char, int> counts, char fallback)
        {
            char best = fallback; int bestN = 0;
            foreach (var kv in counts)
                if (kv.Value > bestN) { best = kv.Key; bestN = kv.Value; }
            return best;
        }

        private static char TerrainToChar(TerrainDef td)
        {
            if (td == null) return '?';
            var n = td.defName;
            if (n == "SoilRich") return 'R';
            if (n == "Soil" || n == "MossyTerrain") return '.';
            if (n == "Gravel") return ',';
            if (n == "MarshyTerrain") return 'M';
            if (td.IsWater) return '~';
            if (n == "Sand" || n == "SoftSand") return 'S';
            if (n == "Ice") return 'I';
            if (n.Contains("_Rough") || n.Contains("_RoughHewn") || n.Contains("_Smooth")) return '#';
            if (td.layerable) return '_';
            return '?';
        }

        private static char FertilityToChar(float f)
        {
            if (f <= 0f)  return ' ';
            if (f < 0.5f) return '.';
            if (f < 0.7f) return ',';
            if (f < 1.0f) return '+';
            if (f < 1.1f) return 'o';
            if (f < 1.4f) return 'O';
            return '#';
        }

        private static char ThingToChar(Thing t)
        {
            if (t is Mineable) return '\0';

            if (t is Pawn pawn)
            {
                if (pawn.HostileTo(Faction.OfPlayer)) return 'E';
                if (pawn.IsColonist) return 'P';
                if (pawn.RaceProps?.Animal == true) return 'A';
                return 'P';
            }
            if (t is Blueprint) return 'B';
            if (t is Frame) return 'r';
            if (t is Building)
            {
                var def = t.def.defName;
                if (def.Contains("Door")) return 'D';
                if (def == "Wall" || t.def.IsSmoothed) return 'W';
                return 'F';
            }
            if (t is Plant plant)
            {
                if (plant.def.defName.StartsWith("Plant_Tree")) return 'T';
                return 'p';
            }
            if (t.def.category == ThingCategory.Item)
            {
                var dn = t.def.defName;
                if (dn.Contains("Corpse")) return '!';
                var rot = t.TryGetComp<CompRottable>();
                if (rot != null) return '!';
                if (dn.Contains("Medicine")) return '!';
                return '$';
            }
            if (t.def.thingCategories != null &&
                t.def.thingCategories.Any(c => c?.defName?.Contains("Chunk") == true))
                return 'C';

            return '\0';
        }

        private static int ThingCharPriority(char c)
        {
            switch (c)
            {
                case '!': return 90;
                case '$': return 80;
                case 'W': case 'D': return 70;
                case 'F': return 60;
                case 'B': case 'r': return 50;
                case 'E': case 'P': return 40;
                case 'A': return 30;
                case 'T': case 'C': return 20;
                case 'p': return 10;
                default: return -1;
            }
        }

        /// <summary>
        /// Returns the player colony's ideology info including memes, roles, and role assignments. Requires Ideology DLC.
        /// </summary>
        /// <returns>Dictionary with: active (bool), name? (string), roles? (list of {defName, label, assigned, maxCount, requirements}), memes? (list of {defName, label, description})</returns>
        public static object Ideology(Dictionary<string, object> req)
        {
            if (!ModsConfig.IdeologyActive)
                return D("active", false, "error", "Ideology DLC not active");

            var ideo = Faction.OfPlayer?.ideos?.PrimaryIdeo;
            if (ideo == null)
                return D("active", true, "ideology", (object)null);

            // Roles
            var roles = new List<object>();
            foreach (var precept in ideo.PreceptsListForReading)
            {
                var role = precept as Precept_Role;
                if (role == null) continue;

                var assigned = new List<object>();
                foreach (var pawn in PawnsFinder.AllMaps_FreeColonists)
                {
                    if (role.IsAssigned(pawn))
                    {
                        assigned.Add(D(
                            "name", pawn.Name?.ToStringShort ?? "Unknown",
                            "fullName", pawn.Name?.ToStringFull ?? "Unknown"
                        ));
                    }
                }

                var requirements = new List<object>();
                if (role.def.roleRequirements != null)
                {
                    foreach (var rr in role.def.roleRequirements)
                        requirements.Add(rr.GetLabel(role).CapitalizeFirst());
                }

                roles.Add(D(
                    "defName", role.def.defName,
                    "label", role.LabelCap,
                    "assigned", (object)assigned,
                    "maxCount", (object)(role.def.maxCount),
                    "requirements", (object)requirements
                ));
            }

            // Memes
            var memes = ideo.memes?.Select(m => (object)D(
                "defName", m.defName,
                "label", m.LabelCap,
                "description", m.description ?? ""
            )).ToList() ?? new List<object>();

            return D(
                "active", true,
                "name", ideo.name,
                "roles", (object)roles,
                "memes", (object)memes
            );
        }

        /// <summary>
        /// Assigns a pawn to an ideology role, unassigning current holders if at max count. Requires Ideology DLC.
        /// </summary>
        /// <param name="req">
        /// Parameters:
        /// - pawn (string, required): pawn name to assign
        /// - role (string, required): role defName to assign
        /// </param>
        /// <returns>Dictionary with: ok (bool), pawn (string), role (string)</returns>
        public static object AssignRole(Dictionary<string, object> req)
        {
            if (!ModsConfig.IdeologyActive)
                throw new Exception("Ideology DLC not active");

            string pawnName = S(req, "pawn");
            string roleDef = S(req, "role");
            if (pawnName == null || roleDef == null) throw new Exception("Need: pawn, role");

            var pawn = FindPawn(pawnName);
            if (pawn == null) throw new Exception("Pawn not found: " + pawnName);

            var ideo = Faction.OfPlayer?.ideos?.PrimaryIdeo;
            if (ideo == null) throw new Exception("No player ideology found");

            Precept_Role targetRole = null;
            foreach (var precept in ideo.PreceptsListForReading)
            {
                var role = precept as Precept_Role;
                if (role != null && role.def.defName.Equals(roleDef, StringComparison.OrdinalIgnoreCase))
                {
                    targetRole = role;
                    break;
                }
            }
            if (targetRole == null) throw new Exception("Role not found: " + roleDef);

            // Unassign current holder if at max count
            if (targetRole.def.maxCount > 0)
            {
                var currentHolders = PawnsFinder.AllMaps_FreeColonists
                    .Where(p => targetRole.IsAssigned(p)).ToList();
                if (currentHolders.Count >= targetRole.def.maxCount)
                {
                    foreach (var holder in currentHolders)
                        targetRole.Unassign(holder, false);
                }
            }

            targetRole.Assign(pawn, true);

            return D("ok", true, "pawn", pawnName, "role", targetRole.LabelCap);
        }

        /// <summary>
        /// Returns friendly visitor groups on the map (with trader goods if applicable) and incoming world caravans.
        /// </summary>
        /// <returns>Dictionary with: visitors (list of {faction, count, isTrader, traderName?, traderKind?, goods?, pawns}),
        /// caravans (list of {faction, pawnCount, tile, destTile, arriving})</returns>
        public static object Visitors(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) return D("visitors", new List<object>(), "caravans", new List<object>());

            // Visitors / traders on map
            var visitors = new List<object>();
            var factionGroups = new Dictionary<string, List<Pawn>>();

            foreach (var pawn in map.mapPawns.AllPawnsSpawned)
            {
                if (pawn.Dead || pawn.Downed) continue;
                if (pawn.Faction == null || pawn.Faction == Faction.OfPlayer) continue;
                if (pawn.Faction.HostileTo(Faction.OfPlayer)) continue;
                if (pawn.RaceProps.Animal) continue;

                string factionName = pawn.Faction.Name ?? pawn.Faction.def.defName;
                if (!factionGroups.ContainsKey(factionName))
                    factionGroups[factionName] = new List<Pawn>();
                factionGroups[factionName].Add(pawn);
            }

            foreach (var kvp in factionGroups)
            {
                bool hasTrader = kvp.Value.Any(p => p.TraderKind != null);
                var traderPawn = kvp.Value.FirstOrDefault(p => p.TraderKind != null);

                var group = D(
                    "faction", kvp.Key,
                    "count", (object)kvp.Value.Count,
                    "isTrader", (object)hasTrader
                );

                if (hasTrader && traderPawn != null)
                {
                    group["traderName"] = traderPawn.Name?.ToStringShort ?? traderPawn.LabelShort;
                    group["traderKind"] = traderPawn.TraderKind.defName;

                    // List tradeable items
                    var goods = new List<object>();
                    if (traderPawn.trader?.Goods != null)
                    {
                        foreach (var thing in traderPawn.trader.Goods.Take(50))
                        {
                            goods.Add(D(
                                "def", thing.def.defName,
                                "label", thing.LabelCapNoCount,
                                "count", (object)thing.stackCount,
                                "value", (object)RoundF(thing.MarketValue)
                            ));
                        }
                    }
                    group["goods"] = goods;
                }

                var pawns = kvp.Value.Select(p => (object)D(
                    "name", p.Name?.ToStringShort ?? p.LabelShort,
                    "position", D("x", (object)p.Position.x, "z", (object)p.Position.z),
                    "isTrader", (object)(p.TraderKind != null)
                )).ToList();
                group["pawns"] = pawns;

                visitors.Add(group);
            }

            // World caravans heading to this map
            var caravans = new List<object>();
            foreach (var caravan in Find.WorldObjects.Caravans)
            {
                if (caravan.Faction == Faction.OfPlayer) continue;
                if (caravan.Faction.HostileTo(Faction.OfPlayer)) continue;

                // Check if the caravan is heading to our tile
                int destTile = caravan.pather?.Destination ?? -1;
                int mapTile = map.Tile;
                if (destTile != mapTile && caravan.Tile != mapTile) continue;

                caravans.Add(D(
                    "faction", caravan.Faction.Name ?? caravan.Faction.def.defName,
                    "pawnCount", (object)caravan.PawnsListForReading.Count,
                    "tile", (object)caravan.Tile,
                    "destTile", (object)destTile,
                    "arriving", (object)(destTile == mapTile)
                ));
            }

            return D("visitors", (object)visitors, "caravans", (object)caravans);
        }

        /// <summary>
        /// Returns colony wealth breakdown (total, items, buildings, floors, pawns), average beauty/impressiveness across the home area, and per-room stats.
        /// </summary>
        /// <returns>Dictionary with: wealth_total, wealth_items, wealth_buildings, wealth_floors, wealth_pawns (float),
        /// avg_beauty (float), home_cells (int), avg_impressiveness (float), room_count (int),
        /// rooms (list of {role, impressiveness, beauty, cells, roofed, openRoofCount})</returns>
        public static object ColonyStats(Dictionary<string, object> req)
        {
            var map = GetMap();
            if (map == null) throw new Exception("No map loaded");

            var ww = map.wealthWatcher;

            // Force recalculation
            var forceField = typeof(WealthWatcher).GetField("lastCountTick",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            if (forceField != null) forceField.SetValue(ww, -99999);

            float totalWealth = ww.WealthTotal;
            float itemWealth = ww.WealthItems;
            float buildingWealth = ww.WealthBuildings;
            float floorWealth = ww.WealthFloorsOnly;

            // Pawn value
            float pawnWealth = 0;
            foreach (var p in map.mapPawns.FreeColonists)
                pawnWealth += p.MarketValue;

            // Average beauty across home area
            float totalBeauty = 0;
            int beautyCells = 0;
            var homeArea = map.areaManager.Home;
            foreach (var cell in homeArea.ActiveCells)
            {
                totalBeauty += BeautyUtility.CellBeauty(cell, map, null);
                beautyCells++;
            }
            float avgBeauty = beautyCells > 0 ? totalBeauty / beautyCells : 0;

            // Room impressiveness summary
            var roomsField = map.regionGrid.GetType().GetField("allRooms",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            var allRooms = roomsField?.GetValue(map.regionGrid) as List<Room> ?? new List<Room>();
            var playerRooms = allRooms.Where(r => !r.TouchesMapEdge && r.Role != null
                && r.Role.defName != "None").ToList();

            float totalImpress = 0;
            int roomCount = 0;
            var roomDetails = new List<object>();
            foreach (var r in playerRooms)
            {
                float imp = r.GetStat(RoomStatDefOf.Impressiveness);
                float bty = r.GetStat(RoomStatDefOf.Beauty);
                totalImpress += imp;
                roomCount++;
                roomDetails.Add(D(
                    "role", r.Role.defName,
                    "impressiveness", (object)Math.Round(imp, 1),
                    "beauty", (object)Math.Round(bty, 1),
                    "cells", (object)r.CellCount,
                    "roofed", (object)(r.OpenRoofCount == 0),
                    "openRoofCount", (object)r.OpenRoofCount
                ));
            }
            float avgImpress = roomCount > 0 ? totalImpress / roomCount : 0;

            return D(
                "wealth_total",     (object)Math.Round(totalWealth),
                "wealth_items",     (object)Math.Round(itemWealth),
                "wealth_buildings", (object)Math.Round(buildingWealth),
                "wealth_floors",    (object)Math.Round(floorWealth),
                "wealth_pawns",     (object)Math.Round(pawnWealth),
                "avg_beauty",       (object)Math.Round(avgBeauty, 2),
                "home_cells",       (object)beautyCells,
                "avg_impressiveness",(object)Math.Round(avgImpress, 1),
                "room_count",       (object)roomCount,
                "rooms",            roomDetails
            );
        }
        /// <summary>
        /// Returns recent food consumption events from the in-memory ring buffer.
        /// Does not require set_event_log — always active.
        /// </summary>
        /// <returns>Dictionary with: events (list of {tick, hour, pawn, food, nutrition, foodNeedBefore, foodNeedAfter}), count (int)</returns>
        public static object FoodLog(Dictionary<string, object> req)
        {
            var entries = EventLogger.GetFoodLog();
            return D("events", entries, "count", (object)entries.Count);
        }
    }
}
