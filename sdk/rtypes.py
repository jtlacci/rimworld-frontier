"""Type definitions for RimWorld TCP Bridge protocol responses.

TypedDict classes for every command response shape and SDK helper return type.
Imported by ``sdk/rimworld.py`` via ``from rtypes import ...``.
Consumers get types via ``from rimworld import ColonistsResponse, ...``.
"""
from __future__ import annotations

from typing import Any, TypedDict, NotRequired


# ═══════════════════════════════════════════════════════════════════════
#  Shared / Common types
# ═══════════════════════════════════════════════════════════════════════

class Position(TypedDict):
    x: int
    z: int


class Bounds(TypedDict):
    minX: int
    maxX: int
    minZ: int
    maxZ: int


class OkResponse(TypedDict):
    """Base shape for simple write-command acknowledgements."""
    ok: bool


# ═══════════════════════════════════════════════════════════════════════
#  Read command responses
# ═══════════════════════════════════════════════════════════════════════

# ── ping ──────────────────────────────────────────────────────────────

class PingResponse(TypedDict):
    status: str                   # "pong"
    game: str                     # "running" | "no_game"
    map: bool
    time: str                     # "yyyy-MM-dd HH:mm:ss"
    colonists: NotRequired[int]   # present when map loaded
    speed: NotRequired[int]       # present when map loaded


# ── read_colonists ────────────────────────────────────────────────────

class ColonistSkill(TypedDict):
    name: str                     # WorkTypeDef defName
    level: int
    passion: str                  # "None" | "Minor" | "Major"


class ColonistTrait(TypedDict):
    name: str
    description: str


class ColonistInfo(TypedDict):
    name: str
    position: Position
    health: float
    mood: float
    currentJob: str               # JobDef defName or "idle"
    mentalState: str              # MentalStateDef defName or "none"
    isDrafted: bool
    childhood: str
    childhoodDesc: str
    adulthood: str
    adulthoodDesc: str
    traits: list[ColonistTrait]
    disabledWork: str             # comma-separated WorkTags
    skills: list[ColonistSkill]


class ColonistsResponse(TypedDict):
    colonists: list[ColonistInfo]


# ── read_resources ────────────────────────────────────────────────────

ResourcesResponse = dict[str, int]
"""Dynamic keys: ``{"WoodLog": 150, "Steel": 300, ...}``."""


# ── read_map ──────────────────────────────────────────────────────────

class MapSize(TypedDict):
    x: int
    z: int


class MapInfoResponse(TypedDict):
    size: MapSize
    biome: str                    # defName
    avgFertility: float
    homeCells: int
    season: str
    hour: float


# ── read_map_tiles ────────────────────────────────────────────────────

MapTileThing = TypedDict("MapTileThing", {
    "x": int,
    "z": int,
    "kind": str,                  # "building" | "item" | "plant" | "pawn" | "blueprint" | "frame" | ...
    "def": NotRequired[str],      # ThingDef defName
    "label": NotRequired[str],
})


CellDesignation = TypedDict("CellDesignation", {
    "x": int,
    "z": int,
    "def": str,                   # DesignationDef defName
})


class MapTilesResponse(TypedDict):
    """Raw response from ``read_map_tiles`` (single 50x50 page)."""
    x1: int
    z1: int
    x2: int
    z2: int
    width: int
    height: int
    terrainPalette: list[str]     # defName list; index = byte value in terrain grid
    terrain: str                  # base64, column-major
    fertility: str                # base64, 0-255 = 0-100%
    roof: str                     # base64, 0=none 1=thin 2=thick
    fog: str                      # base64, 0=visible 1=fogged
    things: list[dict[str, Any]]  # MapTileThing with extra per-kind fields
    cellDesignations: list[CellDesignation]


class ScanDecodedResponse(TypedDict):
    """Decoded single-page scan (returned by ``scan()`` for regions <= 50x50)."""
    x1: int
    z1: int
    x2: int
    z2: int
    width: int
    height: int
    terrainPalette: list[str]
    terrain: list[int]            # decoded bytes
    fertility: list[int]          # decoded bytes
    roof: list[int]               # decoded bytes
    fog: list[int]                # decoded bytes
    things: list[dict[str, Any]]
    cellDesignations: list[CellDesignation]


