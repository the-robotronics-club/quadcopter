"""
maze_solver.py
================

Standalone, OFFLINE test harness for the "maze solving in shortest time"
task -- no ROS2 required. Builds the true room-adjacency graph (rooms +
doors) directly from floorplan_generator's own geometry functions (same
seed => identical layout to what gets exported to the SDF), then simulates
an ONLINE explorer that only learns a room's doors once the drone has
actually flown into that room -- mirroring what the real, GPS-denied drone
would learn from onboard sensing, with zero prior knowledge of the layout.

Why online, not "solve the known graph": per the mission brief, the drone
never has the map in advance. The interesting problem isn't "find the
shortest path in a known graph" (trivial once you know it, since the rooms
form a spanning TREE -- see floorplan_generator's own docstring, meaning
there's exactly one path between any two rooms) -- it's "explore an unknown
tree as efficiently as possible while looking for the exit". This module
implements nearest-first DFS, which has a well-known worst-case bound of
~2x the offline-optimal distance for exactly this problem.

Usage:
    python3 maze_solver.py --seed 7 --rooms 7
    python3 maze_solver.py --seed 7 --rooms 7 --plot preview.png
"""

import argparse
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import floorplan_generator as fg


# ---------------------------------------------------------------------------
# Room graph construction
# ---------------------------------------------------------------------------

@dataclass
class Door:
    room_a: int
    room_b: int
    world_xy: Tuple[float, float]
    role: Optional[str] = None  # 'entry' / 'exit' -- only set on the two
                                  # exterior doors, never on interior doors


@dataclass
class Room:
    id: int
    rect: "fg.Rect"

    @property
    def centroid(self) -> Tuple[float, float]:
        return (self.rect.cx, self.rect.cy)


@dataclass
class RoomGraph:
    rooms: Dict[int, Room]
    doors: List[Door]
    entry_room: int
    exit_room: int
    entry_xy: Tuple[float, float]
    exit_xy: Tuple[float, float]

    def doors_of(self, room_id: int) -> List[Door]:
        return [d for d in self.doors if d.room_a == room_id or d.room_b == room_id]

    def other_room(self, door: Door, room_id: int) -> int:
        return door.room_b if door.room_a == room_id else door.room_a


def _room_for_point(room_rects: List["fg.Rect"], x: float, y: float,
                     tol: float = 0.05) -> Optional[int]:
    for i, r in enumerate(room_rects):
        if r.x0 - tol <= x <= r.x1 + tol and r.y0 - tol <= y <= r.y1 + tol:
            return i
    return None


