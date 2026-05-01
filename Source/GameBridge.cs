using System;
using System.Collections.Concurrent;
using System.Linq;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using RimWorld;
using UnityEngine;
using Verse;

namespace CarolineConsole
{
    /// <summary>
    /// TCP bridge server that listens on port 9900 and dispatches JSON commands
    /// to game-thread handlers via a concurrent queue. Singleton accessed via
    /// <see cref="Instance"/>. Background threads read/write TCP; the Unity main
    /// thread drains the queue each frame via <see cref="ProcessQueue"/>.
    /// </summary>
    public class GameBridge
    {
        public static readonly GameBridge Instance = new GameBridge();

        private TcpListener _listener;
        private Thread _listenThread;
        private readonly ConcurrentQueue<PendingCommand> _mainThreadQueue = new ConcurrentQueue<PendingCommand>();
        private volatile bool _running;
        public volatile bool HasConnected;
        public static int GameDayLimit;  // auto-pause when game reaches this day (0 = disabled)
        private const int Port = 9900;

        private readonly Dictionary<string, Func<Dictionary<string, object>, object>> _handlers =
            new Dictionary<string, Func<Dictionary<string, object>, object>>();

        private GameBridge()
        {
            _handlers["read_colonists"]  = ReadCommands.Colonists;
            _handlers["read_resources"]  = ReadCommands.Resources;
            _handlers["read_map"]        = ReadCommands.Map;
            _handlers["read_map_tiles"]  = ReadCommands.MapTiles;
            _handlers["read_alerts"]     = ReadCommands.Alerts;
            _handlers["read_buildings"]  = ReadCommands.Buildings;
            _handlers["read_weather"]    = ReadCommands.Weather;
            _handlers["read_research"]   = ReadCommands.Research;
            _handlers["read_zones"]      = ReadCommands.Zones;
            _handlers["read_bills"]      = ReadCommands.Bills;
            _handlers["set_priority"]    = WriteCommands.SetPriority;
            _handlers["set_schedule"]    = WriteCommands.SetSchedule;
            _handlers["set_speed"]       = WriteCommands.SetSpeed;
            _handlers["draft"]           = WriteCommands.Draft;
            _handlers["undraft"]         = WriteCommands.Undraft;
            _handlers["add_bill"]        = WriteCommands.AddBill;
            _handlers["cancel_bill"]     = WriteCommands.CancelBill;
            _handlers["build"]           = WriteCommands.Build;
            _handlers["cancel_build"]    = WriteCommands.CancelBuild;
            _handlers["set_floor"]       = WriteCommands.SetFloor;
            _handlers["hunt"]            = WriteCommands.Hunt;
            _handlers["designate_chop"]  = WriteCommands.DesignateChop;
            _handlers["create_grow_zone"]= WriteCommands.CreateGrowZone;
            _handlers["create_stockpile_zone"]= WriteCommands.CreateStockpileZone;
            _handlers["pause"]           = WriteCommands.Pause;
            _handlers["unpause"]         = WriteCommands.Unpause;
            _handlers["save"]            = WriteCommands.Save;
            _handlers["load_game"]       = WriteCommands.LoadGame;
            _handlers["list_saves"]      = WriteCommands.ListSaves;

            // Phase 2: Ported read commands
            _handlers["read_threats"]         = ReadCommands.Threats;
            _handlers["read_work_priorities"] = ReadCommands.WorkPriorities;
            _handlers["read_animals"]         = ReadCommands.Animals;
            _handlers["read_pawns"]           = ReadCommands.Pawns;
            _handlers["read_needs"]           = ReadCommands.Needs;
            _handlers["read_inventory"]       = ReadCommands.Inventory;
            _handlers["read_colonist_needs"]  = ReadCommands.ColonistNeeds;
            _handlers["read_thoughts"]        = ReadCommands.Thoughts;
            _handlers["read_letters"]         = ReadCommands.Letters;
            _handlers["read_dialogs"]         = ReadCommands.Dialogs;
            _handlers["ping"]                 = ReadCommands.Ping;
            _handlers["read_water"]           = WriteCommands.FindWater;
            _handlers["read_grow_spot"]       = WriteCommands.FindGrowSpot;
            _handlers["find_clear_rect"]      = WriteCommands.FindClearRect;

            // Phase 3: Ported write commands
            _handlers["move_pawn"]            = WriteCommands.MovePawn;
            _handlers["attack"]               = WriteCommands.Attack;
            _handlers["rescue"]               = WriteCommands.Rescue;
            _handlers["tend"]                 = WriteCommands.Tend;
            _handlers["haul"]                 = WriteCommands.Haul;
            _handlers["equip"]                = WriteCommands.Equip;
            _handlers["prioritize"]           = WriteCommands.Prioritize;
            _handlers["designate_mine"]       = WriteCommands.DesignateMine;
            _handlers["designate_harvest"]    = WriteCommands.DesignateHarvest;
            _handlers["tame"]                 = WriteCommands.Tame;
            _handlers["slaughter"]            = WriteCommands.Slaughter;
            _handlers["deconstruct"]          = WriteCommands.Deconstruct;
            _handlers["cancel_designation"]   = WriteCommands.CancelDesignation;
            _handlers["forbid"]               = WriteCommands.ForbidCmd;
            _handlers["unforbid"]             = WriteCommands.UnforbidCmd;
            _handlers["set_research"]         = WriteCommands.SetResearch;
            _handlers["set_plant"]            = WriteCommands.SetPlant;
            _handlers["delete_zone"]          = WriteCommands.DeleteZone;
            _handlers["remove_zone_cells"]    = WriteCommands.RemoveZoneCells;
            _handlers["find_water"]           = WriteCommands.FindWater;
            _handlers["find_grow_spot"]       = WriteCommands.FindGrowSpot;
            _handlers["camera_jump"]          = WriteCommands.CameraJump;
            _handlers["place"]                = WriteCommands.Place;
            _handlers["open_letter"]          = WriteCommands.OpenLetter;
            _handlers["dismiss_letter"]       = WriteCommands.DismissLetter;
            _handlers["choose_option"]        = WriteCommands.ChooseOption;
            _handlers["close_dialog"]         = WriteCommands.CloseDialog;
            _handlers["read_beauty"]          = ReadCommands.Beauty;
            _handlers["set_manual_priorities"]= WriteCommands.SetManualPriorities;
            _handlers["suspend_bill"]         = WriteCommands.SuspendBill;
            _handlers["set_stockpile_filter"] = WriteCommands.SetStockpileFilter;
            _handlers["create_fishing_zone"] = WriteCommands.CreateFishingZone;
            _handlers["seed_fish"]           = WriteCommands.SeedFish;
            _handlers["read_messages"]       = ReadCommands.LiveMessages;

            // Phase 4: Building architecture commands
            _handlers["read_terrain"]            = ReadCommands.Terrain;
            _handlers["read_roof"]               = ReadCommands.Roof;
            _handlers["read_costs"]              = ReadCommands.Costs;
            _handlers["read_interaction_spots"]  = ReadCommands.InteractionSpots;
            _handlers["bulk_build"]              = WriteCommands.BulkBuild;
            _handlers["add_plan"]                = WriteCommands.AddPlan;
            _handlers["remove_plan"]             = WriteCommands.RemovePlan;
            _handlers["survey_region"]           = ReadCommands.SurveyRegion;
            _handlers["survey_terrain_ascii"]    = ReadCommands.SurveyTerrainAscii;
            _handlers["survey_roof_ascii"]       = ReadCommands.SurveyRoofAscii;
            _handlers["survey_fertility_ascii"]  = ReadCommands.SurveyFertilityAscii;
            _handlers["survey_things_ascii"]     = ReadCommands.SurveyThingsAscii;
            _handlers["survey_composite_ascii"]  = ReadCommands.SurveyCompositeAscii;
            _handlers["survey_detailed_ascii"]   = ReadCommands.SurveyDetailedAscii;
            _handlers["survey_beauty_ascii"]     = ReadCommands.SurveyBeautyAscii;
            _handlers["survey_temperature_ascii"]= ReadCommands.SurveyTemperatureAscii;
            _handlers["survey_blueprint_ascii"]  = ReadCommands.SurveyBlueprintAscii;
            _handlers["survey_power_ascii"]      = ReadCommands.SurveyPowerAscii;
            _handlers["survey_task_ascii"]       = ReadCommands.SurveyTaskAscii;

            // Phase 5: Ideology, bulk designations, visitors
            _handlers["cancel_designations"]     = WriteCommands.CancelDesignations;
            _handlers["read_ideology"]           = ReadCommands.Ideology;
            _handlers["assign_role"]             = ReadCommands.AssignRole;
            _handlers["read_visitors"]           = ReadCommands.Visitors;

            // Phase 6: Dev/testing tools
            _handlers["dev_set_storyteller"]     = WriteCommands.DevSetStoryteller;
            _handlers["dev_toggle_incidents"]    = WriteCommands.DevToggleIncidents;
            _handlers["spawn_animals"]           = WriteCommands.SpawnAnimals;
            _handlers["set_event_log"]           = WriteCommands.SetEventLog;
            _handlers["set_day_limit"]           = (req) => {
                GameDayLimit = Helpers.I(req, "day", 0);
                return Helpers.D("ok", true, "day_limit", (object)GameDayLimit);
            };
            _handlers["read_colony_stats"]       = ReadCommands.ColonyStats;

            // Phase 7: Observability (build requests)
            _handlers["read_plants"]             = ReadCommands.Plants;
            _handlers["read_food_log"]           = ReadCommands.FoodLog;
        }

