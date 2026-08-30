# Maze Solving in Shortest Time

Task: visit every room in the maze (to find all survivors) in minimal time,
with zero prior knowledge of the layout (GPS-denied, per mission brief).

## Files

- **`maze_solver.py`** -- PRIMARY DELIVERABLE, recommended for the actual
  "visit all rooms" requirement. Builds the true room-adjacency graph from
  floorplan_generator's geometry, simulates full-coverage online DFS
  exploration (visits every room -- verified via hard assertion, not a
  coverage percentage -- forces the exit-containing branch to be explored
  last, ends at the exit).
- **`frontier_solver.py`** -- supporting/exploratory work, NOT currently
  reliable for full coverage (see Known Limitations #1). Grid-based frontier
  exploration (no room concept, standard Nav2-style approach), with
  realistic limited-range sensing and physical wall clearance for path
  planning. Demonstrates the underlying techniques work, but has a known
  unresolved bug where a whole room can be skipped without any error signal.
- **`floorplan_generator.py`** -- not ours, included so both scripts run
  standalone (imported as a library, not modified).
- **`HEURISTIC_NOTES.md`** -- full writeup of what was tried, what worked,
  what didn't, and why -- including corrections to earlier mistaken claims,
  kept in for transparency.

## Results (both offline, tested against floorplan_generator, no ground-truth cheating)

**maze_solver.py, full coverage** (40 random seeds, 7-room layouts):
- Mean: 1.64x the offline-optimal distance
- Worst case: 7.29x (one specific hard layout with elongated rooms and
  off-center doors -- a real geometric property of that seed, not a bug)
- 100% success rate (every seed, every room visited, exit reached)

**frontier_solver.py, single-target + wall clearance** (30 seeds):
- Mean: 1.67x optimal, 30/30 reached exit, with a tested-safe 0.1m
  physical clearance margin around every wall

## Known limitations / next steps

1. **frontier_solver.py's "full coverage" mode is NOT reliable yet.** Testing
   found it can report success (reached exit, reasonable distance ratio)
   while actually skipping a whole room -- e.g. one test case left a room's
   centroid 6.28m from the nearest point the drone's path ever reached, well
   outside sensor range, with no error or warning. The "reached exit"
   success flag does not guarantee all rooms were visited; grid coverage
   percentage (71.8% typical) is a misleading proxy since the unrevealed
   area isn't evenly distributed -- it can be a whole missed room, not just
   tight corners. Root cause not yet fixed: likely a pathfinding dead-end to
   that room's doorway under the clearance constraint, silently dropped by
   the exploration loop instead of triggering a retry from a different
   angle. **Do not treat frontier_solver.py's full-coverage claim as
   trustworthy without further work.**
2. **maze_solver.py IS reliable for full coverage** -- it explicitly tracks
   which rooms have been visited (`set(visit_order) == set(all rooms)`,
   checked directly as a hard assertion, not inferred from a percentage) and
   is the recommended module for the actual "visit all rooms" requirement.
3. **Tight corridor margins**: testing found some doorways in this maze
   generator become unreachable above ~0.15m drone clearance (1-2 seeds out
   of 30 failed). This maze's doors are close to the mission brief's 1.0m
   minimum corridor width, leaving little real margin for a physical drone.
   Worth flagging to the team -- not something more code can fix, it's a
   property of the arena dimensions vs. drone size.
4. **Not wired into ROS2 yet** -- these are offline, standalone simulations
   proving the exploration/coverage logic. Real integration needs: the
   Mapping team's live `/map` (occupancy grid), and a way to feed waypoint
   decisions to the Navigation team's flight controller. Interface not yet
   confirmed with either team.
5. **Not tested in Gazebo/against a real spawned world** -- these results
   are from directly calling floorplan_generator's geometry functions, not
   from an actual simulated sensor in a physics simulation. Real-world (or
   real-sim) performance may differ.

## How to run

```bash
pip install matplotlib numpy
python3 maze_solver.py --seed 1 --rooms 7 --plot out.png
python3 frontier_solver.py --seed 1 --rooms 7 --plot out2.png
```