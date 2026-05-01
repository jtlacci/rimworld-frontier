"""RimWorld custom save generator.

Takes an existing save as a template, strips it, resizes the map,
and generates terrain with full control over mountains, water, and ruins.

Usage:
    python tools/savegen.py --size 100                    # 100x100 flat Soil
    python tools/savegen.py --size 75 --mountains border  # Mountains around edge
    python tools/savegen.py --size 100 --water river      # River through center
    python tools/savegen.py --size 100 --keep-ruins       # Keep ancient structures
    python tools/savegen.py --size 100 --mountains ring --water corners

Terrain features:
    --mountains: none, border, ring, corners, random
    --water: none, river, lake, border, corners
    --keep-ruins: preserve ancient structures from template
"""

from __future__ import annotations

import argparse
import base64
import random
import struct
import sys
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path


# ── Hash registry (extracted from Baseline-Starter with all DLCs) ────
# These are runtime shortHashes — DLC/mod dependent. If a hash doesn't
# resolve in your game, the terrain will show as null (invisible).

TERRAIN_HASH = {
    "Soil":                 0x86A1,
    "SoilRich":             0x8073,
    "Gravel":               0xFE49,
    "Sand":                 0x52A6,
    "Mud":                  0xA430,
    "Marble_Rough":         0x6B39,
    "Slate_Rough":          0x3D94,
    "WaterShallow":         0x2CB5,
    "WaterOceanShallow":    0xFF89,
    "WaterOceanDeep":       0xA790,
    "TileMarble":           0xF67E,
    "TileGranite":          0x92E0,
    "FlagstoneLimestone":   0xBAF5,
    "FlagstoneSlate":       0x5A3B,
    "FlagstoneGranite":     0xF5A9,
    "FlagstoneSandstone":   0xC1AD,
    "AncientConcrete":      0x94D7,
    "AncientTile":          0x1A6C,
    "BrokenAsphalt":        0xE9CD,
}

ROOF_HASH = {
    "NoRoof":           0x0000,
    "RoofConstructed":  0x140D,
    "RoofRockThin":     0x1A2B,
    "RoofRockThick":    0x2A44,
}

ROCK_HASH = {
    "MineableMarble":               0xFBD4,
    "MineableSlate":                0xD3C5,
    "MineableGranite":              0x6A9D,
    "MineableLimestone":            0xF266,
    "MineableSandstone":            0xB14E,
    "MineableSteel":                0xA95D,
    "MineableComponentsIndustrial": 0x0211,
    "MineableGold":                 0x207F,
    "MineableSilver":               0x1B67,
    "MineableUranium":              0x5BF1,
    "MineablePlasteel":             0xF8E5,
}


# ── Grid generation ──────────────────────────────────────────────────

def _deflate_b64(raw: bytes) -> str:
    """Raw deflate compress and base64 encode."""
    compressed = zlib.compress(raw, 9)[2:-4]
    return base64.b64encode(compressed).decode("ascii")


def _decode_grid(b64_text: str) -> bytes:
    """Base64 decode and raw deflate decompress."""
    return zlib.decompress(base64.b64decode(b64_text), -15)


def _encode_ushort_grid(grid: list[int], width: int, height: int) -> str:
    """Encode a list of ushort values into a deflate+b64 grid string."""
    assert len(grid) == width * height
    raw = struct.pack(f"<{len(grid)}H", *grid)
    return _deflate_b64(raw)


def make_ushort_grid(width: int, height: int, value: int = 0) -> str:
    """Uniform ushort grid."""
    return _encode_ushort_grid([value] * (width * height), width, height)


def make_fog_grid(width: int, height: int, revealed: bool = True) -> str:
    """Fog-of-war grid (packed bits). 0=visible, 1=fogged."""
    total = width * height
    byte_count = (total + 7) // 8
    val = 0x00 if revealed else 0xFF
    return _deflate_b64(bytes([val] * byte_count))


def make_gas_grid(width: int, height: int) -> str:
    """Empty gas grid (4 bytes/cell)."""
    return _deflate_b64(bytes(width * height * 4))


def make_temperature_grid(width: int, height: int, temp_c: float = 20.0) -> str:
    """Temperature grid. Encoding: int(temp*16)+32768."""
    encoded = max(0, min(65535, int(temp_c * 16) + 32768))
    return make_ushort_grid(width, height, encoded)


def read_terrain_hash(grid_b64: str) -> int | None:
    """Read the first non-zero terrain hash from an existing grid."""
    try:
        raw = _decode_grid(grid_b64)
        for i in range(0, min(len(raw), 1000), 2):
            val = struct.unpack_from("<H", raw, i)[0]
            if val != 0:
                return val
    except Exception:
        pass
    return None


# ── Map painting ─────────────────────────────────────────────────────