class RoofCounts(TypedDict):
    open: int
    thin: int
    overhead: int


class ScanMergedResponse(TypedDict):
    """Merged multi-page scan (returned by ``scan()`` for regions > 50x50)."""
    things: list[dict[str, Any]]
    cellDesignations: list[CellDesignation]
    terrain_counts: dict[str, int]
    avg_fertility: float
    roof_counts: RoofCounts
    total_tiles: int


# ── read_alerts ───────────────────────────────────────────────────────

class AlertInfo(TypedDict):
    type: str
    label: str
    priority: str


class AlertsResponse(TypedDict):
    alerts: list[AlertInfo]
    totalChecked: int


# ── read_buildings ────────────────────────────────────────────────────

BuildingInfo = TypedDict("BuildingInfo", {
    "def": str,
    "label": str,
    "position": Position,
    "hitPoints": int,
    "maxHitPoints": int,
    "isSpot": bool,
})


class RoomInfo(TypedDict):
    role: str
    cellCount: int
    roofed: bool
    openRoofCount: int
    temperature: float
    impressiveness: float
    beauty: float
    cleanliness: float
    contents: list[str]           # defName list
    flooredPct: float
    bounds: Bounds


class BuildingsResponse(TypedDict):
    buildings: list[BuildingInfo]
    rooms: list[RoomInfo]


# ── read_weather ──────────────────────────────────────────────────────

class WeatherResponse(TypedDict):
    temperature: float
    condition: str                # defName
    season: str
    dayOfYear: int
    dayOfSeason: int
    hour: float


# ── read_research ─────────────────────────────────────────────────────

AvailableResearch = TypedDict("AvailableResearch", {
    "def": str,
    "label": str,
    "cost": float,
    "progress": float,
})


class ResearchResponse(TypedDict):
    current: str | None           # defName or null
    currentProgress: float        # 0-1
    completed: list[str]          # defName list
    available: list[AvailableResearch]


# ── read_zones ────────────────────────────────────────────────────────

class ZoneInfo(TypedDict):
    type: str
    label: str
    cellCount: int
    bounds: Bounds
    plant: NotRequired[str]       # grow zones only
    priority: NotRequired[str]    # stockpile zones only


class ZonesResponse(TypedDict):
    zones: list[ZoneInfo]


# ── read_bills ────────────────────────────────────────────────────────

class BillInfo(TypedDict):
    index: int
    recipe: str
    label: str
    suspended: bool


WorkbenchInfo = TypedDict("WorkbenchInfo", {
    "def": str,
    "label": str,
    "position": Position,
    "bills": list[BillInfo],
})


class BillsResponse(TypedDict):
    workbenches: list[WorkbenchInfo]


# ── read_threats ──────────────────────────────────────────────────────

class ThreatInfo(TypedDict):
    type: str                     # "hostile" | "fire"
    name: NotRequired[str]
    kind: NotRequired[str]
    faction: NotRequired[str]
    position: Position
    health: NotRequired[float]
    downed: NotRequired[bool]


class ThreatsResponse(TypedDict):
    threats: list[ThreatInfo]


# ── read_work_priorities ──────────────────────────────────────────────

class ColonistPriorities(TypedDict):
    name: str
    priorities: dict[str, int]    # {WorkTypeDef: priority_level}


class WorkPrioritiesResponse(TypedDict):
    colonists: list[ColonistPriorities]


# ── read_animals ──────────────────────────────────────────────────────

class AnimalInfo(TypedDict):
    name: str
    kind: str
    position: Position
    health: float
    tame: bool
    bonded: bool
    downed: bool
    huntDesignated: bool


class AnimalsResponse(TypedDict):
    animals: list[AnimalInfo]
    hunt_designated_count: int


# ── read_plants ───────────────────────────────────────────────────────

class PlantInfo(TypedDict):
    def_: str  # defName (mapped from "def" in protocol)
    position: Position
    growth: float
    harvestable: bool
    yieldDef: str
    yieldCount: int


class PlantsResponse(TypedDict):
    plants: list[PlantInfo]
    count: int


# ── read_food_log ─────────────────────────────────────────────────────

class FoodLogEntry(TypedDict):
    tick: int
    hour: float
    pawn: str
    food: str
    nutrition: float
    foodNeedBefore: float


