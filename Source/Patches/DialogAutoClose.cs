using System.Linq;
using HarmonyLib;
using RimWorld;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// Harmony patch on WindowStack.Add — automatically handles known blocking dialogs
    /// so the agent doesn't need to poll for them.
    /// </summary>
    [HarmonyPatch(typeof(WindowStack), nameof(WindowStack.Add))]
    public static class DialogAutoClose
    {
        // Track auto-closed dialogs so the agent can read what happened
        public static string LastAutoClosed;
        public static int LastAutoClosedTick;

        static void Postfix(Window window)
        {
            if (window == null) return;

            var typeName = window.GetType().Name;

            // --- Colony/faction naming dialogs ---
            if (window is Dialog_NamePlayerSettlement settDialog)
            {
                var settlement = Find.WorldObjects.Settlements
                    .FirstOrDefault(s => s.Faction == Faction.OfPlayer);
                if (settlement != null && string.IsNullOrEmpty(settlement.Name))
                    settlement.Name = "Colony";
                settDialog.Close(false);
                Record("Dialog_NamePlayerSettlement");
                return;
            }

            if (window is Dialog_NamePlayerFactionAndSettlement factionDialog)
            {
                Faction.OfPlayer.Name = "Colony";
                var settlement = Find.WorldObjects.Settlements
                    .FirstOrDefault(s => s.Faction == Faction.OfPlayer);
                if (settlement != null)
                    settlement.Name = "Colony";
                factionDialog.Close(false);
                Record("Dialog_NamePlayerFactionAndSettlement");
                return;
            }

            // --- Research complete popup ---
            if (typeName == "Dialog_MessageBox" || typeName == "Dialog_ResearchFinished")
            {
                // These are informational — safe to auto-close
                window.Close(false);
                Record(typeName);
                return;
            }

            // --- Letter stack popups (raid warnings, events, etc.) ---
            // Don't auto-close these — the agent should read and respond to them
            // But log that they appeared
            if (typeName.StartsWith("Dialog_") && window is Dialog_NodeTree)
            {
                Log.Message($"[CarolineConsole] Dialog opened (not auto-closed): {typeName}");
            }
        }

        private static void Record(string typeName)
        {
            LastAutoClosed = typeName;
            LastAutoClosedTick = Find.TickManager?.TicksGame ?? 0;
            Log.Message($"[CarolineConsole] Auto-closed dialog: {typeName}");
        }
    }
}
