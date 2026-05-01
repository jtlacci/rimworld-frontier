using System;
using System.Collections.Generic;
using System.IO;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;
using static CarolineConsole.Helpers;

namespace CarolineConsole
{
    /// <summary>
    /// Logs colonist job transitions, item pickups/drops, and eating events to a JSONL file.
    /// Activated by the set_event_log TCP command which sets the output path.
    /// Also maintains an always-active food consumption ring buffer queryable via read_food_log.
    /// </summary>
    public static class EventLogger
    {
        private static StreamWriter _writer;
        private static readonly object _lock = new object();

        // Food consumption ring buffer — always active (no set_event_log needed)
        private const int FOOD_LOG_SIZE = 50;
        private static readonly List<Dictionary<string, object>> _foodLog = new List<Dictionary<string, object>>();
        private static readonly object _foodLock = new object();

        public static List<Dictionary<string, object>> GetFoodLog()
        {
            lock (_foodLock)
            {
                return new List<Dictionary<string, object>>(_foodLog);
            }
        }

        public static void AddFoodEntry(Dictionary<string, object> entry)
        {
            lock (_foodLock)
            {
                _foodLog.Add(entry);
                if (_foodLog.Count > FOOD_LOG_SIZE)
                    _foodLog.RemoveAt(0);
            }
        }

        public static bool Active => _writer != null;

        public static void Start(string path)
        {
            Stop();
            try
            {
                _writer = new StreamWriter(path, append: false) { AutoFlush = true };
                Verse.Log.Message($"[CarolineConsole] Event logger started: {path}");
            }
            catch (Exception e)
            {
                Verse.Log.Warning($"[CarolineConsole] Failed to start event logger: {e.Message}");
            }
        }

        public static void Stop()
        {
            lock (_lock)
            {
                if (_writer != null)
                {
                    try { _writer.Close(); } catch { }
                    _writer = null;
                }
            }
        }

        public static void Emit(string pawn, string eventType, string detail,
                                int x = -1, int z = -1, string thing = null, int count = 0)
        {
            if (_writer == null) return;
            try
            {
                var map = Find.CurrentMap;
                int tick = Find.TickManager?.TicksGame ?? 0;
                float hour = map != null ? GenLocalDate.HourFloat(map) : 0f;

                var sb = new System.Text.StringBuilder(128);
                sb.Append("{\"t\":").Append(tick);
                sb.Append(",\"h\":").Append(Math.Round(hour, 1));
                sb.Append(",\"p\":\"").Append(EscJson(pawn)).Append('"');
                sb.Append(",\"e\":\"").Append(eventType).Append('"');
                sb.Append(",\"d\":\"").Append(EscJson(detail)).Append('"');
                if (thing != null)
                    sb.Append(",\"thing\":\"").Append(EscJson(thing)).Append('"');
                if (count > 0)
                    sb.Append(",\"n\":").Append(count);
                if (x >= 0)
                    sb.Append(",\"x\":").Append(x).Append(",\"z\":").Append(z);
                sb.Append('}');

                lock (_lock)
                {
                    _writer?.WriteLine(sb.ToString());
                }
            }
            catch { /* never crash the game for logging */ }
        }

        private static string EscJson(string s)
        {
            if (s == null) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }

    /// <summary>
    /// Logs when a colonist starts a new job.
    /// </summary>
    [HarmonyPatch(typeof(Pawn_JobTracker), nameof(Pawn_JobTracker.StartJob))]
    public static class JobStartPatch
    {
        static void Postfix(Pawn_JobTracker __instance, Job newJob)
        {
            if (!EventLogger.Active) return;
            var pawn = Traverse.Create(__instance).Field("pawn").GetValue<Pawn>();
            if (pawn?.Faction == null || !pawn.Faction.IsPlayer || pawn.RaceProps.Animal) return;

            string name = pawn.Name?.ToStringShort ?? "?";
            string jobDef = newJob?.def?.defName ?? "?";
            string target = newJob?.targetA.Thing?.def?.defName ?? "";
            int x = pawn.Position.x, z = pawn.Position.z;

            EventLogger.Emit(name, "job", jobDef, x, z, target.Length > 0 ? target : null);
        }
    }

    /// <summary>
    /// Logs when a colonist picks up an item to carry.
    /// </summary>
    [HarmonyPatch(typeof(Pawn_CarryTracker), nameof(Pawn_CarryTracker.TryStartCarry), new[] { typeof(Thing), typeof(int), typeof(bool) })]
    public static class CarryStartPatch
    {
        static void Postfix(Pawn_CarryTracker __instance, Thing item, int count, bool __result)
        {
            if (!EventLogger.Active || !__result) return;
            var pawn = __instance.pawn;
            if (pawn?.Faction == null || !pawn.Faction.IsPlayer || pawn.RaceProps.Animal) return;

            string name = pawn.Name?.ToStringShort ?? "?";
            string thingDef = item?.def?.defName ?? "?";
            int x = pawn.Position.x, z = pawn.Position.z;

            EventLogger.Emit(name, "carry", thingDef, x, z, thingDef, count > 0 ? count : item?.stackCount ?? 1);
        }
    }

    /// <summary>
    /// Logs when a colonist eats something (Ingest job completes on food).
    /// Patches the ingest toil to capture what was consumed.
    /// Always writes to the food ring buffer (even without set_event_log).
    /// </summary>
    [HarmonyPatch(typeof(Thing), nameof(Thing.Ingested))]
    public static class IngestPatch
    {
        static void Prefix(Thing __instance, Pawn ingester, float nutritionWanted)
        {
            if (ingester?.Faction == null || !ingester.Faction.IsPlayer || ingester.RaceProps.Animal) return;

            string name = ingester.Name?.ToStringShort ?? "?";
            string thingDef = __instance?.def?.defName ?? "?";
            int count = __instance?.stackCount ?? 1;
            int x = ingester.Position.x, z = ingester.Position.z;

            // Nutrition value of the food item
            float nutrition = 0f;
            try { nutrition = __instance.GetStatValue(StatDefOf.Nutrition); } catch { }

            // Pawn's food need level before ingestion
            float foodNeedBefore = -1f;
            try { foodNeedBefore = ingester.needs?.food?.CurLevelPercentage ?? -1f; } catch { }

            // Always write to food ring buffer
            try
            {
                var map = Find.CurrentMap;
                int tick = Find.TickManager?.TicksGame ?? 0;
                float hour = map != null ? GenLocalDate.HourFloat(map) : 0f;

                EventLogger.AddFoodEntry(D(
                    "tick",           (object)tick,
                    "hour",           (object)Math.Round(hour, 1),
                    "pawn",           name,
                    "food",           thingDef,
                    "nutrition",      (object)Math.Round(nutrition, 3),
                    "foodNeedBefore", (object)Math.Round(foodNeedBefore, 3)
                ));
            }
            catch { /* never crash the game */ }

            // Also write to file log if active
            if (EventLogger.Active)
            {
                EventLogger.Emit(name, "eat", thingDef, x, z, thingDef, count);
            }
        }
    }
}