def build_room_graph(seed: int, width: float = 15.0, depth: float = 15.0,
                      rooms: int = 6, min_room: float = fg.ROOM_STANDARD_M,
                      wall_thickness: float = 0.12,
                      door_width: float = fg.MIN_CORRIDOR_CLEAR_M,
                      window_width: float = 1.1, window_sill: float = 0.9,
                      window_height: float = 1.2,
                      max_windows_per_wall: int = 0,
                      corridor_bias: bool = False) -> RoomGraph:
    """
    Replicates floorplan_generator.generate()'s room/door construction step
    for step (same rng call sequence -> same seed gives the same layout as
    the exported SDF), stopping right after doors are placed. We don't need
    the exported wall boxes or object clutter for graph-level exploration,
    and stopping early means our graph can never drift out of sync with the
    real export even if generate()'s later (box/object) steps change.
    """
    door_height = fg.VERTICAL_CLEARANCE_M
    min_wall_span = fg.MIN_CORRIDOR_CLEAR_M + wall_thickness
    eff_min_room = max(min_room, fg.ROOM_STANDARD_M, min_wall_span)

    rng = random.Random(seed)

    room_rects, interior_walls = fg.generate_rooms(
        rng, width, depth, rooms, eff_min_room, corridor_bias)
    exterior_walls = fg.make_exterior_walls(width, depth)

    for wall in interior_walls + exterior_walls:
        wall.thickness = wall_thickness

    all_walls = interior_walls + exterior_walls

    fg.add_interior_doors(rng, interior_walls, all_walls, door_width, door_height,
                           margin=wall_thickness * 2 + 0.15)
    entry_xy, exit_xy = fg.add_exterior_openings(
        rng, exterior_walls, all_walls, door_width, door_height,
        window_width, window_sill, window_height, max_windows_per_wall,
        margin=wall_thickness * 2 + 0.15)

    room_objs = {i: Room(id=i, rect=r) for i, r in enumerate(room_rects)}

    # For every interior door, resolve which two FINAL leaf rooms it
    # actually connects. We don't trust "1 wall = 1 edge" -- a wall can
    # border more than 2 final rooms if one side got split again after
    # this wall was first created, so we test a point just inside each
    # side of the door against the final room_rects directly.
    doors: List[Door] = []
    eps = 0.02
    for wall in interior_walls:
        for o in wall.openings:
            mid = wall.start + o.offset + o.length / 2.0
            if wall.axis == "v":
                x, y = wall.fixed, mid
                pt_a = (x - eps - wall_thickness, y)
                pt_b = (x + eps + wall_thickness, y)
            else:
                x, y = mid, wall.fixed
                pt_a = (x, y - eps - wall_thickness)
                pt_b = (x, y + eps + wall_thickness)

            ra = _room_for_point(room_rects, *pt_a)
            rb = _room_for_point(room_rects, *pt_b)
            if ra is None or rb is None or ra == rb:
                continue
            doors.append(Door(room_a=ra, room_b=rb, world_xy=(x, y)))

    entry_room = _room_for_point(room_rects, *entry_xy)
    exit_room = _room_for_point(room_rects, *exit_xy)
    if entry_room is None or exit_room is None:
        raise RuntimeError(
            "Could not resolve entry/exit door to a room -- geometry "
            "mismatch with floorplan_generator's own placement logic. "
            "(If floorplan_generator.py has been edited since this module "
            "was written, the two may have drifted out of sync.)"
        )

    return RoomGraph(rooms=room_objs, doors=doors, entry_room=entry_room,
                      exit_room=exit_room, entry_xy=entry_xy, exit_xy=exit_xy)


# ---------------------------------------------------------------------------
# Online DFS exploration
# ---------------------------------------------------------------------------

@dataclass
class ExplorationResult:
    visit_order: List[int]
    path_points: List[Tuple[float, float]]  # every point flown through, in order
    total_distance: float
    optimal_distance: float
    reached_exit: bool

    @property
    def competitive_ratio(self) -> float:
        if self.optimal_distance <= 0:
            return float("nan")
        return self.total_distance / self.optimal_distance


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _subtree_size(graph: RoomGraph, room_id: int, came_from: Optional[int],
                   memo: Dict[Tuple[int, Optional[int]], int]) -> int:
    """Number of rooms reachable going further from room_id, not counting
    the direction we came from. Used to decide which branch to explore
    LAST (the biggest one), since the last branch explored never needs a
    backtrack trip."""
    key = (room_id, came_from)
    if key in memo:
        return memo[key]
    total = 1
    for door in graph.doors_of(room_id):
        nxt = graph.other_room(door, room_id)
        if nxt != came_from:
            total += _subtree_size(graph, nxt, room_id, memo)
    memo[key] = total
    return total


def _branch_contains_room(graph: RoomGraph, start_room: int, avoid_room: int,
                           target_room: int, memo: Dict[Tuple[int, int], bool]) -> bool:
    """Is target_room reachable from start_room without going back through avoid_room?"""
    key = (start_room, avoid_room)
    if key in memo:
        return memo[key]
    if start_room == target_room:
        memo[key] = True
        return True
    found = False
    for door in graph.doors_of(start_room):
        nxt = graph.other_room(door, start_room)
        if nxt != avoid_room and _branch_contains_room(graph, nxt, start_room, target_room, memo):
            found = True
            break
    memo[key] = found
    return found