class MapPainter:
    """Paints terrain, roofs, rock, and fog onto grid arrays."""

    def __init__(self, width: int, height: int, base_terrain: str = "Soil"):
        self.w = width
        self.h = height
        n = width * height
        self.terrain = [TERRAIN_HASH.get(base_terrain, 0x86A1)] * n
        self.roof = [0] * n
        self.rock = [0] * n
        self.fog = [False] * n  # True = fogged (hidden)

    def _idx(self, x: int, z: int) -> int:
        return z * self.w + x

    def _in_bounds(self, x: int, z: int) -> bool:
        return 0 <= x < self.w and 0 <= z < self.h

    def set_terrain(self, x: int, z: int, terrain: str):
        if self._in_bounds(x, z):
            h = TERRAIN_HASH.get(terrain)
            if h is not None:
                self.terrain[self._idx(x, z)] = h

    def set_mountain(self, x: int, z: int, rock_type: str = "MineableMarble"):
        """Place a mountain cell: rough terrain + overhead mountain roof + rock."""
        if not self._in_bounds(x, z):
            return
        idx = self._idx(x, z)
        self.terrain[idx] = TERRAIN_HASH.get("Marble_Rough", 0x6B39)
        self.roof[idx] = ROOF_HASH["RoofRockThick"]
        self.rock[idx] = ROCK_HASH.get(rock_type, ROCK_HASH["MineableMarble"])

    def set_water(self, x: int, z: int, deep: bool = False):
        if not self._in_bounds(x, z):
            return
        idx = self._idx(x, z)
        self.terrain[idx] = TERRAIN_HASH["WaterOceanDeep" if deep else "WaterShallow"]
        self.roof[idx] = 0
        self.rock[idx] = 0

    # ── Preset patterns ──

    def paint_mountains_border(self, thickness: int = 5):
        """Mountain ring around entire map edge."""
        for z in range(self.h):
            for x in range(self.w):
                if (x < thickness or x >= self.w - thickness or
                    z < thickness or z >= self.h - thickness):
                    self.set_mountain(x, z)

    def paint_mountains_ring(self, thickness: int = 4, gap: int = 8):
        """Mountain ring with gaps for entrances at cardinal directions."""
        cx, cz = self.w // 2, self.h // 2
        for z in range(self.h):
            for x in range(self.w):
                if (x < thickness or x >= self.w - thickness or
                    z < thickness or z >= self.h - thickness):
                    # Leave gaps at N/S/E/W
                    dx = abs(x - cx)
                    dz = abs(z - cz)
                    if dx < gap and (z < thickness or z >= self.h - thickness):
                        continue  # N/S gap
                    if dz < gap and (x < thickness or x >= self.w - thickness):
                        continue  # E/W gap
                    self.set_mountain(x, z)

    def paint_mountains_corners(self, size: int = 12):
        """Mountain chunks in each corner."""
        corners = [(0, 0), (self.w - size, 0), (0, self.h - size), (self.w - size, self.h - size)]
        for cx, cz in corners:
            for z in range(cz, min(cz + size, self.h)):
                for x in range(cx, min(cx + size, self.w)):
                    self.set_mountain(x, z)

    def paint_mountains_random(self, density: float = 0.15, seed: int = 42):
        """Random mountain patches avoiding the center."""
        rng = random.Random(seed)
        cx, cz = self.w // 2, self.h // 2
        safe_radius = min(self.w, self.h) // 4
        for z in range(self.h):
            for x in range(self.w):
                dist = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                if dist < safe_radius:
                    continue
                # Higher density near edges
                edge_factor = 1.0 - (dist / (min(self.w, self.h) / 2))
                if rng.random() < density * (1.0 + edge_factor):
                    self.set_mountain(x, z)

    def paint_mountains_side(self, side: str, thickness: int = 8):
        """Fill one side of the map with mountain rock.

        Args:
            side: "left", "right", "top", "bottom"
            thickness: how many cells deep the mountain extends
        """
        for z in range(self.h):
            for x in range(self.w):
                fill = False
                if side == "left" and x < thickness:
                    fill = True
                elif side == "right" and x >= self.w - thickness:
                    fill = True
                elif side == "top" and z >= self.h - thickness:  # high Z = north/top in RimWorld
                    fill = True
                elif side == "bottom" and z < thickness:  # low Z = south/bottom in RimWorld
                    fill = True
                if fill:
                    self.set_mountain(x, z)

    def paint_pond(self, cx: int, cz: int, radius: int):
        """Paint water terrain in a circle — shallow edges, deep center.

        Args:
            cx, cz: center position
            radius: circle radius in cells
        """
        deep_threshold = radius * 0.85  # most of the pond is deep (fish need deep water)
        for z in range(max(0, cz - radius), min(self.h, cz + radius + 1)):
            for x in range(max(0, cx - radius), min(self.w, cx + radius + 1)):
                dist = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                if dist <= radius:
                    if self._in_bounds(x, z) and self.rock[self._idx(x, z)] == 0:
                        self.set_water(x, z, deep=(dist <= deep_threshold))

    def generate_ruins(self, ruins: list[dict], id_start: int = 97000) -> list[ET.Element]:
        """Generate wall ruins around the perimeter of rectangles, with a door on one side.

        Each ruin dict has: x, z (top-left), width, height, stuff (default BlocksGranite).
        Returns a list of Thing XML elements.
        """
        WATER_HASHES = {TERRAIN_HASH.get("WaterShallow", 0), TERRAIN_HASH.get("WaterOceanDeep", 0),
                        TERRAIN_HASH.get("WaterOceanShallow", 0)}
        things = []
        tid = id_start
        for ruin in ruins:
            rx, rz = ruin["x"], ruin["z"]
            rw, rh = ruin["width"], ruin["height"]
            stuff = ruin.get("stuff", "BlocksGranite")
            # Door position: center of the south (bottom) wall
            door_x = rx + rw // 2
            door_z = rz + rh - 1
            # Perimeter cells
            for z in range(rz, rz + rh):
                for x in range(rx, rx + rw):
                    if not self._in_bounds(x, z):
                        continue
                    # Only perimeter
                    on_edge = (x == rx or x == rx + rw - 1 or
                               z == rz or z == rz + rh - 1)
                    if not on_edge:
                        continue
                    idx = self._idx(x, z)
                    if self.rock[idx] != 0 or self.terrain[idx] in WATER_HASHES:
                        continue
                    # Place door or wall
                    if x == door_x and z == door_z:
                        el = ET.Element("thing", Class="Building")
                        ET.SubElement(el, "def").text = "Door"
                        ET.SubElement(el, "id").text = f"Door{tid}"
                        ET.SubElement(el, "map").text = "0"
                        ET.SubElement(el, "pos").text = f"({x}, 0, {z})"
                        ET.SubElement(el, "health").text = "150"
                        ET.SubElement(el, "stuff").text = stuff
                        ET.SubElement(el, "spawnedTick").text = "0"
                        ET.SubElement(el, "despawnedTick").text = "-1"
                    else:
                        el = ET.Element("thing", Class="Building")
                        ET.SubElement(el, "def").text = "Wall"
                        ET.SubElement(el, "id").text = f"Wall{tid}"
                        ET.SubElement(el, "map").text = "0"
                        ET.SubElement(el, "pos").text = f"({x}, 0, {z})"
                        ET.SubElement(el, "health").text = "350"
                        ET.SubElement(el, "stuff").text = stuff
                        ET.SubElement(el, "spawnedTick").text = "0"
                        ET.SubElement(el, "despawnedTick").text = "-1"
                    things.append(el)
                    tid += 1
        return things

    def paint_water_river(self, width: int = 4):
        """River flowing N-S through the map, slightly meandering."""
        rng = random.Random(12)
        cx = self.w // 2
        offset = 0
        for z in range(self.h):
            offset += rng.choice([-1, 0, 0, 1])
            offset = max(-self.w // 4, min(self.w // 4, offset))
            for dx in range(-width // 2, width // 2 + 1):
                x = cx + offset + dx
                deep = abs(dx) < width // 3
                if self._in_bounds(x, z) and self.roof[self._idx(x, z)] == 0:
                    self.set_water(x, z, deep=deep)

    def paint_water_lake(self, radius: int = 0):
        """Lake in the center of the map."""
        if radius <= 0:
            radius = min(self.w, self.h) // 6
        cx, cz = self.w // 2, self.h // 2
        for z in range(self.h):
            for x in range(self.w):
                dist = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                if dist < radius - 1:
                    self.set_water(x, z, deep=True)
                elif dist < radius:
                    self.set_water(x, z, deep=False)

    def paint_water_border(self, width: int = 3):
        """Water border around the map edge."""
        for z in range(self.h):
            for x in range(self.w):
                if (x < width or x >= self.w - width or
                    z < width or z >= self.h - width):
                    deep = (x < width - 1 or x >= self.w - width + 1 or
                            z < width - 1 or z >= self.h - width + 1)
                    self.set_water(x, z, deep=deep)

    def paint_water_corners(self, size: int = 10):
        """Water pools in each corner."""
        corners = [(0, 0), (self.w, 0), (0, self.h), (self.w, self.h)]
        for cx, cz in corners:
            for z in range(self.h):
                for x in range(self.w):
                    dist = ((x - cx) ** 2 + (z - cz) ** 2) ** 0.5
                    if dist < size - 1:
                        self.set_water(x, z, deep=True)
                    elif dist < size:
                        self.set_water(x, z, deep=False)

    def finalize(self):
        """Compute fog: only deep interior mountain cells are fogged.

        A mountain cell is fogged if ALL 8 neighbors are also mountain.
        Surface/edge mountain cells stay revealed so players can see the rock.
        """
        for z in range(self.h):
            for x in range(self.w):
                idx = self._idx(x, z)
                if self.rock[idx] == 0:
                    # Not a mountain cell — always revealed
                    self.fog[idx] = False
                    continue
                # Check all 8 neighbors
                all_mountain = True
                for dz in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dz == 0:
                            continue
                        nx, nz = x + dx, z + dz
                        if not self._in_bounds(nx, nz):
                            all_mountain = False
                            break
                        if self.rock[self._idx(nx, nz)] == 0:
                            all_mountain = False
                            break
                    if not all_mountain:
                        break
                self.fog[idx] = all_mountain

    def encode_terrain(self) -> str:
        return _encode_ushort_grid(self.terrain, self.w, self.h)

    def encode_roof(self) -> str:
        return _encode_ushort_grid(self.roof, self.w, self.h)

    def encode_rock(self) -> str:
        return _encode_ushort_grid(self.rock, self.w, self.h)

    def encode_fog(self) -> str:
        """Encode fog grid (packed bits). True=fogged=1."""
        total = self.w * self.h
        byte_count = (total + 7) // 8
        raw = bytearray(byte_count)
        for i, fogged in enumerate(self.fog):
            if fogged:
                raw[i // 8] |= (1 << (i % 8))
        return _deflate_b64(bytes(raw))

    def generate_berry_bushes(self, count: int = 12, seed: int = 42,
                              id_start: int = 95000) -> list[ET.Element]:
        """Generate berry bushes scattered around the map."""
        rng = random.Random(seed + 7)  # different seed offset from trees
        WATER_HASHES = {TERRAIN_HASH.get("WaterShallow", 0), TERRAIN_HASH.get("WaterOceanDeep", 0),
                        TERRAIN_HASH.get("WaterOceanShallow", 0)}
        bushes = []
        tid = id_start
        attempts = 0
        while len(bushes) < count and attempts < count * 20:
            attempts += 1
            x = rng.randint(2, self.w - 3)
            z = rng.randint(2, self.h - 3)
            idx = self._idx(x, z)
            if self.rock[idx] != 0 or self.terrain[idx] in WATER_HASHES:
                continue
            cx, cz = self.w // 2, self.h // 2
            if abs(x - cx) < 3 and abs(z - cz) < 3:
                continue
            growth = 1.0  # fully grown = harvestable immediately
            el = ET.Element("thing", Class="Plant")
            ET.SubElement(el, "def").text = "Plant_Berry"
            ET.SubElement(el, "id").text = f"Plant_Berry{tid}"
            ET.SubElement(el, "map").text = "0"
            ET.SubElement(el, "pos").text = f"({x}, 0, {z})"
            ET.SubElement(el, "health").text = "120"
            ET.SubElement(el, "spawnedTick").text = "0"
            ET.SubElement(el, "despawnedTick").text = "-1"
            ET.SubElement(el, "growth").text = str(growth)
            ET.SubElement(el, "age").text = str(int(growth * 3600000))
            bushes.append(el)
            tid += 1
        return bushes

    def generate_trees(self, density: float = 0.08, seed: int = 42,
                       id_start: int = 90000) -> list[ET.Element]:
        """Generate tree things on open (non-mountain, non-water) cells."""
        TREE_DEFS = ["Plant_TreeOak", "Plant_TreePoplar", "Plant_TreeBirch"]
        WATER_HASHES = {TERRAIN_HASH.get("WaterShallow", 0), TERRAIN_HASH.get("WaterOceanDeep", 0),
                        TERRAIN_HASH.get("WaterOceanShallow", 0)}

        rng = random.Random(seed)
        trees = []
        tid = id_start

        for z in range(self.h):
            for x in range(self.w):
                idx = self._idx(x, z)
                # Skip mountain, water, and center (leave space for colonists)
                if self.rock[idx] != 0:
                    continue
                if self.terrain[idx] in WATER_HASHES:
                    continue
                cx, cz = self.w // 2, self.h // 2
                if abs(x - cx) < 4 and abs(z - cz) < 4:
                    continue  # Keep center clear for colonists
                if rng.random() > density:
                    continue

                tree_def = rng.choice(TREE_DEFS)
                growth = round(rng.uniform(0.3, 1.0), 4)
                el = ET.Element("thing", Class="Plant")
                ET.SubElement(el, "def").text = tree_def
                ET.SubElement(el, "id").text = f"{tree_def}{tid}"
                ET.SubElement(el, "map").text = "0"
                ET.SubElement(el, "pos").text = f"({x}, 0, {z})"
                ET.SubElement(el, "health").text = "200"
                ET.SubElement(el, "spawnedTick").text = "0"
                ET.SubElement(el, "despawnedTick").text = "-1"
                ET.SubElement(el, "growth").text = str(growth)
                ET.SubElement(el, "age").text = str(int(growth * 3600000))
                trees.append(el)
                tid += 1

        return trees

    def generate_grass(self, density: float = 0.6, seed: int = 42,
                       id_start: int = 98000) -> list[ET.Element]:
        """Generate grass and wild plants on open cells (non-mountain, non-water, non-tree)."""
        GRASS_DEFS = ["Plant_Grass", "Plant_Grass", "Plant_Grass",  # weighted toward regular grass
                      "Plant_TallGrass", "Plant_TallGrass",
                      "Plant_Dandelion", "Plant_Bush", "Plant_Brambles"]
        WATER_HASHES = {TERRAIN_HASH.get("WaterShallow", 0), TERRAIN_HASH.get("WaterOceanDeep", 0),
                        TERRAIN_HASH.get("WaterOceanShallow", 0)}

        rng = random.Random(seed + 3)
        grass = []
        tid = id_start

        for z in range(self.h):
            for x in range(self.w):
                idx = self._idx(x, z)
                if self.rock[idx] != 0:
                    continue
                if self.terrain[idx] in WATER_HASHES:
                    continue
                if rng.random() > density:
                    continue

                grass_def = rng.choice(GRASS_DEFS)
                growth = round(rng.uniform(0.4, 1.0), 4)
                # Age: keep young so grass doesn't hit lifespan and despawn mid-run
                # Grass lifespan ~30-40 days (1.8M-2.4M ticks). Set age to 1-5 days.
                age = int(rng.uniform(60000, 300000))  # 1-5 game days
                el = ET.Element("thing", Class="Plant")
                ET.SubElement(el, "def").text = grass_def
                ET.SubElement(el, "id").text = f"{grass_def}{tid}"
                ET.SubElement(el, "map").text = "0"
                ET.SubElement(el, "pos").text = f"({x}, 0, {z})"
                ET.SubElement(el, "health").text = "80"
                ET.SubElement(el, "spawnedTick").text = "0"
                ET.SubElement(el, "despawnedTick").text = "-1"
                ET.SubElement(el, "growth").text = str(growth)
                ET.SubElement(el, "age").text = str(age)
                grass.append(el)
                tid += 1

        return grass


# ── Thing filtering ──────────────────────────────────────────────────

STRIP_CLASSES = {"Plant", "Filth"}

RUIN_DEFS = {
    "AncientCryptosleepCasket", "AncientBed", "AncientLamp",
    "AncientRuinsWall", "AncientBarricade",
}

MINEABLE_DEFS = {
    "MineableSteel", "MineableComponentsIndustrial",
    "MineableGold", "MineableSilver", "MineableUranium",
    "MineablePlasteel", "MineableJade",
}

STRIP_DEFS_ALWAYS = {"SteamGeyser"}


WILDLIFE_DEFS = {"Deer", "Hare", "Squirrel", "Raccoon", "Turkey", "Ibex", "Gazelle"}


def should_keep_thing(thing: ET.Element, player_faction: str, keep_ruins: bool,
                      keep_wildlife: bool = False) -> bool:
    """Decide if a thing should be kept."""
    thing_class = thing.get("Class", "")
    def_el = thing.find("def")
    def_name = def_el.text if def_el is not None else ""

    for strip in STRIP_CLASSES:
        if strip in thing_class:
            return False

    if def_name.startswith("Plant_") or def_name.startswith("Filth_"):
        return False
    if def_name in STRIP_DEFS_ALWAYS:
        return False
    if def_name in MINEABLE_DEFS:
        return False  # Rock is handled via compressedThingMapDeflate

    # Ruins
    if def_name in RUIN_DEFS:
        return keep_ruins

    # Ruin terrain features (floors are in terrain grid, not things)
    # Ancient walls that aren't in RUIN_DEFS
    if "Ancient" in def_name and not keep_ruins:
        return False

    # Player faction things
    faction_el = thing.find("faction")
    if faction_el is not None and faction_el.text == player_faction:
        return True

    # Unfactioned items
    if faction_el is None and def_el is not None:
        if thing_class in ("", "ThingWithComps"):
            return True

    # Wild animals — keep huntable wildlife if requested
    if "Pawn" in thing_class and (faction_el is None or faction_el.text != player_faction):
        if keep_wildlife and def_name in WILDLIFE_DEFS:
            return True
        return False

    # Structures
    if def_name.startswith("Wall") or def_name.startswith("Door"):
        return keep_ruins  # Non-player walls are ruins

    return False


def reposition_pawn(pawn: ET.Element, x: int, z: int):
    pos_str = f"({x}, 0, {z})"
    pos_el = pawn.find("pos")
    if pos_el is not None:
        pos_el.text = pos_str
    pather = pawn.find("pather")
    if pather is not None:
        for tag in ["nextCell", "destination"]:
            el = pather.find(tag)
            if el is not None:
                el.text = pos_str


def reposition_thing(thing: ET.Element, x: int, z: int):
    pos_el = thing.find("pos")
    if pos_el is not None:
        pos_el.text = f"({x}, 0, {z})"


# ── Main generator ───────────────────────────────────────────────────

def generate_save(
    source_path: str,
    output_path: str,
    map_size: int | None = None,
    terrain: str = "Soil",
    mountains: str = "none",
    water: str = "none",
    trees: bool = False,
    tree_density: float = 0.08,
    keep_ruins: bool = False,
    temperature: float = 20.0,
    seed: int = 42,
    berry_bushes: int = 0,
    keep_wildlife: bool = False,
    starting_packs: int | None = None,
    wildlife_count: int = 0,
    starting_items: dict[str, int] | None = None,
    completed_research: list[str] | None = None,
    wildlife_species: list[str] | None = None,
    wildlife_distribution: dict[str, int] | None = None,
    ruins: list[dict] | None = None,
    ponds: list[dict] | None = None,
    mountain_side: str | None = None,
    mountain_resources: list[dict] | None = None,
    grass: bool = False,
    grass_density: float = 0.6,
):
    print(f"Loading template: {source_path}")
    tree = ET.parse(source_path)
    root = tree.getroot()
    game = root.find("game")

    # ── Find player faction ──
    world = game.find("world")
    faction_mgr = world.find("factionManager")
    player_faction = None
    for faction in faction_mgr.findall("allFactions/li"):
        def_el = faction.find("def")
        if def_el is not None and def_el.text == "PlayerColony":
            load_id = faction.find("loadID")
            if load_id is not None:
                player_faction = f"Faction_{load_id.text}"
                break
    if not player_faction:
        print("ERROR: Could not find PlayerColony faction")
        sys.exit(1)
    print(f"  Player faction: {player_faction}")

    # ── Parse map size ──
    maps = game.find("maps")
    map_li = maps.find("li")
    map_info = map_li.find("mapInfo")
    size_el = map_info.find("size")
    old_size_text = size_el.text
    parts = old_size_text.strip("()").split(",")
    old_map_size = int(parts[0].strip())

    resizing = map_size is not None and map_size != old_map_size
    effective_size = map_size if map_size is not None else old_map_size
    needs_grid_regen = (resizing or mountains != "none" or water != "none" or trees
                        or mountain_side is not None or ponds is not None
                        or ruins is not None or mountain_resources is not None)

    if resizing:
        print(f"  Map size: {old_size_text} → ({effective_size}, 1, {effective_size})")
        size_el.text = f"({effective_size}, 1, {effective_size})"
    else:
        print(f"  Map size: {old_size_text}")

    # ── Generate grids ──
    painter = None
    if needs_grid_regen:
        painter = _paint_and_set_grids(map_li, old_map_size, effective_size, terrain,
                                        mountains, water, temperature, seed,
                                        mountain_side=mountain_side, ponds=ponds,
                                        mountain_resources=mountain_resources)
    else:
        print("  Grids: keeping template data")

    # ── Collect animal templates before filtering ──
    things_el = map_li.find("things")
    all_things = list(things_el)

    # Grab one template per animal species for cloning later
    animal_templates: dict[str, ET.Element] = {}
    for thing in all_things:
        if "Pawn" in thing.get("Class", ""):
            def_el = thing.find("def")
            def_name = def_el.text if def_el is not None else ""
            if def_name in WILDLIFE_DEFS and def_name not in animal_templates:
                import copy
                animal_templates[def_name] = copy.deepcopy(thing)

    # ── Filter things ──
    kept = []
    removed_counts: dict[str, int] = {}

    for thing in all_things:
        if should_keep_thing(thing, player_faction, keep_ruins, keep_wildlife=keep_wildlife):
            kept.append(thing)
        else:
            def_el = thing.find("def")
            d = def_el.text if def_el is not None else thing.get("Class", "unknown")
            removed_counts[d] = removed_counts.get(d, 0) + 1

    things_el.clear()
    for thing in kept:
        things_el.append(thing)

    # Reposition if resizing
    if resizing:
        cx = effective_size // 2
        cz = effective_size // 2
        pawns = [t for t in kept if "Pawn" in t.get("Class", "")]
        items = [t for t in kept if "Pawn" not in t.get("Class", "")]

        for i, pawn in enumerate(pawns):
            reposition_pawn(pawn, cx + (i % 3), cz + (i // 3))

        # Scatter items randomly in open area around center
        item_rng = random.Random(seed + 50)
        margin = 10  # keep away from edges
        for item in items:
            for _ in range(20):  # try up to 20 random positions
                ix = item_rng.randint(margin, effective_size - margin - 1)
                iz = item_rng.randint(margin, effective_size - margin - 1)
                # Avoid mountain side (x < 8 if mountain_side == "left")
                if mountain_side == "left" and ix < 10:
                    continue
                if mountain_side == "right" and ix > effective_size - 10:
                    continue
                break
            reposition_thing(item, ix, iz)

    # Generate trees if requested
    if trees and painter is not None:
        tree_things = painter.generate_trees(density=tree_density, seed=seed)
        for t in tree_things:
            things_el.append(t)
        print(f"  Trees: {len(tree_things)} generated")

    # Generate berry bushes if requested
    if berry_bushes > 0 and painter is not None:
        bush_things = painter.generate_berry_bushes(count=berry_bushes, seed=seed)
        for b in bush_things:
            things_el.append(b)
        print(f"  Berry bushes: {len(bush_things)} generated")

    # Generate grass
    if grass and painter is not None:
        grass_things = painter.generate_grass(density=grass_density, seed=seed)
        for g in grass_things:
            things_el.append(g)
        print(f"  Grass: {len(grass_things)} generated (density={grass_density})")

    # Generate ruins after trees
    if ruins and painter is not None:
        ruin_things = painter.generate_ruins(ruins)
        for r in ruin_things:
            things_el.append(r)
        print(f"  Ruins: {len(ruin_things)} wall/door elements from {len(ruins)} structures")

    # Filter wildlife species if requested
    if wildlife_species is not None and animal_templates:
        filtered = {k: v for k, v in animal_templates.items() if k in wildlife_species}
        skipped = [s for s in wildlife_species if s not in animal_templates]
        if skipped:
            print(f"  Wildlife species not in template (skipped): {skipped}")
        animal_templates = filtered

    # Spawn wildlife by cloning templates
    if wildlife_count > 0 and animal_templates:
        import copy
        rng = random.Random(seed + 99)
        spawned = 0
        tid = 96000

        # Build spawn queue from distribution (exact counts per species)
        spawn_queue: list[str] = []
        if wildlife_distribution:
            for sp, count in wildlife_distribution.items():
                if sp in animal_templates:
                    spawn_queue.extend([sp] * count)
                else:
                    print(f"  Wildlife distribution: {sp} not in templates (skipped)")
            rng.shuffle(spawn_queue)
        elif wildlife_species:
            # Even split across specified species
            per_species = max(1, wildlife_count // len(wildlife_species))
            for sp in wildlife_species:
                if sp in animal_templates:
                    spawn_queue.extend([sp] * per_species)
            rng.shuffle(spawn_queue)
        else:
            # Fallback: even split across all available templates
            species = list(animal_templates.keys())
            per_species = max(1, wildlife_count // len(species))
            for sp in species:
                spawn_queue.extend([sp] * per_species)
            rng.shuffle(spawn_queue)

        attempts = 0
        qi = 0
        while spawned < wildlife_count and qi < len(spawn_queue) and attempts < wildlife_count * 20:
            attempts += 1
            x = rng.randint(3, effective_size - 4)
            z = rng.randint(3, effective_size - 4)
            # Avoid center where colonists spawn
            cx, cz = effective_size // 2, effective_size // 2
            if abs(x - cx) < 8 and abs(z - cz) < 8:
                continue
            sp = spawn_queue[qi]
            template = animal_templates[sp]
            animal = copy.deepcopy(template)
            pos_el = animal.find("pos")
            if pos_el is not None:
                pos_el.text = f"({x}, 0, {z})"
            id_el = animal.find("id")
            if id_el is not None:
                id_el.text = f"{sp}{tid}"
            tid += 1
            things_el.append(animal)
            spawned += 1
            qi += 1
        print(f"  Wildlife: {spawned} animals spawned from {len(animal_templates)} species templates")

    # Limit survival packs if requested
    if starting_packs is not None:
        pack_count = 0
        to_remove = []
        for thing in list(things_el):
            def_el = thing.find("def")
            if def_el is not None and def_el.text == "MealSurvivalPack":
                pack_count += 1
                if pack_count > starting_packs:
                    to_remove.append(thing)
        for thing in to_remove:
            things_el.remove(thing)
        print(f"  Survival packs: kept {starting_packs}, removed {len(to_remove)}")

    # Override starting item quantities
    if starting_items:
        for thing in list(things_el):
            def_el = thing.find("def")
            if def_el is None:
                continue
            def_name = def_el.text
            if def_name in starting_items:
                target = starting_items[def_name]
                if target == 0:
                    things_el.remove(thing)
                else:
                    sc = thing.find("stackCount")
                    if sc is not None:
                        sc.text = str(target)
                    else:
                        ET.SubElement(thing, "stackCount").text = str(target)
        print(f"  Starting items: {starting_items}")

    # Complete research projects
    if completed_research:
        game = root.find("game")
        rm = game.find(".//researchManager")
        if rm is not None:
            progress = rm.find("progress")
            if progress is not None:
                keys_el = progress.find("keys")
                values_el = progress.find("values")
                if keys_el is not None and values_el is not None:
                    key_items = list(keys_el)
                    val_items = list(values_el)
                    # Build lookup of existing research
                    research_map = {}
                    for i, k in enumerate(key_items):
                        research_map[k.text] = i
                    completed = []
                    for proj in completed_research:
                        if proj in research_map:
                            # Set progress to a large number (game treats >= cost as complete)
                            idx = research_map[proj]
                            val_items[idx].text = "10000"
                            completed.append(proj)
                        else:
                            # Add new entry
                            new_key = ET.SubElement(keys_el, "li")
                            new_key.text = proj
                            new_val = ET.SubElement(values_el, "li")
                            new_val.text = "10000"
                            completed.append(proj)
                    print(f"  Completed research: {completed}")

    print(f"  Things: {len(all_things)} → {len(list(things_el))}")
    top_removed = sorted(removed_counts.items(), key=lambda x: -x[1])[:10]
    for d, c in top_removed:
        print(f"    Stripped: {d} x{c}")

    # ── Clear map state ──
    _clear_map_state(map_li, resizing)

    # ── Register water bodies for fishing (Odyssey DLC) ──
    if ponds:
        # The game uses waterBodyTracker (not waterBodyManager)
        wbt = map_li.find(".//waterBodyTracker")
        if wbt is None:
            wbt = ET.SubElement(map_li, "waterBodyTracker")
        water_bodies_el = wbt.find("waterBodies")
        if water_bodies_el is None:
            water_bodies_el = ET.SubElement(wbt, "waterBodies")

        for pond in ponds:
            px, pz, pr = pond["x"], pond["z"], pond["radius"]
            cell_count = 0
            if painter:
                for z in range(max(0, pz - pr), min(effective_size, pz + pr + 1)):
                    for x in range(max(0, px - pr), min(effective_size, px + pr + 1)):
                        dist = ((x - px) ** 2 + (z - pz) ** 2) ** 0.5
                        if dist <= pr:
                            cell_count += 1
            else:
                cell_count = int(3.14 * pr * pr)

            # Population: ~1.5 per tile for small ponds, minimum 50 for reliable fishing
            population = max(50, int(cell_count * 1.5))
            wb = ET.SubElement(water_bodies_el, "li")
            ET.SubElement(wb, "rootCell").text = f"({px}, 0, {pz})"
            ET.SubElement(wb, "cellCount").text = str(cell_count)
            ET.SubElement(wb, "fishType").text = "Freshwater"
            ET.SubElement(wb, "population").text = str(population)
            ET.SubElement(wb, "shouldHaveFish").text = "True"
            common = ET.SubElement(wb, "commonFish")
            ET.SubElement(common, "li").text = "Fish_Bass"
            ET.SubElement(common, "li").text = "Fish_Tilapia"
            uncommon = ET.SubElement(wb, "uncommonFish")
            ET.SubElement(uncommon, "li").text = "Fish_Catfish"
            print(f"  Water body registered: pond at ({px},{pz}), {cell_count} cells, population={population}")

    # ── Camera ──
    camera = map_li.find("rememberedCameraPos")
    if camera is not None:
        root_pos = camera.find("rootPos")
        if root_pos is not None:
            root_pos.text = f"({effective_size / 2.0}, 65, {effective_size / 2.0})"

    # ── World map size ──
    if resizing and world is not None:
        world_info = world.find("info")
        if world_info is not None:
            init_size = world_info.find("initialMapSize")
            if init_size is not None:
                init_size.text = f"({effective_size}, 1, {effective_size})"

    # ── Write ──
    print(f"  Writing: {output_path}")
    ET.indent(tree, space="\t", level=0)
    with open(output_path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        tree.write(f, encoding="utf-8", xml_declaration=True)

    out_size = Path(output_path).stat().st_size
    in_size = Path(source_path).stat().st_size
    print(f"\n  Done! {in_size/1024/1024:.1f} MB → {out_size/1024/1024:.1f} MB "
          f"({out_size/in_size:.0%})")
    print(f"  Features: terrain={terrain}, mountains={mountains}, water={water}, "
          f"ruins={'yes' if keep_ruins else 'no'}")


def _paint_and_set_grids(
    map_li: ET.Element,
    old_size: int,
    new_size: int,
    terrain: str,
    mountains: str,
    water: str,
    temperature: float,
    seed: int,
    mountain_side: str | None = None,
    ponds: list[dict] | None = None,
    mountain_resources: list[dict] | None = None,
):
    """Paint terrain features and write all grids."""
    n = new_size
    painter = MapPainter(n, n, base_terrain=terrain)

    # Paint mountains
    if mountains == "border":
        painter.paint_mountains_border()
    elif mountains == "ring":
        painter.paint_mountains_ring()
    elif mountains == "corners":
        painter.paint_mountains_corners()
    elif mountains == "random":
        painter.paint_mountains_random(seed=seed)

    # Paint mountain side (after preset patterns, before water)
    if mountain_side is not None:
        painter.paint_mountains_side(mountain_side)

    # Paint water (after mountains so water can override mountain edges)
    if water == "river":
        painter.paint_water_river()
    elif water == "lake":
        painter.paint_water_lake()
    elif water == "border":
        painter.paint_water_border()
    elif water == "corners":
        painter.paint_water_corners()

    # Paint ponds (after preset water patterns)
    if ponds:
        for pond in ponds:
            painter.paint_pond(pond["x"], pond["z"], pond["radius"])

    # Finalize: compute fog based on mountain interior vs surface
    painter.finalize()

    # Embed mineable resources in mountains (after finalize sets fog)
    if mountain_resources:
        for res in mountain_resources:
            res_hash = ROCK_HASH.get(res["type"])
            if res_hash is None:
                print(f"  WARNING: Unknown resource type '{res['type']}', skipping")
                continue
            rx, rz = res["x"], res["z"]
            rw, rh = res["width"], res["height"]
            count = 0
            for z in range(rz, rz + rh):
                for x in range(rx, rx + rw):
                    if painter._in_bounds(x, z):
                        idx = painter._idx(x, z)
                        # Only replace existing mountain cells
                        if painter.rock[idx] != 0:
                            painter.rock[idx] = res_hash
                            count += 1
            print(f"  Mountain resource: {res['type']} patch {rw}x{rh} at ({rx},{rz}), {count} cells")

    mountain_cells = sum(1 for r in painter.rock if r != 0)
    fogged_cells = sum(1 for f in painter.fog if f)
    water_cells = sum(1 for t in painter.terrain if t in (TERRAIN_HASH.get("WaterShallow", 0), TERRAIN_HASH.get("WaterOceanDeep", 0)))
    print(f"  Painting: terrain={terrain}, mountains={mountains}, water={water}")
    print(f"  Cells: {mountain_cells} mountain ({fogged_cells} fogged interior), {water_cells} water")

    # ── Write terrain grids ──
    terrain_grid = map_li.find("terrainGrid")
    tg = terrain_grid.find("topGridDeflate")
    if tg is not None:
        tg.text = painter.encode_terrain()

    for sub in ["underGridDeflate", "foundationGridDeflate", "tempGridDeflate", "colorGridDeflate"]:
        el = terrain_grid.find(sub)
        if el is not None:
            el.text = make_ushort_grid(n, n, 0)

    # ── Roof grid ──
    roof_grid = map_li.find("roofGrid")
    if roof_grid is not None:
        el = roof_grid.find("roofsDeflate")
        if el is not None:
            el.text = painter.encode_roof()

    # ── Fog grid (from painter — mountain cells are fogged) ──
    fog_grid = map_li.find("fogGrid")
    if fog_grid is not None:
        el = fog_grid.find("fogGridDeflate")
        if el is not None:
            el.text = painter.encode_fog()

    # ── Snow grid (ushort) ──
    snow_grid = map_li.find("snowGrid")
    if snow_grid is not None:
        el = snow_grid.find("depthGridDeflate")
        if el is not None:
            el.text = make_ushort_grid(n, n, 0)

    # ── Gas grid (4 bytes/cell) ──
    gas_grid = map_li.find("gasGrid")
    if gas_grid is not None:
        el = gas_grid.find("gasDensityDeflate")
        if el is not None:
            el.text = make_gas_grid(n, n)

    # ── Sand grid (ushort) ──
    sand_grid = map_li.find("sandGrid")
    if sand_grid is not None:
        el = sand_grid.find("depthGridDeflate")
        if el is not None:
            el.text = make_ushort_grid(n, n, 0)

    # ── Pollution grid ──
    pollution_grid = map_li.find("pollutionGrid")
    if pollution_grid is not None:
        el = pollution_grid.find("grid")
        if el is not None:
            el.text = ""

    # ── Deep resource grid (ushort) ──
    deep_grid = map_li.find("deepResourceGrid")
    if deep_grid is not None:
        for sub in ["defGridDeflate", "countGridDeflate"]:
            el = deep_grid.find(sub)
            if el is not None:
                el.text = make_ushort_grid(n, n, 0)

    # ── Compressed thing map = rock data ──
    compressed_map = map_li.find("compressedThingMapDeflate")
    if compressed_map is not None:
        compressed_map.text = painter.encode_rock()

    # ── Temperature (ushort) ──
    temp_cache = map_li.find("temperatureCache")
    if temp_cache is not None:
        el = temp_cache.find("temperaturesDeflate")
        if el is not None:
            el.text = make_temperature_grid(n, n, temperature)

    # ── Remove geometry-dependent structures ──
    for tag in ["waterBodyTracker", "layoutStructureSketches"]:
        el = map_li.find(tag)
        if el is not None:
            map_li.remove(el)

    return painter


def _clear_map_state(map_li: ET.Element, resizing: bool):
    """Clear state that references stripped things or old geometry."""
    zone_mgr = map_li.find("zoneManager")
    if zone_mgr is not None:
        zones = zone_mgr.find("allZones")
        if zones is not None:
            zones.clear()

    desig_mgr = map_li.find("designationManager")
    if desig_mgr is not None:
        desigs = desig_mgr.find("allDesignations")
        if desigs is not None:
            desigs.clear()

    if resizing:
        area_mgr = map_li.find("areaManager")
        if area_mgr is not None:
            areas = area_mgr.find("areas")
            if areas is not None:
                for area in areas:
                    grid = area.find("innerGrid")
                    if grid is not None:
                        tc = grid.find("trueCount")
                        if tc is not None:
                            tc.text = "0"
                        cells = grid.find("cells")
                        if cells is not None:
                            cells.clear()

    for mgr_name in ["reservationManager", "enrouteManager",
                      "physicalInteractionReservationManager",
                      "attackTargetReservationManager",
                      "pawnDestinationReservationManager"]:
        mgr = map_li.find(mgr_name)
        if mgr is not None:
            for child in list(mgr):
                if child.tag != "map":
                    child.clear()

    lord_mgr = map_li.find("lordManager")
    if lord_mgr is not None:
        lords = lord_mgr.find("lords")
        if lords is not None:
            lords.clear()


def main():
    parser = argparse.ArgumentParser(description="Generate custom RimWorld saves")
    parser.add_argument("--source", default=None,
                        help="Template save (default: Baseline-Starter.rws)")
    parser.add_argument("--size", type=int, default=None,
                        help="Map size (default: template size)")
    parser.add_argument("--terrain", default="Soil",
                        help="Base terrain: Soil, Gravel, Sand, SoilRich, Mud (default: Soil)")
    parser.add_argument("--mountains", default="none",
                        choices=["none", "border", "ring", "corners", "random"],
                        help="Mountain placement pattern")
    parser.add_argument("--water", default="none",
                        choices=["none", "river", "lake", "border", "corners"],
                        help="Water placement pattern")
    parser.add_argument("--trees", action="store_true",
                        help="Generate trees on open terrain")
    parser.add_argument("--tree-density", type=float, default=0.08,
                        help="Tree density 0.0-1.0 (default: 0.08)")
    parser.add_argument("--keep-ruins", action="store_true",
                        help="Keep ancient structures from template")
    parser.add_argument("--temp", type=float, default=20.0,
                        help="Starting temperature °C (default: 20)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for random features (default: 42)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file (default: auto-named)")

    args = parser.parse_args()

    saves_dir = Path.home() / "Library/Application Support/RimWorld/Saves"
    source = args.source or str(saves_dir / "Baseline-Starter.rws")
    if not Path(source).exists():
        print(f"Template not found: {source}")
        sys.exit(1)

    parts = []
    if args.size:
        parts.append(f"{args.size}x{args.size}")
    if args.mountains != "none":
        parts.append(f"mt-{args.mountains}")
    if args.water != "none":
        parts.append(f"w-{args.water}")
    default_name = f"Custom-{'-'.join(parts) if parts else 'Clean'}.rws"
    output = args.output or str(saves_dir / default_name)

    generate_save(
        source_path=source,
        output_path=output,
        map_size=args.size,
        terrain=args.terrain,
        mountains=args.mountains,
        water=args.water,
        trees=args.trees,
        tree_density=args.tree_density,
        keep_ruins=args.keep_ruins,
        temperature=args.temp,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
