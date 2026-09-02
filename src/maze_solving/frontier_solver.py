"""
frontier_solver.py
====================

Grid-based frontier exploration -- the standard robotics approach (what
Nav2's explore_lite does), simulated offline against floorplan_generator's
geometry, WITHOUT any "room" concept and WITHOUT cheating: the drone only
ever knows what a simulated sensor (limited range + line-of-sight) has
actually revealed, cell by cell, exactly like the real onboard camera would.

Pipeline this stands in for:
    depth camera --> depthimage_to_laserscan --> slam_toolbox (real ROS2)
    == simulated here by: rasterize_walls_to_grid() + reveal_from() ==

    Nav2 explore_lite (real ROS2)
    == simulated here by: find_frontiers() + explore() ==

Usage:
    python3 frontier_solver.py --seed 7 --rooms 7
    python3 frontier_solver.py --seed 7 --rooms 7 --plot out.png
"""

import argparse
import heapq
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

import floorplan_generator as fg

UNKNOWN, FREE, OCCUPIED = 0, 1, 2
Cell = Tuple[int, int]


# ---------------------------------------------------------------------------
# Grid construction (ground truth -- the drone never sees this directly,
# only through reveal_from()'s simulated sensing)
# ---------------------------------------------------------------------------

@dataclass
class Grid:
    resolution: float
    width_m: float
    depth_m: float
    nx: int
    ny: int
    occupied: np.ndarray  # bool, True = wall

    def world_to_cell(self, x: float, y: float) -> Cell:
        return (int(x / self.resolution), int(y / self.resolution))

    def cell_to_world(self, cell: Cell) -> Tuple[float, float]:
        cx, cy = cell
        return ((cx + 0.5) * self.resolution, (cy + 0.5) * self.resolution)

    def in_bounds(self, cell: Cell) -> bool:
        cx, cy = cell
        return 0 <= cx < self.nx and 0 <= cy < self.ny


def rasterize_walls_to_grid(interior_walls: List["fg.Wall"], exterior_walls: List["fg.Wall"],
                             width: float, depth: float, resolution: float = 0.1) -> Grid:
    """
    Marks wall footprints as occupied. Only DOOR openings are cut as
    passable gaps -- window openings are left solid, since the drone
    should never route through a window (and by default no windows are
    generated anyway, --max-windows-per-wall defaults to 0).
    """
    nx = int(math.ceil(width / resolution)) + 1
    ny = int(math.ceil(depth / resolution)) + 1
    occupied = np.zeros((nx, ny), dtype=bool)

    def mark_rect(x0, y0, x1, y1):
        ix0 = max(0, int(x0 / resolution))
        ix1 = min(nx, int(math.ceil(x1 / resolution)))
        iy0 = max(0, int(y0 / resolution))
        iy1 = min(ny, int(math.ceil(y1 / resolution)))
        occupied[ix0:ix1, iy0:iy1] = True

    for wall in interior_walls + exterior_walls:
        door_gaps = sorted(
            [(o.offset, o.offset + o.length) for o in wall.openings if o.kind == "door"]
        )
        # Build the solid sub-segments of this wall (start..end, minus door gaps)
        segments = []
        cursor = wall.start
        for gap_start, gap_end in door_gaps:
            gap_start = max(wall.start, wall.start + (gap_start - wall.start))
            if gap_start > cursor:
                segments.append((cursor, gap_start))
            cursor = max(cursor, wall.start + (gap_end - wall.start))
        if cursor < wall.end:
            segments.append((cursor, wall.end))

        half_t = wall.thickness / 2.0
        for s0, s1 in segments:
            if wall.axis == "h":
                mark_rect(s0, wall.fixed - half_t, s1, wall.fixed + half_t)
            else:
                mark_rect(wall.fixed - half_t, s0, wall.fixed + half_t, s1)

    return Grid(resolution=resolution, width_m=width, depth_m=depth,
                nx=nx, ny=ny, occupied=occupied)


