// References required:
//   Assembly-CSharp.dll        (RimWorld game assembly)
//   UnityEngine.CoreModule.dll (Unity core)
//   0Harmony.dll               (Harmony 2.x — bundled with RimWorld)
//
// These are found in:
//   <RimWorld>/RimWorldWin64_Data/Managed/
//   <RimWorld>/Mods/Core/Current/Assemblies/ (for some versions)

using System.Reflection;
using HarmonyLib;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// Mod entry point. Patches RimWorld via Harmony and starts the TCP bridge.
    /// </summary>
    public class CarolineConsoleMod : Mod
    {
        public static Harmony HarmonyInstance;

        public CarolineConsoleMod(ModContentPack content) : base(content)
        {
            HarmonyInstance = new Harmony("caroline.console");
            HarmonyInstance.PatchAll(Assembly.GetExecutingAssembly());
            Log.Message("[CarolineConsole] Harmony patches applied.");
        }

        public override string SettingsCategory() => "CarolineConsole";
    }

    /// <summary>
    /// Starts the TCP GameBridge when the game finishes loading.
    /// </summary>
    [StaticConstructorOnStartup]
    public static class Startup
    {
        static Startup()
        {
            GameBridge.Instance.Start();
            Log.Message("[CarolineConsole] TCP bridge started on port 9900.");
        }
    }
}
