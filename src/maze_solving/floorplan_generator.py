#!/usr/bin/env python3
"""
floorplan_generator.py
=======================

Procedurally generates a multi-room building floor plan (via seeded
recursive space partitioning), cuts door and window openings into the
walls, and exports it as an SDF file that Gazebo can load directly
(either a standalone <model> or a full <world>).

The same --seed always produces the same layout; different seeds
produce different room counts/shapes/door-window placement.

Key ideas
---------
1. ROOMS: a Binary Space Partition (BSP) recursively splits the building
   footprint into rectangular rooms. Every split immediately creates one
   interior wall *and* records the split as a tree edge.
2. CONNECTIVITY: because every BSP split gets exactly one door, the
   union of all interior doors forms a spanning tree over the rooms --
   every room is guaranteed reachable from every other room, without
   any extra graph search. Rooms therefore behave like they're linked
   by short internal "corridors" (the doorways themselves); you can
   also carve a dedicated corridor room by biasing the partitioner
   (see --corridor).
3. WALLS: every wall is axis-aligned, so no rotations are needed -- a
   wall is just a box whose long axis is X or Y. Door/window openings
   are modeled as *gaps* cut out of that box, which turns one wall into
   2-3 sub-boxes (e.g. base sill + gap + lintel for a window).
4. EXPORT: each sub-box becomes one <collision>/<visual> pair inside a
   single static SDF <link>, which Gazebo renders/collides with
   directly -- no meshes required.

Usage
-----
    python3 floorplan_generator.py --seed 7 --width 14 --depth 10 \\
        --rooms 7 --out house.sdf --world --preview preview.png

    # Different seed -> different building
    python3 floorplan_generator.py --seed 8 --out house2.sdf

Run `python3 floorplan_generator.py --help` for all options.
"""

import argparse
import math
import random
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# --------------------------------------------------------------------------
# HARDCODED COMPETITION ARENA CONSTRAINTS
# --------------------------------------------------------------------------
# These come directly from the mission rulebook and are NOT meant to be
# loosened from the CLI. Anything below reads these constants instead of
# arbitrary user-supplied numbers; --width/--depth/etc. are still accepted
# for convenience but are validated/clamped against these values so an
# out-of-spec arena can never be exported.

ARENA_MAX_DIM_M = 15.0            # arena shall not exceed 15 m x 15 m
GRID_UNIT_M = 1.0                 # modular grid pitch == min corridor width
MIN_CORRIDOR_CLEAR_M = 1.0        # uniform clear corridor width, minimum
ROOM_STANDARD_M = 2.0             # standard room size: 2 m x 2 m
VERTICAL_CLEARANCE_FT = 8.0       # required headroom, corridors AND rooms
VERTICAL_CLEARANCE_M = VERTICAL_CLEARANCE_FT * 0.3048   # = 2.4384 m
HEADER_HEIGHT_M = 0.20            # visible door header/lintel depth
# Walls are built HEADER_HEIGHT_M taller than the mandated clearance so a
# real header box can sit above every doorway without ever eating into
# the 8 ft clear opening a drone actually flies through.
WALL_HEIGHT_M = VERTICAL_CLEARANCE_M + HEADER_HEIGHT_M
DOOR_PERPENDICULAR_CLEARANCE_M = 0.35
# ^ no wall may stand flush across from a doorway within this distance --
# a drone flying straight through a door must not immediately face a
# flat wall at point-blank range. (Kept well under the 2 m standard room
# size / 1 m corridor width so it flags true T-junction dead-ends without
# making every wall on a dense 2 m grid technically "in conflict".)

# Materials -- kept in one place so the exported SDF reads as a single,
# deliberately colour-coded arena rather than flat grey boxes. Chosen for
# maximum at-a-glance contrast: warm light interior walls vs. dark cool
# exterior envelope, a bright lintel colour that reads instantly as "door
# above", cool blue sills for windows, and a light floor that contrasts
# against every wall colour above it.
MAT_WALL_INT = ("0.64 0.54 0.68 1", "0.68 0.58 0.72 1", "0.05 0.05 0.05 1")
MAT_WALL_EXT = ("0.30 0.23 0.34 1", "0.34 0.26 0.38 1", "0.05 0.05 0.05 1")
MAT_HEADER = ("0.95 0.55 0.10 1", "1.00 0.60 0.12 1", "0.10 0.10 0.10 1")
MAT_SILL_INT = ("0.55 0.68 0.78 1", "0.60 0.72 0.82 1", "0.05 0.05 0.05 1")
MAT_SILL_EXT = ("0.20 0.30 0.42 1", "0.24 0.34 0.46 1", "0.05 0.05 0.05 1")
MAT_FLOOR = ("0.92 0.92 0.90 1", "0.96 0.96 0.94 1", "0.02 0.02 0.02 1")
MAT_NET = ("0.55 0.85 0.95 0.35", "0.55 0.85 0.95 0.35", "0.05 0.05 0.05 0.1")
MAT_ENTRY = ("0.05 0.95 0.20 1", "0.10 1.00 0.25 1", "0.30 0.30 0.30 1", "0.05 0.6 0.1 1")
MAT_EXIT = ("0.95 0.05 0.05 1", "1.00 0.10 0.10 1", "0.30 0.30 0.30 1", "0.6 0.05 0.05 1")
# each tuple: (ambient, diffuse, specular[, emissive])

# Optional random obstacle/furniture clutter placed inside rooms (see
# generate_objects below). Colours picked to stay visually distinct from
# every wall/marker colour above, and from each other.
MAT_OBJ_CRATE = ("0.55 0.35 0.15 1", "0.62 0.40 0.18 1", "0.05 0.05 0.05 1")   # wooden crate
MAT_OBJ_RUBBLE = ("0.42 0.42 0.44 1", "0.48 0.48 0.50 1", "0.05 0.05 0.05 1")  # debris/rubble
MAT_OBJ_BARREL = ("0.80 0.70 0.10 1", "0.90 0.78 0.12 1", "0.10 0.10 0.10 1")  # caution-yellow barrel
OBJECT_MATERIALS = {
    "obj_crate": MAT_OBJ_CRATE,
    "obj_rubble": MAT_OBJ_RUBBLE,
    "obj_barrel": MAT_OBJ_BARREL,
}


