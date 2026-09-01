# Exploration Heuristic Notes

## The problem
The maze rooms form a spanning tree (per floorplan_generator's own design:
every interior wall gets exactly one door). That means once the layout is
known, the path is trivial -- there's only one route between any two rooms.
The real problem is **online exploration**: the drone starts with zero prior
knowledge of the layout (GPS-denied, per the mission brief) and only learns
a room's doors once it has actually flown into that room.

## Two heuristics tested

**`nearest`** -- at each room, try the closest unexplored door first.
Simple, but a bad idea in practice: the *nearest* door out of a room is
often the one that loops back toward where you just came from, or into a
small side-room cluster, rather than deeper into the building.

**`farthest_from_entry`** (default) -- at each room, try the door
*farthest* from the point you just entered through. Keeps the drone moving
forward into new territory instead of doubling back.

## Results (60 random seeds, 7-room layouts)

| Heuristic | Mean ratio vs optimal | Worst case observed |
|---|---|---|
| nearest | 2.00x | 7.11x (seed 49) |
| farthest_from_entry | 1.53x | 3.77x (seed 34) |

`farthest_from_entry` is the default in `explore_dfs()`.

## An earlier mistake, corrected here
An early draft of this module claimed a "~2x theoretical worst-case bound"
for DFS tree exploration. That bound applies to a different, easier version
of the problem (exploring a tree of *known* total size and returning to the
start). For "find one target of *unknown* location using pure nearest-first
with no other information," there is no such guarantee -- an adversarial
layout can push the ratio arbitrarily high, which the initial seed-1 test
(4.69x, later found to reach 7.11x elsewhere) demonstrated directly. The
numbers above are real, measured results, not a theoretical claim.

## Grid-frontier exploration (frontier_solver.py) -- separate approach

Unlike the room-graph version above, this one doesn't try to detect
"rooms" at all -- it rasterizes walls into a grid, simulates limited-range
sensing (ray casting, can't see through walls), and does standard frontier
exploration (find the boundary between known-free and unknown, fly there,
repeat). This is what Nav2's explore_lite does in practice.

### Sensor range tested (20 seeds, from_entry heuristic)
| Range | Mean ratio | Worst |
|---|---|---|
| 2.5m | 4.78x | 7.82x |
| 5.0m | 1.97x | 4.43x |
| 6.0m | 1.71x | 3.38x |
| 8.0m | 1.78x | 3.82x |
| 10.0m | 1.74x | 3.96x |

6.0m is the sweet spot -- also realistic for an actual depth camera's
reliable range. Set as default.

### Frontier-selection heuristics tested (30 seeds, 6.0m range)
| Heuristic | Mean ratio | Worst |
|---|---|---|
| nearest | 4.0x | 8.22x |
| farthest (from last point) | 2.03x | 5.61x |
| from_entry (distance from start) | 1.97x | 7.01x |
| from_entry_sized (distance x sqrt(cluster size)) | **1.66x** | **4.13x** |

`from_entry_sized` is the default -- best average AND best worst-case
across the batch.

**Important honest caveat**: `from_entry_sized` is not a strict
improvement on every individual seed. Seed 1 specifically got WORSE under
it (1.46x under plain `from_entry` -> 4.13x under `from_entry_sized`,
making it the new worst-case in the batch). Weighting by cluster size
helps on average but can occasionally mislead when a large-but-wrong
frontier outweighs a small-but-correct one. This is a real tradeoff, not
a bug -- worth knowing before presenting these numbers as unconditionally
better.

### Also filtered
1-2 cell frontier clusters are dropped as noise before scoring -- picking
a target from a tiny sliver wastes a full explore/backtrack cycle on
almost no new information.

- **Directional bias from entry/exit wall placement**: floorplan_generator
  places entry and exit on opposite exterior walls. If the real drone knows
  which wall it entered through, biasing exploration toward the far side of
  the building (not just "away from the last door") might improve on
  `farthest_from_entry` further. Untested.
- **Red/green door color cue**: floorplan_generator paints the exit door
  red and entry green. At the room-graph level (this module) that adds
  nothing beyond "you've reached the exit room" -- but at the raw
  sensor/vision level, spotting red through an open doorway *before* fully
  entering the neighboring room could be a real shortcut. That requires
  wiring into the actual camera/frontier-exploration pipeline, not this
  offline graph simulation. Also: the real competition arena may not have
  colored doors at all -- this is a simulation-only convenience from
  floorplan_generator, so any dependency on it should degrade gracefully.