class FoodLogResponse(TypedDict):
    events: list[FoodLogEntry]
    count: int


# ── read_pawns ────────────────────────────────────────────────────────

class PawnBrief(TypedDict):
    name: str
    position: Position
    health: float
    drafted: NotRequired[bool]    # colonists only


class PrisonerBrief(TypedDict):
    name: str
    position: Position
    health: float


class GuestBrief(TypedDict):
    name: str
    faction: str
    position: Position


class PawnsResponse(TypedDict):
    colonists: list[PawnBrief]
    prisoners: list[PrisonerBrief]
    guests: list[GuestBrief]
    hostile_count: int
    animal_count: int


# ── read_needs ────────────────────────────────────────────────────────

class NeedInfo(TypedDict):
    name: str
    label: str
    level: float


class NeedsResponse(TypedDict):
    needs: list[NeedInfo]


# ── read_inventory ────────────────────────────────────────────────────

EquipmentInfo = TypedDict("EquipmentInfo", {
    "def": str,
    "label": str,
    "hp": int,
    "maxHp": int,
})


ApparelInfo = TypedDict("ApparelInfo", {
    "def": str,
    "label": str,
    "hp": int,
    "maxHp": int,
})


InventoryItem = TypedDict("InventoryItem", {
    "def": str,
    "label": str,
    "count": int,
})


class InventoryResponse(TypedDict):
    equipment: list[EquipmentInfo]
    apparel: list[ApparelInfo]
    inventory: list[InventoryItem]


# ── read_colonist_needs ───────────────────────────────────────────────

class ColonistNeedsSummary(TypedDict):
    name: str
    mood: float
    food: float
    rest: float
    joy: float
    beauty: float
    comfort: float


class ColonistNeedsResponse(TypedDict):
    colonists: list[ColonistNeedsSummary]


# ── read_thoughts ─────────────────────────────────────────────────────

class ThoughtInfo(TypedDict):
    label: str
    mood: float
    daysLeft: float


class ThoughtsResponse(TypedDict):
    thoughts: list[ThoughtInfo]


# ── read_letters ──────────────────────────────────────────────────────

LetterInfo = TypedDict("LetterInfo", {
    "index": int,
    "label": str,
    "type": str,
    "def": str,
    "text": NotRequired[str],
    "has_quest": NotRequired[bool],
})


class LettersResponse(TypedDict):
    letters: list[LetterInfo]


# ── read_dialogs ──────────────────────────────────────────────────────

class DialogOption(TypedDict):
    text: str
    disabled: NotRequired[bool]
    disabledReason: NotRequired[str]


class DialogInfo(TypedDict):
    type: str
    id: str
    title: NotRequired[str]
    text: NotRequired[str]
    options: NotRequired[list[DialogOption]]


class DialogsResponse(TypedDict):
    dialogs: list[DialogInfo]


# ── read_beauty ───────────────────────────────────────────────────────

class BeautyCell(TypedDict):
    x: int
    z: int
    b: float                      # beauty value