# --------------------------------------------------------------------------
# Geometry primitives
# --------------------------------------------------------------------------

@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    name: str = ""

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0


@dataclass
class Opening:
    kind: str          # 'door' or 'window'
    offset: float       # distance from wall.start, along the wall's length
    length: float
    sill: float = 0.9   # only used for windows (height of the base upstand)
    gap_height: float = 1.3   # vertical size of the open hole
    role: Optional[str] = None   # 'entry' / 'exit' tag for the two mission
                                  # access doors; None for ordinary doors


@dataclass
class Wall:
    axis: str            # 'h' (horizontal, fixed y) or 'v' (vertical, fixed x)
    fixed: float          # the constant coordinate (y for 'h', x for 'v')
    start: float          # start of the varying coordinate
    end: float            # end of the varying coordinate
    thickness: float
    exterior: bool = False
    openings: List[Opening] = field(default_factory=list)

    @property
    def length(self) -> float:
        return self.end - self.start


# --------------------------------------------------------------------------
# 1. BSP room partition
# --------------------------------------------------------------------------

def _snap(pos: float, origin: float, unit: float = GRID_UNIT_M) -> float:
    """Snap `pos` onto the modular grid anchored at `origin`, so every
    interior wall lands on the same 1 m pitch as the corridor width --
    this is what keeps corridor widths and grid dimensions uniform across
    the whole arena instead of arbitrary BSP fractions."""
    return origin + round((pos - origin) / unit) * unit


def generate_rooms(rng: random.Random, width: float, depth: float,
                    target_rooms: int, min_room: float,
                    corridor_bias: bool = False
                    ) -> Tuple[List[Rect], List[Wall]]:
    """Recursively split the footprint into `target_rooms` leaf rectangles
    on a modular grid (grid pitch = GRID_UNIT_M, matching the required
    uniform corridor width).

    Returns (rooms, interior_walls). Every interior_walls entry already
    knows its own length/position; doors are added to it later.
    """
    root = Rect(0.0, 0.0, width, depth)
    leaves: List[Rect] = [root]
    interior_walls: List[Wall] = []

    def can_split(r: Rect) -> bool:
        return r.w >= 2 * min_room or r.h >= 2 * min_room

    attempts = 0
    max_attempts = max(50, target_rooms * 25)
    first_split = True

    while len(leaves) < target_rooms and attempts < max_attempts:
        attempts += 1
        splittable = [r for r in leaves if can_split(r)]
        if not splittable:
            break

        # Optionally bias the very first split to be a thin corridor strip
        # along the long axis of the building, mimicking the reference
        # image's central hallway.
        if first_split and corridor_bias:
            r = root
        else:
            r = rng.choice(splittable)
        first_split = False

        can_x = r.w >= 2 * min_room
        can_y = r.h >= 2 * min_room
        if can_x and can_y:
            axis = rng.choice(["x", "y"])
        elif can_x:
            axis = "x"
        else:
            axis = "y"

        ratio = rng.uniform(0.38, 0.62)
        if axis == "x":
            raw_pos = r.x0 + r.w * ratio
            pos = _snap(raw_pos, 0.0)
            # keep both children >= min_room after snapping; nudge to the
            # nearest valid grid line instead of aborting the split
            if pos - r.x0 < min_room:
                pos = _snap(r.x0 + min_room, 0.0)
            if r.x1 - pos < min_room:
                pos = _snap(r.x1 - min_room, 0.0)
            if not (r.x0 + min_room - 1e-6 <= pos <= r.x1 - min_room + 1e-6):
                continue  # no valid grid line fits; skip this split attempt
            child_a = Rect(r.x0, r.y0, pos, r.y1)
            child_b = Rect(pos, r.y0, r.x1, r.y1)
            wall = Wall(axis="v", fixed=pos, start=r.y0, end=r.y1, thickness=0.0)
        else:
            raw_pos = r.y0 + r.h * ratio
            pos = _snap(raw_pos, 0.0)
            if pos - r.y0 < min_room:
                pos = _snap(r.y0 + min_room, 0.0)
            if r.y1 - pos < min_room:
                pos = _snap(r.y1 - min_room, 0.0)
            if not (r.y0 + min_room - 1e-6 <= pos <= r.y1 - min_room + 1e-6):
                continue
            child_a = Rect(r.x0, r.y0, r.x1, pos)
            child_b = Rect(r.x0, pos, r.x1, r.y1)
            wall = Wall(axis="h", fixed=pos, start=r.x0, end=r.x1, thickness=0.0)

        leaves.remove(r)
        leaves.extend([child_a, child_b])
        interior_walls.append(wall)

    for i, r in enumerate(leaves):
        r.name = f"room_{i}"

    return leaves, interior_walls


# --------------------------------------------------------------------------
# 2. Openings (doors on every interior wall + entrance/windows on exterior)
# --------------------------------------------------------------------------

def _perpendicular_conflicts(wall: Wall, all_walls: List[Wall],
                              clearance: float = DOOR_PERPENDICULAR_CLEARANCE_M
                              ) -> List[Tuple[float, float]]:
    """Find offset-space intervals along `wall` where a wall running the
    OTHER axis crosses/touches `wall`'s line. Placing a door inside one of
    these intervals would open it directly onto a flat perpendicular wall
    face -- exactly the "wall perpendicular to a door" case the mission
    rules forbid. Returns forbidden (lo, hi) intervals in wall-local
    offset coordinates (0..wall.length)."""
    other_axis = "v" if wall.axis == "h" else "h"
    line = wall.fixed
    forbidden = []
    for w2 in all_walls:
        if w2 is wall or w2.axis != other_axis:
            continue
        w2_lo, w2_hi = min(w2.start, w2.end), max(w2.start, w2.end)
        # does w2 touch/cross the line this wall sits on?
        if not (w2_lo - 1e-6 <= line <= w2_hi + 1e-6):
            continue
        cross_pos = w2.fixed  # position of the crossing wall along `wall`
        if not (wall.start - 1e-6 <= cross_pos <= wall.end + 1e-6):
            continue
        half = w2.thickness / 2.0 + clearance
        lo = (cross_pos - half) - wall.start
        hi = (cross_pos + half) - wall.start
        forbidden.append((lo, hi))
    forbidden.sort()
    return forbidden