def build_ground_truth_grid(seed: int, width: float = 15.0, depth: float = 15.0,
                             rooms: int = 6, resolution: float = 0.1,
                             corridor_bias: bool = False) -> Tuple[Grid, Tuple[float, float], Tuple[float, float]]:
    """Same rng call sequence as floorplan_generator.generate() -- same seed, same layout."""
    min_wall_span = fg.MIN_CORRIDOR_CLEAR_M + 0.12
    eff_min_room = max(fg.ROOM_STANDARD_M, min_wall_span)
    rng = random.Random(seed)

    room_rects, interior_walls = fg.generate_rooms(rng, width, depth, rooms, eff_min_room, corridor_bias)
    exterior_walls = fg.make_exterior_walls(width, depth)
    for wall in interior_walls + exterior_walls:
        wall.thickness = 0.12

    all_walls = interior_walls + exterior_walls
    fg.add_interior_doors(rng, interior_walls, all_walls, fg.MIN_CORRIDOR_CLEAR_M,
                           fg.VERTICAL_CLEARANCE_M, margin=0.12 * 2 + 0.15)
    entry_xy, exit_xy = fg.add_exterior_openings(
        rng, exterior_walls, all_walls, fg.MIN_CORRIDOR_CLEAR_M, fg.VERTICAL_CLEARANCE_M,
        1.1, 0.9, 1.2, 0, margin=0.12 * 2 + 0.15)

    grid = rasterize_walls_to_grid(interior_walls, exterior_walls, width, depth, resolution)
    return grid, entry_xy, exit_xy


# ---------------------------------------------------------------------------
# Simulated sensing (limited range + line-of-sight -- NOT omniscient)
# ---------------------------------------------------------------------------

def _bresenham(x0: int, y0: int, x1: int, y1: int):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        yield x, y
        if x == x1 and y == y1:
            return
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def reveal_from(truth: Grid, known: np.ndarray, world_pos: Tuple[float, float],
                 sensor_range_m: float = 2.5, n_rays: int = 180) -> None:
    """
    Simulates a limited-range sensor: casts rays outward from world_pos and
    marks cells FREE up until (and including) the first OCCUPIED cell hit,
    stopping there -- cells behind a wall are never revealed, exactly like
    a real depth camera / lidar can't see through walls.
    """
    cx, cy = truth.world_to_cell(*world_pos)
    range_cells = int(sensor_range_m / truth.resolution)

    for i in range(n_rays):
        angle = 2 * math.pi * i / n_rays
        tx = cx + int(range_cells * math.cos(angle))
        ty = cy + int(range_cells * math.sin(angle))
        for x, y in _bresenham(cx, cy, tx, ty):
            if not (0 <= x < truth.nx and 0 <= y < truth.ny):
                break
            if truth.occupied[x, y]:
                known[x, y] = OCCUPIED
                break
            known[x, y] = FREE


# ---------------------------------------------------------------------------
# Frontier detection (known-free cells adjacent to unknown cells)
# ---------------------------------------------------------------------------

def find_frontiers(known: np.ndarray) -> List[List[Cell]]:
    """Returns clusters (connected components) of frontier cells."""
    nx, ny = known.shape
    is_frontier = np.zeros_like(known, dtype=bool)

    free_mask = known == FREE
    for x in range(nx):
        for y in range(ny):
            if not free_mask[x, y]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx2, ny2 = x + dx, y + dy
                if 0 <= nx2 < nx and 0 <= ny2 < ny and known[nx2, ny2] == UNKNOWN:
                    is_frontier[x, y] = True
                    break

    visited = np.zeros_like(is_frontier, dtype=bool)
    clusters: List[List[Cell]] = []
    for x in range(nx):
        for y in range(ny):
            if not is_frontier[x, y] or visited[x, y]:
                continue
            # BFS flood-fill this cluster
            stack = [(x, y)]
            visited[x, y] = True
            cluster = []
            while stack:
                cx, cy = stack.pop()
                cluster.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nx2, ny2 = cx + dx, cy + dy
                    if (0 <= nx2 < nx and 0 <= ny2 < ny and
                            is_frontier[nx2, ny2] and not visited[nx2, ny2]):
                        visited[nx2, ny2] = True
                        stack.append((nx2, ny2))
            clusters.append(cluster)

    return clusters


# ---------------------------------------------------------------------------
# A* pathfinding (used both for real navigation-through-known-space, and
# for computing the offline-optimal baseline on the FULL true grid)
# ---------------------------------------------------------------------------