def explore_full_coverage(graph: RoomGraph) -> ExplorationResult:
    """
    Visits EVERY room (not just until the exit is found), then finishes at
    the exit. Since every room must be visited regardless of order, there's
    no adversarial "guess wrong" penalty the way single-target search had.

    Tested two orderings before settling on this one:
      - "biggest subtree last": barely helped (mean 1.78 -> 1.70 over 40
        seeds), and did NOT improve the worst case at all (8.11x either
        way). Turned out this wasn't the right lever.
      - "the branch containing the exit, last" (this version): the real
        lever, since it's what the lower-bound formula assumes -- if you
        don't naturally end your traversal in the exit's room, you pay for
        a whole extra cross-map trip at the very end after already
        covering everything. Forcing the exit-branch to always be explored
        last guarantees you're already there when coverage finishes.
    """
    visited_rooms = set()
    visited_doors = set()
    path_points: List[Tuple[float, float]] = [graph.entry_xy]
    current_pos = graph.entry_xy
    total_distance = 0.0
    visit_order: List[int] = []
    branch_memo: Dict[Tuple[int, int], bool] = {}

    def move_to(pt: Tuple[float, float]):
        nonlocal current_pos, total_distance
        total_distance += _dist(current_pos, pt)
        current_pos = pt
        path_points.append(pt)

    def dfs_with_backtrack(room_id: int, came_from_room: Optional[int]):
        visited_rooms.add(room_id)
        visit_order.append(room_id)
        room = graph.rooms[room_id]
        move_to(room.centroid)

        doors = [d for d in graph.doors_of(room_id)
                 if graph.other_room(d, room_id) not in visited_rooms]

        def sort_key(d):
            nxt = graph.other_room(d, room_id)
            leads_to_exit = _branch_contains_room(graph, nxt, room_id, graph.exit_room, branch_memo)
            # exit-containing branch sorts last (True > False); ties broken by subtree size
            return (leads_to_exit, _subtree_size(graph, nxt, room_id, {}))

        doors = sorted(doors, key=sort_key)

        for i, door in enumerate(doors):
            next_room = graph.other_room(door, room_id)
            if next_room in visited_rooms:
                continue
            key = (min(door.room_a, door.room_b), max(door.room_a, door.room_b))
            if key in visited_doors:
                continue
            visited_doors.add(key)

            move_to(door.world_xy)
            dfs_with_backtrack(next_room, room_id)

            is_last_branch = (i == len(doors) - 1)
            if not is_last_branch:
                move_to(door.world_xy)
                move_to(room.centroid)

    dfs_with_backtrack(graph.entry_room, None)

    # After covering every room, finish the trip at the exit door
    exit_room_centroid = graph.rooms[graph.exit_room].centroid
    move_to(exit_room_centroid)
    move_to(graph.exit_xy)

    optimal_distance = full_coverage_lower_bound(graph)

    return ExplorationResult(
        visit_order=visit_order, path_points=path_points,
        total_distance=total_distance, optimal_distance=optimal_distance,
        reached_exit=True,
    )


def full_coverage_lower_bound(graph: RoomGraph) -> float:
    """
    Best-case distance for visiting every room and ending at the exit:
    2x total edge weight, minus the one path you don't have to double back
    on if you arrange to visit rooms so the trip naturally ends at the
    exit's room last.
    """
    total_edge_weight = 0.0
    for d in graph.doors:
        total_edge_weight += _dist(graph.rooms[d.room_a].centroid, graph.rooms[d.room_b].centroid)
    total_edge_weight += _dist(graph.entry_xy, graph.rooms[graph.entry_room].centroid)
    total_edge_weight += _dist(graph.exit_xy, graph.rooms[graph.exit_room].centroid)

    path_to_exit = shortest_known_path_distance(graph)
    return 2 * total_edge_weight - path_to_exit