def _overlaps_forbidden(offset: float, item_len: float,
                         forbidden: List[Tuple[float, float]]) -> bool:
    for lo, hi in forbidden:
        if offset < hi and offset + item_len > lo:
            return True
    return False


def _place_offset(rng: random.Random, length: float, item_len: float,
                   margin: float, existing: List[Opening], tries: int = 24,
                   forbidden: Optional[List[Tuple[float, float]]] = None
                   ) -> Optional[float]:
    """Find a non-overlapping offset for an opening of size item_len on a
    wall of given length, respecting corner margins, other openings, and
    (if given) `forbidden` no-door zones opposite perpendicular walls.

    Does an exhaustive fine-grained scan (not just random sampling) so a
    valid slot is found whenever one geometrically exists; falls back to
    the least-bad (minimum forbidden-overlap) slot only if none is clean."""
    usable = length - 2 * margin
    if usable < item_len:
        return None

    forbidden = forbidden or []

    def opening_ok(offset: float) -> bool:
        for o in existing:
            if not (offset + item_len <= o.offset - 0.05 or
                    offset >= o.offset + o.length + 0.05):
                return False
        return True

    step = min(0.05, usable / 40.0) if usable > 0 else 0.05
    step = max(step, 1e-3)
    n_steps = max(1, int(usable / step))

    best_fallback = None
    best_fallback_overlap = None
    for i in range(n_steps + 1):
        offset = margin + (i / n_steps) * (usable - item_len) if n_steps else margin
        if not opening_ok(offset):
            continue
        if not _overlaps_forbidden(offset, item_len, forbidden):
            return offset
        overlap = sum(max(0.0, min(offset + item_len, hi) - max(offset, lo))
                       for lo, hi in forbidden)
        if best_fallback is None or overlap < best_fallback_overlap:
            best_fallback, best_fallback_overlap = offset, overlap
    return best_fallback


def add_interior_doors(rng: random.Random, walls: List[Wall],
                        all_walls: List[Wall],
                        door_width: float, door_height: float,
                        margin: float) -> None:
    """Give every interior (BSP-split) wall exactly one door -> guarantees
    every room is reachable from every other room. Door offsets avoid the
    "no wall perpendicular to a door" zones computed against the FULL
    wall list (interior + exterior), so no drone flies straight out of a
    doorway into a flat wall face."""
    for wall in walls:
        w = min(door_width, max(0.6, wall.length - 2 * margin))
        forbidden = _perpendicular_conflicts(wall, all_walls)
        offset = _place_offset(rng, wall.length, w, margin, wall.openings,
                                forbidden=forbidden)
        if offset is None:
            # wall too short for a full door margin; place the widest door
            # that still fits, aiming for the mandated corridor width and
            # never leaving the room unreachable
            w = min(wall.length, max(MIN_CORRIDOR_CLEAR_M, wall.length * 0.5))
            offset = max(0.0, (wall.length - w) / 2.0)
        wall.openings.append(Opening(kind="door", offset=offset, length=w,
                                      gap_height=door_height))


def _wall_world_point(wall: Wall, offset: float, length: float) -> Tuple[float, float]:
    mid = wall.start + offset + length / 2.0
    if wall.axis == "h":
        return (mid, wall.fixed)
    return (wall.fixed, mid)


def add_exterior_openings(rng: random.Random, ext_walls: List[Wall],
                           all_walls: List[Wall],
                           door_width: float, door_height: float,
                           window_width: float, window_sill: float,
                           window_height: float, max_windows_per_wall: int,
                           margin: float
                           ) -> Tuple[Optional[Tuple[float, float]],
                                      Optional[Tuple[float, float]]]:
    """Add the mission's single designated entry point and single
    designated exit point (on two different exterior walls), plus a
    scattering of windows across all exterior walls. Returns
    (entry_xy, exit_xy) in world coordinates."""
    # Pick a pair of OPPOSITE exterior walls (south<->north or west<->east)
    # rather than any 2 of the 4, so entry and exit are always separated by
    # the full building span on that axis instead of possibly landing on
    # two walls that share a corner (and could end up close together).
    opposite_pairs = [(ext_walls[0], ext_walls[1]), (ext_walls[2], ext_walls[3])]
    chosen_pair = rng.choice(opposite_pairs)
    entry_wall, exit_wall = rng.sample(chosen_pair, 2)
    entry_xy = None
    exit_xy = None

    for wall, role in ((entry_wall, "entry"), (exit_wall, "exit")):
        w = min(door_width, wall.length - 2 * margin)
        if w <= 0:
            continue  # wall too short for any opening at all -- skip cleanly
        forbidden = _perpendicular_conflicts(wall, all_walls)
        offset = _place_offset(rng, wall.length, w, margin, wall.openings,
                                forbidden=forbidden)
        if offset is None:
            continue
        wall.openings.append(
            Opening(kind="door", offset=offset, length=w,
                    gap_height=door_height, role=role))
        xy = _wall_world_point(wall, offset, w)
        if role == "entry":
            entry_xy = xy
        else:
            exit_xy = xy

    for wall in ext_walls:
        n_windows = rng.randint(0, max_windows_per_wall)
        for _ in range(n_windows):
            w = min(window_width, wall.length - 2 * margin)
            if w < 0.4:
                continue
            forbidden = _perpendicular_conflicts(wall, all_walls)
            offset = _place_offset(rng, wall.length, w, margin, wall.openings,
                                    forbidden=forbidden)
            if offset is None:
                continue
            wall.openings.append(
                Opening(kind="window", offset=offset, length=w,
                        sill=window_sill, gap_height=window_height))

    return entry_xy, exit_xy


