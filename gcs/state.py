"""
Mission state model. This is a direct port of the `state` object from the
original web GCS's <script> block, kept dependency-free (no Qt imports)
so it can be unit tested in isolation from the UI.

IMPORTANT (carried over from the original): there is no preloaded
blueprint and no known starting coordinate. The drone has no GPS (the
arena is a fully enclosed, GPS-denied space) — its onboard VIO/SLAM
estimator invents its own local (x, y) frame anchored wherever it was
powered on. Nothing should be drawn/considered "fixed" until the first
telemetry message actually arrives (see DroneState.has_fix below).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DroneState:
    x: float = 0.0
    y: float = 0.0
    heading: float = 0.0
    estimated: bool = False
    has_fix: bool = False
    trail: List[Tuple[float, float]] = field(default_factory=list)

    def push_trail(self, x: float, y: float, max_len: int = 400) -> None:
        self.trail.append((x, y))
        if len(self.trail) > max_len:
            self.trail.pop(0)


@dataclass
class ViewState:
    scale: float = 28.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    auto_fit: bool = True


class MissionState:
    """Everything the UI needs to render a single mission run."""

    def __init__(self) -> None:
        self.connected: bool = False
        self.cells: Dict[Tuple[int, int], str] = {}
        self.rooms: Dict[str, dict] = {}
        self.survivors: Dict[int, dict] = {}
        self.waypoints: Dict[str, dict] = {}   # "entry" / "exit" -> payload
        self.objects: Dict[int, dict] = {}
        self.drone = DroneState()
        self.cell_size_m: float = 1.0
        self.start_time: Optional[float] = None
        self.server_elapsed: Optional[float] = None
        self.server_elapsed_at: Optional[float] = None
        self.view = ViewState()

    def reset(self) -> None:
        """A fresh connection means a fresh drone boot means a fresh,
        unrelated local coordinate origin — anything drawn from a
        previous session has to be cleared rather than blended in."""
        self.cells.clear()
        self.rooms.clear()
        self.survivors.clear()
        self.waypoints.clear()
        self.objects.clear()
        self.drone = DroneState()
        self.view = ViewState()
        self.start_time = None
        self.server_elapsed = None
        self.server_elapsed_at = None