def inflate_occupied(occupied: np.ndarray, radius_cells: int) -> np.ndarray:
    """
    Grows every occupied (wall) cell outward by radius_cells, so path
    planning treats anything within that radius of a wall as blocked too --
    without this, A* happily plans a path that grazes directly along a wall
    pixel, which is fine for a zero-size point but not for a real drone
    with physical width. Circular kernel dilation.
    """
    if radius_cells <= 0:
        return occupied.copy()
    inflated = occupied.copy()
    for dx in range(-radius_cells, radius_cells + 1):
        for dy in range(-radius_cells, radius_cells + 1):
            if dx * dx + dy * dy > radius_cells * radius_cells:
                continue  # keep the kernel roughly circular, not square
            if dx == 0 and dy == 0:
                continue
            shifted = np.zeros_like(occupied)
            src_x0, src_x1 = max(0, -dx), occupied.shape[0] - max(0, dx)
            dst_x0, dst_x1 = max(0, dx), occupied.shape[0] - max(0, -dx)
            src_y0, src_y1 = max(0, -dy), occupied.shape[1] - max(0, dy)
            dst_y0, dst_y1 = max(0, dy), occupied.shape[1] - max(0, -dy)
            if src_x1 <= src_x0 or src_y1 <= src_y0:
                continue
            shifted[dst_x0:dst_x1, dst_y0:dst_y1] = occupied[src_x0:src_x1, src_y0:src_y1]
            inflated |= shifted
    return inflated