def make_exterior_walls(width: float, depth: float) -> List[Wall]:
    return [
        Wall(axis="h", fixed=0.0, start=0.0, end=width, thickness=0.0, exterior=True),   # south
        Wall(axis="h", fixed=depth, start=0.0, end=width, thickness=0.0, exterior=True),  # north
        Wall(axis="v", fixed=0.0, start=0.0, end=depth, thickness=0.0, exterior=True),   # west
        Wall(axis="v", fixed=width, start=0.0, end=depth, thickness=0.0, exterior=True),  # east
    ]


# --------------------------------------------------------------------------
# 3. Turn a Wall (with openings) into a list of solid 3D boxes
# --------------------------------------------------------------------------

@dataclass
class Box:
    cx: float
    cy: float
    cz: float
    sx: float
    sy: float
    sz: float
    exterior: bool = False
    role: str = "wall"    # 'wall' | 'header' | 'sill' -- drives SDF material


def wall_to_boxes(wall: Wall, wall_height: float) -> List[Box]:
    """Split one wall into solid boxes, leaving gaps for its openings.
    Every door gets a real header box above the opening (wall_height is
    built HEADER_HEIGHT_M taller than the mandated clear height, so the
    header never eats into the required 8 ft clearance)."""
    segments: List[Tuple[float, float, float, float, str]] = []  # (s, e, z_lo, z_hi, role)
    openings = sorted(wall.openings, key=lambda o: o.offset)
    cursor = 0.0
    L = wall.length

    for o in openings:
        o_start = max(0.0, o.offset)
        o_end = min(L, o.offset + o.length)
        if o_start > cursor:
            segments.append((cursor, o_start, 0.0, wall_height, "wall"))

        if o.kind == "door":
            top = min(o.gap_height, wall_height)
            if top < wall_height:
                segments.append((o_start, o_end, top, wall_height, "header"))
            # nothing below the header: open doorway down to the floor
        else:  # window
            sill = min(o.sill, wall_height)
            top = min(o.sill + o.gap_height, wall_height)
            if sill > 0:
                segments.append((o_start, o_end, 0.0, sill, "sill"))
            if top < wall_height:
                segments.append((o_start, o_end, top, wall_height, "header"))

        cursor = max(cursor, o_end)

    if cursor < L:
        segments.append((cursor, L, 0.0, wall_height, "wall"))

    boxes = []
    for (s, e, z_lo, z_hi, role) in segments:
        length = e - s
        if length <= 1e-6 or (z_hi - z_lo) <= 1e-6:
            continue
        mid = wall.start + (s + e) / 2.0
        cz = (z_lo + z_hi) / 2.0
        sz = z_hi - z_lo
        if wall.axis == "h":
            cx, cy = mid, wall.fixed
            sx, sy = length, wall.thickness
        else:
            cx, cy = wall.fixed, mid
            sx, sy = wall.thickness, length
        boxes.append(Box(cx, cy, cz, sx, sy, sz, exterior=wall.exterior, role=role))
    return boxes


# --------------------------------------------------------------------------
# 3b. Optional random obstacle/furniture clutter placed inside rooms
# --------------------------------------------------------------------------
# Purely additive: does not touch wall/door/room geometry at all. Each
# object is confined to a room's *clear interior* -- inset from every one
# of that room's edges by half the wall thickness plus a safety margin, the
# same inset a wall box itself occupies -- so an object can never
# geometrically overlap a wall. This is verified programmatically below
# (verify_objects_clear_of_walls) rather than just assumed.

def generate_objects(rng: random.Random, room_rects: List[Rect],
                      wall_thickness: float,
                      min_per_room: int = 0, max_per_room: int = 2,
                      min_size: float = 0.3, max_size: float = 0.6,
                      wall_clearance: float = 0.15) -> List[Box]:
    """Scatter small obstacle boxes (crates / rubble / barrels) inside each
    room -- matches the 'damaged building' arena theme -- while guaranteeing
    every object stays clear of every wall."""
    objects: List[Box] = []
    inset = wall_thickness / 2.0 + wall_clearance
    kinds = list(OBJECT_MATERIALS.keys())

    for room in room_rects:
        inner = Rect(room.x0 + inset, room.y0 + inset,
                     room.x1 - inset, room.y1 - inset)
        if inner.w <= min_size or inner.h <= min_size:
            continue  # room too small to safely fit any object

        n_target = rng.randint(min_per_room, max_per_room)
        placed: List[Tuple[float, float, float, float]] = []  # x0,y0,x1,y1
        tries_left = max(1, n_target) * 20

        while len(placed) < n_target and tries_left > 0:
            tries_left -= 1
            side_x = rng.uniform(min_size, min(max_size, inner.w))
            side_y = rng.uniform(min_size, min(max_size, inner.h))
            cx = rng.uniform(inner.x0 + side_x / 2.0, inner.x1 - side_x / 2.0)
            cy = rng.uniform(inner.y0 + side_y / 2.0, inner.y1 - side_y / 2.0)
            x0, y0 = cx - side_x / 2.0, cy - side_y / 2.0
            x1, y1 = cx + side_x / 2.0, cy + side_y / 2.0

            gap = 0.1  # keep objects from touching each other too
            overlap = any(not (x1 + gap <= ox0 or x0 - gap >= ox1 or
                                y1 + gap <= oy0 or y0 - gap >= oy1)
                          for (ox0, oy0, ox1, oy1) in placed)
            if overlap:
                continue

            placed.append((x0, y0, x1, y1))
            height = rng.uniform(0.25, 0.9)
            kind = rng.choice(kinds)
            objects.append(Box(cx, cy, height / 2.0, side_x, side_y, height,
                               exterior=False, role=kind))

    return objects