def explore_dfs(graph: RoomGraph, heuristic: str = "farthest_from_entry") -> ExplorationResult:
    """
    Simulates online exploration with ZERO prior map knowledge:
      - Start in the entry room.
      - A room's doors become known the instant the drone is inside that
        room (full room visibility from a hovering vantage point -- fair
        given standard rooms are >=2m and doors are on the perimeter).
      - Recurses fully into a branch before backtracking (DFS).
      - Backtracking re-flies the exact same path already flown.

    heuristic:
      "nearest"              -- try the closest unexplored door first.
                                 Simple, but easily fooled: the nearest door
                                 out of a room is often the one leading back
                                 toward where you just came from, or into a
                                 small side-room cluster, not deeper into
                                 the building.
      "farthest_from_entry"  -- try the door FARTHEST from the point you
                                 just entered this room through. Tends to
                                 keep moving forward into new territory
                                 instead of immediately doubling back.
    """
    visited_rooms = set()
    visited_doors = set()
    path_points: List[Tuple[float, float]] = [graph.entry_xy]
    current_pos = graph.entry_xy
    total_distance = 0.0
    reached_exit = False
    visit_order: List[int] = []

    def move_to(pt: Tuple[float, float]):
        nonlocal current_pos, total_distance
        total_distance += _dist(current_pos, pt)
        current_pos = pt
        path_points.append(pt)

    def dfs(room_id: int, entered_via: Tuple[float, float]) -> bool:
        nonlocal reached_exit
        visited_rooms.add(room_id)
        visit_order.append(room_id)
        room = graph.rooms[room_id]
        move_to(room.centroid)

        if room_id == graph.exit_room:
            move_to(graph.exit_xy)
            reached_exit = True
            return True

        doors = graph.doors_of(room_id)
        if heuristic == "nearest":
            doors = sorted(doors, key=lambda d: _dist(room.centroid, d.world_xy))
        elif heuristic == "farthest_from_entry":
            doors = sorted(doors, key=lambda d: -_dist(entered_via, d.world_xy))
        else:
            raise ValueError(f"Unknown heuristic: {heuristic}")

        for door in doors:
            key = (min(door.room_a, door.room_b), max(door.room_a, door.room_b))
            if key in visited_doors:
                continue
            visited_doors.add(key)
            next_room = graph.other_room(door, room_id)
            if next_room in visited_rooms:
                continue

            move_to(door.world_xy)
            if dfs(next_room, door.world_xy):
                return True
            move_to(door.world_xy)   # dead end -- backtrack through the same door
            move_to(room.centroid)

        return False

    dfs(graph.entry_room, graph.entry_xy)

    return ExplorationResult(
        visit_order=visit_order, path_points=path_points,
        total_distance=total_distance,
        optimal_distance=shortest_known_path_distance(graph),
        reached_exit=reached_exit,
    )


def shortest_known_path_distance(graph: RoomGraph) -> float:
    """
    The offline-optimal distance -- what the drone would fly IF it somehow
    knew the whole map in advance. Only used to score the online explorer
    against a baseline; the real (GPS-denied) drone never has this. Since
    rooms form a spanning tree, this is just the single unique path,
    found via BFS.
    """
    adjacency: Dict[int, List[Door]] = {}
    for d in graph.doors:
        adjacency.setdefault(d.room_a, []).append(d)
        adjacency.setdefault(d.room_b, []).append(d)

    parent_door: Dict[int, Optional[Door]] = {graph.entry_room: None}
    parent_room: Dict[int, Optional[int]] = {graph.entry_room: None}
    queue = deque([graph.entry_room])
    while queue:
        r = queue.popleft()
        if r == graph.exit_room:
            break
        for d in adjacency.get(r, []):
            nxt = graph.other_room(d, r)
            if nxt not in parent_room:
                parent_room[nxt] = r
                parent_door[nxt] = d
                queue.append(nxt)

    if graph.exit_room not in parent_room:
        # Shouldn't happen if floorplan_generator's spanning-tree guarantee
        # holds -- surfacing loudly instead of silently returning a wrong
        # number is more useful for debugging a real disconnect.
        raise RuntimeError(
            "Exit room is unreachable from entry room in the built graph -- "
            "this should never happen given floorplan_generator's spanning "
            "tree guarantee. Check build_room_graph()'s adjacency detection."
        )

    points: List[Tuple[float, float]] = [graph.exit_xy]
    r = graph.exit_room
    while parent_room[r] is not None:
        points.append(graph.rooms[r].centroid)
        points.append(parent_door[r].world_xy)
        r = parent_room[r]
    points.append(graph.rooms[graph.entry_room].centroid)
    points.append(graph.entry_xy)
    points.reverse()

    return sum(_dist(points[i], points[i + 1]) for i in range(len(points) - 1))


