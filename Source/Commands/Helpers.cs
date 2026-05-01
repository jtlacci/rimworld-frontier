using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using RimWorld;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// Shared utility methods for parameter extraction, pawn lookup, dialog introspection,
    /// and response building used by all command handlers.
    /// </summary>
    public static class Helpers
    {
        /// <summary>
        /// Returns the current map, falling back to the first available map.
        /// </summary>
        /// <returns>The active <see cref="Map"/>, or null if no maps are loaded.</returns>
        public static Map GetMap()
        {
            return Find.CurrentMap ?? Find.Maps.FirstOrDefault();
        }

        /// <summary>
        /// Finds a pawn by short name, checking free colonists first then all spawned pawns.
        /// </summary>
        /// <param name="name">Case-insensitive short name of the pawn.</param>
        /// <returns>The matching <see cref="Pawn"/>, or null if not found.</returns>
        public static Pawn FindPawn(string name)
        {
            var map = GetMap();
            if (map == null) return null;
            var pawn = map.mapPawns.FreeColonists.FirstOrDefault(p =>
                p.Name != null && p.Name.ToStringShort.Equals(name, StringComparison.OrdinalIgnoreCase));
            if (pawn != null) return pawn;
            return map.mapPawns.AllPawnsSpawned.FirstOrDefault(p =>
                p.Name != null && p.Name.ToStringShort.Equals(name, StringComparison.OrdinalIgnoreCase));
        }

        /// <summary>
        /// Finds a spawned animal by name, defName, or label (case-insensitive).
        /// </summary>
        /// <param name="name">Animal name, defName, or short label to match.</param>
        /// <returns>The matching animal <see cref="Pawn"/>, or null if not found.</returns>
        public static Pawn FindAnimal(string name)
        {
            var map = GetMap();
            if (map == null) return null;
            return map.mapPawns.AllPawnsSpawned.FirstOrDefault(p =>
                p.RaceProps.Animal &&
                ((p.Name != null && p.Name.ToStringShort.Equals(name, StringComparison.OrdinalIgnoreCase)) ||
                 p.def.defName.Equals(name, StringComparison.OrdinalIgnoreCase) ||
                 p.LabelShort.Equals(name, StringComparison.OrdinalIgnoreCase)));
        }

        /// <summary>
        /// Extracts a string value from the request dictionary.
        /// </summary>
        /// <param name="req">The request parameter dictionary.</param>
        /// <param name="key">The key to look up.</param>
        /// <returns>The string value, or null if the key is missing or null.</returns>
        public static string S(Dictionary<string, object> req, string key)
        {
            object v;
            if (req.TryGetValue(key, out v) && v != null) return v.ToString();
            return null;
        }

        /// <summary>
        /// Extracts an integer value from the request dictionary, handling int/long/double/string coercion.
        /// </summary>
        /// <param name="req">The request parameter dictionary.</param>
        /// <param name="key">The key to look up.</param>
        /// <param name="def">Default value if the key is missing (default 0).</param>
        /// <returns>The integer value, or <paramref name="def"/> if missing.</returns>
        public static int I(Dictionary<string, object> req, string key, int def = 0)
        {
            object v;
            if (req.TryGetValue(key, out v) && v != null)
            {
                if (v is int) return (int)v;
                if (v is long) return (int)(long)v;
                if (v is double) return (int)(double)v;
                int r;
                if (int.TryParse(v.ToString(), out r)) return r;
            }
            return def;
        }

        /// <summary>
        /// Extracts a boolean value from the request dictionary, handling bool and string "true"/"false".
        /// </summary>
        /// <param name="req">The request parameter dictionary.</param>
        /// <param name="key">The key to look up.</param>
        /// <param name="def">Default value if the key is missing (default false).</param>
        /// <returns>The boolean value, or <paramref name="def"/> if missing.</returns>
        public static bool B(Dictionary<string, object> req, string key, bool def = false)
        {
            object v;
            if (req.TryGetValue(key, out v) && v != null)
            {
                if (v is bool) return (bool)v;
                return v.ToString().ToLower() == "true";
            }
            return def;
        }

        /// <summary>
        /// Builds a response dictionary from alternating key-value pairs.
        /// </summary>
        /// <param name="kv">Alternating string keys and object values, e.g. D("ok", true, "x", 5).</param>
        /// <returns>A new dictionary populated with the key-value pairs.</returns>
        public static Dictionary<string, object> D(params object[] kv)
        {
            var d = new Dictionary<string, object>();
            for (int i = 0; i + 1 < kv.Length; i += 2)
                d[kv[i] as string] = kv[i + 1];
            return d;
        }

        /// <summary>
        /// Converts an <see cref="IntVec3"/> position to a dictionary with x and z keys.
        /// </summary>
        /// <param name="pos">The map position.</param>
        /// <returns>Dictionary with keys: x (int), z (int).</returns>
        public static Dictionary<string, object> PosDict(IntVec3 pos)
        {
            var d = new Dictionary<string, object>();
            d["x"] = pos.x;
            d["z"] = pos.z;
            return d;
        }

        /// <summary>
        /// Rounds a float to 2 decimal places for JSON-friendly output.
        /// </summary>
        /// <param name="val">The value to round.</param>
        /// <returns>The rounded float.</returns>
        public static float RoundF(float val)
        {
            return (float)Math.Round(val, 2);
        }

        /// <summary>
        /// Locates a workstation building by position (x, z) or by defName.
        /// </summary>
        /// <param name="req">Request with either x/z coordinates or a "building" defName string.</param>
        /// <returns>The <see cref="Building"/> at the given location or matching the defName.</returns>
        /// <exception cref="Exception">Thrown if no building is found or parameters are missing.</exception>
        public static Building FindWorkstation(Dictionary<string, object> req)
        {
            int x = I(req, "x", -1);
            int z = I(req, "z", I(req, "y", -1));
            string bld = S(req, "building");

            var map = GetMap();
            if (map == null) throw new Exception("No active map");

            if (x >= 0 && z >= 0)
            {
                var pos = new IntVec3(x, 0, z);
                var building = pos.GetFirstBuilding(map);
                if (building == null) throw new Exception("No building at (" + x + "," + z + ")");
                return building;
            }
            else if (bld != null)
            {
                foreach (var b in map.listerBuildings.allBuildingsColonist)
                {
                    if (b.def.defName.Equals(bld, StringComparison.OrdinalIgnoreCase))
                        return b;
                }
                throw new Exception("No " + bld + " found");
            }
            throw new Exception("Need: x,z or building (defName)");
        }

        // Dialog helpers

        /// <summary>
        /// Retrieves the current dialog node from a Dialog_NodeTree via reflection.
        /// </summary>
        /// <param name="dnt">The dialog tree window.</param>
        /// <returns>The current <see cref="DiaNode"/>, or null if inaccessible.</returns>
        public static DiaNode GetCurNode(Dialog_NodeTree dnt)
        {
            var field = typeof(Dialog_NodeTree).GetField("curNode",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (field != null) return field.GetValue(dnt) as DiaNode;
            return null;
        }

        /// <summary>
        /// Finds the topmost Dialog_NodeTree in the window stack.
        /// </summary>
        /// <returns>The first <see cref="Dialog_NodeTree"/> found, or null if none open.</returns>
        public static Dialog_NodeTree FindTopDialog()
        {
            foreach (var window in Find.WindowStack.Windows)
            {
                var dnt = window as Dialog_NodeTree;
                if (dnt != null) return dnt;
            }
            return null;
        }

        /// <summary>
        /// Extracts the title string from a Dialog_NodeTree via reflection.
        /// </summary>
        /// <param name="dnt">The dialog tree window.</param>
        /// <returns>The dialog title, or empty string if unavailable.</returns>
        public static string GetDialogTitle(Dialog_NodeTree dnt)
        {
            var titleField = typeof(Dialog_NodeTree).GetField("title",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (titleField != null)
            {
                var title = titleField.GetValue(dnt) as string;
                if (title != null) return title;
            }
            return "";
        }

        /// <summary>
        /// Enumerates all dialog options from the current node of a Dialog_NodeTree.
        /// </summary>
        /// <param name="dnt">The dialog tree window.</param>
        /// <returns>List of option dictionaries, each with: index (int), text (string), disabled (bool),
        /// disabled_reason (string, if disabled), has_link (bool), resolves (bool).</returns>
        public static List<object> GetDialogOptions(Dialog_NodeTree dnt)
        {
            var options = new List<object>();
            var node = GetCurNode(dnt);
            if (node != null && node.options != null)
            {
                for (int i = 0; i < node.options.Count; i++)
                {
                    var opt = node.options[i];
                    var od = D();
                    od["index"] = i;

                    var textField = typeof(DiaOption).GetField("text",
                        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    if (textField != null)
                    {
                        var t = textField.GetValue(opt) as string;
                        od["text"] = t ?? "???";
                    }

                    od["disabled"] = opt.disabled;
                    if (opt.disabled && opt.disabledReason != null)
                        od["disabled_reason"] = opt.disabledReason;
                    od["has_link"] = opt.link != null;
                    od["resolves"] = opt.resolveTree;

                    options.Add(od);
                }
            }
            return options;
        }
    }
}