def verify_objects_clear_of_walls(object_boxes: List[Box],
                                   wall_boxes: List[Box]) -> int:
    """Belt-and-braces runtime check: confirm no obstacle box's XY
    footprint overlaps any wall box's XY footprint. Should never fire
    given the inset in generate_objects(); raises immediately if it ever
    does, so a bad placement can never silently ship."""
    def extent(b: Box):
        return (b.cx - b.sx / 2.0, b.cx + b.sx / 2.0,
                b.cy - b.sy / 2.0, b.cy + b.sy / 2.0)

    for ob in object_boxes:
        ox0, ox1, oy0, oy1 = extent(ob)
        for wb in wall_boxes:
            wx0, wx1, wy0, wy1 = extent(wb)
            if ox0 < wx1 and ox1 > wx0 and oy0 < wy1 and oy1 > wy0:
                raise RuntimeError(
                    f"Object at ({ob.cx:.2f},{ob.cy:.2f}) overlaps a wall "
                    f"box at ({wb.cx:.2f},{wb.cy:.2f}) -- placement bug.")
    return len(object_boxes)


# --------------------------------------------------------------------------
# 4. SDF export
# --------------------------------------------------------------------------

def _set_material(el: ET.Element, mat: Tuple[str, ...]) -> None:
    """mat = (ambient, diffuse, specular[, emissive]) rgba strings."""
    material = ET.SubElement(el, "material")
    ET.SubElement(material, "ambient").text = mat[0]
    ET.SubElement(material, "diffuse").text = mat[1]
    if len(mat) > 2:
        ET.SubElement(material, "specular").text = mat[2]
    if len(mat) > 3:
        ET.SubElement(material, "emissive").text = mat[3]


def _box_material(b: "Box") -> Tuple[str, ...]:
    if b.role in OBJECT_MATERIALS:
        return OBJECT_MATERIALS[b.role]
    if b.role == "header":
        return MAT_HEADER
    if b.role == "sill":
        return MAT_SILL_EXT if b.exterior else MAT_SILL_INT
    return MAT_WALL_EXT if b.exterior else MAT_WALL_INT


def _add_box_link_geometry(link: ET.Element, boxes: List[Box]) -> None:
    for i, b in enumerate(boxes):
        for kind in ("collision", "visual"):
            el = ET.SubElement(link, kind, {"name": f"{kind}_{i}"})
            pose = ET.SubElement(el, "pose")
            pose.text = f"{b.cx:.4f} {b.cy:.4f} {b.cz:.4f} 0 0 0"
            geom = ET.SubElement(el, "geometry")
            box_el = ET.SubElement(geom, "box")
            size = ET.SubElement(box_el, "size")
            size.text = f"{b.sx:.4f} {b.sy:.4f} {b.sz:.4f}"
            if kind == "visual":
                _set_material(el, _box_material(b))


