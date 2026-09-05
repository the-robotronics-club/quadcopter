"""Local bench-test simulator — lets you exercise the whole UI with no
drone/bridge link, exactly mirroring the original JS `Simulate` button.
Emits the same message shape the BridgeClient would, so main_window's
handle_message() doesn't need to know the difference."""

import math
import random

from PySide6.QtCore import QObject, QTimer, Signal

from .map_canvas import grid_label


class Simulator(QObject):
    message = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._t = 0
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._seeded = set()
        self._obj_id = 0

    def start(self) -> None:
        self._t = 0
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0
        self._seeded = set()
        self._obj_id = 0
        self._timer.start(400)

    def stop(self) -> None:
        self._timer.stop()

    def running(self) -> bool:
        return self._timer.isActive()

    def _emit(self, type_: str, data: dict) -> None:
        self.message.emit({"type": type_, "data": data})

    def _tick(self) -> None:
        self._t += 1
        t = self._t
        self._heading = (self._heading + 8) % 360
        self._x += math.cos(math.radians(self._heading)) * 0.3
        self._y += math.sin(math.radians(self._heading)) * 0.3

        self._emit("telemetry", {
            "x": self._x, "y": self._y, "heading_deg": self._heading,
            "estimated": (t % 15 < 3),
            "battery_pct": max(20, 100 - t * 0.3),
            "rssi_pct": 70 + round(math.sin(t / 5) * 15),
        })

        cx, cy = round(self._x), round(self._y)
        new_cells = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (cx + dx, cy + dy)
                if key in self._seeded:
                    continue
                self._seeded.add(key)
                r = random.random()
                if dx == 0 and dy == 0:
                    kind = "corridor"
                elif r < 0.10:
                    kind = "door"
                elif r < 0.16:
                    kind = "window"
                elif r < 0.30:
                    kind = "wall"
                elif r < 0.45:
                    kind = "room"
                else:
                    kind = "floor"
                new_cells.append({"x": cx + dx, "y": cy + dy, "kind": kind})
        if new_cells:
            self._emit("map_update", {"cell_size_m": 1.0, "cells": new_cells})

        self._emit("mission_status", {
            "phase": "SEARCHING", "coverage_pct": min(100, t * 0.8), "elapsed_s": t,
        })

        if t == 8:
            self._emit("waypoint", {"role": "entry", "x": cx, "y": cy, "t": t})
        if t == 70:
            self._emit("waypoint", {"role": "exit", "x": cx, "y": cy, "t": t})
        if t in (20, 55):
            self._emit("survivor", {
                "id": 1 if t == 20 else 2,
                "grid_box": grid_label(cx, cy),
                "x": cx, "y": cy,
                "confidence": 0.8 + random.random() * 0.18,
                "t": t,
            })
        if t % 12 == 0:
            self._obj_id += 1
            kinds = ["obj_crate", "obj_rubble", "obj_barrel"]
            self._emit("object", {
                "id": self._obj_id,
                "kind": kinds[self._obj_id % 3],
                "x": cx + (random.random() - 0.5),
                "y": cy + (random.random() - 0.5),
                "t": t,
            })