def astar(blocked: np.ndarray, start: Cell, goal: Cell) -> Optional[List[Cell]]:
    nx, ny = blocked.shape

    def h(a: Cell, b: Cell) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    open_set = [(h(start, goal), 0.0, start)]
    came_from: Dict[Cell, Cell] = {}
    g_score = {start: 0.0}
    visited: Set[Cell] = set()

    while open_set:
        _, g, current = heapq.heappop(open_set)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        cx, cy = current
        for dx, dy, cost in ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                              (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
            nxt = (cx + dx, cy + dy)
            if not (0 <= nxt[0] < nx and 0 <= nxt[1] < ny):
                continue
            if blocked[nxt[0], nxt[1]]:
                continue
            tentative_g = g + cost
            if tentative_g < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative_g
                came_from[nxt] = current
                heapq.heappush(open_set, (tentative_g + h(nxt, goal), tentative_g, nxt))

    return None  # no path found


# ---------------------------------------------------------------------------
# Exploration loop
# ---------------------------------------------------------------------------

@dataclass
class FrontierResult:
    path_points: List[Tuple[float, float]]
    total_distance: float
    optimal_distance: float
    reached_exit: bool
    steps: int

    @property
    def competitive_ratio(self) -> float:
        if self.optimal_distance <= 0:
            return float("nan")
        return self.total_distance / self.optimal_distance


def _cluster_targets(known: np.ndarray, min_size: int = 3) -> List[Tuple[Cell, int]]:
    clusters = find_frontiers(known)
    clusters = [c for c in clusters if len(c) >= min_size]
    targets = []
    for cluster in clusters:
        cx = sum(c[0] for c in cluster) / len(cluster)
        cy = sum(c[1] for c in cluster) / len(cluster)
        nearest = min(cluster, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
        targets.append((nearest, len(cluster)))
    return targets


def explore_dfs(truth: Grid, entry_xy: Tuple[float, float], exit_xy: Tuple[float, float],
                 sensor_range_m: float = 6.0, max_steps: int = 500) -> FrontierResult:
    """
    Real DFS structure on top of frontier detection: when multiple frontier
    directions are available, commit fully to the best one and push the
    REST onto a stack. Only reconsider those deferred alternatives once the
    committed branch is fully exhausted (no new frontiers left along it) --
    then backtrack exactly to where the choice was made and resume from
    there, same commit/backtrack discipline as maze_solver.py's room-graph
    DFS, but built from real discovered frontiers instead of ground truth.

    This fixes explore()'s core issue: explore() re-scores ALL currently
    known frontiers globally every step, so it can abandon a
    partially-explored branch for a bigger-looking one elsewhere, and when
    that turns out to be a dead end, doesn't cleanly resume the original
    branch -- it just re-picks globally again, which has no DFS backtracking
    guarantee.
    """
    known = np.zeros((truth.nx, truth.ny), dtype=np.uint8)
    pos = entry_xy
    path_points = [pos]
    total_distance = 0.0
    reached_exit = False
    steps = 0

    reveal_from(truth, known, pos, sensor_range_m)
    exit_cell = truth.world_to_cell(*exit_xy)
    entry_cell = truth.world_to_cell(*entry_xy)

    def move_along(path_cells: List[Cell]):
        nonlocal pos, total_distance
        for cell in path_cells[1:]:
            wp = truth.cell_to_world(cell)
            total_distance += math.hypot(wp[0] - pos[0], wp[1] - pos[1])
            pos = wp
            path_points.append(pos)
            reveal_from(truth, known, pos, sensor_range_m)

    def score(target: Tuple[Cell, int]) -> float:
        # Tested distance-only (no size weighting) based on a theory that
        # size-weighting was dominated by sensor-range-arc artifacts rather
        # than real doorway size -- that theory was correct as far as it
        # goes (large clusters ARE often just sensor-range arcs, not real
        # rooms), but empirically REMOVING size-weighting made results
        # worse overall (mean 1.97/worst 7.01 vs 1.66/4.13 WITH size
        # weighting, 30-seed batch). Likely explanation: preferring the
        # large "look around the current room fully" arc first, before
        # committing to any specific exit direction, ends up being a
        # reasonable proxy for maze_solver.py's "room's doors are known
        # once you're inside it" assumption -- even though that's not
        # what the size weighting was originally intended to capture.
        # Keeping size-weighting because it measurably performs better,
        # not because the original justification for it was right.
        cell, size = target
        dist = math.hypot(cell[0] - entry_cell[0], cell[1] - entry_cell[1])
        return dist * math.sqrt(size)

    # stack entries: (return_point_cell, sorted list of deferred (cell, size) options)
    stack: List[Tuple[Cell, List[Tuple[Cell, int]]]] = []

    for step in range(max_steps):
        steps = step + 1
        if known[exit_cell] != UNKNOWN:
            blocked = known != FREE
            pos_cell = truth.world_to_cell(*pos)
            blocked[pos_cell] = False
            blocked[exit_cell] = False
            path = astar(blocked, pos_cell, exit_cell)
            if path:
                move_along(path)
                reached_exit = True
                break

        options = sorted(_cluster_targets(known), key=score, reverse=True)

        if not options:
            if not stack:
                break  # nothing left anywhere, exit not found -- shouldn't happen
            return_point, deferred = stack.pop()
            blocked = known != FREE
            pos_cell = truth.world_to_cell(*pos)
            blocked[pos_cell] = False
            blocked[return_point] = False
            back_path = astar(blocked, pos_cell, return_point)
            if back_path:
                move_along(back_path)
            options = deferred  # resume exactly where we left off

        if not options:
            continue

        target_cell, _ = options[0]
        remaining = options[1:]

        if remaining:
            # real branch point -- remember where we were BEFORE committing,
            # so we can return here later if this branch dead-ends
            stack.append((truth.world_to_cell(*pos), remaining))

        blocked = known != FREE
        pos_cell = truth.world_to_cell(*pos)
        blocked[pos_cell] = False
        blocked[target_cell] = False
        path = astar(blocked, pos_cell, target_cell)
        if path:
            move_along(path)

    optimal_blocked = truth.occupied
    optimal_path = astar(optimal_blocked, truth.world_to_cell(*entry_xy), exit_cell)
    optimal_distance = 0.0
    if optimal_path:
        prev = truth.cell_to_world(optimal_path[0])
        for cell in optimal_path[1:]:
            wp = truth.cell_to_world(cell)
            optimal_distance += math.hypot(wp[0] - prev[0], wp[1] - prev[1])
            prev = wp

    return FrontierResult(path_points=path_points, total_distance=total_distance,
                           optimal_distance=optimal_distance, reached_exit=reached_exit,
                           steps=steps)


def explore(truth: Grid, entry_xy: Tuple[float, float], exit_xy: Tuple[float, float],
            sensor_range_m: float = 6.0, heuristic: str = "from_entry_sized",
            max_steps: int = 500, drone_clearance_m: float = 0.1,
            full_coverage: bool = True, seed: int = 0, rooms: int = 6) -> FrontierResult:
    """
    full_coverage=True (default): keeps exploring via frontiers until NONE
    remain (the entire reachable area has been sensed), THEN paths to the
    exit -- this is what "visit all rooms to find all survivors" requires.
    full_coverage=False: stops the moment the exit becomes visible, same as
    the original single-target behavior (kept for comparison/testing).
    """
    known = np.zeros((truth.nx, truth.ny), dtype=np.uint8)
    pos = entry_xy
    path_points = [pos]
    total_distance = 0.0
    reached_exit = False
    last_target = entry_xy

    clearance_cells = int(math.ceil(drone_clearance_m / truth.resolution))

    reveal_from(truth, known, pos, sensor_range_m)

    exit_cell = truth.world_to_cell(*exit_xy)

    for step in range(max_steps):
        if not full_coverage and known[exit_cell] != UNKNOWN:
            # Single-target mode only: go straight there the moment it's visible
            known_occupied = known == OCCUPIED
            blocked = (known != FREE) | inflate_occupied(known_occupied, clearance_cells)
            blocked[truth.world_to_cell(*pos)] = False
            blocked[exit_cell] = False
            path = astar(blocked, truth.world_to_cell(*pos), exit_cell)
            if path:
                for cell in path[1:]:
                    wp = truth.cell_to_world(cell)
                    total_distance += math.hypot(wp[0] - pos[0], wp[1] - pos[1])
                    pos = wp
                    path_points.append(pos)
                reached_exit = True
                break

        clusters = find_frontiers(known)
        min_cluster = 1 if full_coverage else 3  # full coverage needs to chase down every
                                                    # pocket, even tiny ones; single-target
                                                    # mode can safely ignore noise slivers
        clusters = [c for c in clusters if len(c) >= min_cluster]
        if not clusters:
            break  # nothing left to explore -- full coverage complete (or single-target
                    # mode ran out of options without finding the exit, which shouldn't
                    # happen on a connected map)

        centroids = []
        for cluster in clusters:
            cx = sum(c[0] for c in cluster) / len(cluster)
            cy = sum(c[1] for c in cluster) / len(cluster)
            # snap to nearest actual frontier cell in the cluster
            nearest = min(cluster, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
            centroids.append((nearest, len(cluster)))

        pos_cell = truth.world_to_cell(*pos)
        last_cell = truth.world_to_cell(*last_target)
        entry_cell = truth.world_to_cell(*entry_xy)

        if heuristic == "nearest":
            ranked = sorted(centroids, key=lambda c: math.hypot(c[0][0] - pos_cell[0], c[0][1] - pos_cell[1]))
        elif heuristic == "farthest":
            ranked = sorted(centroids, key=lambda c: -math.hypot(c[0][0] - last_cell[0], c[0][1] - last_cell[1]))
        elif heuristic == "from_entry":
            ranked = sorted(centroids, key=lambda c: -math.hypot(c[0][0] - entry_cell[0], c[0][1] - entry_cell[1]))
        else:  # "from_entry_sized"
            def score(c):
                (cell, size) = c
                dist = math.hypot(cell[0] - entry_cell[0], cell[1] - entry_cell[1])
                return -(dist * math.sqrt(size))
            ranked = sorted(centroids, key=score)

        known_occupied = known == OCCUPIED
        blocked = (known != FREE) | inflate_occupied(known_occupied, clearance_cells)
        blocked[pos_cell] = False

        # Try candidates in ranked order -- if the top pick is unreachable
        # under the clearance constraint, fall through to the next-best
        # rather than retrying the same failing target every step (which
        # burns the whole step budget with zero progress).
        path = None
        for target_cell, _size in ranked:
            blocked[target_cell] = False
            path = astar(blocked, pos_cell, target_cell)
            blocked[target_cell] = (known[target_cell] != FREE)  # restore for next candidate's check
            if path:
                break

        if not path:
            break  # every currently-known frontier is unreachable under the clearance
                    # constraint -- nothing more to try without new information

        last_target = pos
        for cell in path[1:]:
            wp = truth.cell_to_world(cell)
            total_distance += math.hypot(wp[0] - pos[0], wp[1] - pos[1])
            pos = wp
            path_points.append(pos)
            reveal_from(truth, known, pos, sensor_range_m)

    if full_coverage:
        # Frontiers exhausted (or step budget hit) -- finish with a final
        # trip to the exit through whatever's now known
        known_occupied = known == OCCUPIED
        blocked = (known != FREE) | inflate_occupied(known_occupied, clearance_cells)
        blocked[truth.world_to_cell(*pos)] = False
        blocked[exit_cell] = False
        path = astar(blocked, truth.world_to_cell(*pos), exit_cell)
        if path:
            for cell in path[1:]:
                wp = truth.cell_to_world(cell)
                total_distance += math.hypot(wp[0] - pos[0], wp[1] - pos[1])
                pos = wp
                path_points.append(pos)
            reached_exit = True

    if full_coverage:
        # Fair baseline: the validated room-graph full-coverage lower bound
        # (same underlying maze, same seed) rather than a simple point-to-point
        # distance, since "visit everywhere then exit" is a different problem
        # than "reach the exit" -- see maze_solver.py's full_coverage_lower_bound(),
        # tested and confirmed correct earlier in this project.
        import maze_solver as _ms
        graph = _ms.build_room_graph(seed=seed, width=truth.width_m,
                                      depth=truth.depth_m, rooms=rooms)
        optimal_distance = _ms.full_coverage_lower_bound(graph)
    else:
        # Offline-optimal baseline ALSO respects the same clearance margin, so
        # it's a fair, apples-to-apples comparison -- not comparing a
        # safety-constrained real path against an unsafe zero-clearance ideal
        optimal_blocked = inflate_occupied(truth.occupied, clearance_cells)
        optimal_path = astar(optimal_blocked, truth.world_to_cell(*entry_xy), exit_cell)
        optimal_distance = 0.0
        if optimal_path:
            prev = truth.cell_to_world(optimal_path[0])
            for cell in optimal_path[1:]:
                wp = truth.cell_to_world(cell)
                optimal_distance += math.hypot(wp[0] - prev[0], wp[1] - prev[1])
                prev = wp

    return FrontierResult(path_points=path_points, total_distance=total_distance,
                           optimal_distance=optimal_distance, reached_exit=reached_exit,
                           steps=step + 1)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_result(truth: Grid, result: FrontierResult, entry_xy, exit_xy, path: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(truth.occupied.T, origin="lower", cmap="Greys",
              extent=[0, truth.width_m, 0, truth.depth_m], alpha=0.6)

    xs = [p[0] for p in result.path_points]
    ys = [p[1] for p in result.path_points]
    ax.plot(xs, ys, color="royalblue", linewidth=1.2, alpha=0.85,
            label=f"Explored path ({result.total_distance:.1f} m)")

    ax.plot(*entry_xy, marker="o", color="green", markersize=12, label="Entry")
    ax.plot(*exit_xy, marker="o", color="red", markersize=12, label="Exit")

    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"Frontier exploration -- {result.total_distance:.1f} m flown "
                 f"vs {result.optimal_distance:.1f} m optimal "
                 f"({result.competitive_ratio:.2f}x), {result.steps} steps")
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
    p.add_argument("--resolution", type=float, default=0.1)
    p.add_argument("--sensor-range", type=float, default=6.0)
    p.add_argument("--drone-clearance", type=float, default=0.1,
                   help="Drone radius + safety margin in meters, used to inflate "
                        "walls so planned paths keep physical clearance. NOTE: "
                        "testing found some doorways in this maze generator become "
                        "genuinely unreachable above ~0.15m clearance (1-2 seeds out "
                        "of 30 failed) -- this maze's doors are close to the mission "
                        "brief's 1.0m minimum corridor width, leaving little real "
                        "margin for any physical drone. Worth flagging to the team.")
    p.add_argument("--heuristic", choices=["nearest", "farthest", "from_entry", "from_entry_sized"],
                   default="from_entry_sized")
    p.add_argument("--plot", type=str, default=None)
    args = p.parse_args()

    truth, entry_xy, exit_xy = build_ground_truth_grid(
        args.seed, args.width, args.depth, args.rooms, args.resolution)

    result = explore(truth, entry_xy, exit_xy, args.sensor_range, args.heuristic,
                      drone_clearance_m=args.drone_clearance, seed=args.seed, rooms=args.rooms)

    print(f"seed={args.seed}  grid={truth.nx}x{truth.ny} @ {args.resolution}m/cell")
    print(f"reached exit = {result.reached_exit}  (in {result.steps} exploration steps)")
    print(f"total distance flown     = {result.total_distance:.2f} m")
    print(f"offline-optimal distance = {result.optimal_distance:.2f} m")
    print(f"competitive ratio        = {result.competitive_ratio:.2f}x")

    if args.plot:
        plot_result(truth, result, entry_xy, exit_xy, args.plot)
        print(f"Wrote plot -> {args.plot}")


if __name__ == "__main__":
    main()