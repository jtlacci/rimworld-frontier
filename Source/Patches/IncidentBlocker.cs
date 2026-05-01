using HarmonyLib;
using RimWorld;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// When WriteCommands.IncidentsDisabled is true, block all storyteller incidents.
    /// This gives consistent test runs without random raids, events, etc.
    /// </summary>
    [HarmonyPatch(typeof(Storyteller), nameof(Storyteller.MakeIncidentsForInterval))]
    public static class IncidentBlocker
    {
        static bool Prefix()
        {
            return !WriteCommands.IncidentsDisabled;
        }
    }

    /// <summary>
    /// When WriteCommands.IncidentsDisabled is true, block wild animal spawning.
    /// Patches both the tick method and the actual spawn method to catch all paths.
    /// </summary>
    [HarmonyPatch(typeof(WildAnimalSpawner), nameof(WildAnimalSpawner.WildAnimalSpawnerTick))]
    public static class WildAnimalSpawnBlocker
    {
        static bool Prefix()
        {
            return !WriteCommands.IncidentsDisabled;
        }
    }

    /// <summary>
    /// Belt-and-suspenders: also block the actual spawn call in case WildAnimalSpawnerTick
    /// isn't the only caller, or the method name changed across RimWorld versions.
    /// </summary>
    [HarmonyPatch(typeof(WildAnimalSpawner), "SpawnRandomWildAnimalAt")]
    public static class WildAnimalSpawnAtBlocker
    {
        static bool Prefix()
        {
            return !WriteCommands.IncidentsDisabled;
        }
    }

    /// <summary>
    /// Block GenSpawn for wild animal pawns when incidents are disabled AND bridge is connected.
    /// Uses HarmonyTargetMethods to patch ALL GenSpawn.Spawn overloads that take a Thing parameter.
    /// </summary>
    public static class AnimalSpawnBlocker
    {
        [HarmonyTargetMethods]
        static System.Collections.Generic.IEnumerable<System.Reflection.MethodBase> TargetMethods()
        {
            foreach (var m in typeof(GenSpawn).GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static))
            {
                if (m.Name != "Spawn") continue;
                var p = m.GetParameters();
                if (p.Length > 0 && p[0].ParameterType == typeof(Thing))
                    yield return m;
            }
        }

        static bool Prefix(Thing newThing)
        {
            if (!WriteCommands.IncidentsDisabled) return true;
            if (WriteCommands.AllowNextAnimalSpawn) return true;  // bypass for spawn_animals command
            if (newThing is Pawn pawn && pawn.RaceProps.Animal && pawn.Faction == null)
                return false;
            return true;
        }
    }
}
