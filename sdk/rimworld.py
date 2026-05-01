"""Python SDK for the RimWorld TCP Bridge mod (port 9900)."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from typing import Any

from rtypes import (  # noqa: E402  — sdk/rtypes.py, on sys.path via sdk/
    AddBillResponse, AddCookingBillsResult, AddPlanResponse, AlertsResponse,
    AnimalsResponse, AsciiSurveyResponse, AssignRoleResponse, AttackResponse,
    BeautyResponse, BillsResponse, BuildBarracksResult, BuildHallwayResult, FoodLogResponse,
    BuildResponse, BuildRoomGridResult, BuildRoomResult, BuildStorageRoomResult,
    BuildingsResponse, BulkBuildResponse, CameraJumpResponse,
    CancelBillResponse, CancelBuildResponse, CancelDesignationResponse,
    CancelDesignationsResponse, CheckBuildableResult, ChooseOptionResponse,
    ChopResponse, ClearRectResponse, CloseDialogResponse, ColonistNeedsResponse,
    ColonistsResponse, ColonyHealthCheckResult, ColonyStatsResponse,
    CostCheckResult, CostsResponse, Day1SetupResult, DeconstructResponse,
    DeleteZoneResponse, DetailedAsciiSurveyResponse, DialogsResponse,
    DismissLetterResponse, DraftResponse, EquipResponse, FishingZoneResponse,
    ForbidResponse, GrowSpotResponse, GrowZoneResponse, HarvestResponse,
    HaulResponse, HuntAllWildlifeResult, HuntResponse, IdeologyResponse,
    InteractionSpotsResponse, InventoryResponse, LettersResponse,
    ListSavesResponse, LoadGameResponse, MapInfoResponse, MessagesResponse,
    MineResponse, MonitoredSleepResult, MovePawnResponse, NeedsResponse,
    OkResponse, OpenLetterResponse, PauseResponse, PawnsResponse,
    PingResponse, PlaceResponse, PrioritizeResponse, RemovePlanResponse,
    RemoveZoneCellsResponse, RescueResponse, ResearchResponse,
    PlantsResponse, ResourcesResponse, RoofCell, RoofDict,
    SaveResponse, ScanDecodedResponse, ScanMergedResponse,
    SecureFoodStockpileResult, SetFloorResponse, SetManualPrioritiesResponse,
    SetPlantResponse, SetPriorityResponse, SetResearchResponse,
    SetScheduleResponse, SetSpeedResponse, SetStockpileFilterResponse,
    SetStorytellerResponse, SetupCookingResult, SetupDiningResult,
    SetupProductionResult, SetupRecreationResult, SetupZonesResult,
    SlaughterResponse, SpawnAnimalsResponse, StockpileResponse,
    SurveyRegionResponse, SuspendBillResponse, TameResponse, TendResponse,
    TerrainCell, TerrainDict, ThoughtsResponse, ThreatsResponse,
    ToggleIncidentsResponse, UnpauseResponse, VerifyRoomResult,
    VisitorsResponse, WaitForConstructionResult, WaterResponse,
    WeatherResponse, WorkPrioritiesResponse, ZonesResponse,
)


class RimError(Exception):
    """Raised when the game returns an error response."""


class _Cache:
    """Simple TTL cache keyed by arbitrary strings."""

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str, ttl: float) -> Any | None:
        entry = self._store.get(key)
        if entry and time.monotonic() - entry[1] < ttl:
            return entry[0]
        return None

    def put(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic())

    def invalidate(self, *prefixes: str) -> None:
        """Drop entries whose key starts with any of *prefixes*.
        Call with no args to drop everything.
        """
        if not prefixes:
            self._store.clear()
        else:
            self._store = {
                k: v for k, v in self._store.items()
                if not any(k.startswith(p) for p in prefixes)
            }


class RimClient:
    """Persistent TCP connection to the RimWorld bridge.

    Usage::

        with RimClient() as r:
            print(r.colonists())
            r.build_room(120, 134, 128, 140, doors=[(124, 134)])

    Read queries are cached with a short TTL (default 2 s) so repeated
    calls within the same operation (e.g. collision-check then build) reuse
    data.  Any write command automatically invalidates relevant caches.
    """

    # seconds before cached reads are re-fetched
    CACHE_TTL = 2.0

    def __init__(self, host: str = "127.0.0.1", port: int = 9900, timeout: int = 30,
                 log_path: str | None = None) -> None:
        self._id: int = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((host, port))
        self._buf: bytes = b""
        self._cache = _Cache()
        self._log_file: Any = None
        self._batch_id: int = 0
        _log_path = log_path or os.environ.get("RIM_SDK_LOG")
        if _log_path:
            try:
                self._log_file = open(_log_path, "a")
            except OSError:
                pass

    # ── core ──────────────────────────────────────────────────────────

    def send(self, command: str, **kwargs: Any) -> Any:
        """Send a command and return the parsed response ``data`` dict.

        Raises :class:`RimError` on game-side errors.
        """
        self._id += 1
        msg_id = self._id
        msg = {"id": msg_id, "command": command, **kwargs}
        t0 = time.monotonic()
        self._sock.sendall(json.dumps(msg).encode() + b"\n")
        resp = self._recv()
        ms = (time.monotonic() - t0) * 1000
        if "error" in resp:
            self._log_call(msg_id, command, kwargs, ok=False, ms=ms, error=resp["error"])
            raise RimError(resp["error"])
        self._log_call(msg_id, command, kwargs, ok=True, ms=ms)
        return resp.get("data")

    def _send_cached(self, command: str, **kwargs: Any) -> Any:
        """Like :meth:`send` but caches the result for ``CACHE_TTL`` seconds."""
        key = command + json.dumps(kwargs, sort_keys=True)
        hit = self._cache.get(key, self.CACHE_TTL)
        if hit is not None:
            self._log_call(0, command, kwargs, ok=True, ms=0, cached=True)
            return hit
        result = self.send(command, **kwargs)
        self._cache.put(key, result)
        return result

    def send_batch(self, commands: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """Send multiple commands, return list of results.

        *commands* is a list of ``(command_name, kwargs_dict)`` tuples.
        Pipelines all writes then reads all responses — much faster than
        calling :meth:`send` in a loop for bulk operations like wall placement.
        Raises :class:`RimError` on the first error encountered.
        """
        if not commands:
            return []
        self._batch_id += 1
        bid = self._batch_id
        t0 = time.monotonic()
        buf = bytearray()
        ids = []
        for cmd, kw in commands:
            self._id += 1
            ids.append(self._id)
            msg = {"id": self._id, "command": cmd, **kw}
            buf += json.dumps(msg).encode() + b"\n"
        self._sock.sendall(buf)
        results = []
        for i, _ in enumerate(ids):
            resp = self._recv()
            ms = (time.monotonic() - t0) * 1000
            cmd, kw = commands[i]
            if "error" in resp:
                self._log_call(ids[i], cmd, kw, ok=False, ms=ms, error=resp["error"], batch_id=bid)
                raise RimError(resp["error"])
            self._log_call(ids[i], cmd, kw, ok=True, ms=ms, batch_id=bid)
            results.append(resp.get("data"))
        return results

    def send_batch_lenient(self, commands: list[tuple[str, dict[str, Any]]]) -> tuple[list[dict[str, Any]], int]:
        """Like :meth:`send_batch` but skips errors instead of raising.

        Returns ``(successes, error_count)``.
        """
        if not commands:
            return [], 0
        self._batch_id += 1
        bid = self._batch_id
        t0 = time.monotonic()
        buf = bytearray()
        ids = []
        for cmd, kw in commands:
            self._id += 1
            ids.append(self._id)
            msg = {"id": self._id, "command": cmd, **kw}
            buf += json.dumps(msg).encode() + b"\n"
        self._sock.sendall(buf)
        results = []
        errors = 0
        for i, _ in enumerate(ids):
            resp = self._recv()
            ms = (time.monotonic() - t0) * 1000
            cmd, kw = commands[i]
            if "error" in resp:
                self._log_call(ids[i], cmd, kw, ok=False, ms=ms, error=resp["error"], batch_id=bid)
                errors += 1
            else:
                self._log_call(ids[i], cmd, kw, ok=True, ms=ms, batch_id=bid)
                results.append(resp.get("data"))
        return results, errors

    def close(self) -> None:
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None
        try:
            self._sock.close()
        except OSError:
            pass

    def _log_call(self, cmd_id: int, command: str, args: dict[str, Any],
                  ok: bool, ms: float, error: str | None = None,
                  cached: bool = False, batch_id: int | None = None) -> None:
        if self._log_file is None:
            return
        entry: dict[str, Any] = {
            "ts": time.time(), "id": cmd_id, "cmd": command,
            "args": args, "ok": ok, "ms": round(ms, 1),
        }
        if cached:
            entry["cached"] = True
        if batch_id is not None:
            entry["batch_id"] = batch_id
        if error is not None:
            entry["error"] = error
        try:
            self._log_file.write(json.dumps(entry) + "\n")
            self._log_file.flush()
        except Exception:
            pass

    def restart_game(self, save: str | None = None, timeout: int = 120) -> RimClient:
        """Kill RimWorld, relaunch via Steam, reconnect, and optionally load a save.

        Args:
            save: Save file name (without .rws) to load after restart.
                  If None, stays at the main menu.
            timeout: Max seconds to wait for the bridge to come back up.

        Returns a new connected RimClient.
        """
        self.close()

        # Kill RimWorld process
        subprocess.run(["pkill", "-f", "RimWorld"], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        time.sleep(2)

        # Force kill if still alive
        subprocess.run(["pkill", "-9", "-f", "RimWorld"], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        time.sleep(2)

        # Relaunch via Steam
        subprocess.Popen(["open", "steam://rungameid/294100"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Poll for TCP bridge to come back up
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            time.sleep(3)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect(("127.0.0.1", 9900))
                s.close()
                # Bridge is up — create fresh client
                client = RimClient()
                if save:
                    # Give the main menu a moment to fully initialize
                    time.sleep(3)
                    client.load_game(save)
                    # Wait for save to finish loading (connection drops and reconnects)
                    time.sleep(5)
                    reconnect_start = time.monotonic()
                    while time.monotonic() - reconnect_start < timeout:
                        time.sleep(3)
                        try:
                            client = RimClient()
                            return client
                        except (ConnectionRefusedError, OSError):
                            continue
                    raise TimeoutError(f"Game did not finish loading save within {timeout}s")
                return client
            except (ConnectionRefusedError, OSError):
                continue
        raise TimeoutError(f"RimWorld bridge did not come back within {timeout}s")

    def __enter__(self) -> RimClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ── read helpers (cached) ────────────────────────────────────────

    def ping(self) -> PingResponse:
        return self.send("ping")

    def colonists(self) -> ColonistsResponse:
        return self._send_cached("read_colonists")

    def pawns(self) -> PawnsResponse:
        return self._send_cached("read_pawns")

    def animals(self) -> AnimalsResponse:
        data = self._send_cached("read_animals")
        # Normalize: server returns "kind" but callers expect "def"
        if isinstance(data, dict):
            for a in data.get("animals", []):
                if isinstance(a, dict) and "kind" in a and "def" not in a:
                    a["def"] = a["kind"]
        return data  # type: ignore[return-value]

    def plants(self, filter: str | None = None) -> PlantsResponse:
        """Get harvestable plants. filter: comma-separated defNames (e.g. 'Plant_Berry')."""
        kw: dict[str, Any] = {}
        if filter:
            kw["filter"] = filter
        return self._send_cached("read_plants", **kw)

    def food_log(self) -> FoodLogResponse:
        """Get recent food consumption events from the in-memory ring buffer (last 50)."""
        return self.send("read_food_log")

    def resources(self) -> ResourcesResponse:
        return self._send_cached("read_resources")

    def map_info(self) -> MapInfoResponse:
        return self._send_cached("read_map")

    def weather(self) -> WeatherResponse:
        return self._send_cached("read_weather")

    def research(self) -> ResearchResponse:
        return self._send_cached("read_research")

    def buildings(self) -> BuildingsResponse:
        return self._send_cached("read_buildings")

    def zones(self) -> ZonesResponse:
        return self._send_cached("read_zones")

    def alerts(self) -> AlertsResponse:
        return self._send_cached("read_alerts")

    def messages(self) -> MessagesResponse:
        """Read top-of-screen messages (food rotted, construction failed, etc.)."""
        return self.send("read_messages")

    def threats(self) -> ThreatsResponse:
        return self._send_cached("read_threats")

    def work_priorities(self) -> WorkPrioritiesResponse:
        return self._send_cached("read_work_priorities")

    def needs(self, pawn: str) -> NeedsResponse:
        return self._send_cached("read_needs", pawn=pawn)

    def colonist_needs(self) -> ColonistNeedsResponse:
        return self._send_cached("read_colonist_needs")

    def thoughts(self, pawn: str) -> ThoughtsResponse:
        return self._send_cached("read_thoughts", pawn=pawn)

    def inventory(self, pawn: str) -> InventoryResponse:
        return self._send_cached("read_inventory", pawn=pawn)

    def beauty(self, x1: int, z1: int, x2: int, z2: int) -> BeautyResponse:
        """Read beauty values for a region (max 50x50). Returns avg and non-zero cells."""
        return self._send_cached("read_beauty", x1=x1, z1=z1, x2=x2, z2=z2)

    def fishing_zone(self, x1: int, z1: int, x2: int | None = None, z2: int | None = None) -> FishingZoneResponse:
        """Create a fishing zone on water cells."""
        kw = dict(x1=x1, z1=z1)
        if x2 is not None: kw["x2"] = x2
        if z2 is not None: kw["z2"] = z2
        return self.send("create_fishing_zone", **kw)

    def bills(self) -> BillsResponse:
        return self._send_cached("read_bills")

    def terrain(self, x1: int, z1: int, x2: int, z2: int) -> TerrainDict:
        """Read terrain data for a region. Returns dict keyed by (x,z).

        Each value has: terrain (defName), fertility, isWater, isRock.
        Cached with standard TTL. Invalidated on builds.
        """
        data = self._send_cached("read_terrain", x1=x1, z1=z1, x2=x2, z2=z2)
        result = {}
        for c in data.get("cells", []):
            result[(c["x"], c["z"])] = c
        return result

    def roof(self, x1: int, z1: int, x2: int, z2: int) -> RoofDict:
        """Read roof status for a region. Returns dict keyed by (x,z).

        Each value has: roof (defName or None).
        """
        data = self._send_cached("read_roof", x1=x1, z1=z1, x2=x2, z2=z2)
        result = {}
        for c in data.get("cells", []):
            result[(c["x"], c["z"])] = c
        return result

    def costs(self, blueprint: str, stuff: str | None = None) -> CostsResponse:
        """Get material costs for a building defName. Returns {costs, workAmount}."""
        kw = {"blueprint": blueprint}
        if stuff is not None:
            kw["stuff"] = stuff
        return self._send_cached("read_costs", **kw)

    def interaction_spots(self, x1: int, z1: int, x2: int, z2: int) -> InteractionSpotsResponse:
        """Get interaction cells for buildings in a region."""
        return self._send_cached("read_interaction_spots",
                                 x1=x1, z1=z1, x2=x2, z2=z2)

    def letters(self) -> LettersResponse:
        return self.send("read_letters")  # not cached — transient

    def dialogs(self) -> DialogsResponse:
        return self.send("read_dialogs")  # not cached — transient

    def scan(self, x1: int, z1: int, x2: int, z2: int) -> ScanDecodedResponse | ScanMergedResponse | None:
        """Read map tiles in a region and decode base64 grids into lists.

        Automatically pages in 50x50 chunks if the region is larger.
        """
        P = self._TILE_PAGE
        if x2 - x1 < P and z2 - z1 < P:
            data = self._send_cached("read_map_tiles", x1=x1, z1=z1, x2=x2, z2=z2)
            if data is None:
                return data
            out = dict(data)
            for key in ("terrain", "fertility", "roof", "fog"):
                raw = out.get(key)
                if isinstance(raw, str):
                    out[key] = list(base64.b64decode(raw))
            return out  # type: ignore[return-value]
        # Page across the region, merge things + designations + terrain stats
        merged_things = []
        merged_desigs = []
        terrain_counts = {}
        fertility_sum = 0.0
        roof_open = 0
        roof_thin = 0
        roof_overhead = 0
        total_tiles = 0
        for px in range(x1, x2 + 1, P):
            for pz in range(z1, z2 + 1, P):
                page = self.send("read_map_tiles", x1=px, z1=pz,
                                 x2=min(px + P - 1, x2),
                                 z2=min(pz + P - 1, z2))
                if not page:
                    continue
                merged_things.extend(page.get("things", []))
                merged_desigs.extend(page.get("cellDesignations", []))
                # Decode terrain grid
                palette = page.get("terrainPalette", [])
                raw_terrain = page.get("terrain")
                if isinstance(raw_terrain, str) and palette:
                    terrain_bytes = base64.b64decode(raw_terrain)
                    for b in terrain_bytes:
                        name = palette[b] if b < len(palette) else "Unknown"
                        terrain_counts[name] = terrain_counts.get(name, 0) + 1
                    total_tiles += len(terrain_bytes)
                # Decode fertility grid
                raw_fert = page.get("fertility")
                if isinstance(raw_fert, str):
                    for b in base64.b64decode(raw_fert):
                        fertility_sum += b / 255.0
                # Decode roof grid
                raw_roof = page.get("roof")
                if isinstance(raw_roof, str):
                    for b in base64.b64decode(raw_roof):
                        if b == 0:
                            roof_open += 1
                        elif b == 1:
                            roof_thin += 1
                        else:
                            roof_overhead += 1
        avg_fertility = round(fertility_sum / total_tiles, 2) if total_tiles else 0
        return {
            "things": merged_things,
            "cellDesignations": merged_desigs,
            "terrain_counts": terrain_counts,
            "avg_fertility": avg_fertility,
            "roof_counts": {"open": roof_open, "thin": roof_thin, "overhead": roof_overhead},
            "total_tiles": total_tiles,
        }

    # server clamps read_map_tiles to 50×50 per request
    _TILE_PAGE = 50

    def scan_items(self, x1: int, z1: int, x2: int, z2: int, kind: str) -> list[dict[str, Any]]:
        """Like :meth:`scan` but returns only things matching *kind*.

        *kind* is passed to the server to filter on the wire (e.g.
        ``"item"``, ``"building"``, ``"building,blueprint,frame"``).
        """
        data = self._send_cached("read_map_tiles", x1=x1, z1=z1, x2=x2, z2=z2,
                                 kind=kind)
        if data is None:
            return []
        return data.get("things", [])

    # ── write helpers ─────────────────────────────────────────────────

    def pause(self) -> PauseResponse:
        return self.send("pause")

    def unpause(self, speed: int = 4) -> UnpauseResponse:
        """Unpause the game. Defaults to speed 4 (ultrafast — skips rendering).
        Speed 3=superfast, 4=ultrafast. Also auto-dismisses ImmediateWindow dialogs.
        """
        return self.send("unpause", speed=speed)

    def speed(self, n: int) -> SetSpeedResponse:
        return self.send("set_speed", speed=n)

    def save(self, name: str | None = None) -> SaveResponse:
        kw = {}
        if name:
            kw["name"] = name
        return self.send("save", **kw)

    def load_game(self, name: str) -> LoadGameResponse:
        """Load a save file by name (without .rws extension).
        The game will begin loading asynchronously — the TCP connection
        will drop. Use restart_game() or reconnect manually after.
        """
        return self.send("load_game", name=name)

    def list_saves(self) -> ListSavesResponse:
        return self._send_cached("list_saves")

    def camera(self, x: int, z: int) -> CameraJumpResponse:
        return self.send("camera_jump", x=x, z=z)

    # construction — invalidate buildings + terrain cache
    def build(self, blueprint: str, x: int, z: int, stuff: str | None = None, rotation: int | None = None) -> BuildResponse:
        kw = {"blueprint": blueprint, "x": x, "y": z}
        if stuff is not None:
            kw["stuff"] = stuff
        if rotation is not None:
            kw["rotation"] = rotation
        self._cache.invalidate("read_buildings", "read_map_tiles", "read_terrain",
                               "read_interaction_spots")
        return self.send("build", **kw)

    def bulk_build(self, ops: list[dict[str, Any]]) -> BulkBuildResponse:
        """Send multiple build ops in one request. Returns per-cell results.

        *ops* is a list of dicts with keys: blueprint, x, y (z), stuff, rotation.
        """
        self._cache.invalidate("read_buildings", "read_map_tiles", "read_terrain",
                               "read_interaction_spots")
        return self.send("bulk_build", ops=ops)

    def wall(self, x: int, z: int, stuff: str = "BlocksGranite") -> BuildResponse:
        return self.build("Wall", x, z, stuff=stuff)

    def door(self, x: int, z: int, stuff: str = "BlocksGranite") -> BuildResponse:
        return self.build("Door", x, z, stuff=stuff)

    def floor(self, floor_def: str, x1: int, z1: int, x2: int | None = None, z2: int | None = None, stuff: str | None = None) -> SetFloorResponse:
        """Designate floor placement over a rectangle (or single tile)."""
        kw = {"floor": floor_def, "x1": x1, "z1": z1,
              "x2": x2 if x2 is not None else x1,
              "z2": z2 if z2 is not None else z1}
        if stuff is not None:
            kw["stuff"] = stuff
        self._cache.invalidate("read_map_tiles")
        return self.send("set_floor", **kw)

    def plan(self, x1: int, z1: int, x2: int | None = None, z2: int | None = None) -> AddPlanResponse:
        """Place planning designations over a rectangle (or single tile)."""
        return self.send("add_plan", x1=x1, z1=z1,
                         x2=x2 if x2 is not None else x1,
                         z2=z2 if z2 is not None else z1)

    def remove_plan(self, x1: int, z1: int, x2: int | None = None, z2: int | None = None) -> RemovePlanResponse:
        """Remove planning designations from a rectangle (or single tile)."""
        return self.send("remove_plan", x1=x1, z1=z1,
                         x2=x2 if x2 is not None else x1,
                         z2=z2 if z2 is not None else z1)

    def cancel_build(self, x: int, z: int) -> CancelBuildResponse:
        self._cache.invalidate("read_buildings", "read_map_tiles")
        return self.send("cancel_build", x=x, y=z)

    def place(self, thing_def: str, x: int, z: int, stuff: str | None = None, rotation: int | None = None) -> PlaceResponse:
        kw = {"thingDef": thing_def, "x": x, "z": z}
        if stuff is not None:
            kw["stuffDef"] = stuff
        if rotation is not None:
            kw["rotation"] = rotation
        self._cache.invalidate("read_buildings", "read_map_tiles")
        return self.send("place", **kw)

    def deconstruct(self, x: int, z: int) -> DeconstructResponse:
        self._cache.invalidate("read_buildings", "read_map_tiles")
        return self.send("deconstruct", x=x, z=z)

    def cancel_designation(self, x: int, z: int) -> CancelDesignationResponse:
        return self.send("cancel_designation", x=x, z=z)

    def cancel_designations(self, x1: int, z1: int, x2: int, z2: int, kind: str | None = None) -> CancelDesignationsResponse:
        """Cancel all designations in a region. Optional kind: chop, harvest, mine, deconstruct, hunt, haul."""
        kw: dict[str, Any] = {"x1": x1, "z1": z1, "x2": x2, "z2": z2}
        if kind is not None:
            kw["kind"] = kind
        return self.send("cancel_designations", **kw)

    def ideology(self) -> IdeologyResponse:
        """Read ideology info: name, memes, roles and assignments."""
        return self._send_cached("read_ideology")

    def assign_role(self, pawn: str, role: str) -> AssignRoleResponse:
        """Assign an ideology role to a pawn. E.g. assign_role('Levin', 'IdeoRole_Moralist')."""
        self._cache.invalidate("read_colonists", "read_ideology")
        return self.send("assign_role", pawn=pawn, role=role)

    def visitors(self) -> VisitorsResponse:
        """Read visitors/traders on map and incoming caravans."""
        return self._send_cached("read_visitors")

    # dev/testing tools
    def disable_incidents(self) -> ToggleIncidentsResponse:
        """Disable all storyteller incidents (raids, events, weather, etc.)."""
        return self.send("dev_toggle_incidents", enable=True)

    def enable_incidents(self) -> ToggleIncidentsResponse:
        """Re-enable storyteller incidents."""
        return self.send("dev_toggle_incidents", enable=False)

    def set_storyteller(self, name: str | None = None, difficulty: str | None = None) -> SetStorytellerResponse:
        """Change storyteller and/or difficulty.

        name: "Cassandra", "Phoebe", or "Randy"
        difficulty: "Peaceful", "Community", "Adventure", "Strive", "Blood"
        """
        kw = {}
        if name:
            kw["name"] = name
        if difficulty:
            kw["difficulty"] = difficulty
        return self.send("dev_set_storyteller", **kw)

    def colony_stats(self) -> ColonyStatsResponse:
        """Colony wealth, beauty, impressiveness, and room breakdown."""
        return self._send_cached("read_colony_stats")

    # colonist management
    def draft(self, colonist: str) -> DraftResponse:
        self._cache.invalidate("read_colonists")
        return self.send("draft", colonist=colonist)

    def undraft(self, colonist: str) -> DraftResponse:
        self._cache.invalidate("read_colonists")
        return self.send("undraft", colonist=colonist)

    def move_pawn(self, pawn: str, x: int, z: int) -> MovePawnResponse:
        return self.send("move_pawn", pawn=pawn, x=x, z=z)

    def attack(self, pawn: str, target: str | None = None, x: int | None = None, z: int | None = None) -> AttackResponse:
        kw: dict[str, Any] = {"pawn": pawn}
        if target is not None:
            kw["target"] = target
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        return self.send("attack", **kw)

    def rescue(self, pawn: str, target: str) -> RescueResponse:
        return self.send("rescue", pawn=pawn, target=target)

    def tend(self, pawn: str, target: str | None = None) -> TendResponse:
        kw: dict[str, Any] = {"pawn": pawn}
        if target is not None:
            kw["target"] = target
        return self.send("tend", **kw)

    def equip(self, pawn: str, thing: str | None = None, x: int | None = None, z: int | None = None) -> EquipResponse:
        kw: dict[str, Any] = {"pawn": pawn}
        if thing is not None:
            kw["thing"] = thing
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        return self.send("equip", **kw)

    def prioritize(self, pawn: str, work_type: str) -> PrioritizeResponse:
        return self.send("prioritize", pawn=pawn, workType=work_type)

    def set_priority(self, colonist: str, work: str, level: int) -> SetPriorityResponse:
        self._cache.invalidate("read_work_priorities")
        return self.send("set_priority", colonist=colonist, work=work, priority=level)

    def set_priorities(self, colonist: str, priorities: dict[str, int]) -> list[dict[str, Any]]:
        """Set multiple work priorities at once (batched).

        *priorities* is a dict mapping work type names to priority levels.
        """
        cmds = [("set_priority", {"colonist": colonist, "work": w, "priority": l})
                for w, l in priorities.items()]
        self._cache.invalidate("read_work_priorities")
        return self.send_batch(cmds)

    def set_schedule(self, colonist: str, schedule: list[str] | str) -> SetScheduleResponse:
        """Set 24-hour schedule. *schedule* is a list of 24 strings
        (each 'sleep', 'work', 'joy'/'recreation', or 'anything'),
        or a single string applied to all 24 hours."""
        if isinstance(schedule, str):
            schedule = [schedule] * 24
        return self.send("set_schedule", colonist=colonist, schedule=schedule)

    def haul(self, pawn: str, x: int, z: int) -> HaulResponse:
        return self.send("haul", pawn=pawn, x=x, z=z)

    # designations
    def chop(self, x: int, z: int, radius: int | None = None, _force: bool = False) -> ChopResponse:
        """Designate trees for chopping.

        On food-scarce maps (detected by day1_setup), ALL chop calls are BLOCKED
        after Phase 1 setup unless _force=True (used by emergency fuel chops in
        monitored_sleep/colony_health_check). This is the definitive fix for
        the PlantCutting queue saturation bug (runs 1-11): tree-chop and berry-
        harvest both use PlantCutting, and colonists always pick nearest job.
        117 accumulated tree designations in run 11 drowned 4/15 berry bushes.
        """
        # BLOCK all non-emergency chops on food-scarce maps after Phase 1
        if getattr(self, '_chop_blocked', False) and not _force:
            print(f"  CHOP BLOCKED: food-scarce mode — chop({x},{z},r={radius}) rejected. "
                  f"Berry harvest needs full PlantCutting queue.")
            return {"designated": 0, "blocked": True}  # type: ignore[return-value]

        kw: dict[str, Any] = {"x": x, "z": z}
        max_r = getattr(self, '_max_chop_radius', None)
        # If no radius given, default to a safe value (prevents full-map designation)
        if radius is None:
            radius = max_r if max_r is not None else 15
        # Clamp to food-scarce cap when active
        if max_r is not None and radius > max_r:
            print(f"  CHOP GUARD: Clamped radius {radius} → {max_r} (food-scarce mode)")
            radius = max_r
        kw["radius"] = radius
        return self.send("designate_chop", **kw)

    def harvest(self, x: int, z: int, radius: int | None = None, def_filter: str | None = None) -> HarvestResponse:
        """Designate harvestable plants for harvesting.

        *def_filter* is an optional comma-separated string of defNames to
        target (e.g. ``"Plant_Berry,Plant_HealrootWild"``).
        """
        kw: dict[str, Any] = {"x": x, "z": z}
        if radius is not None:
            kw["radius"] = radius
        if def_filter is not None:
            kw["def"] = def_filter
        return self.send("designate_harvest", **kw)

    def mine(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None) -> MineResponse:
        kw = {}
        if x1 is not None:
            kw.update(x1=x1, z1=z1, x2=x2, z2=z2)
        return self.send("designate_mine", **kw)

    def hunt(self, animal: str | None = None) -> HuntResponse:
        kw = {}
        if animal is not None:
            kw["animal"] = animal
        return self.send("hunt", **kw)

    # Dangerous megafauna that can wipe a small colony if auto-hunted.
    # These animals retaliate aggressively and require multiple well-armed colonists.
    # Run 008: auto-hunting a Rhinoceros killed 2/3 colonists → 13 pts lost.
    DANGEROUS_SPECIES = {
        "Rhinoceros", "Thrumbo", "Megasloth", "Elephant",
        "Bear_Grizzly", "Bear_Polar",
        "Warg", "Panther", "Cougar", "Lynx",
        "Megaspider", "Spelopede", "Megascarab",
        "Cobra",
    }

    def spawn_animals(self, species: str, count: int = 1, x: int | None = None, z: int | None = None, manhunter: bool = False) -> SpawnAnimalsResponse:
        """Spawn wild animals on the map at runtime."""
        kwargs = {"species": species, "count": count, "manhunter": manhunter}
        if x is not None:
            kwargs["x"] = x
        if z is not None:
            kwargs["z"] = z
        return self.send("spawn_animals", **kwargs)

    def set_event_log(self, path: str | None = None) -> dict[str, Any]:
        """Start or stop the game-side event logger (job transitions, pickups, eating).

        Args:
            path: JSONL file path to write events. None/empty to stop.
        """
        kw: dict[str, Any] = {}
        if path:
            kw["path"] = path
        return self.send("set_event_log", **kw)

    def hunt_all_wildlife(self) -> HuntAllWildlifeResult:
        """Hunt all SAFE wild animals on the map. Skips dangerous megafauna.

        Reads the animal list, filters out DANGEROUS_SPECIES, and designates
        hunting for every remaining wild species. Returns dict with designated,
        species, skipped (dangerous), already_designated, edge_animals.
        """
        result: dict[str, Any] = {"designated": 0, "species": [], "skipped": [], "already_designated": 0, "errors": [], "edge_animals": []}
        try:
            animals_data = self.send("read_animals")
            if not isinstance(animals_data, dict):
                return result  # type: ignore[return-value]
            all_animals = animals_data.get("animals", [])
            # Collect unique wild species and track positions
            wild_species = set()
            wild_positions = []
            for a in all_animals:
                if isinstance(a, dict) and not a.get("tame", False) and not a.get("downed", False):
                    kind = a.get("kind", "")
                    if kind:
                        wild_species.add(kind)
                        pos = a.get("position", {})
                        wild_positions.append({"kind": kind, "x": pos.get("x", -1), "z": pos.get("z", -1)})
            result["species"] = sorted(wild_species)
            # Hunt each species individually — SKIP dangerous megafauna
            for species in wild_species:
                if species in self.DANGEROUS_SPECIES:
                    result["skipped"].append(species)
                    print(f"  AUTO-HUNT: SKIPPED dangerous species '{species}'")
                    continue
                try:
                    resp = self.hunt(species)
                    designated = resp.get("designated", 0) if isinstance(resp, dict) else 0
                    result["designated"] += designated
                    if designated == 0:
                        result["already_designated"] += 1
                except Exception as e:
                    result["errors"].append(f"{species}: {e}")
            # Diagnose edge animals that may be unreachable by hunters
            try:
                map_info = self.map_info()
                map_sz = map_info.get("size", {})
                mx = (map_sz.get("x", 250) if isinstance(map_sz, dict) else 250)
                mz = (map_sz.get("z", 250) if isinstance(map_sz, dict) else 250)
                for wp in wild_positions:
                    ax, az = wp["x"], wp["z"]
                    if ax < 0:
                        continue
                    edge_dist = min(ax, az, mx - 1 - ax, mz - 1 - az)
                    if edge_dist < 5:
                        msg = f"{wp['kind']} at ({ax},{az}) — {edge_dist} tiles from edge"
                        result["edge_animals"].append(msg)
            except Exception:
                pass
        except Exception as e:
            result["errors"].append(f"read_animals: {e}")
        return result  # type: ignore[return-value]

    def tame(self, animal: str) -> TameResponse:
        return self.send("tame", animal=animal)

    def slaughter(self, animal: str) -> SlaughterResponse:
        return self.send("slaughter", animal=animal)

    def forbid(self, x: int | None = None, z: int | None = None, thing_def: str | None = None) -> ForbidResponse:
        kw = {}
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        if thing_def is not None:
            kw["thingDef"] = thing_def
        return self.send("forbid", **kw)

    def unforbid_all(self) -> ForbidResponse:
        """Unforbid all items on the map.

        Uses server-side bulk unforbid — no scan/paging needed.
        Call at game start to ensure crash-landed / dropped items are accessible.
        """
        return self.send("unforbid", all="true")

    def unforbid(self, x: int | None = None, z: int | None = None, thing_def: str | None = None) -> ForbidResponse:
        kw = {}
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        if thing_def is not None:
            kw["thingDef"] = thing_def
        return self.send("unforbid", **kw)

    # zones — invalidate zone cache on writes
    _GROWABLE_TERRAIN = {"Soil", "SoilRich", "Gravel", "MarshyTerrain", "MossyTerrain"}

    def grow_zone(self, x1: int, z1: int, x2: int, z2: int, plant: str | None = None, check_soil: bool = True) -> GrowZoneResponse:
        """Create a growing zone.

        Validates placement before creating:
        - With *check_soil* (default), scans terrain and rejects areas where
          less than half the cells are growable soil (sand/rock/water).
        - Checks for existing buildings/blueprints and zones in the area and
          raises :class:`RimError` on overlap.
        """
        building_map, zone_occ = self._get_occupancy(x1, z1, x2, z2)
        if zone_occ:
            raise RimError(
                f"Zone overlap: {len(zone_occ)} cells already belong to a zone. "
                f"Delete existing zones first."
            )
        if building_map:
            raise RimError(
                f"Building overlap: {len(building_map)} cells have buildings/blueprints."
            )
        if check_soil:
            survey = self.survey_region(x1, z1, x2, z2)
            terrain_counts = survey.get("terrain_counts", {})
            growable = sum(terrain_counts.get(t, 0) for t in self._GROWABLE_TERRAIN)
            total = (abs(x2 - x1) + 1) * (abs(z2 - z1) + 1)
            if total and growable / total < 0.8:
                raise RimError(
                    f"Only {growable}/{total} cells ({growable*100//total}%) are growable soil. "
                    f"Non-growable terrain: {', '.join(f'{k}: {v}' for k, v in terrain_counts.items() if k not in self._GROWABLE_TERRAIN)}. "
                    f"Use check_soil=False to override."
                )
        kw: dict[str, Any] = {"x1": x1, "z1": z1, "x2": x2, "z2": z2}
        if plant is not None:
            kw["plant"] = plant
        self._cache.invalidate("read_zones")
        return self.send("create_grow_zone", **kw)

    def stockpile(self, x1: int, z1: int, x2: int, z2: int, priority: str | None = None) -> StockpileResponse:
        """Create a stockpile zone.

        C# server gracefully handles overlap by skipping occupied cells.
        Returns response with 'cells' count and 'skipped' count.
        """
        kw: dict[str, Any] = {"x1": x1, "z1": z1, "x2": x2, "z2": z2}
        if priority is not None:
            kw["priority"] = priority
        self._cache.invalidate("read_zones")
        return self.send("create_stockpile_zone", **kw)

    def delete_zone(self, x: int | None = None, z: int | None = None) -> DeleteZoneResponse:
        kw = {}
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        self._cache.invalidate("read_zones")
        return self.send("delete_zone", **kw)

    def remove_zone_cells(self, x1: int, z1: int, x2: int | None = None, z2: int | None = None) -> RemoveZoneCellsResponse:
        """Remove cells from zones in a rect (or single cell if x2/z2 omitted).

        Zones that lose all cells are auto-deleted.
        """
        kw: dict[str, Any] = {"x1": x1, "z1": z1}
        if x2 is not None:
            kw["x2"] = x2
        if z2 is not None:
            kw["z2"] = z2
        self._cache.invalidate("read_zones")
        return self.send("remove_zone_cells", **kw)

    def set_plant(self, zone: str | None = None, plant: str | None = None) -> SetPlantResponse:
        kw = {}
        if zone is not None:
            kw["zone"] = zone
        if plant is not None:
            kw["plant"] = plant
        self._cache.invalidate("read_zones")
        return self.send("set_plant", **kw)

    # production
    def add_bill(self, workbench: str, recipe: str, count: int | None = None,
                 x: int | None = None, z: int | None = None,
                 target_all: bool = False) -> AddBillResponse:
        """Add bill to workbench. Use x/z for position targeting, target_all to broadcast."""
        kw: dict[str, Any] = {"workbench": workbench, "recipe": recipe}
        if count is not None:
            kw["count"] = count
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        if target_all:
            kw["target_all"] = True
        return self.send("add_bill", **kw)

    def cancel_bill(self, workbench: str, bill_index: int) -> CancelBillResponse:
        return self.send("cancel_bill", workbench=workbench, billIndex=bill_index)

    def suspend_bill(self, workbench: str, bill_index: int, suspended: bool = True) -> SuspendBillResponse:
        return self.send("suspend_bill", workbench=workbench,
                         billIndex=bill_index, suspended=suspended)

    # priorities
    def set_manual_priorities(self, enabled: bool = True) -> SetManualPrioritiesResponse:
        """Toggle manual (1-4) vs simple (on/off) priority mode."""
        self._cache.invalidate("read_work_priorities")
        return self.send("set_manual_priorities", enabled=enabled)

    # stockpile filter
    def set_stockpile_filter(self, zone: str | None = None, x: int | None = None, z: int | None = None,
                             allow: list[str] | None = None, disallow: list[str] | None = None,
                             allow_all: bool = False, disallow_all: bool = False,
                             priority: str | None = None) -> SetStockpileFilterResponse:
        """Modify a stockpile's storage filter.

        *allow* / *disallow* are lists of ThingDef names, ThingCategoryDef
        names, or SpecialThingFilterDef names.
        """
        kw = {}
        if zone is not None:
            kw["zone"] = zone
        if x is not None:
            kw["x"] = x
        if z is not None:
            kw["z"] = z
        if allow is not None:
            kw["allow"] = allow
        if disallow is not None:
            kw["disallow"] = disallow
        if allow_all:
            kw["allow_all"] = True
        if disallow_all:
            kw["disallow_all"] = True
        if priority is not None:
            kw["priority"] = priority
        self._cache.invalidate("read_zones")
        return self.send("set_stockpile_filter", **kw)

    # research
    def set_research(self, project: str) -> SetResearchResponse:
        self._cache.invalidate("read_research")
        return self.send("set_research", project=project)

    # dialogs / letters
    def open_letter(self, index: int) -> OpenLetterResponse:
        return self.send("open_letter", index=index)

    def dismiss_letter(self, index: int) -> DismissLetterResponse:
        return self.send("dismiss_letter", index=index)

    def choose_option(self, index: int) -> ChooseOptionResponse:
        return self.send("choose_option", index=index)

    def close_dialog(self, dialog_type: str | None = None, **kwargs: Any) -> CloseDialogResponse:
        """Close a dialog window.

        *dialog_type* targets a specific window type (e.g.
        ``"Dialog_NamePlayerFactionAndSettlement"``).  Without it, closes
        the topmost substantive dialog (skipping ImmediateWindows).

        For naming dialogs, pass *factionName* and *settlementName*.
        """
        kw = {}
        if dialog_type is not None:
            kw["type"] = dialog_type
        kw.update(kwargs)
        return self.send("close_dialog", **kw)

    # finding / survey
    def survey_region(self, x1: int, z1: int, x2: int, z2: int) -> SurveyRegionResponse:
        return self._send_cached("survey_region", x1=x1, z1=z1, x2=x2, z2=z2)

    def _ascii_kw(self, x1: int | None, z1: int | None, x2: int | None, z2: int | None, scale: int | None) -> dict[str, int]:
        kw = {}
        if x1 is not None: kw["x1"] = x1
        if z1 is not None: kw["z1"] = z1
        if x2 is not None: kw["x2"] = x2
        if z2 is not None: kw["z2"] = z2
        if scale is not None: kw["scale"] = scale
        return kw

    def survey_terrain_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_terrain_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_roof_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_roof_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_fertility_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_fertility_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_things_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_things_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_composite_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_composite_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_detailed_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> DetailedAsciiSurveyResponse:
        return self.send("survey_detailed_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_beauty_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_beauty_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_temperature_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_temperature_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_blueprint_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_blueprint_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_power_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_power_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def survey_task_ascii(self, x1: int | None = None, z1: int | None = None, x2: int | None = None, z2: int | None = None, scale: int | None = None) -> AsciiSurveyResponse:
        return self._send_cached("survey_task_ascii", **self._ascii_kw(x1, z1, x2, z2, scale))

    def find_water(self) -> WaterResponse:
        return self.send("find_water")

    def find_grow_spot(self, size: int | None = None, radius: int | None = None, cx: int | None = None, cz: int | None = None) -> GrowSpotResponse:
        kw = {}
        if size is not None:
            kw["size"] = size
        if radius is not None:
            kw["radius"] = radius
        if cx is not None:
            kw["cx"] = cx
        if cz is not None:
            kw["cz"] = cz
        return self.send("find_grow_spot", **kw)

    def find_clear_rect(self, width: int = 9, height: int = 7, cx: int | None = None, cz: int | None = None, radius: int = 30) -> ClearRectResponse:
        """Find a clear rectangular area for building (no rock, water, or existing buildings)."""
        kw = {"width": width, "height": height, "radius": radius}
        if cx is not None:
            kw["cx"] = cx
        if cz is not None:
            kw["cz"] = cz
        return self.send("find_clear_rect", **kw)

    # ── day 1 setup (moves boilerplate from prompt to SDK — FREE) ────

    def day1_setup(self) -> Day1SetupResult:
        """Complete Day 1 setup: read state, assign roles, set priorities,
        set research, hunt, harvest, chop trees. Returns structured result.

        Wraps each section in try/except so one failure doesn't block the rest.
        """
        self.pause()
        self.set_manual_priorities(True)
        try:
            self.unforbid_all()
        except Exception:
            pass

        # Read all state
        colonists = self.colonists()
        resources = self.resources()
        map_info = self.map_info()
        research = self.research()
        animals = self.animals()

        # ── FOOD-SCARCE MODE DETECTION ──
        # When starting food is minimal (0-2 packs/meals), enable SDK-level
        # chop radius enforcement.  This is the #1 fix for feed_the_colony:
        # over-chopping (114 trees in run 009) floods PlantCutting queue and
        # starves berry harvesting (only 20% yield).  The overseer ignores
        # prompt radius advice, so enforcement MUST be at SDK level.
        packs = resources.get("MealSurvivalPack", 0)
        starting_meals = packs + resources.get("MealSimple", 0) + resources.get("MealFine", 0)
        wild_count = sum(1 for a in animals.get("animals", [])
                         if isinstance(a, dict) and not a.get("tame", False))
        # Food-scarce = few starting meals AND limited meat sources (<=6 wild animals)
        if starting_meals <= 2 and wild_count <= 6:
            self._food_scarce_mode = True
            self._max_chop_radius = 5  # ~8 trees max = ~240 wood (enough for campfire fuel + basic builds)
            print(f"  FOOD-SCARCE MODE: meals={starting_meals}, wildlife={wild_count}, "
                  f"max_chop_radius={self._max_chop_radius}")
        else:
            self._food_scarce_mode = getattr(self, '_food_scarce_mode', False)
            print(f"  Food mode: normal (meals={starting_meals}, wildlife={wild_count})")

        # Dismiss naming dialogs
        try:
            for d in self.dialogs():
                dtype = d.get("type", "") if isinstance(d, dict) else str(d)
                if "Name" in dtype:
                    self.close_dialog(dtype, factionName="Colony",
                                      settlementName="Colony")
        except Exception:
            pass

        # Find colonists and assign roles based on skills
        cols = colonists.get("colonists", [])
        skills = {}
        for c in cols:
            name = c["name"]
            # Extract short name
            if "'" in name:
                short = name.split("'")[1]
            else:
                short = name.split()[-1]
            skills[short] = {s["name"]: s["level"] for s in c.get("skills", [])}

        # Build disabled work tags for each colonist
        # Hunting requires Violent, Cooking requires Cooking, Research requires Intellectual
        disabled = {}
        for c in cols:
            cname = c["name"]
            short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
            dw = c.get("disabledWork", "")
            disabled[short] = set(tag.strip() for tag in dw.split(",") if tag.strip())
            if disabled[short]:
                print(f"  DISABLED WORK: {short} cannot do: {disabled[short]}")

        names = list(skills.keys())
        # Filter by work ability — prevents assigning roles colonists can't perform
        # CRITICAL FIX (run 008): Gabs had Violent disabled but was assigned hunter.
        # Hunt designations succeeded (marks animals) but no colonist could fulfill
        # the actual Hunt job → 4 hares never killed → 80+ points lost.
        can_hunt = [n for n in names if "Violent" not in disabled.get(n, set())]
        can_cook_list = [n for n in names if "Cooking" not in disabled.get(n, set())]
        can_research_list = [n for n in names if "Intellectual" not in disabled.get(n, set())]
        print(f"  ROLE CANDIDATES: hunt={can_hunt}, cook={can_cook_list}, research={can_research_list}")

        hunter = max(can_hunt or names, key=lambda n: skills[n].get("Shooting", 0))
        cook = max(can_cook_list or names, key=lambda n: skills[n].get("Cooking", 0))
        researcher = max(can_research_list or names, key=lambda n: skills[n].get("Intellectual", 0))
        if cook == hunter:
            alt_cooks = [n for n in (can_cook_list or names) if n != hunter]
            if alt_cooks:
                cook = max(alt_cooks, key=lambda n: skills[n].get("Cooking", 0))
            else:
                cook = max([n for n in names if n != hunter],
                           key=lambda n: skills[n].get("Cooking", 0))
        if researcher in (hunter, cook):
            remaining = [n for n in names if n not in (hunter, cook)]
            if remaining:
                can_res_remaining = [n for n in remaining if "Intellectual" not in disabled.get(n, set())]
                researcher = can_res_remaining[0] if can_res_remaining else remaining[0]
            else:
                researcher = names[0]

        # Detect Greedy and Ascetic traits
        greedy_colonist = None
        ascetic_colonist = None
        for c in cols:
            traits = c.get("traits", [])
            cname = c["name"]
            short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
            for t in traits:
                tlabel = ((t.get("label") or t.get("name") or t.get("def") or "") if isinstance(t, dict) else str(t)).lower()
                if "greedy" in tlabel and not greedy_colonist:
                    greedy_colonist = short
                    print(f"  WARNING: {short} has Greedy trait — needs impressive private bedroom (imp≥30)")
                if "ascetic" in tlabel and not ascetic_colonist:
                    ascetic_colonist = short
                    print(f"  WARNING: {short} has Ascetic trait — prefers raw food (+3 mood), bad as primary cook")

        # Ascetic cook swap: Ascetic colonists eat raw food for +3 mood, sabotaging
        # the cooking pipeline (consume ingredients at 0.05 nutrition instead of cooking
        # meals at 0.9 nutrition). Swap cook to the best non-Ascetic colonist.
        # CRITICAL FIX (runs 1-4): allow the hunter to become cook if they're the
        # best non-Ascetic cook. Previously excluded hunter from alternatives, which
        # forced picking a Cooking=1 colonist over a Cooking=5 hunter.
        if ascetic_colonist and ascetic_colonist == cook:
            # Consider ALL non-Ascetic colonists that CAN cook (Cooking work not disabled)
            all_non_ascetic = [n for n in names if n != cook and "Cooking" not in disabled.get(n, set())]
            if not all_non_ascetic:
                all_non_ascetic = [n for n in names if n != cook]  # fallback: anyone non-ascetic
            if all_non_ascetic:
                old_cook = cook
                cook = max(all_non_ascetic, key=lambda n: skills[n].get("Cooking", 0))
                # If the new cook was the hunter, reassign hunter role — MUST check Violent disability
                # CRITICAL FIX (run 008): Without this check, Gabs (Violent disabled) was
                # reassigned as hunter after Ascetic swap moved her off cook duty.
                if cook == hunter:
                    remaining_hunters = [n for n in can_hunt if n != cook]
                    if not remaining_hunters:
                        remaining_hunters = [n for n in names if n != cook]  # fallback
                    hunter = max(remaining_hunters, key=lambda n: skills[n].get("Shooting", 0))
                    print(f"  ASCETIC SWAP: cook {old_cook} → {cook}, hunter reassigned → {hunter}")
                else:
                    print(f"  ASCETIC SWAP: cook {old_cook} → {cook} (Ascetic colonists eat raw food, sabotage cooking pipeline)")
                # Re-check researcher assignment
                if researcher in (hunter, cook):
                    remaining = [n for n in names if n not in (hunter, cook)]
                    if remaining:
                        researcher = remaining[0]

        # Set work priorities — Construction=2 for ALL so buildings get built
        # PlantCutting=3 (was 4) for base, but food-scarce maps get PlantCutting=1
        # for hunter+researcher (CRITICAL: PlantCutting is work type #14, Construction
        # is #11. At equal priority, Construction ALWAYS wins because it's checked first.
        # PlantCutting=2 was tried in run_005 and FAILED — 8/20 berry bushes unharvested.
        # PlantCutting=1 guarantees berry harvest before construction.)
        try:
            for n in names:
                try:
                    self.set_priority(n, "Construction", 2)
                    self.set_priority(n, "Hauling", 3)
                    self.set_priority(n, "Doctor", 3)  # Everyone can tend
                    self.set_priority(n, "PlantCutting", 3)  # Berry harvesting — competes with hauling
                    # CRITICAL FIX (runs 003-004): Disable Growing on food-scarce maps.
                    # No grow zone exists (skipped), so Growing=0 prevents ALL sowing labor.
                    # Run 004: grow zone CutPlant:TallGrass/ChoppedStump clearing tasks
                    # competed with berry harvesting, and Sow:Plant_Rice diverted labor.
                    growing_prio = 0 if getattr(self, '_food_scarce_mode', False) else 4
                    self.set_priority(n, "Growing", growing_prio)
                    self.set_priority(n, "Cleaning", 3)  # Same as Hauling — prevents filth wrecking room impressiveness
                except Exception:
                    pass
            self.set_priority(hunter, "Hunting", 1)
            # CRITICAL FIX (run_005): PlantCutting=2 tied with Construction=2, and
            # Construction (#11) always beat PlantCutting (#14) in check order.
            # 8 of 20 berry bushes went unharvested. On food-scarce maps, PlantCutting=1
            # guarantees harvesting beats Construction=2. Hunting=1 (#10) still fires
            # before PlantCutting=1 (#14) when hunt targets exist (same priority, earlier order).
            hunter_plant_prio = 1 if getattr(self, '_food_scarce_mode', False) else 2
            self.set_priority(hunter, "PlantCutting", hunter_plant_prio)
            self.set_priority(hunter, "Construction", 2)
            self.set_priority(cook, "Cooking", 1)
            # CRITICAL FIX (run 11): Doctor=1 ties with Cooking=1, but Doctor is resolved
            # BEFORE Cooking in RimWorld's work type order → cook always tends before cooking.
            # Run 11: Benjamin spent 3.8 hours on TendPatient after bills activated.
            # On food-scarce maps: Doctor=3 so Cooking=1 always wins.
            # On normal maps: Doctor=1 is fine (food not critical).
            cook_doctor_prio = 3 if getattr(self, '_food_scarce_mode', False) else 1
            self.set_priority(cook, "Doctor", cook_doctor_prio)
            self.set_priority(cook, "Hauling", 2)
            self.set_priority(cook, "Construction", 3)    # Lower than Hauling(2) — cook hauls raw meat before building
            self.set_priority(cook, "PlantCutting", 2)    # CRITICAL: berry harvesting uses PlantCutting (NOT Growing). Cooking=1 takes priority, so cook harvests berries between cooking jobs.
            # CRITICAL FIX (runs 003-004): On food-scarce maps, cook Growing=0 (disabled).
            # Run 004: Benjamin was Sow:Plant_Rice at snap 75 while 2 hares went unhunted
            # and food reserves declined. Rice can't mature in a 5-day scenario. Cook must
            # ONLY cook, haul ingredients, and harvest berries — never sow.
            cook_growing_prio = 0 if getattr(self, '_food_scarce_mode', False) else 2
            self.set_priority(cook, "Growing", cook_growing_prio)
            # Researcher does research primarily — building_progress already exceeds
            # max with 2 builders (cook+hunter), so extra construction labor is wasted.
            # Research=1 lets them complete 2+ projects for research_progress points.
            # Cleaning=2 ensures researcher cleans barracks between research sessions
            # (prevents filth from tanking room impressiveness — Cleaning=3 never fires).
            self.set_priority(researcher, "Research", 1)
            self.set_priority(researcher, "Construction", 2)  # Same as hunter — more builders for barracks completion
            self.set_priority(researcher, "Cleaning", 2)      # MUST be 2 — at 3 filth never gets cleaned, tanks impressiveness
            # CRITICAL FIX (run_005): PlantCutting=2 tied with Construction=2 →
            # Construction always won. On food-scarce maps, PlantCutting=1 means
            # researcher harvests berries BEFORE researching (PlantCutting #14 < Research #21
            # in check order). Once berries exhausted, no PlantCutting jobs → falls to Research.
            researcher_plant_prio = 1 if getattr(self, '_food_scarce_mode', False) else 2
            self.set_priority(researcher, "PlantCutting", researcher_plant_prio)
            self.set_priority(researcher, "Hauling", 4)        # Low — research is priority

            # Disable Cooking for Ascetic colonist — Ascetics preferentially eat raw food
            # even when assigned to cook. Disabling prevents them from grabbing ingredients
            # as Cooking jobs and eating them raw (14 Meat_Hare consumed raw in run 004).
            if ascetic_colonist and ascetic_colonist != cook:
                try:
                    self.set_priority(ascetic_colonist, "Cooking", 0)
                    print(f"  ASCETIC: Disabled Cooking for {ascetic_colonist} (prevents raw food consumption)")
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: priority setting error: {e}")

        # Verify priorities were set correctly
        try:
            wp = self.work_priorities()
            for col in wp.get("colonists", []):
                cname = col.get("name", "?")
                prios = col.get("priorities", {})
                p_con = prios.get("Construction", "?")
                p_haul = prios.get("Hauling", "?")
                p_hunt = prios.get("Hunting", "?")
                p_cook = prios.get("Cooking", "?")
                print(f"  PRIO {cname}: Con={p_con} Haul={p_haul} Hunt={p_hunt} Cook={p_cook}")
        except Exception:
            pass

        # Set research — cheapest available for fastest completion
        # Score needs 2 completed projects. ColoredLights(300) completes first, then Brewing(400)
        completed = [item["def"] if isinstance(item, dict) else item  # type: ignore[index]
                     for item in research.get("completed", [])]
        cheap_chain = ["ColoredLights", "Brewing", "Batteries", "NobleApparel"]
        try:
            for proj in cheap_chain:
                if proj not in completed:
                    self.set_research(proj)
                    print(f"  RESEARCH: set to {proj}")
                    break
        except Exception:
            pass

        # Find base center: use map center (works for all map sizes)
        # Colonist positions are unreliable on resized maps (savegen puts them near edges)
        map_size_data = map_info.get("size", {})
        map_w = map_size_data.get("x", 250) if isinstance(map_size_data, dict) else 250
        map_h = map_size_data.get("z", 250) if isinstance(map_size_data, dict) else 250
        center_x = map_w // 2
        center_z = map_h // 2

        # Equip hunter with a ranged weapon (CRITICAL for hunting to work)
        # Crash-landed scenario drops weapons on ground — colonists won't auto-equip
        equipped_weapon = None
        ranged_weapons = [
            "Gun_BoltActionRifle", "Gun_Revolver", "Gun_Autopistol",
            "Gun_MachinePistol", "Gun_PumpShotgun", "Gun_SurvivalRifle",
            "Bow_Short", "Bow_Great", "Gun_ChargeLance", "Gun_ChargeRifle",
            # Melee fallback — colonists can melee-hunt with these
            "MeleeWeapon_Knife", "MeleeWeapon_Gladius", "MeleeWeapon_Mace",
        ]
        for weapon in ranged_weapons:
            try:
                result = self.equip(hunter, thing=weapon)
                equipped_weapon = weapon
                break
            except Exception:
                continue

        # Hunt animals — prefer safe ones, fallback to herd animals if no safe options
        hunted = set()
        truly_dangerous = {"Bear_Grizzly", "Bear_Polar", "Rhinoceros", "Elephant",
                           "Thrumbo", "Megasloth", "Warg", "Cougar", "Panther",
                           "Lynx", "Wolf_Timber", "Wolf_Arctic", "Cobra",
                           "Boomrat", "Boomalope"}  # Predators + explosive = never hunt
        herd_animals = {"Muffalo", "Horse", "Donkey"}  # Risky but huntable if no alternatives
        safe_large = {"Deer", "Elk", "Ibex", "Dromedary", "Cow", "Caribou", "Alpaca", "Yak"}
        safe_small = {"Turkey", "Hare", "Raccoon", "Gazelle"}
        # Hunt tiny animals too — they steal cooked meals from stockpiles
        safe_tiny = {"Squirrel", "GuineaPig", "Chinchilla", "Tortoise", "Iguana", "Rat"}
        try:
            seen = {}
            for a in animals.get("animals", []):
                adef = a.get("kind", "") or a.get("def", "")
                if adef:
                    seen[adef] = seen.get(adef, 0) + 1
            print(f"  ANIMALS on map: {dict(seen)}")
            safe_seen = {k: v for k, v in seen.items() if k not in truly_dangerous and k not in herd_animals}
            # Hunt ALL safe species — large first for meat, then small, then tiny to stop food theft
            for species in list(safe_large & set(safe_seen)) + list(safe_small & set(safe_seen)) + list(safe_tiny & set(safe_seen)):
                try:
                    self.hunt(species)
                    hunted.add(species)
                except Exception:
                    pass
            # Priority 2: herd animals (if no safe options) — limit to 1 to reduce retaliation risk
            if not hunted:
                herd_seen = {k: v for k, v in seen.items() if k in herd_animals}
                for species in herd_seen:
                    try:
                        self.hunt(species)
                        hunted.add(species)
                        print(f"  WARNING: hunting herd animal {species} — retaliation risk!")
                        break  # Only hunt 1 herd species
                    except Exception:
                        pass
            # Priority 3: blind fallback
            if not hunted:
                for species in ["Deer", "Elk", "Turkey", "Hare", "Raccoon", "Muffalo"]:
                    if len(hunted) >= 2:
                        break
                    try:
                        self.hunt(species)
                        hunted.add(species)
                    except Exception:
                        pass
        except Exception:
            pass

        # Log hunting results for diagnostics
        if hunted:
            print(f"  HUNTING: designated {list(hunted)}, weapon={equipped_weapon}")
        else:
            print(f"  HUNTING: NO ANIMALS designated! weapon={equipped_weapon}")

        # Belt-and-suspenders: also call hunt_all_wildlife() to catch any species
        # missed by the safe-list approach above (e.g., species with unexpected defNames).
        # This ensures ALL safe animals are designated, not just pre-listed ones.
        hunt_all_result = None
        try:
            hunt_all_result = self.hunt_all_wildlife()
            extra = hunt_all_result.get("designated", 0)
            if extra > 0:
                print(f"  HUNT_ALL: {extra} additional animals designated: {hunt_all_result.get('species', [])}")
        except Exception:
            pass

        # Harvest wild plants (berries, healroot) — FULL MAP radius for maximum berry yield.
        # Berry bushes are the primary food safety net on food-scarce maps.
        # radius=45 was too small on some maps — use max(map_w, map_h) for full coverage.
        harvest_radius = max(map_w, map_h)
        try:
            self.harvest(center_x, center_z, radius=harvest_radius)
        except Exception:
            pass

        # Chop trees near base — SKIP ENTIRELY on food-scarce maps.
        # CRITICAL FIX (runs 003-004): Even chop(radius=3) creates 2-3 tree-chop
        # PlantCutting tasks near center. Colonists pick these over distant berry bushes
        # EVERY time (nearest-job selection). In run 004, Gabs switched from
        # HarvestDesignated:Plant_Berry → CutPlant:Plant_TreeOak at snap 8, the exact
        # moment berries peaked at 129/200. Berry harvest was abandoned permanently.
        # Previous fix (radius=3 + block future) was insufficient — the INITIAL chop
        # still poisons the queue. Zero chop on food-scarce maps; emergency fuel chops
        # in monitored_sleep use _force=True if wood hits zero.
        if getattr(self, '_food_scarce_mode', False):
            print(f"  CHOP SKIPPED: food-scarce mode — zero chop designations at setup. "
                  f"Berry harvest gets 100% of PlantCutting queue from tick 0.")
        else:
            try:
                self.chop(center_x, center_z, radius=5)
            except Exception:
                pass

        # FOOD-SCARCE: Block ALL future chop() calls after initial setup.
        # The initial chop gives enough wood for campfire fuel. Any additional
        # chop designations poison the PlantCutting queue, killing berry harvests.
        # This was recommended in runs 9, 10, 11 audits but never implemented.
        # colony_health_check() and monitored_sleep() emergency chops use _force=True.
        if getattr(self, '_food_scarce_mode', False):
            self._chop_blocked = True
            print(f"  CHOP BLOCKED: All future chop() calls blocked (food-scarce mode). "
                  f"Berry harvest gets 100% of PlantCutting queue.")

        # Store cook name for monitored_sleep/colony_health_check to force cook priority
        self._cook_name = cook

        # ── COOK SCHEDULE: all-work on food-scarce maps ──
        # On food-scarce maps, the cook needs maximum throughput. Default "anything"
        # schedule includes recreation breaks and early sleep. "work" schedule means
        # the cook works continuously — only stops to eat when critically hungry.
        # This adds ~6 extra cooking hours/day → ~2 extra meals/day.
        if getattr(self, '_food_scarce_mode', False):
            try:
                # Cook: 20h work, 4h sleep (minimum to avoid exhaustion collapse)
                cook_sched = ["work"] * 24
                cook_sched[0] = "sleep"
                cook_sched[1] = "sleep"
                cook_sched[2] = "sleep"
                cook_sched[3] = "sleep"
                self.set_schedule(cook, cook_sched)
                print(f"  COOK SCHEDULE: {cook} set to 20h work / 4h sleep (max throughput)")
            except Exception as e:
                print(f"  COOK SCHEDULE: Failed to set: {e}")

        return {
            "colonists": cols,
            "skills": skills,
            "resources": resources if isinstance(resources, dict) else {},
            "map_info": map_info,
            "research": research,
            "animals": animals,
            "center_x": center_x,
            "center_z": center_z,
            "hunter": hunter,
            "cook": cook,
            "researcher": researcher,
            "hunted": list(hunted),
            "equipped_weapon": equipped_weapon,
            "completed_research": completed,
            "greedy_colonist": greedy_colonist,
            "food_scarce": getattr(self, '_food_scarce_mode', False),
        }

    # ── colony setup helpers (replaces ~170 lines of AGENT_OVERSEER.md code) ──

    def setup_cooking(self, cx: int, cz: int) -> SetupCookingResult:
        """Place campfire + butcher spot + fueled stove near center.
        Returns {campfire: (x,z)|None, butcher: (x,z)|None, stove: (x,z)|None}.

        CRITICAL (runs 9-13 fix): On food-scarce maps, the overseer sleeps 20s
        before calling add_cooking_bills(), creating a 7+ game-hour cooking gap
        that wastes ~45% of nutrition budget. This method now includes an
        AGGRESSIVE bill-addition loop: if the campfire is placed as a blueprint,
        it unpauses briefly (2s intervals at speed 4), waits for construction,
        and adds cooking bills BEFORE returning. This guarantees bills are active
        within ~4s of campfire placement, regardless of overseer behavior.
        """
        result: dict[str, Any] = {"campfire": None, "butcher": None, "stove": None}

        # Campfire — try close positions first
        for dx in [3, -3, 5, -5, 8, -8]:
            try:
                self.build("Campfire", cx + dx, cz)
                result["campfire"] = (cx + dx, cz)
                break
            except Exception:
                continue

        # ── RAW FOOD STOCKPILE adjacent to campfire (food-scarce fix) ──
        # 8-run recurring issue: cook walks 10+ tiles to grab ingredients from
        # main stockpile, producing ~1 meal/4hrs. With ingredients adjacent to
        # campfire, cook walks 1 tile → ~1 meal/2hrs → doubles throughput.
        # Critical priority ensures raw food hauled here FIRST (before main stockpile).
        # Also reduces raw eating: colonists eat from main stockpile (closer to base)
        # while raw food accumulates near campfire for cooking.
        result["raw_food_stockpile"] = None
        if result["campfire"] and getattr(self, '_food_scarce_mode', False):
            cfx, cfz = result["campfire"]
            # 3x1 strip adjacent to campfire (small to avoid blocking other builds)
            for dz_offset in [1, -1, 2, -2]:
                try:
                    sz1, sz2 = cfz + dz_offset, cfz + dz_offset
                    sx1, sx2 = cfx - 1, cfx + 1
                    self.stockpile(sx1, sz1, sx2, sz2, priority="Critical")
                    # Only accept raw food — no meals, no other items
                    self.set_stockpile_filter(
                        x=sx1, z=sz1, disallow_all=True,
                        allow=["RawBerries", "RawRice", "RawCorn", "RawPotatoes",
                               "Meat_Human", "Meat_Hare", "Meat_Turkey", "Meat_Deer",
                               "Meat_Elk", "Meat_Muffalo", "Meat_Squirrel", "Meat_Raccoon",
                               "Meat_Tortoise", "Meat_Megasloth", "Meat_Iguana", "Meat_Rat",
                               "Meat_Gazelle", "Meat_Caribou", "Meat_Alpaca"])
                    result["raw_food_stockpile"] = (sx1, sz1)
                    self._raw_food_stockpile_pos = (sx1, sz1)
                    print(f"  RAW FOOD STOCKPILE: Created Critical 3x1 at ({sx1},{sz1})-({sx2},{sz2}) "
                          f"adjacent to campfire at ({cfx},{cfz})")
                    break
                except Exception:
                    continue
            if not result["raw_food_stockpile"]:
                print(f"  RAW FOOD STOCKPILE: Failed to create adjacent to campfire")

        # Butcher spots — try near campfire or center
        anchor_x = result["campfire"][0] if result["campfire"] else cx + 5
        for dx in [2, -2, 3, -3]:
            try:
                self.build("ButcherSpot", anchor_x + dx, cz)
                result["butcher"] = (anchor_x + dx, cz)
                break
            except Exception:
                continue

        # Second butcher spot for throughput
        for dx in [-2, 2, -3, 3]:
            if result["butcher"] and (anchor_x + dx, cz) == result["butcher"]:
                continue
            try:
                self.build("ButcherSpot", anchor_x + dx, cz)
                break
            except Exception:
                continue

        # Add butcher bills IMMEDIATELY — ButcherSpot requires NO construction
        # (it's an instant "spot" placement), so bills can be active from tick 0.
        # This is the #1 pipeline compression: without this, corpses sit on the
        # ground for 6+ game hours until add_cooking_bills() runs after Phase 1 sleep.
        if result["butcher"]:
            try:
                self.add_bill("ButcherSpot", "ButcherCorpseFlesh")
                result["butcher_bill_immediate"] = True
                print(f"  BUTCHER BILL: Added immediately (no construction wait)")
            except Exception as e:
                result["butcher_bill_immediate"] = False
                print(f"  BUTCHER BILL: Immediate add failed: {e}")

        # Fueled stove — build on ALL maps for 2x cooking throughput.
        # FueledStove: 80 stuff, 0 components, no research, 100% cook speed.
        # Campfire is only 50% speed — the throughput ceiling on food missions.
        if getattr(self, '_food_scarce_mode', False):
            # Food-scarce: build with wood if we have enough (80 build + 40 fuel reserve)
            res = self.resources()
            wood = res.get("WoodLog", 0)
            if wood >= 120:
                for fdx in [4, -4, 6, -6, 3, -3]:
                    try:
                        self.build("FueledStove", anchor_x + fdx, cz, stuff="WoodLog")
                        result["stove"] = (anchor_x + fdx, cz)
                        print(f"  STOVE: FueledStove at ({anchor_x + fdx},{cz}) — 2x cooking speed")
                        break
                    except Exception:
                        continue
                if not result.get("stove"):
                    print("  STOVE: all positions blocked, campfire only")
            else:
                print(f"  STOVE SKIPPED: only {wood} wood (need 120+ for stove + fuel)")
        else:
            # Normal mode: build stove with default stuff
            for fdx in [4, -4, 6, -6, 3, -3]:
                try:
                    self.build("FueledStove", anchor_x + fdx, cz)
                    result["stove"] = (anchor_x + fdx, cz)
                    break
                except Exception:
                    continue

        # ── AGGRESSIVE BILL ADDITION (runs 9-13 fix) ──
        # The overseer DOES NOT use monitored_sleep() — it does time.sleep(20)
        # then add_cooking_bills(). This 20s real-time delay = 7+ game hours
        # without cooking bills, costing 40+ points.
        #
        # Fix: try adding bills NOW. If campfire was instant (noCost), succeed
        # immediately. If it's a blueprint, briefly unpause the game at speed 4
        # and poll every 2s until the campfire is constructed and bills are added.
        # Max wait: 12s real time (enough for any campfire to build at speed 4).
        #
        # This runs DURING the setup phase (game is normally paused). The brief
        # unpause lets colonists start construction while we wait. Hunting and
        # harvesting designations from day1_setup execute concurrently — that's
        # actually beneficial (berry + meat collection starts earlier).
        campfire_bill_added = False
        if result["campfire"]:
            # Attempt 1: try immediately (works if campfire is noCost / instant)
            try:
                self._cache.invalidate("read_buildings")
                self.add_bill("Campfire", "CookMealSimple")
                campfire_bill_added = True
                self._cooking_bills_added = True
                result["campfire_bill"] = True
                print(f"  CAMPFIRE BILL: Added immediately (instant campfire)")
            except Exception:
                # Campfire is a blueprint — needs construction first.
                # Unpause and wait for it to be built.
                print(f"  CAMPFIRE BILL: Campfire is blueprint, starting construction wait loop...")
                try:
                    self.unpause()
                    for attempt in range(6):  # 6 × 2s = 12s max
                        time.sleep(2)
                        self.pause()
                        try:
                            self._cache.invalidate("read_buildings")
                            self.add_bill("Campfire", "CookMealSimple")
                            campfire_bill_added = True
                            self._cooking_bills_added = True
                            result["campfire_bill"] = True
                            elapsed = (attempt + 1) * 2
                            print(f"  CAMPFIRE BILL: Added after {elapsed}s construction wait "
                                  f"(saved ~{20 - elapsed}s vs overseer's sleep(20))")
                            break
                        except Exception as e:
                            if attempt < 5:
                                self.unpause()
                            else:
                                print(f"  CAMPFIRE BILL: Still blueprint after 12s: {e}")
                    # Ensure game is paused when we return (other setup may follow)
                    try:
                        self.pause()
                    except Exception:
                        pass
                except Exception as e:
                    print(f"  CAMPFIRE BILL: Construction wait loop error: {e}")
                    try:
                        self.pause()
                    except Exception:
                        pass

        if not campfire_bill_added and result["campfire"]:
            result["campfire_bill"] = False
            print(f"  CAMPFIRE BILL: DEFERRED — campfire still building. "
                  f"add_cooking_bills() or monitored_sleep() must add bills later.")

        return result  # type: ignore[return-value]

    def setup_dining(self, cx: int, cz: int) -> SetupDiningResult:
        """Place table + 2 chairs. Returns {table: (x,z)|None, chairs: [(x,z),...]}.
        Table+chairs BEFORE walls in queue — prevents 'ate without table' penalty.

        FOOD-SCARCE SKIP (runs 9-11): On food-scarce maps, dining is SKIPPED entirely.
        Table (~45 wood) + 2 chairs (~70 wood) = ~115 wood consumed. This drains the
        campfire fuel supply, causing 5.8 game-hour bill delay (run 11). The -3 mood
        from 'ate without table' is negligible compared to starvation (-15 mood, 20 pts
        lost on no_starvation). Dining furniture is built later in Phase 2 barracks.
        """
        result: dict[str, Any] = {"table": None, "chairs": []}

        # SKIP dining on food-scarce maps — save ALL wood for campfire fuel
        if getattr(self, '_food_scarce_mode', False):
            print(f"  DINING SKIPPED: food-scarce mode — saving ~115 wood for campfire fuel "
                  f"(table+chairs not built). 'Ate without table' = -3 mood, acceptable.")
            result["skipped_food_scarce"] = True
            return result  # type: ignore[return-value]

        for tx, tz in [(cx, cz + 2), (cx, cz - 2), (cx + 2, cz), (cx - 2, cz),
                       (cx + 4, cz + 2), (cx - 4, cz - 2)]:
            try:
                self.build("Table1x2c", tx, tz, stuff="WoodLog")
                result["table"] = (tx, tz)
                break
            except Exception:
                continue

        if result["table"]:
            tx, tz = result["table"]
            for chair_dx in [-1, 1]:
                try:
                    self.build("DiningChair", tx + chair_dx, tz, stuff="WoodLog")
                    result["chairs"].append((tx + chair_dx, tz))
                except Exception:
                    continue

        return result  # type: ignore[return-value]

    def add_cooking_bills(self, retry: bool = False, max_retries: int = 8, retry_delay: int = 8) -> AddCookingBillsResult:
        """Check built cooking buildings and add missing bills. Idempotent.

        Args:
            retry: If True and no cooking station is found, wait and retry
                   up to max_retries times (for when campfire is still building).
                   Default 8 retries × 8s = 64s — covers campfire build time.
            max_retries: Max retry attempts when retry=True.
            retry_delay: Seconds between retries.
        Returns {campfire_bill: bool, butcher_bill: bool, stove_bill: bool}.
        """
        result: dict[str, Any] = {"campfire_bill": False, "butcher_bill": False, "stove_bill": False,
                  "buildings_found": []}

        attempts = max_retries if retry else 1
        for attempt in range(attempts):
            try:
                self._cache.invalidate("read_buildings")  # force fresh read
                buildings = self.buildings()
                blist = buildings.get("buildings", [])
                cooking_defs = ["Campfire", "ButcherSpot", "FueledStove", "ElectricStove"]
                result["buildings_found"] = [b.get("def") for b in blist
                                             if b.get("def") in cooking_defs]

                has_any_station = False
                if any(b.get("def") == "Campfire" for b in blist):
                    has_any_station = True
                    try:
                        self.add_bill("Campfire", "CookMealSimple")
                        result["campfire_bill"] = True
                    except Exception as e:
                        # DIAGNOSTIC: silent bill failures caused 6-hour gap in run 009.
                        # Log the error so next audit can pinpoint the C# failure mode.
                        print(f"  BILL FAIL: Campfire exists but add_bill threw: {e}")
                        result["campfire_bill_error"] = str(e)
                if any(b.get("def") == "ButcherSpot" for b in blist):
                    try:
                        self.add_bill("ButcherSpot", "ButcherCorpseFlesh")
                        result["butcher_bill"] = True
                    except Exception:
                        pass
                if any(b.get("def") == "FueledStove" for b in blist):
                    has_any_station = True
                    try:
                        self.add_bill("FueledStove", "CookMealSimple")
                        result["stove_bill"] = True
                    except Exception as e:
                        print(f"  BILL FAIL: FueledStove exists but add_bill threw: {e}")
                        result["stove_bill_error"] = str(e)
                if any(b.get("def") == "ElectricStove" for b in blist):
                    has_any_station = True
                    try:
                        self.add_bill("ElectricStove", "CookMealSimple")
                        result["electric_stove_bill"] = True
                    except Exception as e:
                        print(f"  BILL FAIL: ElectricStove exists but add_bill threw: {e}")
                        result["electric_stove_bill_error"] = str(e)

                # If we found a station and added at least one bill, done
                if has_any_station and (result["campfire_bill"] or result["stove_bill"] or result.get("electric_stove_bill")):
                    break
                # Station found but ALL bill adds failed — retry (might be fuel/timing issue)
                if has_any_station and not result["campfire_bill"] and not result["stove_bill"] and not result.get("electric_stove_bill"):
                    if retry and attempt < attempts - 1:
                        print(f"  add_cooking_bills: station exists but bills failed (attempt {attempt+1}/{attempts}), retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                # If no station found and retrying, wait for construction to finish
                if not has_any_station and retry and attempt < attempts - 1:
                    print(f"  add_cooking_bills: no cooking station yet (attempt {attempt+1}/{attempts}), waiting {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                break  # station exists but bill add failed, or no retries
            except Exception:
                if retry and attempt < attempts - 1:
                    time.sleep(retry_delay)
                    continue
                break

        return result  # type: ignore[return-value]

    def setup_zones(self, cx: int, cz: int) -> SetupZonesResult:
        """Place main stockpile, food stockpile, dump zone, grow zone.
        Returns {main: (x1,z1)|None, food: (x1,z1)|None, dump: (x1,z1)|None, grow: (x1,z1)|None}.
        """
        result: dict[str, Any] = {"main": None, "food": None, "dump": None, "grow": None}

        # Main stockpile — size depends on map size.
        # On 50×50 maps: 20×20 stockpile at center covers (15,15)-(34,34) = 357 cells,
        # which ENTIRELY overlaps the barracks build area, blocking ALL interior
        # placement (door, beds, furniture, sculptures). This is a 5-run-old bug
        # (runs 1, 3, 4, 8, 9). Fix: use 10×10 on small maps (≤75×75).
        # On larger maps (250×250): 20×20 is fine, plenty of room for buildings.
        # Delete ALL existing zones at center first (temp stockpile, prior zones)
        for dx, dz in [(0, 0), (1, 1), (-1, -1), (3, 3), (-3, -3), (5, 5), (-5, -5), (8, 0), (0, 8)]:
            try:
                self.delete_zone(cx + dx, cz + dz)
            except Exception:
                pass
        try:
            mi = self.map_info()
            ms = mi.get("size", {})
            mw = (ms.get("x", 250) if isinstance(ms, dict) else 250)
        except Exception:
            mw = 250
        if mw <= 75:
            # Small map: 10×10 stockpile (100 cells) offset from center
            # Place it NORTH of center so barracks can be built AT center
            sp_half = 5
            sx1, sz1 = cx - sp_half, cz - sp_half - 8  # 8 tiles north of center
            sp_size = sp_half * 2 - 1  # 9 → 10×10
            print(f"  ZONES: Small map ({mw}×{mw}) → 10×10 stockpile at ({sx1},{sz1})")
        else:
            sp_half = 10
            sx1, sz1 = cx - sp_half, cz - sp_half
            sp_size = sp_half * 2 - 1  # 19 → 20×20
        try:
            resp = self.stockpile(sx1, sz1, sx1 + sp_size, sz1 + sp_size, priority="Important")
            # I-036 observability: log actual cell count from C# response
            cells_created = resp.get("cells", 0) if isinstance(resp, dict) else 0
            cells_skipped = resp.get("skipped", 0) if isinstance(resp, dict) else 0
            result["main_cells"] = cells_created
            result["main_skipped"] = cells_skipped
            if cells_created < 100:
                result["main_warning"] = f"Only {cells_created} cells created ({cells_skipped} skipped)!"
            try:
                self.set_stockpile_filter(x=sx1, z=sz1, allow_all=True, disallow=["StoneChunks"])
            except Exception:
                pass
            result["main"] = (sx1, sz1)
        except Exception as e:
            result["main_error"] = str(e)

        # Food stockpile — NOT created here. Main stockpile handles food initially.
        # secure_food_stockpile() creates a Critical indoor food zone in Phase 2.
        # Previously this placed food at (cx+15, cz+5) which on small maps lands
        # at the map edge (40,30), exposed to wild animals. The main stockpile
        # (Important priority, centered) is safer and closer to cooking stations.
        result["food"] = None  # will be set by secure_food_stockpile()

        # Dump zone for stone chunks only
        try:
            self.stockpile(cx - 40, cz - 40, cx - 33, cz - 33, priority="Low")
            try:
                self.set_stockpile_filter(x=cx - 40, z=cz - 40, disallow_all=True, allow=["StoneChunks"])
            except Exception:
                pass
            result["dump"] = (cx - 40, cz - 40)
        except Exception:
            pass

        # Grow zone — SKIP on food-scarce maps (runs 003-004 fix).
        # Rice takes 5.5 days to mature. On food-scarce scenarios (~5 day duration),
        # it NEVER produces food. But the grow zone generates CutPlant:TallGrass and
        # CutPlant:ChoppedStump clearing jobs that compete with berry harvesting in
        # the PlantCutting queue, AND sowing labor diverts the cook from cooking.
        # This was the #1 unapplied fix from run 003 audit (71.1% → identical 71.2%).
        if getattr(self, '_food_scarce_mode', False):
            print(f"  ZONES: SKIPPING grow zone (food-scarce mode — rice cannot mature in time)")
            result["grow"] = None
            result["grow_skipped"] = "food_scarce_mode"
        else:
            try:
                spot = self.find_grow_spot(size=10, radius=40, cx=cx, cz=cz)
                self.grow_zone(spot["x1"], spot["z1"], spot["x2"], spot["z2"], plant="Plant_Rice")
                result["grow"] = (spot["x1"], spot["z1"])
            except Exception:
                pass

        return result  # type: ignore[return-value]

    def secure_food_stockpile(self, bx: int, bz: int, bx2: int, bz2: int) -> SecureFoodStockpileResult:
        """Create a Critical-priority food stockpile inside an enclosed room.

        APPROACH (run 007 fix): The main stockpile (20x20) overlaps the barracks
        interior. C# skips cells already claimed by another zone, so ALL food zone
        candidates inside the barracks get 0 cells. Fix: DELETE the main stockpile
        first, create the food zone (cells are now unclaimed), then RECREATE the
        main stockpile (it naturally skips the food zone's cells).

        This solves the 3-run recurring bug (runs 004, 005, 007) where the food
        zone either fails to create or lands in the wrong room with wrong priority.

        Args:
            bx, bz: room top-left corner (from build_barracks)
            bx2, bz2: room bottom-right corner (from build_barracks)
        Returns:
            dict with food stockpile position or error
        """
        result: dict[str, Any] = {}
        print(f"  secure_food_stockpile: room bounds ({bx},{bz})-({bx2},{bz2})")

        # ── STEP 1: Find and DELETE the main stockpile ──
        # The main stockpile (20x20, Important) covers the barracks interior.
        # We must remove it so the food zone can claim those cells.
        main_info = None
        try:
            zones_data = self.zones()
            main_zone = None
            main_cells = 0
            for z in zones_data.get("zones", []):
                if not isinstance(z, dict):
                    continue
                ztype = z.get("type", "")
                if "stockpile" not in ztype.lower() and "Stockpile" not in ztype:
                    continue
                zcells = z.get("cellCount", z.get("cells", 0))
                if zcells > main_cells:
                    main_cells = zcells
                    main_zone = z

            if main_zone:
                bounds = main_zone.get("bounds", {})
                main_info = {
                    "label": main_zone.get("label", ""),
                    "x1": bounds.get("minX", -1),
                    "z1": bounds.get("minZ", -1),
                    "x2": bounds.get("maxX", -1),
                    "z2": bounds.get("maxZ", -1),
                    "cells": main_cells,
                }
                # Delete the main stockpile — try multiple positions
                deleted = False
                del_positions = [
                    (main_info["x1"], main_info["z1"]),
                    (main_info["x1"] + 1, main_info["z1"] + 1),
                    ((main_info["x1"] + main_info["x2"]) // 2,
                     (main_info["z1"] + main_info["z2"]) // 2),
                ]
                for dx, dz in del_positions:
                    try:
                        self.delete_zone(dx, dz)
                        deleted = True
                        print(f"  DELETED main stockpile '{main_info['label']}' "
                              f"({main_cells} cells) at ({dx},{dz})")
                        break
                    except Exception:
                        continue
                if not deleted:
                    print(f"  WARNING: could not delete main stockpile — "
                          f"food zone may get 0 cells")
            else:
                print(f"  NOTE: no main stockpile found to delete")
        except Exception as e:
            print(f"  Main stockpile lookup failed: {e}")

        # Also clean up stale small outdoor food zones from previous runs
        try:
            zones_data = self.zones()
            for z in zones_data.get("zones", []):
                if not isinstance(z, dict):
                    continue
                ztype = z.get("type", "")
                if "stockpile" not in ztype.lower() and "Stockpile" not in ztype:
                    continue
                zcells = z.get("cellCount", z.get("cells", 999))
                if zcells < 30:
                    zb = z.get("bounds", {})
                    zx = zb.get("minX", z.get("x", -1))
                    zz = zb.get("minZ", z.get("z", -1))
                    if zx >= 0 and zz >= 0:
                        try:
                            self.delete_zone(zx, zz)
                            print(f"  Deleted stale small zone at ({zx},{zz}), "
                                  f"{zcells} cells")
                        except Exception:
                            pass
        except Exception:
            pass

        # ── STEP 2: Create food zone inside the barracks ──
        # Cells are now unclaimed (main stockpile deleted). This WILL succeed.
        food_placed = False
        food_zone_label = None
        candidates = [
            # Full interior row (most cells = most food capacity)
            (bx + 1, bz + 1, bx2 - 1, bz + 1),                   # top row
            (bx + 1, bz2 - 1, bx2 - 1, bz2 - 1),                 # bottom row
            # Half-interior strips
            (bx + 1, bz + 1, bx + 3, bz + 1),                    # top-left 3x1
            (bx + 1, bz + 1, bx + 2, min(bz + 3, bz2 - 1)),     # left 2-col
            (bx2 - 2, bz + 1, bx2 - 1, min(bz + 3, bz2 - 1)),   # right 2-col
            # Small 2x1 zones
            (bx + 2, bz + 1, bx + 3, bz + 1),
            (bx + 2, bz2 - 1, bx + 3, bz2 - 1),
            # Single cell fallbacks
            (bx + 1, bz + 1, bx + 1, bz + 1),
            (bx + 2, bz + 1, bx + 2, bz + 1),
            (bx + 3, bz + 1, bx + 3, bz + 1),
            (bx2 - 1, bz2 - 1, bx2 - 1, bz2 - 1),
        ]
        for fx1, fz1, fx2, fz2 in candidates:
            try:
                resp = self.stockpile(fx1, fz1, fx2, fz2, priority="Critical")
                actual_cells = resp.get("cells", 0) if isinstance(resp, dict) else 0
                actual_prio = resp.get("priority", "?") if isinstance(resp, dict) else "?"
                food_zone_label = resp.get("label", None) if isinstance(resp, dict) else None
                if actual_cells == 0:
                    print(f"  Food zone at ({fx1},{fz1})-({fx2},{fz2}): "
                          f"0 cells (skipped), trying next")
                    continue
                # Set food-only filter + Critical priority
                filter_kw = {"disallow_all": True,
                             "allow": ["MeatRaw", "PlantFoodRaw", "Foods"],
                             "priority": "Critical"}
                if food_zone_label:
                    self.set_stockpile_filter(zone=food_zone_label, **filter_kw)
                else:
                    self.set_stockpile_filter(x=fx1, z=fz1, **filter_kw)
                result["food"] = (fx1, fz1)
                result["bounds"] = (fx1, fz1, fx2, fz2)
                result["zone_label"] = food_zone_label
                result["actual_priority"] = actual_prio
                food_placed = True
                inside = fx1 >= bx and fz1 >= bz and fx2 <= bx2 and fz2 <= bz2
                print(f"  FOOD SECURED: '{food_zone_label}' at ({fx1},{fz1})-"
                      f"({fx2},{fz2}), {actual_cells} cells, "
                      f"priority={actual_prio}, inside={inside}")
                break
            except Exception:
                continue
        if not food_placed:
            # Last resort: adjacent to room
            for fx1, fz1, fx2, fz2 in [
                (bx + 1, bz - 2, bx + 4, bz - 1),
                (bx + 1, bz2 + 1, bx + 4, bz2 + 2),
            ]:
                try:
                    resp = self.stockpile(fx1, fz1, fx2, fz2, priority="Critical")
                    food_zone_label = resp.get("label", None) if isinstance(resp, dict) else None
                    filter_kw = {"disallow_all": True,
                                 "allow": ["MeatRaw", "PlantFoodRaw", "Foods"],
                                 "priority": "Critical"}
                    if food_zone_label:
                        self.set_stockpile_filter(zone=food_zone_label, **filter_kw)
                    else:
                        self.set_stockpile_filter(x=fx1, z=fz1, **filter_kw)
                    result["food"] = (fx1, fz1)
                    result["bounds"] = (fx1, fz1, fx2, fz2)
                    result["zone_label"] = food_zone_label
                    food_placed = True
                    print(f"  FOOD FALLBACK: '{food_zone_label}' at ({fx1},{fz1})-"
                          f"({fx2},{fz2}) adjacent to room")
                    break
                except Exception:
                    continue
        if not food_placed:
            result["error"] = "all food stockpile positions failed"
            print(f"  WARNING: failed to create indoor food stockpile")

        # ── STEP 3: Recreate the main stockpile ──
        # It will naturally skip cells already claimed by the food zone.
        # Food categories are excluded so colonists ONLY haul food to the
        # Critical indoor zone, never to the main outdoor stockpile.
        if main_info and main_info.get("x1", -1) >= 0:
            try:
                resp = self.stockpile(main_info["x1"], main_info["z1"],
                                      main_info["x2"], main_info["z2"],
                                      priority="Important")
                new_cells = resp.get("cells", 0) if isinstance(resp, dict) else 0
                new_label = resp.get("label", "") if isinstance(resp, dict) else ""
                skipped = main_info["cells"] - new_cells
                print(f"  MAIN RECREATED: '{new_label}' {new_cells} cells "
                      f"(was {main_info['cells']}, {skipped} now food zone)")

                # Exclude food + stone chunks from main stockpile
                try:
                    filter_kw2 = {"allow_all": True,
                                  "disallow": ["StoneChunks", "MeatRaw",
                                               "PlantFoodRaw", "Foods"]}
                    if new_label:
                        self.set_stockpile_filter(zone=new_label, **filter_kw2)
                    else:
                        self.set_stockpile_filter(x=main_info["x1"],
                                                  z=main_info["z1"],
                                                  **filter_kw2)
                    print(f"  MAIN FILTER: excluded food + stone chunks")
                except Exception as e:
                    print(f"  WARNING: main stockpile filter failed: {e}")
            except Exception as e:
                print(f"  WARNING: main stockpile recreation failed: {e}")
                result["main_recreate_error"] = str(e)
        elif not main_info:
            print(f"  NOTE: no main stockpile to recreate (none was deleted)")

        return result  # type: ignore[return-value]

    def build_barracks(self, cx: int, cz: int, material: str = "Steel") -> BuildBarracksResult:
        """Build 7x6 barracks: walls + door + 3 beds + 2 endtables + dresser + 2 torchLamps + indoor campfire + sculpture + floor.
        Enlarged from 7x5 to 7x6 (5x4 interior) to guarantee room for sculpture.
        Returns {x1, z1, x2, z2, built: [...], failed: [...]}.
        """
        result: dict[str, Any] = {"x1": 0, "z1": 0, "x2": 0, "z2": 0, "built": [], "failed": []}

        # Find clear area (7x6 — 5x4 interior guarantees room for sculpture)
        try:
            spot = self.find_clear_rect(width=7, height=6, cx=cx, cz=cz, radius=20)
            bx, bz = spot["x1"], spot["z1"]
        except Exception:
            bx, bz = cx - 8, cz - 5

        result["x1"], result["z1"] = bx, bz
        result["x2"], result["z2"] = bx + 6, bz + 5

        def _try(label, fn):
            try:
                fn()
                result["built"].append(label)
            except Exception:
                result["failed"].append(label)

        # ── ZONE CLEARING (9-run recurring fix) ──
        # C# Build command refuses to place buildings on zone cells. The stockpile
        # zone from setup_zones() often extends into the barracks footprint,
        # blocking north wall placement. Clear ALL zone cells in the barracks
        # footprint before placing walls. This is the single fix for the
        # "rooms=[] across all snapshots" bug that has recurred for 9 runs.
        try:
            self.remove_zone_cells(bx, bz, bx + 6, bz + 5)
            print(f"  BARRACKS: Cleared zone cells in footprint ({bx},{bz})-({bx+6},{bz+5})")
        except Exception as e:
            print(f"  BARRACKS: Zone clear attempt: {e}")

        # Walls via batch (7x6 exterior) — SKIP DOOR POSITION
        # 8-run recurring bug: wall placed at (bx+3, bz) then door fails with
        # "existing blueprint/frame has Blueprint_Wall". Fix: exclude the door cell.
        door_pos = (bx + 3, bz)
        wall_positions = []
        for x in range(bx, bx + 7):
            if (x, bz) != door_pos:
                wall_positions.append((x, bz))
            wall_positions.append((x, bz + 5))
        for z in [bz + 1, bz + 2, bz + 3, bz + 4]:
            wall_positions += [(bx, z), (bx + 6, z)]
        cmds = [("build", {"blueprint": "Wall", "x": x, "y": z, "stuff": material}) for x, z in wall_positions]
        _, errs = self.send_batch_lenient(cmds)
        result["built"].append(f"walls({len(cmds)-errs}/{len(cmds)})")

        # If walls had errors, retry individually to diagnose which ones failed
        if errs > 0:
            retry_count = 0
            for x, z in wall_positions:
                try:
                    self.build("Wall", x, z, stuff=material)
                    retry_count += 1
                except Exception:
                    pass
            if retry_count > 0:
                result["built"].append(f"wall_retries({retry_count})")
                print(f"  BARRACKS: Retried individual walls, {retry_count} additional placed")

        # ── WOOD FUEL PRESERVATION (runs 9-12 fix) ──
        # On food-scarce maps, ALL furniture/door/floor MUST use Steel/Concrete
        # instead of WoodLog. This is the #1 food pipeline fix:
        # Runs 9-12: all 277 starting wood consumed by blueprint reservations
        # (beds=150w, door=25w, endtables=50w, dresser=50w, floor=60w = 335w total).
        # Campfire built at d1h8.4 but zero fuel → first meal at d1h19.9 (11.5h delay).
        # With Steel furniture: 0 wood consumed → 277+ wood available for campfire fuel
        # → first meal within ~1h of campfire completion → 15-20 meals (vs 6).
        furniture_stuff = "Steel" if getattr(self, '_food_scarce_mode', False) else "WoodLog"
        floor_type = "Concrete" if getattr(self, '_food_scarce_mode', False) else "WoodPlankFloor"
        if furniture_stuff == "Steel":
            print(f"  BARRACKS: Steel furniture + Concrete floor (food-scarce: preserving ALL wood for campfire fuel)")

        # Door on south wall center
        _try("door", lambda: self.build("Door", bx + 3, bz, stuff=furniture_stuff))

        # Sculpture FIRST — biggest single impressiveness boost (~+15-20)
        # Must go before beds/furniture to claim a free cell.
        # Interior cells: bx+1..bx+5, bz+1..bz+4 (5x4 = 20 cells).
        # Try Steel first — wood often runs out during construction.
        sculpture_placed = False
        sculpture_errors = []
        for stuff in ["Steel", "WoodLog"]:
            for sx, sz in [(bx + 4, bz + 2), (bx + 5, bz + 2), (bx + 4, bz + 1),
                            (bx + 2, bz + 1), (bx + 3, bz + 1), (bx + 5, bz + 1),
                            (bx + 1, bz + 1), (bx + 4, bz + 4), (bx + 5, bz + 4),
                            (bx + 1, bz + 4), (bx + 2, bz + 4), (bx + 3, bz + 4),
                            (bx + 1, bz + 2), (bx + 2, bz + 2), (bx + 3, bz + 2),
                            # Outside barracks fallbacks (adjacent to door)
                            (bx + 3, bz - 1), (bx + 4, bz - 1),
                            (bx + 2, bz - 1), (bx + 3, bz + 6)]:
                try:
                    self.build("SculptureSmall", sx, sz, stuff=stuff)
                    result["built"].append(f"sculpture({stuff}@{sx},{sz})")
                    sculpture_placed = True
                    print(f"  SCULPTURE placed at ({sx},{sz}) stuff={stuff}")
                    break
                except Exception as e:
                    sculpture_errors.append(f"({sx},{sz})/{stuff}: {e}")
                    continue
            if sculpture_placed:
                break
        if not sculpture_placed:
            result["failed"].append("sculpture")
            # Log ALL errors so auditor can diagnose the root cause
            print(f"  WARNING: SculptureSmall failed at ALL {len(sculpture_errors)} positions:")
            for err in sculpture_errors[:6]:
                print(f"    {err}")

        # 3 beds along middle row
        for i, bed_x in enumerate([bx + 1, bx + 2, bx + 3]):
            _try(f"bed{i+1}", lambda bx_=bed_x: self.build("Bed", bx_, bz + 3, stuff=furniture_stuff))

        # Furniture — push impressiveness ≥30
        _try("endtable1", lambda: self.build("EndTable", bx + 4, bz + 4, stuff=furniture_stuff))
        _try("endtable2", lambda: self.build("EndTable", bx + 1, bz + 2, stuff=furniture_stuff))
        _try("torchlamp1", lambda: self.build("TorchLamp", bx + 5, bz + 1))
        _try("torchlamp2", lambda: self.build("TorchLamp", bx + 5, bz + 4))
        _try("dresser", lambda: self.build("Dresser", bx + 4, bz + 3, stuff=furniture_stuff))
        _try("indoor_campfire", lambda: self.build("Campfire", bx + 5, bz + 3))

        # Floor (covers full 5x4 interior)
        # food-scarce: Concrete (uses steel, no wood) vs WoodPlankFloor
        try:
            self.floor(floor_type, bx + 1, bz + 1, bx + 5, bz + 4)
            result["built"].append(f"floor({floor_type})")
        except Exception:
            result["failed"].append("floor")

        # Store barracks bounds for colony_health_check() auto-food-stockpile
        self._barracks_bounds = {"x1": bx, "z1": bz, "x2": bx + 6, "z2": bz + 5}

        return result  # type: ignore[return-value]

    def build_storage_room(self, cx: int, cz: int, material: str = "WoodLog") -> BuildStorageRoomResult:
        """Build 7x5 storage room with interior stockpile zone + furniture.
        WoodLog walls by default — saves steel for barracks. If wood < 100,
        auto-switches to Steel to preserve campfire fuel.
        Returns {x1, z1, x2, z2, built: [...], failed: [...]}.
        """
        result: dict[str, Any] = {"x1": 0, "z1": 0, "x2": 0, "z2": 0, "built": [], "failed": []}

        # Wood fuel reservation: storage room walls use ~100 wood (20 segments × 5).
        # Campfire needs ~5 wood/refuel. With 256 starting wood, building storage room
        # walls + barracks flooring + other builds depletes ALL wood, causing 18+ game
        # hours of zero cooking fuel. Switch to Steel when wood < 300 (keeps ~100+ for fuel).
        # Steel is always abundant (1000+) in crash-landed scenarios.
        if material == "WoodLog":
            try:
                res = self.resources()
                wood = res.get("WoodLog", 0)
                steel = res.get("Steel", 0)
                if wood < 300 and steel >= 200:
                    material = "Steel"
                    result["material_override"] = f"WoodLog->Steel (wood={wood}<300, preserving campfire fuel)"
                    print(f"  build_storage_room: switching to Steel walls (wood={wood} < 300, steel={steel}, preserving campfire fuel)")
            except Exception:
                pass

        try:
            sspot = self.find_clear_rect(width=7, height=5, cx=cx, cz=cz - 10, radius=25)
            srx, srz = sspot["x1"], sspot["z1"]
        except Exception:
            srx, srz = cx + 10, cz - 10

        result["x1"], result["z1"] = srx, srz
        result["x2"], result["z2"] = srx + 6, srz + 4

        # Clear zone cells in storage room footprint (same fix as barracks)
        try:
            self.remove_zone_cells(srx, srz, srx + 6, srz + 4)
        except Exception:
            pass

        def _try(label, fn):
            try:
                fn()
                result["built"].append(label)
            except Exception:
                result["failed"].append(label)

        # Walls — SKIP DOOR POSITION (same fix as barracks: wall at door cell blocks door placement)
        sr_door_pos = (srx + 3, srz)
        sr_walls = []
        for x in range(srx, srx + 7):
            if (x, srz) != sr_door_pos:
                sr_walls.append((x, srz))
            sr_walls.append((x, srz + 4))
        for z in [srz + 1, srz + 2, srz + 3]:
            sr_walls += [(srx, z), (srx + 6, z)]
        scmds = [("build", {"blueprint": "Wall", "x": x, "y": z, "stuff": material}) for x, z in sr_walls]
        _, errs = self.send_batch_lenient(scmds)
        result["built"].append(f"walls({len(scmds)-errs}/{len(scmds)})")

        # Door — Steel in food-scarce mode (preserve wood for campfire fuel)
        storage_door_stuff = "Steel" if getattr(self, '_food_scarce_mode', False) else "WoodLog"
        _try("door", lambda: self.build("Door", srx + 3, srz, stuff=storage_door_stuff))

        # Minimal furniture — TorchLamp boosts impressiveness cheaply (prevents negative avg)
        _try("torchlamp", lambda: self.build("TorchLamp", srx + 1, srz + 1))

        # Floor — Concrete in food-scarce mode (no wood), WoodPlankFloor otherwise
        storage_floor = "Concrete" if getattr(self, '_food_scarce_mode', False) else "WoodPlankFloor"
        try:
            self.floor(storage_floor, srx + 1, srz + 1, srx + 5, srz + 3)
            result["built"].append(f"floor({storage_floor})")
        except Exception:
            result["failed"].append("floor")

        # Interior stockpile zone — needed for storage_room score
        # Whitelist only clean items to prevent ugly stuff tanking impressiveness
        try:
            self.stockpile(srx + 1, srz + 1, srx + 5, srz + 3, priority="Normal")
            try:
                self.set_stockpile_filter(x=srx + 1, z=srz + 1,
                                          disallow_all=True,
                                          allow=["MedicineHerbal", "MedicineIndustrial",
                                                 "MealSimple", "MealFine", "MealSurvivalPack",
                                                 "Silver", "Gold", "Steel", "ComponentIndustrial"])
            except Exception:
                pass
            result["built"].append("stockpile_zone")
        except Exception:
            result["failed"].append("stockpile_zone")

        return result  # type: ignore[return-value]

    def setup_recreation(self, cx: int, cz: int) -> SetupRecreationResult:
        """Place HorseshoesPin with fallback positions.
        Returns {horseshoes: (x,z)|None}.
        """
        result: dict[str, Any] = {"horseshoes": None}
        for hx, hz in [(cx + 3, cz + 3), (cx - 3, cz - 3), (cx + 6, cz),
                        (cx, cz + 6), (cx + 8, cz + 8)]:
            try:
                self.build("HorseshoesPin", hx, hz)
                result["horseshoes"] = (hx, hz)
                break
            except Exception:
                continue
        return result  # type: ignore[return-value]

    def setup_production(self, cx: int, cz: int, bx: int, bz: int, sx: int | None = None, sz: int | None = None) -> SetupProductionResult:
        """Place research bench + tailoring bench.

        bx,bz = barracks origin. sx,sz = storage room origin (optional).
        If storage room coords provided, tries placing benches INSIDE the
        storage room first (roofed = research speed bonus).
        Returns {research_bench: (x,z)|None, tailoring_bench: (x,z)|None}.
        """
        result: dict[str, Any] = {"research_bench": None, "tailoring_bench": None}

        # Build position lists — prioritize inside storage room if available
        research_positions = []
        tailoring_positions = []
        if sx is not None and sz is not None:
            # Inside storage room (7x5 room, interior is sx+1..sx+5, sz+1..sz+3)
            research_positions += [(sx + 1, sz + 2), (sx + 3, sz + 2), (sx + 2, sz + 1)]
            tailoring_positions += [(sx + 4, sz + 2), (sx + 2, sz + 3), (sx + 4, sz + 1)]
        # Fallback: near barracks (outdoor)
        research_positions += [
            (bx - 3, bz + 2), (bx + 9, bz + 2), (bx - 3, bz - 2),
            (bx + 9, bz - 2), (bx - 5, bz), (bx + 11, bz),
            (bx - 3, bz + 6), (bx + 9, bz + 6)]
        tailoring_positions += [
            (bx + 9, bz - 2), (bx - 3, bz + 6), (bx + 9, bz + 6),
            (bx - 5, bz + 2), (bx + 11, bz + 2), (bx - 3, bz - 3),
            (bx + 9, bz - 4), (bx - 5, bz + 6), (bx + 11, bz + 6)]

        # Research bench
        for rx, rz in research_positions:
            try:
                self.build("SimpleResearchBench", rx, rz, stuff="Steel")
                result["research_bench"] = (rx, rz)
                break
            except Exception:
                continue

        # HandTailoringBench — Steel in food-scarce mode (preserve wood for campfire fuel)
        tailoring_stuff = "Steel" if getattr(self, '_food_scarce_mode', False) else "WoodLog"
        for tx, tz in tailoring_positions:
            if result["research_bench"] == (tx, tz):
                continue
            try:
                self.build("HandTailoringBench", tx, tz, stuff=tailoring_stuff)
                result["tailoring_bench"] = (tx, tz)
                break
            except Exception:
                continue

        return result  # type: ignore[return-value]

    def monitored_sleep(self, duration: float, check_interval: float = 5) -> MonitoredSleepResult:
        """Unpause and sleep for *duration* seconds, pausing every *check_interval*
        to add cooking bills as soon as the campfire finishes building.

        check_interval=5 (was 10): campfire finishes at ~10-15s. With 5s checks,
        bills are added within 5s of campfire completion. This eliminates the
        catastrophic window where 57 raw meat was consumed raw (0.05 nutrition each)
        before cooking bills activated (audit: bills gap = single biggest food loss).

        Also tries adding bills PRE-EMPTIVELY before the first unpause — if the
        campfire was somehow already built during the setup phase, bills activate at t=0.

        After bills are added, also re-designates harvest to ensure berry bushes
        are being actively cut (food pipeline compression).

        Returns dict with {bills_added, elapsed_when_added, bill_result}.
        Game is PAUSED when this method returns.
        """
        import math
        iterations = max(1, int(math.ceil(duration / check_interval)))
        actual_interval = duration / iterations

        bills_added = False
        bill_result = {}

        # PRE-EMPTIVE bills attempt: try adding bills BEFORE first unpause.
        # If campfire was pre-built or instant, this activates cooking at t=0.
        try:
            self._cache.invalidate("read_buildings")
            bill_result = self.add_cooking_bills(retry=False)
            if bill_result.get("campfire_bill") or bill_result.get("stove_bill"):
                bills_added = True
                print(f"  MONITORED: Pre-emptive bills SUCCESS — cooking active before unpause!")
        except Exception:
            pass

        self.unpause()

        for i in range(iterations):
            time.sleep(actual_interval)
            self.pause()

            # Try to add cooking bills if not already done
            if not bills_added:
                try:
                    self._cache.invalidate("read_buildings")
                    bill_result = self.add_cooking_bills(retry=False)
                    if bill_result.get("campfire_bill") or bill_result.get("stove_bill"):
                        bills_added = True
                        elapsed = actual_interval * (i + 1)
                        print(f"  MONITORED: Cooking bills added at {elapsed:.0f}s/{duration:.0f}s "
                              f"(saved ~{duration - elapsed:.0f}s of idle campfire)")
                        # ── PIPELINE COMPRESSION (runs 9-11 fix) ──
                        # When bills activate, do 4 things to maximize food throughput:
                        # 1. Cancel ALL chop designations (free PlantCutting for berries)
                        # 2. Re-designate harvest (berry bushes)
                        # 3. Re-designate hunting (more raw ingredients)
                        # 4. Force cook priority (prevent TendPatient/Skygaze stealing cook labor)
                        try:
                            mi = self.map_info()
                            msz = mi.get("size", {})
                            mcx = (msz.get("x", 250) if isinstance(msz, dict) else 250) // 2
                            mcz = (msz.get("z", 250) if isinstance(msz, dict) else 250) // 2
                            mx = (msz.get("x", 250) if isinstance(msz, dict) else 250)
                            mz = (msz.get("z", 250) if isinstance(msz, dict) else 250)
                            # 1. Cancel ALL tree-chop designations
                            try:
                                cancel_result = self.cancel_designations(0, 0, mx, mz, kind="chop")
                                cancelled = cancel_result.get("cancelled", 0) if isinstance(cancel_result, dict) else 0
                                if cancelled > 0:
                                    print(f"  MONITORED: Cancelled {cancelled} chop designations → PlantCutting queue clear for berries")
                            except Exception:
                                pass
                            # 2. Re-designate harvest
                            self.harvest(mcx, mcz, radius=max(mx, mz))
                            print(f"  MONITORED: Re-designated harvest after bills activated")
                        except Exception:
                            pass
                        # 3. Re-designate hunting
                        try:
                            self.hunt_all_wildlife()
                        except Exception:
                            pass
                        # 4. Force cook to COOK — not TendPatient/Skygaze
                        # Run 11: Benjamin idle 3.8 game hours after bills activated
                        # (TendPatient, Skygaze, HaulToCell) before first DoBill.
                        # Fix: Cooking=1, Doctor=4 so cooking always beats tending.
                        cook_name = getattr(self, '_cook_name', None)
                        if cook_name:
                            try:
                                self.set_priority(cook_name, "Cooking", 1)
                                self.set_priority(cook_name, "Doctor", 4)
                                self.set_priority(cook_name, "Hauling", 3)
                                print(f"  MONITORED: Forced {cook_name} Cooking=1, Doctor=4 → cook will prioritize cooking over tending")
                            except Exception:
                                pass
                    elif bill_result.get("buildings_found"):
                        # Station exists but bill add FAILED. Check if wood=0
                        # (campfire needs fuel to cook). Trigger emergency micro-chop.
                        elapsed = actual_interval * (i + 1)
                        errors = [bill_result.get("campfire_bill_error", ""),
                                  bill_result.get("stove_bill_error", "")]
                        err_str = "; ".join(e for e in errors if e)
                        print(f"  MONITORED: Station found ({bill_result['buildings_found']}) "
                              f"but bills FAILED at {elapsed:.0f}s/{duration:.0f}s"
                              + (f" errors=[{err_str}]" if err_str else ""))
                        # Emergency fuel: if wood=0 and we have a campfire/stove,
                        # chop 2-3 nearby trees so fuel arrives ASAP
                        try:
                            self._cache.invalidate("read_resources")
                            res = self.resources()
                            wood = res.get("WoodLog", 0)
                            if wood < 30:
                                mi = self.map_info()
                                msz = mi.get("size", {})
                                mcx = (msz.get("x", 250) if isinstance(msz, dict) else 250) // 2
                                mcz = (msz.get("z", 250) if isinstance(msz, dict) else 250) // 2
                                self.chop(mcx, mcz, radius=3, _force=True)  # micro-chop: bypass _chop_blocked
                                print(f"  MONITORED: Emergency fuel chop (wood={wood}, radius=3)")
                        except Exception:
                            pass
                except Exception:
                    pass

            # Continue running for remaining intervals
            if i < iterations - 1:
                self.unpause()

        # Game is now paused
        if not bills_added:
            print(f"  MONITORED: No cooking station built after {duration:.0f}s — bills deferred")

        return {"bills_added": bills_added, "bill_result": bill_result}

    def reach_distant_berries(self) -> dict[str, Any]:
        """Find unharvested berry bushes on the map and draft+move colonists to reach them.

        The core 8-run problem: harvest(radius=50) designates all bushes but colonists
        always pick the nearest PlantCutting task. Distant edge bushes (>15 tiles from
        center) never get harvested because colonists get interrupted (eating, hauling,
        sleeping) before walking 20+ tiles.

        Fix: scan map tiles for harvestable Plant_Berry, find the most distant ones,
        draft a non-cook colonist, move them RIGHT NEXT to the bush, then undraft.
        The colonist's nearest PlantCutting task is now the berry bush they're standing on.

        Returns {bushes_found, bushes_targeted, colonists_moved}.
        """
        result: dict[str, Any] = {"bushes_found": 0, "bushes_targeted": 0,
                                   "colonists_moved": [], "errors": []}
        try:
            mi = self.map_info()
            msz = mi.get("size", {})
            mx = msz.get("x", 50) if isinstance(msz, dict) else 50
            mz = msz.get("z", 50) if isinstance(msz, dict) else 50
            map_cx, map_cz = mx // 2, mz // 2

            # Scan map for Plant_Berry things
            tiles = self.scan(0, 0, mx - 1, mz - 1)
            things = tiles.get("things", []) if isinstance(tiles, dict) else []

            berry_bushes = []
            for t in things:
                if not isinstance(t, dict):
                    continue
                tdef = t.get("def", "")
                if "Berry" not in tdef:
                    continue
                # Only harvestable bushes (fully grown, not yet harvested)
                if not t.get("harvestable", False):
                    continue
                tx = t.get("x", -1)
                tz = t.get("z", -1)
                if tx < 0:
                    continue
                dist = abs(tx - map_cx) + abs(tz - map_cz)
                berry_bushes.append({"x": tx, "z": tz, "dist": dist, "def": tdef})

            result["bushes_found"] = len(berry_bushes)
            if not berry_bushes:
                return result

            # Sort by distance from center (descending — target farthest first)
            berry_bushes.sort(key=lambda b: b["dist"], reverse=True)
            print(f"  BERRY SCAN: {len(berry_bushes)} harvestable bushes found, "
                  f"farthest at dist={berry_bushes[0]['dist']} ({berry_bushes[0]['x']},{berry_bushes[0]['z']})")

            # Re-designate harvest to make sure all are designated
            try:
                self.harvest(map_cx, map_cz, radius=max(mx, mz), def_filter="Plant_Berry")
            except Exception:
                pass

            # Get non-cook colonists for draft+move
            cook_name = getattr(self, '_cook_name', None)
            col_data = self.colonists()
            cols = col_data.get("colonists", [])
            available = []
            for c in cols:
                cname = c.get("name", "?")
                short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
                job = c.get("currentJob", "")
                # Skip cook, skip downed colonists, skip those in mental break
                if short == cook_name:
                    continue
                if job in ("Wait_Downed", "FleeAndCower"):
                    continue
                if c.get("mentalState"):
                    continue
                pos = c.get("position", {})
                cx = pos.get("x", map_cx)
                cz_pos = pos.get("z", map_cz)
                available.append({"name": short, "full_name": cname, "x": cx, "z": cz_pos})

            if not available:
                result["errors"].append("No available colonists for berry reach")
                return result

            # Assign colonists to distant bushes (1 colonist per bush, max 2 moves)
            moved = 0
            for bush in berry_bushes:
                if moved >= 2:  # Limit to 2 draft-moves per health check
                    break
                bx, bz = bush["x"], bush["z"]
                # Only target bushes >10 tiles from center (nearby ones get harvested naturally)
                if bush["dist"] <= 10:
                    break

                # Find closest available colonist to this bush
                best_col = min(available, key=lambda c: abs(c["x"] - bx) + abs(c["z"] - bz))
                try:
                    self.draft(best_col["name"])
                    self.move_pawn(best_col["name"], bx, bz)
                    self.undraft(best_col["name"])
                    result["colonists_moved"].append(
                        f"{best_col['name']} → berry at ({bx},{bz}) dist={bush['dist']}")
                    print(f"  BERRY REACH: Moved {best_col['name']} to ({bx},{bz}) "
                          f"(berry bush dist={bush['dist']} from center)")
                    moved += 1
                    result["bushes_targeted"] += 1
                    # Remove this colonist from available pool
                    available = [c for c in available if c["name"] != best_col["name"]]
                    if not available:
                        break
                except Exception as e:
                    result["errors"].append(f"Move {best_col['name']} to ({bx},{bz}): {e}")
        except Exception as e:
            result["errors"].append(f"reach_distant_berries: {e}")

        return result

    def colony_health_check(self) -> ColonyHealthCheckResult:
        """Comprehensive colony diagnostic. Calls resources/buildings/colonists/
        needs/zones/weather/alerts internally. Returns structured status dict.

        All sections wrapped in try/except — partial results on failure.
        """
        status: dict[str, Any] = {
            "food": {"raw": 0, "meals": 0, "packs": 0, "campfire_built": False,
                     "bills_active": False, "status": "unknown"},
            "shelter": {"beds": 0, "barracks_enclosed": False},
            "wood": {"count": 0, "status": "unknown"},
            "construction": {"blueprints_pending": 0},
            "mood": {"avg": 50.0, "worst": ("unknown", 50.0)},
            "game_day": 0.0,
            "alerts": [],
        }

        # Weather / game day — EARLY so food pipeline checks can use game_day
        try:
            weather = self.weather()
            day = weather.get("dayOfYear", 1)
            hour = weather.get("hour", 0)
            status["game_day"] = day + hour / 24.0
        except Exception:
            pass

        # Resources
        try:
            res = self.resources()
            wood = res.get("WoodLog", 0)
            status["wood"]["count"] = wood
            status["wood"]["status"] = "ok" if wood >= 100 else ("warning" if wood >= 30 else "critical")

            # Count all meat types (Meat_Squirrel, Meat_Turkey, etc.) not just "MeatRaw"
            raw_meat = sum(v for k, v in res.items() if isinstance(v, (int, float)) and k.startswith("Meat_"))
            raw = raw_meat + res.get("RawBerries", 0) + res.get("RawRice", 0) + res.get("RawCorn", 0) + res.get("RawPotatoes", 0)
            meals = res.get("MealSimple", 0) + res.get("MealFine", 0)
            packs = res.get("MealSurvivalPack", 0)
            status["food"]["raw"] = raw
            status["food"]["meals"] = meals
            status["food"]["packs"] = packs
        except Exception:
            pass

        # Buildings — check for ANY cooking station (not just Campfire), count beds
        try:
            self._cache.invalidate("read_buildings")  # fresh data for health check
            buildings = self.buildings()
            blist = buildings.get("buildings", [])
            cooking_stations = ["Campfire", "FueledStove", "ElectricStove"]
            has_cooking_station = any(b.get("def") in cooking_stations for b in blist)
            status["food"]["campfire_built"] = has_cooking_station
            status["food"]["cooking_stations"] = [b.get("def") for b in blist
                                                   if b.get("def") in cooking_stations]
            status["shelter"]["beds"] = sum(1 for b in blist if b.get("def") == "Bed")
        except Exception:
            pass

        # Barracks enclosed — query room roles from C# (reliable) instead of geometry heuristic
        try:
            stats = self.colony_stats()
            rooms = stats.get("rooms", [])
            for room in rooms:
                role = room.get("role", "")
                if role.lower() in ("barracks", "bedroom"):
                    status["shelter"]["barracks_enclosed"] = True
                    break
        except Exception:
            pass

        # AUTO-SECURE FOOD STOCKPILE inside barracks (runs once)
        # This fixes the 6-run recurring bug where secure_food_stockpile() was called
        # in Phase 2 before walls were built, causing the food zone to end up in the
        # storage room. Now it triggers in Phase 3+ when barracks is actually enclosed.
        # Food inside barracks = colonists eat immediately upon waking (reduces
        # transient hunger dips that cost 8+ points on food_sustained).
        # FALLBACK (run 0.5 fix): also triggers if barracks_bounds exist and
        # game_day >= 2.0, even without room detection. This covers cases where
        # the door was placed but room detection is delayed.
        status["food"]["stockpile_auto_secured"] = False
        game_day_for_secure = status.get("game_day", 0)
        barracks_ready = status["shelter"]["barracks_enclosed"]
        time_fallback = (game_day_for_secure >= 2.0
                         and hasattr(self, '_barracks_bounds') and self._barracks_bounds)
        if (hasattr(self, '_barracks_bounds') and self._barracks_bounds
                and not getattr(self, '_food_secured', False)
                and (barracks_ready or time_fallback)):
            try:
                bb = self._barracks_bounds
                food_result = self.secure_food_stockpile(
                    bb["x1"], bb["z1"], bb["x2"], bb["z2"])
                self._food_secured = True
                status["food"]["stockpile_auto_secured"] = True
                print(f"  AUTO-FOOD-STOCKPILE: Secured inside barracks {bb}: {food_result}")
            except Exception as e:
                print(f"  AUTO-FOOD-STOCKPILE failed: {e}")

        # Bills — check if cooking bills are active
        try:
            bill_data = self.bills()
            # C# returns {"workbenches": [{def, bills: [{recipe, ...}]}]}
            workbenches = bill_data.get("workbenches", []) if isinstance(bill_data, dict) else []
            for wb in workbenches:
                if not isinstance(wb, dict):
                    continue
                for b in wb.get("bills", []):
                    if isinstance(b, dict) and "cook" in b.get("recipe", "").lower():
                        status["food"]["bills_active"] = True
                        break
                if status["food"]["bills_active"]:
                    break
        except Exception:
            pass

        # AUTO-FIX BILLS: If any cooking station exists but no cooking bills
        # are active, add them NOW. This is the #1 food pipeline fix —
        # closes the bills gap where raw_food=186 sits uncookable for hours.
        # Embedded here so every health check iteration auto-heals.
        status["food"]["bills_auto_fixed"] = False
        if status["food"].get("campfire_built") and not status["food"].get("bills_active"):
            try:
                bill_result = self.add_cooking_bills(retry=False)
                if bill_result.get("campfire_bill") or bill_result.get("stove_bill"):
                    status["food"]["bills_active"] = True
                    status["food"]["bills_auto_fixed"] = True
                    print(f"  AUTO-BILLS: Fixed missing cooking bills! {bill_result}")
                else:
                    print(f"  AUTO-BILLS: Station exists ({status['food'].get('cooking_stations', [])}) "
                          f"but bill add returned: {bill_result}")
            except Exception as e:
                print(f"  AUTO-BILLS FAILED: {e}")

        # Food status — packs provide safety but meals=0+raw=0 means cooking is broken
        try:
            meals_and_raw = status["food"]["meals"] + status["food"]["raw"]
            total_food = meals_and_raw + status["food"]["packs"]
            bills_active = status["food"].get("bills_active", True)
            if total_food == 0:
                status["food"]["status"] = "critical"
            elif meals_and_raw == 0:
                # Only packs — cooking pipeline is broken, trigger bills check
                status["food"]["status"] = "warning"
            elif not bills_active:
                # Bills inactive — cooking will stall, intervene early
                status["food"]["status"] = "warning"
            elif total_food < 10:
                status["food"]["status"] = "warning"
            else:
                status["food"]["status"] = "ok"
        except Exception:
            pass

        # Print food pipeline state for observability (audit needs this)
        try:
            food = status["food"]
            print(f"  FOOD STATE: meals={food['meals']}, raw={food['raw']}, packs={food['packs']}, "
                  f"bills={food['bills_active']}, stations={food.get('cooking_stations', [])}, "
                  f"status={food['status']}"
                  + (f", AUTO-FIXED-BILLS" if food.get('bills_auto_fixed') else ""))
        except Exception:
            pass

        # ── HUNT-STALL DETECTION + AUTO-FIX ──
        # Detect when hunt designations are active but no colonist can fulfill them.
        # This catches the run 008 bug: Gabs assigned hunter (Violent disabled) → hares
        # marked for hunting but never killed. Auto-fix: find a Violent-capable colonist,
        # set Hunting=1, and re-designate hunting.
        status["hunting"] = {"stalled": False, "wild_animals": 0, "hunter_capable": True}
        try:
            animals_data = self.animals()
            wild_count = sum(1 for a in animals_data.get("animals", [])
                            if isinstance(a, dict) and not a.get("tame", False))
            status["hunting"]["wild_animals"] = wild_count

            if wild_count > 0 and status["food"]["status"] in ("critical", "warning"):
                # Check if any colonist can actually hunt (Violent not disabled + Hunting > 0)
                colonist_data_hunt = self.colonists()
                cols_hunt = colonist_data_hunt.get("colonists", [])
                wp_data = self.work_priorities()
                # Build hunting priority lookup: short_name → hunting priority
                hunt_prios = {}
                for wp_col in wp_data.get("colonists", []):
                    wp_name = wp_col.get("name", "?")
                    wp_short = wp_name.split("'")[1] if "'" in wp_name else wp_name.split()[-1]
                    hunt_prios[wp_short] = wp_col.get("priorities", {}).get("Hunting", 0)

                effective_hunter = None
                for c in cols_hunt:
                    dw = c.get("disabledWork", "")
                    dw_set = set(tag.strip() for tag in dw.split(",") if tag.strip())
                    if "Violent" in dw_set:
                        continue
                    name = c.get("name", "?")
                    short = name.split("'")[1] if "'" in name else name.split()[-1]
                    if hunt_prios.get(short, 0) > 0:
                        effective_hunter = short
                        break

                if not effective_hunter:
                    status["hunting"]["stalled"] = True
                    status["hunting"]["hunter_capable"] = False
                    print(f"  HUNT STALL: {wild_count} wild animals but NO colonist has Hunting enabled + Violent capability!")
                    # AUTO-FIX: Find best Violent-capable colonist and assign Hunting=1
                    best_hunter = None
                    best_shooting = -1
                    for c in cols_hunt:
                        dw = c.get("disabledWork", "")
                        dw_set = set(tag.strip() for tag in dw.split(",") if tag.strip())
                        if "Violent" in dw_set:
                            continue
                        name = c.get("name", "?")
                        short = name.split("'")[1] if "'" in name else name.split()[-1]
                        shooting = 0
                        for s in c.get("skills", []):
                            if s.get("name") == "Shooting":
                                shooting = s.get("level", 0)
                                break
                        if shooting > best_shooting:
                            best_shooting = shooting
                            best_hunter = short
                    if best_hunter:
                        try:
                            self.set_priority(best_hunter, "Hunting", 1)
                            self.hunt_all_wildlife()
                            status["hunting"]["auto_fixed"] = best_hunter
                            print(f"  HUNT AUTO-FIX: Assigned {best_hunter} (Shooting={best_shooting}) as hunter, re-designated all wildlife")
                        except Exception as e:
                            print(f"  HUNT AUTO-FIX FAILED: {e}")
        except Exception:
            pass

        # ── FOOD COOKABILITY CHECK ──
        # Detect when raw food exists but is below the cooking threshold (0.5 nutrition).
        # 6 berries = 0.3 nutrition < 0.5 needed for a simple meal → uncookable.
        # This masks as "food exists" but colonists go idle because bills can't produce.
        # NEW: cookable_meals metric for telemetry (run 009 auditor requested this).
        try:
            raw = status["food"]["raw"]
            meals = status["food"]["meals"]
            cookable_meals = raw // 10  # ~10 raw food units = 0.5 nutrition = 1 meal
            status["food"]["cookable_meals"] = cookable_meals
            wild = status.get("hunting", {}).get("wild_animals", 0)
            if raw > 0 and meals == 0 and raw < 10:
                status["food"]["sub_threshold"] = True
                status["food"]["status"] = "critical"  # Upgrade from warning to critical
                print(f"  FOOD SUB-THRESHOLD: raw={raw} < 10 units (cookable_meals=0), "
                      f"wild_animals={wild}. Need more via hunting/harvesting.")
                # AUTO-FIX: if sub-threshold AND wild animals exist, trigger immediate hunt
                if wild > 0:
                    try:
                        hunt_sub = self.hunt_all_wildlife()
                        designated = hunt_sub.get("designated", 0) if isinstance(hunt_sub, dict) else 0
                        print(f"  SUB-THRESHOLD HUNT: Triggered emergency hunt → {designated} designated")
                    except Exception:
                        pass
            else:
                status["food"]["sub_threshold"] = False

            # ── PROACTIVE BERRY HARVEST (runs 1-13 fix) ──
            # Problem (8 consecutive runs): harvest(radius=50) designates all 15
            # bushes but 4 at map edges never get harvested because colonists
            # always pick nearest PlantCutting tasks. The old trigger waited for
            # food="critical" (total=0) — by then it's too late (colonist must
            # WALK to edge + harvest + WALK back = 3+ game hours).
            #
            # Fix: on food-scarce maps, trigger the berry emergency PROACTIVELY
            # any time total food < 30 OR after game day 1.5. This gives colonists
            # time to reach distant bushes BEFORE food runs out. Also triggers
            # on any "critical" or "warning" food status for non-food-scarce maps.
            food_total = raw + meals
            berry_emergency_trigger = False
            if getattr(self, '_food_scarce_mode', False):
                # Proactive: trigger early on food-scarce maps
                game_day = status.get("game_day", 0)
                berry_emergency_trigger = (food_total < 30 or game_day >= 1.5
                                           or status["food"]["status"] in ("critical", "warning"))
            else:
                berry_emergency_trigger = (status["food"]["status"] == "critical")
            if berry_emergency_trigger:
                try:
                    mi_berry = self.map_info()
                    msz_berry = mi_berry.get("size", {})
                    mcx_berry = (msz_berry.get("x", 250) if isinstance(msz_berry, dict) else 250) // 2
                    mcz_berry = (msz_berry.get("z", 250) if isinstance(msz_berry, dict) else 250) // 2
                    mx_berry = msz_berry.get("x", 250) if isinstance(msz_berry, dict) else 250
                    mz_berry = msz_berry.get("z", 250) if isinstance(msz_berry, dict) else 250

                    # 1. Cancel ALL chop designations (free PlantCutting queue for berries)
                    try:
                        cancel_res = self.cancel_designations(0, 0, mx_berry, mz_berry, kind="chop")
                        cancelled = cancel_res.get("cancelled", 0) if isinstance(cancel_res, dict) else 0
                        if cancelled > 0:
                            print(f"  BERRY EMERGENCY: Cancelled {cancelled} chop designations")
                    except Exception:
                        pass

                    # 2. Re-designate harvest (full map)
                    try:
                        self.harvest(mcx_berry, mcz_berry, radius=max(mx_berry, mz_berry))
                        print(f"  BERRY EMERGENCY: Re-designated harvest (full map)")
                    except Exception:
                        pass

                    # 3. Boost ALL non-cook colonists PlantCutting=1
                    # On food-scarce maps, food scoring is 100% of the scenario.
                    # Multiple colonists walking to different map edges in parallel
                    # covers more ground faster (4 distant bushes at 4 different edges).
                    # Construction=4 is acceptable — this scenario has ZERO shelter scoring.
                    cook_name = getattr(self, '_cook_name', None)
                    boosted = []
                    try:
                        col_data = self.colonists()
                        for c in col_data.get("colonists", []):
                            cname = c.get("name", "?")
                            short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
                            if short != cook_name:  # Don't reassign cook
                                self.set_priority(short, "PlantCutting", 1)
                                self.set_priority(short, "Construction", 4)
                                self.set_priority(short, "Research", 4)
                                boosted.append(short)
                        if boosted:
                            status["food"]["berry_harvesters_boosted"] = boosted
                            print(f"  BERRY EMERGENCY: Boosted {boosted} PlantCutting=1, "
                                  f"Construction=4 (forcing ALL distant berry harvest)")
                    except Exception:
                        pass

                    # 4. DRAFT+MOVE colonists to distant berry bushes (NEW)
                    # Priority boost alone doesn't work — colonists still pick nearest
                    # PlantCutting task. Draft+move teleports them TO the bush, making
                    # it their nearest task. This is the fix for the 8-run edge-bush problem.
                    try:
                        berry_reach = self.reach_distant_berries()
                        if berry_reach.get("colonists_moved"):
                            status["food"]["berry_reach"] = berry_reach
                            print(f"  BERRY REACH: {berry_reach['bushes_targeted']} distant bushes targeted "
                                  f"via draft+move: {berry_reach['colonists_moved']}")
                    except Exception as e:
                        print(f"  BERRY REACH error: {e}")
                except Exception:
                    pass
        except Exception:
            pass

        # Colonist needs — mood
        try:
            needs = self.colonist_needs()
            moods = []
            worst_name, worst_mood = "unknown", 100.0
            for c in needs.get("colonists", []):
                mood = c.get("mood", 0.5) * 100
                moods.append(mood)
                name = c.get("name", "?")
                if mood < worst_mood:
                    worst_mood = mood
                    worst_name = name
            if moods:
                status["mood"]["avg"] = sum(moods) / len(moods)
                status["mood"]["worst"] = (worst_name, worst_mood)
        except Exception:
            pass

        # ── COMBAT DETECTION ──
        # Detect active attacks via colonist jobs: FleeAndCower = under attack,
        # Wait_Downed = incapacitated. When combat is active, auto-boost Doctor
        # priority and unforbid all medicine. This is the #1 survival fix —
        # the warg attack in run 007 killed all colonists because the overseer
        # had NO combat response protocol.
        status["combat"] = {"active": False, "fleeing": [], "downed": []}
        try:
            colonist_data = self.colonists()
            colonists_list = colonist_data.get("colonists", [])
            for c in colonists_list:
                name = c.get("name", "?")
                short = name.split("'")[1] if "'" in name else name.split()[-1]
                job = c.get("currentJob", "")
                if job == "FleeAndCower":
                    status["combat"]["fleeing"].append(short)
                    status["combat"]["active"] = True
                elif job == "Wait_Downed":
                    status["combat"]["downed"].append(short)
                    status["combat"]["active"] = True

            if status["combat"]["active"]:
                fleeing = status["combat"]["fleeing"]
                downed = status["combat"]["downed"]
                print(f"  COMBAT DETECTED: fleeing={fleeing}, downed={downed}")

                # AUTO-RESPONSE: boost Doctor for all non-downed colonists,
                # unforbid medicine so tending can happen immediately
                for c in colonists_list:
                    cname = c.get("name", "?")
                    cshort = cname.split("'")[1] if "'" in cname else cname.split()[-1]
                    cjob = c.get("currentJob", "")
                    if cjob != "Wait_Downed":
                        try:
                            self.set_priority(cshort, "Doctor", 1)
                        except Exception:
                            pass
                try:
                    self.unforbid_all()
                except Exception:
                    pass
                print(f"  COMBAT RESPONSE: boosted Doctor=1 for non-downed, "
                      f"unforbid all medicine")
        except Exception as e:
            print(f"  Combat detection error: {e}")

        # Weather / game day — already read at top of colony_health_check

        # Alerts
        try:
            alert_data = self.alerts()
            for a in alert_data.get("alerts", []):
                status["alerts"].append(a.get("label", "unknown"))
        except Exception:
            pass

        # Blueprint count
        try:
            mi = self.map_info()
            w = mi.get("size", {}).get("x", 250)
            h = mi.get("size", {}).get("z", 250)
            blueprints = self.scan_items(0, 0, w, h, kind="blueprint,frame")
            status["construction"]["blueprints_pending"] = len(blueprints) if isinstance(blueprints, list) else 0
        except Exception:
            pass

        # Auto-queue research if idle — ensures research never stalls between cycles
        try:
            research = self.research()
            status["research_current"] = research.get("current", None)
            completed = [p["def"] if isinstance(p, dict) else p  # type: ignore[index]
                         for p in research.get("completed", [])]
            status["research_completed"] = len(completed)
            if not research.get("current"):
                for proj in ["ColoredLights", "Brewing", "Batteries", "NobleApparel"]:
                    if proj not in completed:
                        self.set_research(proj)
                        status["research_auto_queued"] = proj
                        break
        except Exception:
            pass

        # Wild animal count — food competition signal for reactive hunting
        try:
            animals_data = self.send("read_animals")
            if isinstance(animals_data, dict):
                all_animals = animals_data.get("animals", [])
                status["wild_animals"] = sum(1 for a in all_animals
                                             if isinstance(a, dict) and not a.get("tame", False))
            elif isinstance(animals_data, list):
                status["wild_animals"] = len(animals_data)
            else:
                status["wild_animals"] = 0
        except Exception:
            status["wild_animals"] = -1

        # AUTO-HUNT: Guaranteed re-hunting on every health check.
        # Prompt-level ALWAYS blocks are unreliable — the overseer skips them.
        # By embedding hunting in colony_health_check(), every reactive iteration
        # that reads status will also re-designate all wild animals for hunting.
        # This is the single highest-value automation: 4 unhunted animals = 16.9 pts lost.
        status["hunt_result"] = None
        if status.get("wild_animals", 0) > 0:
            try:
                hunt_result = self.hunt_all_wildlife()
                status["hunt_result"] = hunt_result
                designated = hunt_result.get("designated", 0)
                species = hunt_result.get("species", [])
                already = hunt_result.get("already_designated", 0)
                skipped = hunt_result.get("skipped", [])
                errors = hunt_result.get("errors", [])
                print(f"  AUTO-HUNT: {designated} designated, already={already}, species={species}")
                if skipped:
                    print(f"  AUTO-HUNT: SKIPPED dangerous species: {skipped}")
                if errors:
                    print(f"  AUTO-HUNT errors: {errors}")
                if designated == 0 and already == 0 and len(skipped) == 0 and status["wild_animals"] > 0:
                    print(f"  AUTO-HUNT WARNING: {status['wild_animals']} wild animals but 0 designated — possible targeting failure")
            except Exception as e:
                print(f"  AUTO-HUNT FAILED: {e}")
                status["hunt_result"] = {"error": str(e)}

        # AUTO-HARVEST: Re-designate berry/plant harvesting when food is low.
        # Mirrors AUTO-HUNT above. Berry bushes are the primary food safety net on
        # food-scarce maps (15 bushes = ~150 berries = ~15 meals). Without repeated
        # harvest designations, colonists never cut them — the single harvest call in
        # day1_setup expires/gets cancelled and is never re-issued.
        # Also boosts PlantCutting priority during food crises so someone actually
        # goes and harvests instead of hauling/constructing.
        #
        # CRITICAL FIX (runs 1-4): CANCEL all chop (tree-cutting) designations BEFORE
        # re-designating harvest. Tree-chop and berry-harvest both use PlantCutting
        # work type. Colonists pick the nearest PlantCutting job — trees near center
        # beat distant berry bushes EVERY TIME. By cancelling chop designations during
        # food crises, berry bushes become the ONLY PlantCutting targets.
        status["harvest_result"] = None
        status["chop_cancelled"] = False
        if status["food"]["status"] in ("warning", "critical"):
            try:
                map_info_h = self.map_info()
                map_sz_h = map_info_h.get("size", {})
                mx = (map_sz_h.get("x", 250) if isinstance(map_sz_h, dict) else 250)
                mz = (map_sz_h.get("z", 250) if isinstance(map_sz_h, dict) else 250)
                hcx, hcz = mx // 2, mz // 2

                # Step 1: Cancel ALL tree-chop designations to clear PlantCutting queue
                try:
                    cancel_result = self.cancel_designations(0, 0, mx, mz, kind="chop")
                    cancelled = cancel_result.get("cancelled", 0) if isinstance(cancel_result, dict) else 0
                    if cancelled > 0:
                        status["chop_cancelled"] = True
                        print(f"  AUTO-HARVEST: Cancelled {cancelled} tree-chop designations (freeing PlantCutting for berries)")
                except Exception as e:
                    print(f"  AUTO-HARVEST: chop cancel failed: {e}")

                # Step 2: Re-designate berry/plant harvest across full map
                harvest_result = self.harvest(hcx, hcz, radius=max(mx, mz))
                status["harvest_result"] = harvest_result
                designated = harvest_result.get("designated", 0) if isinstance(harvest_result, dict) else 0
                print(f"  AUTO-HARVEST: {designated} plants designated (food={status['food']['status']})")
            except Exception as e:
                print(f"  AUTO-HARVEST FAILED: {e}")
                status["harvest_result"] = {"error": str(e)}

            # Boost PlantCutting priority during food crisis — ensures colonists
            # actually go cut berry bushes instead of hauling/constructing.
            # CRITICAL FIX (run_005): On food-scarce maps, ALWAYS boost to 1.
            # PlantCutting=2 ties with Construction=2, and Construction (#11) wins
            # over PlantCutting (#14) in check order. day1_setup() sets PlantCutting=1
            # for hunter+researcher on food-scarce maps — don't downgrade to 2.
            if getattr(self, '_food_scarce_mode', False):
                boost_level = 1  # Never downgrade from 1 on food-scarce maps
            else:
                boost_level = 1 if status["food"]["status"] == "critical" else 2
            try:
                col_data = self.colonists()
                for c in col_data.get("colonists", []):
                    cname = c.get("name", "?")
                    short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
                    try:
                        self.set_priority(short, "PlantCutting", boost_level)
                    except Exception:
                        pass
                print(f"  AUTO-HARVEST: Boosted PlantCutting={boost_level} for all colonists")
            except Exception:
                pass

            # ── FORCE COOK PRIORITY during food crisis (runs 9-11 fix) ──
            # Run 11: Benjamin (cook) spent 3.8 game hours on TendPatient/Skygaze/HaulToCell
            # after bills activated, before first DoBill at d1h18.4. Root cause: Doctor=1
            # outranks Cooking=1 when there are tending jobs. Fix: set Doctor=4 for the cook
            # during food crisis so Cooking=1 always wins. Also set Hauling=3 (below Cooking=1)
            # so cook doesn't haul when meals are urgently needed.
            cook_name = getattr(self, '_cook_name', None)
            if cook_name and status["food"].get("bills_active"):
                try:
                    self.set_priority(cook_name, "Cooking", 1)
                    self.set_priority(cook_name, "Doctor", 4)
                    self.set_priority(cook_name, "Hauling", 3)
                    # CRITICAL FIX (runs 003-004): Force cook Growing=0 during food crisis.
                    # Run 004: Benjamin was Sow:Plant_Rice at snap 75 (day 2) while 2 hares
                    # went unhunted and food reserves declined. Cook must NEVER sow.
                    self.set_priority(cook_name, "Growing", 0)
                    print(f"  COOK PRIORITY: Forced {cook_name} Cooking=1, Doctor=4, Growing=0 during food {status['food']['status']}")
                except Exception:
                    pass

            # ── AUTO-DELETE FUTILE GROW ZONES (runs 003-004 fix) ──
            # On food-scarce maps, grow zones divert labor in two ways:
            # 1. CutPlant clearing jobs (TallGrass/ChoppedStump) compete with berry harvest
            #    in the PlantCutting queue — colonists clear the grow zone instead of berries
            # 2. Sowing labor diverts the cook and other colonists from useful work
            # The overseer may create grow zones despite setup_zones() skipping them.
            # Delete ALL grow zones on food-scarce maps during food crisis.
            if getattr(self, '_food_scarce_mode', False):
                try:
                    zones_data = self.zones()
                    for z in zones_data.get("zones", []):
                        if not isinstance(z, dict):
                            continue
                        ztype = z.get("type", "")
                        if "grow" in ztype.lower() or "Growing" in ztype:
                            zb = z.get("bounds", {})
                            zx = zb.get("minX", z.get("x", -1))
                            zz = zb.get("minZ", z.get("z", -1))
                            if zx >= 0 and zz >= 0:
                                try:
                                    self.delete_zone(zx, zz)
                                    print(f"  AUTO-DELETE GROW ZONE: Deleted grow zone at ({zx},{zz}) — "
                                          f"food-scarce mode, grow zone diverts labor from berry harvest")
                                    status["food"]["grow_zone_deleted"] = True
                                except Exception:
                                    pass
                    # Also force ALL colonists Growing=0 — no sowing on food-scarce maps
                    try:
                        col_data_grow = self.colonists()
                        for c in col_data_grow.get("colonists", []):
                            cname = c.get("name", "?")
                            short = cname.split("'")[1] if "'" in cname else cname.split()[-1]
                            try:
                                self.set_priority(short, "Growing", 0)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

        # Construction stalled flag — true when no blueprints pending and resources plentiful
        bp = status["construction"].get("blueprints_pending", 0)
        wood = status["wood"].get("count", 0)
        steel = 0
        try:
            steel = self.resources().get("Steel", 0)
        except Exception:
            pass
        status["construction_stalled"] = (bp == 0 and wood > 300 and steel > 200)

        return status  # type: ignore[return-value]

    # ── composite builders ────────────────────────────────────────────

    # Minimum gap (in tiles) between a new standalone building and existing
    # buildings/zones.  Set to 0 when intentionally abutting (e.g. adding a
    # room to an existing structure).
    BUILDING_GAP = 2

    def build_room(self, x1: int, z1: int, x2: int, z2: int, stuff: str = "BlocksGranite", doors: list[tuple[int, int]] | None = None,
                   floor: str | None = None, floor_stuff: str | None = None, gap: int | None = None) -> BuildRoomResult:
        """Build a rectangular room with shared-wall support.

        Perimeter walls are placed except where a compatible wall already
        exists (shared wall).  Doors are placed at positions in *doors*.

        If *floor* is given (e.g. ``"WoodPlankFloor"``), also designates
        flooring on all interior cells.

        *gap* controls the minimum spacing checked around the room (defaults
        to ``BUILDING_GAP``).  Pass ``gap=0`` when intentionally adjoining
        an existing structure.

        Returns ``{"placed": N, "shared": N, "skipped_zone": N, "results": [...]}``.
        """
        if gap is None:
            gap = self.BUILDING_GAP
        check_x1 = x1 - gap
        check_z1 = z1 - gap
        check_x2 = x2 + gap
        check_z2 = z2 + gap
        building_map, zone_occ = self._get_occupancy(check_x1, check_z1, check_x2, check_z2)
        door_set = set(doors or [])

        # Collect perimeter cells
        perimeter = set()
        for x in range(x1, x2 + 1):
            perimeter.add((x, z1))
            perimeter.add((x, z2))
        for z in range(z1 + 1, z2):
            perimeter.add((x1, z))
            perimeter.add((x2, z))

        footprint = set()
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                footprint.add((x, z))

        # Gap check — objects in the margin but outside the footprint
        margin_occupied = set(building_map.keys()) | zone_occ
        margin_hits = margin_occupied - footprint
        if margin_hits and gap > 0:
            raise RimError(
                f"build_room too close: {len(margin_hits)} cells within {gap}-tile gap "
                f"of ({x1},{z1})-({x2},{z2}). Use gap=0 to adjoin existing structures."
            )

        # Zone collisions on perimeter — always fatal
        zone_blocked = perimeter & zone_occ
        if zone_blocked:
            raise RimError(
                f"build_room zone overlap: {len(zone_blocked)} perimeter cells have zones "
                f"at ({x1},{z1})-({x2},{z2})."
            )

        # Building collisions on perimeter — shared wall logic
        cmds = []
        shared = 0
        non_wall_blocked = []
        for x, z in sorted(perimeter):
            if (x, z) in door_set:
                # Always try to place doors (even if wall exists, it will error)
                cmds.append(("build", {"blueprint": "Door", "x": x, "y": z, "stuff": stuff}))
                continue
            existing = building_map.get((x, z))
            if existing:
                # Compatible wall already here — skip (shared wall)
                if existing["def"] in ("Wall", "Door"):
                    shared += 1
                    continue
                else:
                    non_wall_blocked.append((x, z, existing["def"]))
                    continue
            cmds.append(("build", {"blueprint": "Wall", "x": x, "y": z, "stuff": stuff}))

        if non_wall_blocked:
            details = ", ".join(f"({x},{z})={d}" for x, z, d in non_wall_blocked)
            raise RimError(
                f"build_room blocked by non-wall buildings: {details}"
            )

        self._cache.invalidate("read_buildings", "read_map_tiles", "read_terrain")
        results, errors = self.send_batch_lenient(cmds) if cmds else ([], 0)
        if floor:
            self.floor(floor, x1 + 1, z1 + 1, x2 - 1, z2 - 1, stuff=floor_stuff)
        return {"placed": len(results), "shared": shared, "errors": errors,
                "results": results}

    def build_room_grid(self, origin_x: int, origin_z: int, cols: int, rows: int, room_w: int, room_h: int,
                        stuff: str = "BlocksGranite", doors: list[tuple[int, int]] | None = None, gap: int | None = None) -> BuildRoomGridResult:
        """Build a grid of rooms sharing walls.

        Raises :class:`RimError` if any wall cell collides with existing
        non-wall buildings or zones, or if existing structures are within *gap* tiles.
        """
        if gap is None:
            gap = self.BUILDING_GAP
        total_w = cols * room_w + cols + 1
        total_h = rows * room_h + rows + 1
        ex = origin_x + total_w - 1
        ez = origin_z + total_h - 1
        check_x1 = origin_x - gap
        check_z1 = origin_z - gap
        check_x2 = ex + gap
        check_z2 = ez + gap
        building_map, zone_occ = self._get_occupancy(check_x1, check_z1, check_x2, check_z2)
        door_set = set(doors or [])
        wall_cells = set()
        footprint = set()
        for dx in range(total_w):
            for dz in range(total_h):
                x = origin_x + dx
                z = origin_z + dz
                footprint.add((x, z))
                on_vert = dx % (room_w + 1) == 0
                on_horiz = dz % (room_h + 1) == 0
                if on_vert or on_horiz:
                    wall_cells.add((x, z))
        # Zone collisions
        zone_blocked = wall_cells & zone_occ
        if zone_blocked:
            raise RimError(
                f"build_room_grid zone overlap: {len(zone_blocked)} wall cells "
                f"at origin ({origin_x},{origin_z})."
            )
        margin_occupied = set(building_map.keys()) | zone_occ
        margin_hits = margin_occupied - footprint
        if margin_hits and gap > 0:
            raise RimError(
                f"build_room_grid too close: {len(margin_hits)} cells within {gap}-tile gap "
                f"of origin ({origin_x},{origin_z}). Use gap=0 to adjoin existing structures."
            )
        cmds = []
        shared = 0
        for x, z in sorted(wall_cells):
            if (x, z) in door_set:
                cmds.append(("build", {"blueprint": "Door", "x": x, "y": z, "stuff": stuff}))
                continue
            existing = building_map.get((x, z))
            if existing and existing["def"] in ("Wall", "Door"):
                shared += 1
                continue
            bp = "Wall"
            cmds.append(("build", {"blueprint": bp, "x": x, "y": z, "stuff": stuff}))
        self._cache.invalidate("read_buildings", "read_map_tiles", "read_terrain")
        results, errors = self.send_batch_lenient(cmds) if cmds else ([], 0)
        return {"placed": len(results), "shared": shared, "errors": errors}

    def build_hallway(self, x1: int, z1: int, x2: int, z2: int, stuff: str = "BlocksGranite",
                      doors: list[tuple[int, int]] | None = None, floor: str | None = None, floor_stuff: str | None = None) -> BuildHallwayResult:
        """Build a 3-wide hallway (1-tile walkway + walls on each side).

        Specify the hallway by its walkable centerline endpoints:
        - Horizontal: ``(x1, z, x2, z)`` — builds walls at z-1 and z+1
        - Vertical: ``(x, z1, x, z2)`` — builds walls at x-1 and x+1

        *doors* is a list of ``(x, z)`` wall positions to place doors
        (e.g. for connecting to adjacent rooms).
        """
        door_set = set(doors or [])
        cmds = []
        floor_cells = []
        if z1 == z2:
            # Horizontal hallway
            z = z1
            mn, mx = min(x1, x2), max(x1, x2)
            for x in range(mn, mx + 1):
                for wz in (z - 1, z + 1):
                    bp = "Door" if (x, wz) in door_set else "Wall"
                    cmds.append(("build", {"blueprint": bp, "x": x, "y": wz, "stuff": stuff}))
                floor_cells.append((x, z))
        elif x1 == x2:
            # Vertical hallway
            x = x1
            mn, mz = min(z1, z2), max(z1, z2)
            for z in range(mn, mz + 1):
                for wx in (x - 1, x + 1):
                    bp = "Door" if (wx, z) in door_set else "Wall"
                    cmds.append(("build", {"blueprint": bp, "x": wx, "y": z, "stuff": stuff}))
                floor_cells.append((x, z))
        else:
            raise RimError("Hallway must be horizontal (same z) or vertical (same x)")
        self._cache.invalidate("read_buildings", "read_map_tiles")
        results, errors = self.send_batch_lenient(cmds)
        if floor and floor_cells:
            for fx, fz in floor_cells:
                try:
                    self.floor(floor, fx, fz, stuff=floor_stuff)
                except Exception:
                    pass
        return {"placed": len(results), "errors": errors}

    # ── validation & new builders ────────────────────────────────────

    def check_buildable(self, cells: list[tuple[int, int]], stuff: str | None = None) -> CheckBuildableResult:
        """Pre-flight check: which cells are clear vs blocked.

        *cells* is a list of ``(x, z)`` tuples.
        Returns ``{"clear": [(x,z),...], "blocked": [{"x":x, "z":z, "reason":"water"}, ...]}``.
        Never raises.
        """
        if not cells:
            return {"clear": [], "blocked": []}

        xs = [c[0] for c in cells]
        zs = [c[1] for c in cells]
        x1, x2 = min(xs), max(xs)
        z1, z2 = min(zs), max(zs)

        # Get terrain for the region
        terrain_data = self.terrain(x1, z1, x2, z2)
        building_map, zone_occ = self._get_occupancy(x1, z1, x2, z2)

        clear = []
        blocked = []
        for x, z in cells:
            t = terrain_data.get((x, z))
            if t and t.get("isWater"):
                blocked.append({"x": x, "z": z, "reason": "water"})
            elif t and t.get("isRock"):
                blocked.append({"x": x, "z": z, "reason": "rock"})
            elif (x, z) in building_map:
                info = building_map[(x, z)]
                blocked.append({"x": x, "z": z, "reason": "building",
                                "def": info["def"]})
            elif (x, z) in zone_occ:
                blocked.append({"x": x, "z": z, "reason": "zone"})
            else:
                clear.append((x, z))
        return {"clear": clear, "blocked": blocked}

    def cost_check(self, blueprint: str, stuff: str | None = None, count: int = 1) -> CostCheckResult:
        """Check if we can afford *count* of *blueprint*.

        Returns ``{"affordable": bool, "need": {def: N}, "have": {def: N}}``.
        """
        cost_data = self.costs(blueprint, stuff=stuff)
        res = self.resources()

        need = {}
        for c in cost_data.get("costs", []):
            need[c["defName"]] = c["count"] * count

        # Map resource defNames to resource keys
        _RES_MAP = {
            "Steel": "steel", "WoodLog": "wood", "ComponentIndustrial": "components",
            "Silver": "silver", "Gold": "gold", "Plasteel": "plasteel",
            "ComponentSpacer": "advancedComponents", "Cloth": "cloth",
        }

        have = {}
        affordable = True
        for def_name, needed in need.items():
            res_key = _RES_MAP.get(def_name)
            if res_key:
                available = res.get(res_key, 0)
            else:
                # Stone blocks etc — check via defName prefix matching
                # Resources returns named counts; stone blocks use defName directly
                available = res.get(def_name, 0)
            have[def_name] = available
            if available < needed:
                affordable = False

        return {"affordable": affordable, "need": need, "have": have}

    def verify_room(self, x1: int, z1: int, x2: int, z2: int) -> VerifyRoomResult:
        """Post-build audit of a room. Checks walls, doors, interior.

        Returns ``{"complete": bool, "missing_walls": [...], "blocked_doors": [...]}``.
        """
        # Scan the area for things
        items = self.scan_items(x1, z1, x2, z2, kind="building,blueprint,frame")

        # Build a map of what's at each cell
        cell_map = {}
        for t in items:
            pos = (t["x"], t["z"])
            kind = t.get("kind", "")
            def_name = t.get("def", "")
            building_def = t.get("building", def_name)  # blueprints/frames store target in "building"
            if kind in ("building", "blueprint", "frame"):
                cell_map[pos] = {"kind": kind, "def": building_def}

        # Check perimeter
        missing_walls = []
        doors = []
        for x in range(x1, x2 + 1):
            for z in (z1, z2):
                c = cell_map.get((x, z))
                if not c:
                    missing_walls.append({"x": x, "z": z})
                elif c["def"] in ("Door", "Autodoor"):
                    doors.append((x, z))
        for z in range(z1 + 1, z2):
            for x in (x1, x2):
                c = cell_map.get((x, z))
                if not c:
                    missing_walls.append({"x": x, "z": z})
                elif c["def"] in ("Door", "Autodoor"):
                    doors.append((x, z))

        # Check door clearance
        blocked_doors = []
        for dx, dz in doors:
            # A door needs at least one cell clear on each side
            if dx == x1 or dx == x2:
                # Door on east/west wall — check x-1 and x+1
                pass  # door on perimeter, outside is always clear
            if dz == z1 or dz == z2:
                # Door on north/south wall
                pass

        return {
            "complete": len(missing_walls) == 0,
            "missing_walls": missing_walls,
            "blocked_doors": blocked_doors,
            "doors": [{"x": d[0], "z": d[1]} for d in doors],
        }

    def build_room_adjacent(self, existing_bounds: tuple[int, int, int, int], direction: str, width: int, height: int,
                            stuff: str = "BlocksGranite", doors: list[tuple[int, int]] | None = None,
                            floor: str | None = None, floor_stuff: str | None = None) -> BuildRoomResult:
        """Build a room sharing one wall with an existing room.

        *existing_bounds* is ``(x1, z1, x2, z2)`` of the existing room.
        *direction* is "north", "south", "east", or "west".
        *doors* is a list of ``(x, z)`` tuples for door placement in the NEW room.

        Returns same format as :meth:`build_room`.
        """
        ex1, ez1, ex2, ez2 = existing_bounds

        if direction == "north":
            # New room above (higher z): shares the existing north wall
            nx1 = ex1
            nz1 = ez2          # shared wall
            nx2 = nx1 + width - 1
            nz2 = nz1 + height - 1
        elif direction == "south":
            nx1 = ex1
            nz2 = ez1          # shared wall
            nz1 = nz2 - height + 1
            nx2 = nx1 + width - 1
        elif direction == "east":
            nx1 = ex2           # shared wall
            nz1 = ez1
            nx2 = nx1 + width - 1
            nz2 = nz1 + height - 1
        elif direction == "west":
            nx2 = ex1           # shared wall
            nx1 = nx2 - width + 1
            nz1 = ez1
            nz2 = nz1 + height - 1
        else:
            raise RimError(f"Invalid direction: {direction}. Use north/south/east/west.")

        return self.build_room(nx1, nz1, nx2, nz2, stuff=stuff, doors=doors,
                               floor=floor, floor_stuff=floor_stuff, gap=0)

    def build_with_budget(self, plan: list[tuple[str, int, int, str | None]], budget: dict[str, int] | None = None) -> tuple[list[dict[str, Any]], list[tuple[str, int, int, str | None]]]:
        """Place as many builds as affordable. Returns ``(placed, deferred)``.

        *plan* is a list of ``(blueprint, x, z, stuff)`` tuples.
        *budget* is a resource dict (from :meth:`resources`); fetched if None.
        """
        if budget is None:
            budget = self.resources()

        _RES_MAP = {
            "Steel": "steel", "WoodLog": "wood", "ComponentIndustrial": "components",
            "Silver": "silver", "Gold": "gold", "Plasteel": "plasteel",
            "ComponentSpacer": "advancedComponents", "Cloth": "cloth",
        }

        # Track remaining resources
        remaining = dict(budget)
        placed_cmds = []
        deferred = []

        for blueprint, x, z, item_stuff in plan:
            cost_data = self.costs(blueprint, stuff=item_stuff)
            can_afford = True
            for c in cost_data.get("costs", []):
                def_name = c["defName"]
                res_key = _RES_MAP.get(def_name, def_name)
                if remaining.get(res_key, 0) < c["count"]:
                    can_afford = False
                    break

            if can_afford:
                # Deduct costs
                for c in cost_data.get("costs", []):
                    res_key = _RES_MAP.get(c["defName"], c["defName"])
                    remaining[res_key] = remaining.get(res_key, 0) - c["count"]
                placed_cmds.append(("build", {"blueprint": blueprint,
                                              "x": x, "y": z, "stuff": item_stuff}))
            else:
                deferred.append((blueprint, x, z, item_stuff))

        self._cache.invalidate("read_buildings", "read_map_tiles", "read_terrain")
        if placed_cmds:
            results, errors = self.send_batch_lenient(placed_cmds)
        else:
            results, errors = [], 0

        return results, deferred

    def wait_for_construction(self, x1: int, z1: int, x2: int, z2: int, timeout: int = 120) -> WaitForConstructionResult:
        """Wait until all blueprints/frames in region become completed buildings.

        Uses speed(3) and polls periodically. Returns when done or on timeout.
        """
        self.speed(3)
        start = time.monotonic()
        poll_interval = 3.0

        while time.monotonic() - start < timeout:
            time.sleep(poll_interval)
            self._cache.invalidate("read_map_tiles")
            items = self.scan_items(x1, z1, x2, z2, kind="blueprint,frame")
            if not items:
                self.speed(1)
                return {"done": True, "elapsed": round(time.monotonic() - start, 1)}  # type: ignore[return-value]

        self.speed(1)
        remaining = self.scan_items(x1, z1, x2, z2, kind="blueprint,frame")
        return {"done": False, "remaining": len(remaining),
                "elapsed": round(time.monotonic() - start, 1)}

    # ── collision detection ──────────────────────────────────────────

    def _get_occupancy(self, x1: int, z1: int, x2: int, z2: int) -> tuple[dict[tuple[int, int], dict[str, Any]], set[tuple[int, int]]]:
        """Return ``(building_map, zone_overlap)`` with richer collision data.

        *building_map* is a dict ``{(x,z): {"type": "building"|"blueprint"|"frame",
        "def": defName, "stuff": stuffName|None}}``.

        *zone_overlap* is a set of ``(x, z)`` tuples.
        """
        bld = self.buildings()  # cached, small payload
        building_map = {}
        for b in bld.get("buildings", []):
            p = b.get("position", {})
            bx, bz = p.get("x", -1), p.get("z", -1)
            if x1 <= bx <= x2 and z1 <= bz <= z2:
                building_map[(bx, bz)] = {
                    "type": "building",
                    "def": b.get("def", "unknown"),
                    "stuff": None,  # buildings() doesn't return stuff
                }
        zone_data = self.zones()  # cached
        zone_overlap = set()
        for z in zone_data.get("zones", []):
            zb = z.get("bounds", {})
            if not zb:
                continue
            # AABB overlap test
            if (zb.get("minX", 999) <= x2 and zb.get("maxX", -1) >= x1
                    and zb.get("minZ", 999) <= z2 and zb.get("maxZ", -1) >= z1):
                ox1 = max(x1, zb["minX"])
                ox2 = min(x2, zb["maxX"])
                oz1 = max(z1, zb["minZ"])
                oz2 = min(z2, zb["maxZ"])
                for x in range(ox1, ox2 + 1):
                    for zz in range(oz1, oz2 + 1):
                        zone_overlap.add((x, zz))
        return building_map, zone_overlap

    # ── internals ─────────────────────────────────────────────────────

    def _recv(self) -> dict[str, Any]:
        """Read one newline-delimited JSON response, stripping any BOM."""
        while b"\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        if line.startswith(b"\xef\xbb\xbf"):
            line = line[3:]
        return json.loads(line)