def build_sdf(boxes: List[Box], width: float, depth: float,
              model_name: str, as_world: bool,
              wall_height: float = VERTICAL_CLEARANCE_M,
              entry_xy: Optional[Tuple[float, float]] = None,
              exit_xy: Optional[Tuple[float, float]] = None,
              floor_thickness: float = 0.05,
              object_boxes: Optional[List[Box]] = None
              ) -> str:
    sdf = ET.Element("sdf", {"version": "1.6"})
    parent = sdf

    if as_world:
        world = ET.SubElement(sdf, "world", {"name": "generated_floorplan_world"})

        # Inline sun + ground plane instead of `model://` includes: those
        # rely on Gazebo's model database / Fuel cache being resolvable,
        # which fails offline or with a bare gz-sim install. Defining them
        # directly makes the world file fully self-contained.
        light = ET.SubElement(world, "light", {"name": "sun", "type": "directional"})
        ET.SubElement(light, "cast_shadows").text = "true"
        ET.SubElement(light, "pose").text = "0 0 10 0 0 0"
        ET.SubElement(light, "diffuse").text = "0.8 0.8 0.8 1"
        ET.SubElement(light, "specular").text = "0.2 0.2 0.2 1"
        ET.SubElement(light, "direction").text = "-0.5 0.1 -0.9"

        ground = ET.SubElement(world, "model", {"name": "ground_plane"})
        ET.SubElement(ground, "static").text = "true"
        gplink = ET.SubElement(ground, "link", {"name": "link"})
        gcol = ET.SubElement(gplink, "collision", {"name": "collision"})
        gcgeom = ET.SubElement(gcol, "geometry")
        gcplane = ET.SubElement(gcgeom, "plane")
        ET.SubElement(gcplane, "normal").text = "0 0 1"
        ET.SubElement(gcplane, "size").text = "100 100"
        gvis = ET.SubElement(gplink, "visual", {"name": "visual"})
        gvgeom = ET.SubElement(gvis, "geometry")
        gvplane = ET.SubElement(gvgeom, "plane")
        ET.SubElement(gvplane, "normal").text = "0 0 1"
        ET.SubElement(gvplane, "size").text = "100 100"
        gmat = ET.SubElement(gvis, "material")
        ET.SubElement(gmat, "ambient").text = "0.8 0.8 0.8 1"
        ET.SubElement(gmat, "diffuse").text = "0.8 0.8 0.8 1"

        parent = world

    model = ET.SubElement(parent, "model", {"name": model_name})
    ET.SubElement(model, "static").text = "true"
    ET.SubElement(model, "pose").text = "0 0 0 0 0 0"

    # walls
    wall_link = ET.SubElement(model, "link", {"name": "walls"})
    _add_box_link_geometry(wall_link, boxes)

    # floor slab matching the footprint
    floor_link = ET.SubElement(model, "link", {"name": "floor"})
    floor_box = Box(width / 2.0, depth / 2.0, -floor_thickness / 2.0,
                     width, depth, floor_thickness, role="floor")
    for kind in ("collision", "visual"):
        el = ET.SubElement(floor_link, kind, {"name": kind})
        pose = ET.SubElement(el, "pose")
        pose.text = f"{floor_box.cx:.4f} {floor_box.cy:.4f} {floor_box.cz:.4f} 0 0 0"
        geom = ET.SubElement(el, "geometry")
        box_el = ET.SubElement(geom, "box")
        size = ET.SubElement(box_el, "size")
        size.text = f"{floor_box.sx:.4f} {floor_box.sy:.4f} {floor_box.sz:.4f}"
        if kind == "visual":
            _set_material(el, MAT_FLOOR)

    # net cover over the top of the arena -- required so the arena is
    # fully enclosed and GPS-denied, matching a physical safety net rather
    # than a solid roof (thin, translucent, still collidable).
    net_link = ET.SubElement(model, "link", {"name": "ceiling_net"})
    net_box = Box(width / 2.0, depth / 2.0, wall_height + 0.02,
                   width, depth, 0.04)
    for kind in ("collision", "visual"):
        el = ET.SubElement(net_link, kind, {"name": kind})
        pose = ET.SubElement(el, "pose")
        pose.text = f"{net_box.cx:.4f} {net_box.cy:.4f} {net_box.cz:.4f} 0 0 0"
        geom = ET.SubElement(el, "geometry")
        box_el = ET.SubElement(geom, "box")
        size = ET.SubElement(box_el, "size")
        size.text = f"{net_box.sx:.4f} {net_box.sy:.4f} {net_box.sz:.4f}"
        if kind == "visual":
            _set_material(el, MAT_NET)

    # designated entry / exit markers (visual only, non-colliding) so the
    # single mandated entry point and single mandated exit point are
    # identifiable in the exported world
    for tag, xy, mat in (("entry_marker", entry_xy, MAT_ENTRY),
                          ("exit_marker", exit_xy, MAT_EXIT)):
        if xy is None:
            continue
        mk_link = ET.SubElement(model, "link", {"name": tag})
        vis = ET.SubElement(mk_link, "visual", {"name": "visual"})
        pose = ET.SubElement(vis, "pose")
        pose.text = f"{xy[0]:.4f} {xy[1]:.4f} {wall_height / 2.0:.4f} 0 0 0"
        geom = ET.SubElement(vis, "geometry")
        cyl = ET.SubElement(geom, "cylinder")
        ET.SubElement(cyl, "radius").text = "0.08"
        ET.SubElement(cyl, "length").text = f"{wall_height:.4f}"
        _set_material(vis, mat)

    # optional random obstacle/furniture clutter -- collidable so it reads
    # as real obstacles for the drone, purely additive to the arena
    if object_boxes:
        objects_link = ET.SubElement(model, "link", {"name": "objects"})
        _add_box_link_geometry(objects_link, object_boxes)

    raw = ET.tostring(sdf, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # drop the extra blank lines minidom likes to add
    return "\n".join(line for line in pretty.split("\n") if line.strip())


# --------------------------------------------------------------------------
# 5. Preview render (matplotlib, isometric-ish, matches the reference look)
# --------------------------------------------------------------------------

def render_preview(boxes: List[Box], width: float, depth: float, path: str,
                    entry_xy: Optional[Tuple[float, float]] = None,
                    exit_xy: Optional[Tuple[float, float]] = None,
                    wall_height: float = VERTICAL_CLEARANCE_M,
                    object_boxes: Optional[List[Box]] = None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect((width, depth, max(width, depth) * 0.35))

    # ground grid, extending past the footprint like the reference image
    pad = max(width, depth) * 0.6
    gx0, gx1 = -pad, width + pad
    gy0, gy1 = -pad, depth + pad
    step = 1.0
    xs = [gx0 + i * step for i in range(int((gx1 - gx0) / step) + 1)]
    ys = [gy0 + i * step for i in range(int((gy1 - gy0) / step) + 1)]
    for x in xs:
        ax.plot([x, x], [gy0, gy1], [0, 0], color="0.75", linewidth=0.4)
    for y in ys:
        ax.plot([gx0, gx1], [y, y], [0, 0], color="0.75", linewidth=0.4)

    def cuboid_faces(b: Box):
        x0, x1 = b.cx - b.sx / 2, b.cx + b.sx / 2
        y0, y1 = b.cy - b.sy / 2, b.cy + b.sy / 2
        z0, z1 = b.cz - b.sz / 2, b.cz + b.sz / 2
        pts = {
            "lll": (x0, y0, z0), "hll": (x1, y0, z0),
            "hhl": (x1, y1, z0), "lhl": (x0, y1, z0),
            "llh": (x0, y0, z1), "hlh": (x1, y0, z1),
            "hhh": (x1, y1, z1), "lhh": (x0, y1, z1),
        }
        faces = [
            [pts["lll"], pts["hll"], pts["hhl"], pts["lhl"]],  # bottom
            [pts["llh"], pts["hlh"], pts["hhh"], pts["lhh"]],  # top
            [pts["lll"], pts["hll"], pts["hlh"], pts["llh"]],  # front
            [pts["lhl"], pts["hhl"], pts["hhh"], pts["lhh"]],  # back
            [pts["lll"], pts["lhl"], pts["lhh"], pts["llh"]],  # left
            [pts["hll"], pts["hhl"], pts["hhh"], pts["hlh"]],  # right
        ]
        return faces

    # colour palette mirrors the SDF materials 1:1 so the preview and the
    # Gazebo-loaded arena read the same way at a glance
    PREVIEW_COLORS = {
        "header": "#f28c12",
        "sill_int": "#8fb4c9",
        "sill_ext": "#33495e",
        "wall_int": "#a38aad",
        "wall_ext": "#4d3a5c",
        "obj_crate": "#8c592a",
        "obj_rubble": "#787a7d",
        "obj_barrel": "#cca31c",
    }

    def box_color(b: Box) -> str:
        if b.role == "header":
            return PREVIEW_COLORS["header"]
        if b.role == "sill":
            return PREVIEW_COLORS["sill_ext"] if b.exterior else PREVIEW_COLORS["sill_int"]
        if b.role in OBJECT_MATERIALS:
            return PREVIEW_COLORS[b.role]
        return PREVIEW_COLORS["wall_ext"] if b.exterior else PREVIEW_COLORS["wall_int"]

    # mplot3d doesn't do real depth-buffering across separate Poly3DCollection
    # artists -- small objects sitting "inside" a tall wall's bounding volume
    # can get drawn in the wrong order. Work around it with an explicit
    # painter's-algorithm pass: sort every box (walls AND objects together)
    # farthest-from-camera first and add them to the axes in that order, so
    # nearer geometry is always drawn on top of farther geometry.
    elev_r = math.radians(28)
    azim_r = math.radians(-60)
    cam_dir = (math.cos(elev_r) * math.cos(azim_r),
               math.cos(elev_r) * math.sin(azim_r),
               math.sin(elev_r))
    all_draw_boxes = list(boxes) + list(object_boxes or [])
    all_draw_boxes.sort(
        key=lambda b: b.cx * cam_dir[0] + b.cy * cam_dir[1] + b.cz * cam_dir[2])

    for b in all_draw_boxes:
        edge = "0.2" if b.role in OBJECT_MATERIALS else "0.3"
        collection = Poly3DCollection(cuboid_faces(b), facecolor=box_color(b),
                                       edgecolor=edge, linewidths=0.4)
        ax.add_collection3d(collection)

    # entry / exit markers as small vertical posts, matching the SDF cylinders
    for xy, color in ((entry_xy, "#0dff33"), (exit_xy, "#ff1010")):
        if xy is None:
            continue
        ax.plot([xy[0], xy[0]], [xy[1], xy[1]], [0, wall_height],
                color=color, linewidth=4, solid_capstyle="round")

    ax.set_xlim(gx0, gx1)
    ax.set_ylim(gy0, gy1)
    ax.set_zlim(0, max(width, depth) * 0.5)
    ax.view_init(elev=28, azim=-60)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# --------------------------------------------------------------------------
# 6. CLI
# --------------------------------------------------------------------------

def generate(seed: int, width: float, depth: float, rooms: int,
             min_room: float, wall_height: float, wall_thickness: float,
             door_width: float, door_height: float, window_width: float,
             window_sill: float, window_height: float,
             max_windows_per_wall: int, corridor_bias: bool,
             add_objects: bool = True,
             min_objects_per_room: int = 0, max_objects_per_room: int = 2,
             object_min_size: float = 0.3, object_max_size: float = 0.6
             ) -> Tuple[List[Box], List[Rect], Tuple[float, float], Tuple[float, float], List[Box]]:
    # ---- enforce the hardcoded mission constraints -----------------------
    if width > ARENA_MAX_DIM_M + 1e-6 or depth > ARENA_MAX_DIM_M + 1e-6:
        raise ValueError(
            f"Arena footprint {width}m x {depth}m exceeds the mandated "
            f"max of {ARENA_MAX_DIM_M}m x {ARENA_MAX_DIM_M}m.")
    if min_room < ROOM_STANDARD_M:
        min_room = ROOM_STANDARD_M          # standard room size: 2m x 2m
    if wall_height < WALL_HEIGHT_M:
        wall_height = WALL_HEIGHT_M  # 8 ft clearance + a real header depth
    # every doorway/opening a drone flies through is the "corridor" for
    # mission-rule purposes -- clamp its width up to the mandated uniform
    # clear width, same as min_room/wall_height above.
    if door_width < MIN_CORRIDOR_CLEAR_M:
        door_width = MIN_CORRIDOR_CLEAR_M
    # the clear opening under the header is pinned to exactly 8 ft --
    # never affected by whatever wall_height ends up being, so headroom
    # through every doorway stays >= the mandated clearance
    door_height = VERTICAL_CLEARANCE_M
    min_wall_span = MIN_CORRIDOR_CLEAR_M + wall_thickness
    if min_room < min_wall_span:
        min_room = min_wall_span

    rng = random.Random(seed)

    room_rects, interior_walls = generate_rooms(
        rng, width, depth, rooms, min_room, corridor_bias)
    exterior_walls = make_exterior_walls(width, depth)

    for wall in interior_walls + exterior_walls:
        wall.thickness = wall_thickness

    all_walls = interior_walls + exterior_walls

    add_interior_doors(rng, interior_walls, all_walls, door_width, door_height,
                        margin=wall_thickness * 2 + 0.15)
    entry_xy, exit_xy = add_exterior_openings(
        rng, exterior_walls, all_walls, door_width, door_height,
        window_width, window_sill, window_height, max_windows_per_wall,
        margin=wall_thickness * 2 + 0.15)

    boxes: List[Box] = []
    for wall in all_walls:
        boxes.extend(wall_to_boxes(wall, wall_height))

    # optional random obstacle/furniture clutter -- purely additive, never
    # touches wall/door/room geometry; verified clear of every wall below
    object_boxes: List[Box] = []
    if add_objects:
        object_boxes = generate_objects(
            rng, room_rects, wall_thickness,
            min_per_room=min_objects_per_room, max_per_room=max_objects_per_room,
            min_size=object_min_size, max_size=object_max_size)
        verify_objects_clear_of_walls(object_boxes, boxes)

    return boxes, room_rects, entry_xy, exit_xy, object_boxes


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=0, help="RNG seed; same seed = same building")
    p.add_argument("--width", type=float, default=15.0,
                   help=f"Building footprint width (m), max {ARENA_MAX_DIM_M}")
    p.add_argument("--depth", type=float, default=15.0,
                   help=f"Building footprint depth (m), max {ARENA_MAX_DIM_M}")
    p.add_argument("--rooms", type=int, default=6, help="Target number of rooms")
    p.add_argument("--min-room", type=float, default=ROOM_STANDARD_M,
                   help=f"Minimum room side length (m); clamped up to the "
                        f"standard {ROOM_STANDARD_M} m room size")
    p.add_argument("--wall-height", type=float, default=WALL_HEIGHT_M,
                   help=f"Wall height (m); clamped up to {WALL_HEIGHT_M:.4f} m "
                        f"= {VERTICAL_CLEARANCE_FT} ft clearance + "
                        f"{HEADER_HEIGHT_M} m header depth")
    p.add_argument("--wall-thickness", type=float, default=0.12, help="Wall thickness (m)")
    p.add_argument("--door-width", type=float, default=MIN_CORRIDOR_CLEAR_M,
                   help=f"Door/opening width (m); clamped up to the mandated "
                        f"uniform corridor clear width of {MIN_CORRIDOR_CLEAR_M} m")
    p.add_argument("--door-height", type=float, default=VERTICAL_CLEARANCE_M,
                   help="Door clear-opening height (m); always pinned to the "
                        "8 ft mandated clearance -- the header above it eats "
                        "into wall_height, never into this")
    p.add_argument("--window-width", type=float, default=1.1, help="Window width (m)")
    p.add_argument("--window-sill", type=float, default=0.9, help="Window sill height (m)")
    p.add_argument("--window-height", type=float, default=1.2, help="Window opening height (m)")
    p.add_argument("--max-windows-per-wall", type=int, default=0,
                    help="Max random windows placed on each exterior wall "
                         "(0 = no windows, doors only)")
    p.add_argument("--corridor", action="store_true",
                    help="Bias the first split to create a long corridor-like room")
    p.add_argument("--no-objects", dest="objects", action="store_false", default=True,
                    help="Disable random obstacle/furniture clutter inside rooms "
                         "(on by default; every object is guaranteed clear of "
                         "every wall)")
    p.add_argument("--min-objects-per-room", type=int, default=0,
                    help="Minimum obstacle objects placed per room")
    p.add_argument("--max-objects-per-room", type=int, default=2,
                    help="Maximum obstacle objects placed per room")
    p.add_argument("--object-min-size", type=float, default=0.3,
                    help="Minimum obstacle footprint side length (m)")
    p.add_argument("--object-max-size", type=float, default=0.6,
                    help="Maximum obstacle footprint side length (m)")
    p.add_argument("--model-name", type=str, default="generated_floorplan")
    p.add_argument("--world", action="store_true",
                    help="Wrap the model in a full <world> (ground_plane + sun) "
                         "instead of exporting a bare <model>")
    p.add_argument("--out", type=str, default="floorplan.sdf", help="Output SDF path")
    p.add_argument("--preview", type=str, default=None,
                    help="Optional PNG path for a 3D matplotlib preview")
    args = p.parse_args()

    if args.width > ARENA_MAX_DIM_M or args.depth > ARENA_MAX_DIM_M:
        p.error(f"--width/--depth cannot exceed the mandated arena size of "
                 f"{ARENA_MAX_DIM_M}m x {ARENA_MAX_DIM_M}m "
                 f"(got {args.width}m x {args.depth}m)")

    # a wall needs at least 2*margin of clear span before a door/window can
    # even be considered; below that, exterior walls can't host a real
    # entry/exit opening at all -- fail loudly here instead of silently
    # shipping an arena with no entry or exit.
    min_margin_span = 2 * (args.wall_thickness * 2 + 0.15)
    if args.width < min_margin_span or args.depth < min_margin_span:
        p.error(f"--width/--depth ({args.width}m x {args.depth}m) too small "
                 f"for --wall-thickness {args.wall_thickness}m: each exterior "
                 f"wall needs at least {min_margin_span:.2f}m of clear span "
                 f"to fit an entry/exit opening. Increase --width/--depth or "
                 f"decrease --wall-thickness.")

    boxes, rooms, entry_xy, exit_xy, object_boxes = generate(
        seed=args.seed, width=args.width, depth=args.depth, rooms=args.rooms,
        min_room=args.min_room, wall_height=args.wall_height,
        wall_thickness=args.wall_thickness, door_width=args.door_width,
        door_height=args.door_height, window_width=args.window_width,
        window_sill=args.window_sill, window_height=args.window_height,
        max_windows_per_wall=args.max_windows_per_wall,
        corridor_bias=args.corridor,
        add_objects=args.objects,
        min_objects_per_room=args.min_objects_per_room,
        max_objects_per_room=args.max_objects_per_room,
        object_min_size=args.object_min_size, object_max_size=args.object_max_size,
    )

    wall_height = max(args.wall_height, WALL_HEIGHT_M)
    sdf_text = build_sdf(boxes, args.width, args.depth, args.model_name, args.world,
                          wall_height=wall_height, entry_xy=entry_xy, exit_xy=exit_xy,
                          object_boxes=object_boxes)
    with open(args.out, "w") as f:
        f.write(sdf_text)
    print(f"Wrote SDF ({'world' if args.world else 'model'}) -> {args.out}")
    print(f"  seed={args.seed}  rooms={len(rooms)}  wall_boxes={len(boxes)}")
    if entry_xy:
        print(f"  entry point -> ({entry_xy[0]:.2f}, {entry_xy[1]:.2f})")
    if exit_xy:
        print(f"  exit point  -> ({exit_xy[0]:.2f}, {exit_xy[1]:.2f})")
    if entry_xy and exit_xy:
        dist = math.hypot(exit_xy[0] - entry_xy[0], exit_xy[1] - entry_xy[1])
        print(f"  entry<->exit straight-line distance = {dist:.2f} m "
              f"(opposite walls, kept far apart)")
    if args.objects:
        print(f"  objects = {len(object_boxes)} (crates/rubble/barrels), "
              f"all verified clear of every wall")

    if args.preview:
        render_preview(boxes, args.width, args.depth, args.preview,
                        entry_xy=entry_xy, exit_xy=exit_xy, wall_height=wall_height,
                        object_boxes=object_boxes)
        print(f"Wrote preview -> {args.preview}")


if __name__ == "__main__":
    main()
