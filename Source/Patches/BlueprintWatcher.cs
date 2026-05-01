using System;
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// Periodic watcher that emits events when blueprints, frames, buildings,
    /// bills, or power state change. Called from MainThreadDispatcher every ~2s.
    /// </summary>
    public static class BlueprintWatcher
    {
        // Track previous state to detect transitions
        private static readonly Dictionary<string, string> _buildingState = new Dictionary<string, string>();
        // key = "defName@x,z", value = "blueprint" | "frame:45%" | "built" | "built:powered" | "built:unpowered"

        private static readonly Dictionary<string, int> _billCounts = new Dictionary<string, int>();
        // key = "defName@x,z", value = bill count

        public static void Check(Map map)
        {
            var currentBuildings = new HashSet<string>();

            // Scan all player buildings, blueprints, and frames
            foreach (var thing in map.listerThings.AllThings)
            {
                if (thing.Faction != Faction.OfPlayer) continue;

                string def = null;
                string state = null;
                int x = thing.Position.x, z = thing.Position.z;

                if (thing is Blueprint bp)
                {
                    def = bp.def.entityDefToBuild?.defName ?? bp.def.defName;
                    state = "blueprint";
                }
                else if (thing is Frame frame)
                {
                    def = frame.def.entityDefToBuild?.defName ?? frame.def.defName;
                    float pct = frame.WorkLeft > 0 && frame.def.entityDefToBuild is ThingDef td
                        ? 1f - (frame.WorkLeft / td.GetStatValueAbstract(StatDefOf.WorkToBuild))
                        : 0f;
                    int pctInt = (int)(Math.Max(0, Math.Min(1, pct)) * 100);
                    state = $"frame:{pctInt}%";
                }
                else if (thing is Building bldg && !(thing is Blueprint) && !(thing is Frame))
                {
                    def = bldg.def.defName;
                    // Check power state
                    var powerComp = bldg.TryGetComp<CompPowerTrader>();
                    if (powerComp != null)
                        state = powerComp.PowerOn ? "built:powered" : "built:unpowered";
                    else
                        state = "built";
                }

                if (def == null || state == null) continue;

                string key = $"{def}@{x},{z}";
                currentBuildings.Add(key);

                string prev;
                if (_buildingState.TryGetValue(key, out prev))
                {
                    if (prev != state)
                    {
                        // State changed — emit event
                        EventLogger.Emit("world", "build", $"{prev}->{state}", x, z, def);
                        _buildingState[key] = state;
                    }
                }
                else
                {
                    // New building/blueprint
                    EventLogger.Emit("world", "build", state, x, z, def);
                    _buildingState[key] = state;
                }

                // Track bills on workbenches
                if (thing is Building_WorkTable workbench)
                {
                    int billCount = workbench.BillStack?.Count ?? 0;
                    int prevBills;
                    if (_billCounts.TryGetValue(key, out prevBills))
                    {
                        if (billCount != prevBills)
                        {
                            string billNames = string.Join(",",
                                workbench.BillStack.Bills.Select(b => b.recipe?.defName ?? "?"));
                            EventLogger.Emit("world", "bills",
                                $"{prevBills}->{billCount}: {billNames}", x, z, def, billCount);
                            _billCounts[key] = billCount;
                        }
                    }
                    else if (billCount > 0)
                    {
                        string billNames = string.Join(",",
                            workbench.BillStack.Bills.Select(b => b.recipe?.defName ?? "?"));
                        EventLogger.Emit("world", "bills",
                            $"0->{billCount}: {billNames}", x, z, def, billCount);
                        _billCounts[key] = billCount;
                    }
                    else
                    {
                        _billCounts[key] = 0;
                    }
                }
            }

            // Detect destroyed/removed buildings
            foreach (var key in _buildingState.Keys.ToList())
            {
                if (!currentBuildings.Contains(key))
                {
                    var parts = key.Split('@');
                    string def = parts[0];
                    var pos = parts.Length > 1 ? parts[1].Split(',') : new[] { "0", "0" };
                    int x = int.Parse(pos[0]), z = int.Parse(pos[1]);
                    EventLogger.Emit("world", "build", $"{_buildingState[key]}->gone", x, z, def);
                    _buildingState.Remove(key);
                    _billCounts.Remove(key);
                }
            }
        }
    }
}