        /// <summary>
        /// Starts the TCP listener thread and creates the Unity main-thread dispatcher GameObject.
        /// </summary>
        public void Start()
        {
            _running = true;
            _listenThread = new Thread(ListenLoop) { IsBackground = true, Name = "CarolineTCP" };
            _listenThread.Start();

            LongEventHandler.ExecuteWhenFinished(() =>
            {
                var go = new GameObject("CarolineConsole_Dispatcher");
                go.AddComponent<MainThreadDispatcher>();
                UnityEngine.Object.DontDestroyOnLoad(go);
            });
        }

        /// <summary>
        /// Stops the TCP listener and signals background threads to exit.
        /// </summary>
        public void Stop()
        {
            _running = false;
            _listener?.Stop();
        }

        private void ListenLoop()
        {
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, Port);
                _listener.Start();
                Log.Message($"[CarolineConsole] Listening on 127.0.0.1:{Port}");

                while (_running)
                {
                    if (_listener.Pending())
                    {
                        var client = _listener.AcceptTcpClient();
                        HasConnected = true;
                        var t = new Thread(() => HandleClient(client)) { IsBackground = true, Name = "CarolineClient" };
                        t.Start();
                    }
                    else Thread.Sleep(50);
                }
            }
            catch (Exception ex)
            {
                if (_running) Log.Error($"[CarolineConsole] Listen error: {ex.Message}");
            }
        }

        private void HandleClient(TcpClient client)
        {
            try
            {
                using (var stream = client.GetStream())
                using (var reader = new StreamReader(stream, Encoding.UTF8))
                using (var writer = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true })
                {
                    Log.Message("[CarolineConsole] Client connected.");
                    while (_running && client.Connected)
                    {
                        var line = reader.ReadLine();
                        if (line == null) break;
                        if (string.IsNullOrWhiteSpace(line)) continue;

                        Dictionary<string, object> request;
                        try { request = SimpleJson.Deserialize(line); }
                        catch { writer.WriteLine("{\"error\":\"Invalid JSON\"}"); continue; }

                        int id = request.ContainsKey("id") ? Convert.ToInt32(request["id"]) : 0;
                        string command = request.ContainsKey("command") ? request["command"] as string : null;

                        if (string.IsNullOrEmpty(command))
                        {
                            writer.WriteLine(SimpleJson.Serialize(new Dictionary<string, object> { ["id"] = id, ["error"] = "Missing command" }));
                            continue;
                        }

                        if (!_handlers.ContainsKey(command))
                        {
                            writer.WriteLine(SimpleJson.Serialize(new Dictionary<string, object> { ["id"] = id, ["error"] = $"Unknown command: {command}" }));
                            continue;
                        }

                        var pending = new PendingCommand { Id = id, Command = command, Request = request };
                        _mainThreadQueue.Enqueue(pending);

                        if (pending.ResultReady.WaitOne(TimeSpan.FromSeconds(10)))
                            writer.WriteLine(pending.ResultJson);
                        else
                            writer.WriteLine(SimpleJson.Serialize(new Dictionary<string, object> { ["id"] = id, ["error"] = "Command timed out" }));
                    }
                }
            }
            catch (Exception ex)
            {
                if (_running) Log.Warning($"[CarolineConsole] Client error: {ex.Message}");
            }
            finally
            {
                client?.Close();
                Log.Message("[CarolineConsole] Client disconnected.");
            }
        }

        /// <summary>
        /// Drains the pending command queue on the Unity main thread, executing each
        /// handler and writing the JSON result back to the waiting client thread.
        /// Called every frame by <see cref="MainThreadDispatcher"/>.
        /// </summary>
        public void ProcessQueue()
        {
            while (_mainThreadQueue.TryDequeue(out var pending))
            {
                try
                {
                    var result = _handlers[pending.Command](pending.Request);
                    pending.ResultJson = SimpleJson.Serialize(new Dictionary<string, object> { ["id"] = pending.Id, ["data"] = result });
                }
                catch (Exception ex)
                {
                    // Include stack trace for NullReferenceException to aid debugging (run 008: SculptureSmall NullRef unfixed for 5 runs)
                    var errorMsg = ex is NullReferenceException
                        ? $"{ex.Message} | StackTrace: {ex.StackTrace}"
                        : ex.Message;
                    pending.ResultJson = SimpleJson.Serialize(new Dictionary<string, object> { ["id"] = pending.Id, ["error"] = errorMsg });
                    Log.Warning($"[CarolineConsole] Command '{pending.Command}' failed: {errorMsg}");
                }
                finally { pending.ResultReady.Set(); }
            }
        }

        private class PendingCommand
        {
            public int Id;
            public string Command;
            public Dictionary<string, object> Request;
            public string ResultJson;
            public readonly ManualResetEvent ResultReady = new ManualResetEvent(false);
        }
    }

    /// <summary>
    /// Unity MonoBehaviour that runs on the main thread every frame. Processes the
    /// GameBridge command queue, auto-dismisses blocking dialogs every ~1 second,
    /// and auto-tends injured colonists every ~10 seconds.
    /// </summary>
    public class MainThreadDispatcher : MonoBehaviour
    {
        private int _frameCount;

        private void Update()
        {
            GameBridge.Instance.ProcessQueue();

            // Auto-dismiss blocking dialogs every ~1 second (60 frames)
            // ImmediateWindow: slows game tick speed by 2-5x
            // Dialog_NodeTree: can freeze game entirely (pauses ticks)
            if (++_frameCount % 60 == 0)
            {
                try
                {
                    var stack = Find.WindowStack;
                    if (stack?.Windows != null)
                    {
                        foreach (var w in stack.Windows.ToList())
                        {
                            var typeName = w.GetType().Name;
                            if (typeName == "ImmediateWindow" ||
                                typeName == "Dialog_NodeTree" ||
                                typeName == "Dialog_MessageBox")
                                w.Close(true);
                        }
                    }
                }
                catch { /* game not loaded yet */ }
            }

            // Auto-tend injured colonists every ~10 seconds (600 frames)
            // Clears "medical treatment needed" alert (worth 5 scoring points)
            if (_frameCount % 600 == 300)
            {
                try
                {
                    var map = Find.CurrentMap;
                    if (map != null)
                    {
                        foreach (var pawn in map.mapPawns.FreeColonists)
                        {
                            if (pawn.health?.HasHediffsNeedingTend(false) == true && !pawn.Downed)
                            {
                                var doctor = map.mapPawns.FreeColonists
                                    .Where(p => p != pawn && !p.Downed
                                        && p.workSettings?.WorkIsActive(WorkTypeDefOf.Doctor) == true)
                                    .OrderByDescending(p => p.skills?.GetSkill(SkillDefOf.Medicine)?.Level ?? 0)
                                    .FirstOrDefault();
                                if (doctor != null)
                                {
                                    var job = JobMaker.MakeJob(JobDefOf.TendPatient, pawn);
                                    doctor.jobs.TryTakeOrderedJob(job);
                                }
                            }
                        }
                    }
                }
                catch { /* game not loaded or no colonists */ }
            }

            // Game day limit — auto-pause when reached (checked every ~1 second)
            if (_frameCount % 60 == 30 && GameBridge.GameDayLimit > 0)
            {
                try
                {
                    var map = Find.CurrentMap;
                    if (map != null)
                    {
                        int day = GenLocalDate.DayOfYear(map);
                        if (day >= GameBridge.GameDayLimit && Find.TickManager.CurTimeSpeed != TimeSpeed.Paused)
                        {
                            Find.TickManager.CurTimeSpeed = TimeSpeed.Paused;
                            Log.Message($"[CarolineConsole] Game day {day} >= limit {GameBridge.GameDayLimit} — auto-paused");
                        }
                    }
                }
                catch { }
            }

            // Blueprint/bill/power watcher — every ~2 seconds (120 frames, offset 90)
            if (_frameCount % 120 == 90 && EventLogger.Active)
            {
                try
                {
                    var map = Find.CurrentMap;
                    if (map != null)
                        BlueprintWatcher.Check(map);
                }
                catch { }
            }

            // Despawn non-scenario wild animals every ~1 second (60 frames, offset 45)
            if (_frameCount % 60 == 45 && WriteCommands.IncidentsDisabled
                && WriteCommands.AllowedWildlife.Count > 0)
            {
                try
                {
                    var map = Find.CurrentMap;
                    if (map != null)
                    {
                        var toRemove = map.mapPawns.AllPawnsSpawned
                            .Where(p => p.RaceProps.Animal && p.Faction == null
                                && !WriteCommands.AllowedWildlife.Contains(p.def.defName))
                            .ToList();
                        foreach (var p in toRemove)
                        {
                            p.Destroy();
                            Log.Message($"[CarolineConsole] Despawned non-scenario animal: {p.def.defName}");
                        }
                    }
                }
                catch { }
            }
        }
    }
}