class BeautyResponse(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int
    avg: float
    cells: list[BeautyCell]       # non-zero beauty cells only


# ── read_messages ─────────────────────────────────────────────────────

class LiveMessage(TypedDict):
    text: str
    age: float                    # game-seconds


class MessagesResponse(TypedDict):
    messages: list[LiveMessage]


# ── read_terrain ──────────────────────────────────────────────────────

class TerrainCell(TypedDict):
    x: int
    z: int
    terrain: str                  # defName
    fertility: float
    isWater: bool
    isRock: bool


class TerrainResponse(TypedDict):
    cells: list[TerrainCell]


# ── read_roof ─────────────────────────────────────────────────────────

class RoofCell(TypedDict):
    x: int
    z: int
    roof: str | None              # defName or null


class RoofResponse(TypedDict):
    cells: list[RoofCell]


# ── read_costs ────────────────────────────────────────────────────────

class CostItem(TypedDict):
    defName: str
    count: int


class CostsResponse(TypedDict):
    costs: list[CostItem]
    workAmount: float


# ── read_interaction_spots ────────────────────────────────────────────

class InteractionSpot(TypedDict):
    building: str
    bx: int
    bz: int
    ix: int
    iz: int


class InteractionSpotsResponse(TypedDict):
    spots: list[InteractionSpot]


# ── read_ideology ─────────────────────────────────────────────────────

class RoleAssignment(TypedDict):
    name: str
    fullName: str


class IdeologyRole(TypedDict):
    defName: str
    label: str
    assigned: list[RoleAssignment]
    maxCount: int
    requirements: list[str]


class IdeologyMeme(TypedDict):
    defName: str
    label: str
    description: str


class IdeologyResponse(TypedDict):
    active: bool
    name: str
    roles: list[IdeologyRole]
    memes: list[IdeologyMeme]


# ── read_visitors ─────────────────────────────────────────────────────

VisitorGood = TypedDict("VisitorGood", {
    "def": str,
    "label": str,
    "count": int,
    "value": float,
})


class VisitorPawn(TypedDict):
    name: str
    position: Position
    isTrader: bool


class VisitorGroup(TypedDict):
    faction: str
    count: int
    isTrader: bool
    traderName: NotRequired[str]
    traderKind: NotRequired[str]
    goods: NotRequired[list[VisitorGood]]
    pawns: list[VisitorPawn]


class CaravanInfo(TypedDict):
    faction: str
    pawnCount: int
    tile: int
    destTile: int
    arriving: bool


class VisitorsResponse(TypedDict):
    visitors: list[VisitorGroup]
    caravans: list[CaravanInfo]


# ── read_colony_stats ─────────────────────────────────────────────────

class ColonyStatsRoom(TypedDict):
    role: str
    impressiveness: float
    beauty: float
    cells: int
    roofed: bool
    temperature: float


class ColonyStatsResponse(TypedDict):
    wealth_total: float
    wealth_items: float
    wealth_buildings: float
    wealth_floors: float
    wealth_pawns: float
    avg_beauty: float
    rooms: list[ColonyStatsRoom]
    avg_impressiveness: float


# ── read_water / find_water ───────────────────────────────────────────

class WaterBody(TypedDict):
    type: str                     # "river" | "lake" | "marsh"
    direction: str | None         # "N-S" | "E-W" | null
    bounds: list[int]             # [x1, z1, x2, z2]
    cell_count: int


class WaterResponse(TypedDict):
    bodies: list[WaterBody]
    total_water_cells: int


# ── find_grow_spot / read_grow_spot ───────────────────────────────────

class GrowSpotResponse(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int
    cells: int


# ── find_clear_rect ───────────────────────────────────────────────────

class ClearRectResponse(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int


# ── survey_region ─────────────────────────────────────────────────────

class SurveyRoofBreakdown(TypedDict):
    open: int
    thin: int
    overhead: int


class SurveyThingCounts(TypedDict):
    tree: int
    chunk: int
    building: int
    plant: int
    item: int
    pawn: int


class SurveyRegionResponse(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int
    total_tiles: int
    terrain_counts: dict[str, int]    # {defName: count}
    water_tiles: int
    rock_tiles: int
    buildable_tiles: int
    avg_fertility: float
    rich_soil_tiles: int
    roof: SurveyRoofBreakdown
    thing_counts: SurveyThingCounts


# ── survey ASCII variants ─────────────────────────────────────────────

class AsciiSurveyResponse(TypedDict):
    """Common response shape for all survey_*_ascii commands."""
    x1: int
    z1: int
    x2: int
    z2: int
    scale: int
    grid: list[str]               # row strings
    legend: dict[str, str]        # {char: description}


class AsciiSurveyEntityInfo(TypedDict):
    type: str
    char: str
    name: str
    x: int
    z: int
    job: NotRequired[str]
    tame: NotRequired[bool]


class DetailedAsciiSurveyResponse(TypedDict):
    """Response for ``survey_detailed_ascii`` with entity legend."""
    x1: int
    z1: int
    x2: int
    z2: int
    scale: int
    grid: list[str]
    entities: list[AsciiSurveyEntityInfo]
    legend: dict[str, str]


# ── list_saves ────────────────────────────────────────────────────────

class SaveInfo(TypedDict):
    name: str
    modified: str
    size_mb: float


class ListSavesResponse(TypedDict):
    saves: list[SaveInfo]


# ═══════════════════════════════════════════════════════════════════════
#  Write command responses
# ═══════════════════════════════════════════════════════════════════════

# ── set_priority ──────────────────────────────────────────────────────

class SetPriorityResponse(TypedDict):
    ok: bool
    colonist: str
    work: str
    priority: int


# ── set_schedule ──────────────────────────────────────────────────────

class SetScheduleResponse(TypedDict):
    ok: bool
    colonist: str


# ── set_speed ─────────────────────────────────────────────────────────

class SetSpeedResponse(TypedDict):
    ok: bool
    speed: int


# ── draft / undraft ───────────────────────────────────────────────────

class DraftResponse(TypedDict):
    ok: bool
    colonist: str
    drafted: bool


# ── add_bill ──────────────────────────────────────────────────────────

class AddBillResponse(TypedDict):
    ok: bool
    workbench: str
    recipe: str
    count: int


# ── cancel_bill ───────────────────────────────────────────────────────

class CancelBillResponse(TypedDict):
    ok: bool
    workbench: str
    removedIndex: int


# ── suspend_bill ──────────────────────────────────────────────────────

class SuspendBillResponse(TypedDict):
    ok: bool
    workbench: str
    billIndex: int
    suspended: bool


# ── build ─────────────────────────────────────────────────────────────

class BuildResponse(TypedDict):
    ok: bool
    blueprint: str
    x: int
    y: int                        # NOTE: wire format uses "y" not "z"
    stuff: str | None
    instant: NotRequired[bool]    # true for no-cost items (spots)
    warning: NotRequired[str]     # e.g. "under overhead mountain"


# ── cancel_build ──────────────────────────────────────────────────────

class CancelBuildResponse(TypedDict):
    ok: bool
    x: int
    y: int                        # wire format uses "y"


# ── bulk_build ────────────────────────────────────────────────────────

class BulkBuildResult(TypedDict):
    ok: NotRequired[bool]
    error: NotRequired[str]
    x: NotRequired[int]
    y: NotRequired[int]
    cells: NotRequired[list[dict[str, Any]]]
    blueprint: NotRequired[str]
    stuff: NotRequired[str | None]
    instant: NotRequired[bool]
    warning: NotRequired[str]


class BulkBuildResponse(TypedDict):
    results: list[BulkBuildResult]


# ── set_floor ─────────────────────────────────────────────────────────

class SetFloorResponse(TypedDict):
    ok: bool
    floor: str
    placed: int
    skipped: int


# ── hunt ──────────────────────────────────────────────────────────────

class HuntResponse(TypedDict):
    ok: bool
    designated: int
    animal: str
    targets: str                  # comma-separated names


# ── designate_chop ────────────────────────────────────────────────────

class ChopResponse(TypedDict):
    ok: bool
    designated: int


# ── designate_harvest ─────────────────────────────────────────────────

class HarvestResponse(TypedDict):
    ok: bool
    designated: int


# ── designate_mine ────────────────────────────────────────────────────

class MineResponse(TypedDict):
    ok: bool
    designated: int


# ── create_grow_zone ──────────────────────────────────────────────────

class GrowZoneResponse(TypedDict):
    ok: bool
    cells: int
    skipped: int
    plant: str


# ── create_stockpile_zone ────────────────────────────────────────────

class StockpileResponse(TypedDict):
    ok: bool
    cells: int
    skipped: int
    priority: str
    label: str


# ── create_fishing_zone ──────────────────────────────────────────────

class FishingZoneResponse(TypedDict):
    ok: bool
    type: str                     # zone type name
    cells: int
    skipped: int
    label: str


# ── seed_fish ─────────────────────────────────────────────────────────

class SeedFishResponse(TypedDict):
    ok: bool
    population: float
    shouldHaveFish: bool
    cellCount: int
    cell: str


# ── pause ─────────────────────────────────────────────────────────────

class PauseResponse(TypedDict):
    ok: bool
    paused: bool                  # always True


# ── unpause ───────────────────────────────────────────────────────────

class UnpauseResponse(TypedDict):
    ok: bool
    paused: bool                  # always False
    speed: int
    dialogs_dismissed: int


# ── save ──────────────────────────────────────────────────────────────

class SaveResponse(TypedDict):
    ok: bool
    saved: bool


# ── load_game ─────────────────────────────────────────────────────────

class LoadGameResponse(TypedDict):
    ok: bool
    loading: str


# ── move_pawn ─────────────────────────────────────────────────────────

class MovePawnResponse(TypedDict):
    ok: bool
    pawn: str
    x: int
    z: int


# ── attack ────────────────────────────────────────────────────────────

class AttackResponse(TypedDict):
    ok: bool
    pawn: str
    target: str


# ── rescue ────────────────────────────────────────────────────────────

class RescueResponse(TypedDict):
    ok: bool
    pawn: str
    target: str


# ── tend ──────────────────────────────────────────────────────────────

class TendResponse(TypedDict):
    ok: bool
    pawn: str
    target: str


# ── haul ──────────────────────────────────────────────────────────────

class HaulResponse(TypedDict):
    ok: bool
    pawn: str
    item: str


# ── equip ─────────────────────────────────────────────────────────────

class EquipResponse(TypedDict):
    ok: bool
    pawn: str
    action: str                   # "equipping" | "wearing"
    item: str


# ── prioritize ────────────────────────────────────────────────────────

class PrioritizeResponse(TypedDict):
    ok: bool
    pawn: str
    workType: str


# ── tame ──────────────────────────────────────────────────────────────

class TameResponse(TypedDict):
    ok: bool
    animal: str                   # label
    kind: str                     # defName


# ── slaughter ─────────────────────────────────────────────────────────

class SlaughterResponse(TypedDict):
    ok: bool
    animal: str


# ── deconstruct ───────────────────────────────────────────────────────

class DeconstructResponse(TypedDict):
    ok: bool
    building: str                 # defName
    x: int
    z: int


# ── cancel_designation ────────────────────────────────────────────────

class CancelDesignationResponse(TypedDict):
    ok: bool
    x: int
    z: int


# ── cancel_designations ──────────────────────────────────────────────

class CancelDesignationsBounds(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int


class CancelDesignationsResponse(TypedDict):
    ok: bool
    cancelled: int
    bounds: CancelDesignationsBounds
    kind: str


# ── forbid / unforbid ────────────────────────────────────────────────

class ForbidResponse(TypedDict):
    ok: bool
    count: int
    forbidden: bool               # True for forbid, False for unforbid


# ── set_research ──────────────────────────────────────────────────────

class SetResearchResponse(TypedDict):
    ok: bool
    project: str                  # label


# ── set_plant ─────────────────────────────────────────────────────────

class SetPlantResponse(TypedDict):
    ok: bool
    zone: str                     # label
    plant: str


# ── delete_zone ───────────────────────────────────────────────────────

class DeleteZoneResponse(TypedDict):
    ok: bool
    deleted: str | int            # zone label or count


# ── remove_zone_cells ─────────────────────────────────────────────────

class RemoveZoneCellsResponse(TypedDict):
    ok: bool
    removed: int                  # cells removed from zones
    deleted: int                  # zones fully deleted (lost all cells)


# ── camera_jump ───────────────────────────────────────────────────────

class CameraJumpResponse(TypedDict):
    ok: bool
    x: int
    z: int


# ── place ─────────────────────────────────────────────────────────────

class PlaceResponse(TypedDict):
    ok: bool
    thingDef: str
    x: int
    z: int


# ── open_letter ───────────────────────────────────────────────────────

class OpenLetterResponse(TypedDict):
    label: str
    type: str
    text: str
    dialog_opened: bool
    dialog_title: NotRequired[str]
    options: NotRequired[list[DialogOption]]


# ── dismiss_letter ────────────────────────────────────────────────────

class DismissLetterResponse(TypedDict):
    ok: bool
    dismissed: str                # label


# ── choose_option ─────────────────────────────────────────────────────

class ChooseOptionResponse(TypedDict):
    ok: bool
    selected: str                 # option text
    result: str                   # "navigated" | "action executed"
    new_text: NotRequired[str]    # if navigated
    new_options: NotRequired[list[dict[str, Any]]]  # if navigated
    dialog_closed: NotRequired[bool]  # if action executed


# ── close_dialog ──────────────────────────────────────────────────────

class CloseDialogResponse(TypedDict):
    ok: bool
    closed: str                   # window type name
    factionName: NotRequired[str]
    settlementName: NotRequired[str]


# ── set_manual_priorities ─────────────────────────────────────────────

class SetManualPrioritiesResponse(TypedDict):
    ok: bool
    manualPriorities: bool


# ── set_stockpile_filter ─────────────────────────────────────────────

class SetStockpileFilterResponse(TypedDict):
    ok: bool
    zone: str                     # label
    priority: str
    allowed: int
    disallowed: int


# ── add_plan ──────────────────────────────────────────────────────────

class AddPlanResponse(TypedDict):
    ok: bool
    planned: int


# ── remove_plan ───────────────────────────────────────────────────────

class RemovePlanResponse(TypedDict):
    ok: bool
    removed: int


# ── assign_role ───────────────────────────────────────────────────────

class AssignRoleResponse(TypedDict):
    ok: bool
    pawn: str
    role: str                     # label


# ── dev_set_storyteller ───────────────────────────────────────────────

class SetStorytellerResponse(TypedDict):
    ok: bool
    storyteller: str              # defName
    difficulty: str               # defName


# ── dev_toggle_incidents ──────────────────────────────────────────────

class ToggleIncidentsResponse(TypedDict):
    ok: bool
    incidents_disabled: bool


# ── spawn_animals ─────────────────────────────────────────────────────

class SpawnedAnimalDetail(TypedDict):
    species: str
    x: int
    z: int
    manhunter: bool


class SpawnAnimalsResponse(TypedDict):
    ok: bool
    spawned: int
    species: str
    details: list[SpawnedAnimalDetail]


# ═══════════════════════════════════════════════════════════════════════
#  SDK helper return types
# ═══════════════════════════════════════════════════════════════════════

# ── terrain() — SDK transforms cells into dict keyed by (x,z) ────────

TerrainDict = dict[tuple[int, int], TerrainCell]
"""``terrain()`` returns ``{(x, z): TerrainCell, ...}``."""

RoofDict = dict[tuple[int, int], RoofCell]
"""``roof()`` returns ``{(x, z): RoofCell, ...}``."""


# ── hunt_all_wildlife() ───────────────────────────────────────────────

class HuntAllWildlifeResult(TypedDict):
    designated: int
    species: list[str]
    skipped: list[str]            # dangerous species
    already_designated: int
    errors: list[str]
    edge_animals: list[str]


# ── day1_setup() ──────────────────────────────────────────────────────

class Day1SetupResult(TypedDict):
    colonists: list[ColonistInfo]
    skills: dict[str, dict[str, int]]   # {short_name: {skill_name: level}}
    resources: dict[str, int]
    map_info: MapInfoResponse
    research: ResearchResponse
    animals: AnimalsResponse
    center_x: int
    center_z: int
    hunter: str
    cook: str
    researcher: str
    hunted: list[str]
    equipped_weapon: str | None
    completed_research: list[str]
    greedy_colonist: str | None


# ── setup_cooking() ───────────────────────────────────────────────────

class SetupCookingResult(TypedDict):
    campfire: tuple[int, int] | None
    butcher: tuple[int, int] | None
    stove: tuple[int, int] | None
    butcher_bill_immediate: NotRequired[bool]


# ── setup_dining() ────────────────────────────────────────────────────

class SetupDiningResult(TypedDict):
    table: tuple[int, int] | None
    chairs: list[tuple[int, int]]


# ── add_cooking_bills() ──────────────────────────────────────────────

class AddCookingBillsResult(TypedDict):
    campfire_bill: bool
    butcher_bill: bool
    stove_bill: bool
    buildings_found: list[str]


# ── setup_zones() ────────────────────────────────────────────────────

class SetupZonesResult(TypedDict):
    main: tuple[int, int] | None
    food: tuple[int, int] | None
    dump: tuple[int, int] | None
    grow: tuple[int, int] | None
    main_cells: NotRequired[int]
    main_skipped: NotRequired[int]
    main_warning: NotRequired[str]
    main_error: NotRequired[str]


# ── secure_food_stockpile() ──────────────────────────────────────────

class SecureFoodStockpileResult(TypedDict):
    food: NotRequired[tuple[int, int]]
    bounds: NotRequired[tuple[int, int, int, int]]
    zone_label: NotRequired[str]
    actual_priority: NotRequired[str]
    error: NotRequired[str]
    main_recreate_error: NotRequired[str]


# ── build_barracks() ─────────────────────────────────────────────────

class BuildBarracksResult(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int
    built: list[str]
    failed: list[str]


# ── build_storage_room() ─────────────────────────────────────────────

class BuildStorageRoomResult(TypedDict):
    x1: int
    z1: int
    x2: int
    z2: int
    built: list[str]
    failed: list[str]
    material_override: NotRequired[str]


# ── setup_recreation() ───────────────────────────────────────────────

class SetupRecreationResult(TypedDict):
    horseshoes: tuple[int, int] | None


# ── setup_production() ───────────────────────────────────────────────

class SetupProductionResult(TypedDict):
    research_bench: tuple[int, int] | None
    tailoring_bench: tuple[int, int] | None


# ── monitored_sleep() ────────────────────────────────────────────────

class MonitoredSleepResult(TypedDict):
    bills_added: bool
    bill_result: AddCookingBillsResult | dict[str, Any]


# ── colony_health_check() ────────────────────────────────────────────

class FoodStatus(TypedDict):
    raw: int
    meals: int
    packs: int
    campfire_built: bool
    bills_active: bool
    status: str                   # "ok" | "warning" | "critical" | "unknown"
    cooking_stations: NotRequired[list[str]]
    bills_auto_fixed: NotRequired[bool]
    stockpile_auto_secured: NotRequired[bool]


class ShelterStatus(TypedDict):
    beds: int
    barracks_enclosed: bool


class WoodStatus(TypedDict):
    count: int
    status: str                   # "ok" | "warning" | "critical" | "unknown"


class ConstructionStatus(TypedDict):
    blueprints_pending: int


class MoodStatus(TypedDict):
    avg: float
    worst: tuple[str, float]      # (name, mood_pct)


class CombatStatus(TypedDict):
    active: bool
    fleeing: list[str]
    downed: list[str]


class ColonyHealthCheckResult(TypedDict):
    food: FoodStatus
    shelter: ShelterStatus
    wood: WoodStatus
    construction: ConstructionStatus
    mood: MoodStatus
    game_day: float
    alerts: list[str]
    combat: NotRequired[CombatStatus]
    research_current: NotRequired[str | None]
    research_completed: NotRequired[int]
    research_auto_queued: NotRequired[str]
    wild_animals: NotRequired[int]
    hunt_result: NotRequired[HuntAllWildlifeResult | None]
    construction_stalled: NotRequired[bool]


# ── build_room() ──────────────────────────────────────────────────────

class BuildRoomResult(TypedDict):
    placed: int
    shared: int
    errors: int
    results: list[dict[str, Any]]


# ── build_room_grid() ────────────────────────────────────────────────

class BuildRoomGridResult(TypedDict):
    placed: int
    shared: int
    errors: int


# ── build_hallway() ──────────────────────────────────────────────────

class BuildHallwayResult(TypedDict):
    placed: int
    errors: int


# ── check_buildable() ────────────────────────────────────────────────

BlockedCell = TypedDict("BlockedCell", {
    "x": int,
    "z": int,
    "reason": str,                # "water" | "rock" | "building" | "zone"
    "def": NotRequired[str],      # present when reason == "building"
})


class CheckBuildableResult(TypedDict):
    clear: list[tuple[int, int]]
    blocked: list[BlockedCell]


# ── cost_check() ─────────────────────────────────────────────────────

class CostCheckResult(TypedDict):
    affordable: bool
    need: dict[str, int]
    have: dict[str, int]


# ── verify_room() ────────────────────────────────────────────────────

class MissingWall(TypedDict):
    x: int
    z: int


class DoorPosition(TypedDict):
    x: int
    z: int


class VerifyRoomResult(TypedDict):
    complete: bool
    missing_walls: list[MissingWall]
    blocked_doors: list[dict[str, Any]]
    doors: list[DoorPosition]


# ── wait_for_construction() ──────────────────────────────────────────

class WaitForConstructionResult(TypedDict):
    done: bool
    elapsed: float
    remaining: NotRequired[int]   # present when done=False