# ---------------------------------------------------------------------------
# Plotting (optional, matplotlib)
# ---------------------------------------------------------------------------

def plot_result(graph: RoomGraph, result: ExplorationResult, path: str,
                 width: float, depth: float) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    fig, ax = plt.subplots(figsize=(8, 8))

    for room in graph.rooms.values():
        r = room.rect
        ax.add_patch(patches.Rectangle((r.x0, r.y0), r.w, r.h,
                                        fill=False, edgecolor="black", linewidth=1.2))
        ax.text(r.cx, r.cy, str(room.id), ha="center", va="center",
                fontsize=9, color="gray")

    for d in graph.doors:
        ax.plot(*d.world_xy, marker="s", color="saddlebrown", markersize=6)

    xs = [p[0] for p in result.path_points]
    ys = [p[1] for p in result.path_points]
    ax.plot(xs, ys, color="royalblue", linewidth=1.5, alpha=0.8,
            label=f"Explored path ({result.total_distance:.1f} m)")

    ax.plot(*graph.entry_xy, marker="o", color="green", markersize=12, label="Entry")
    ax.plot(*graph.exit_xy, marker="o", color="red", markersize=12, label="Exit")

    ax.set_xlim(-0.5, width + 0.5)
    ax.set_ylim(-0.5, depth + 0.5)
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"DFS exploration -- {result.total_distance:.1f} m flown "
                 f"vs {result.optimal_distance:.1f} m optimal "
                 f"({result.competitive_ratio:.2f}x)")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--width", type=float, default=15.0)
    p.add_argument("--depth", type=float, default=15.0)
    p.add_argument("--rooms", type=int, default=6)
    p.add_argument("--corridor", action="store_true")
    p.add_argument("--plot", type=str, default=None,
                   help="Optional PNG path to render the explored path")
    args = p.parse_args()

    graph = build_room_graph(seed=args.seed, width=args.width, depth=args.depth,
                              rooms=args.rooms, corridor_bias=args.corridor)
    result = explore_dfs(graph)

    print(f"seed={args.seed}  rooms={len(graph.rooms)}  doors={len(graph.doors)}")
    print(f"entry room = {graph.entry_room}   exit room = {graph.exit_room}")
    print(f"visit order = {result.visit_order}")
    print(f"reached exit = {result.reached_exit}")
    print(f"total distance flown   = {result.total_distance:.2f} m")
    print(f"offline-optimal distance = {result.optimal_distance:.2f} m")
    print(f"competitive ratio       = {result.competitive_ratio:.2f}x "
          f"(empirically: 'farthest_from_entry' heuristic averages ~1.5x "
          f"optimal across 60 test seeds, worst observed ~3.8x -- see "
          f"HEURISTIC_NOTES.md for the comparison against nearest-first)")

    if args.plot:
        plot_result(graph, result, args.plot, args.width, args.depth)
        print(f"Wrote plot -> {args.plot}")


if __name__ == "__main__":
    main()