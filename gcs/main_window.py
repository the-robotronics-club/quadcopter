"""
NIDAR GCS — native desktop main window.

---- Message schema this app expects from the PX4 companion bridge ----
(unchanged from the original web GCS — the bridge contract, not the
transport, is what matters):

  {"type":"telemetry","data":{
      "x":3.4,"y":1.2,"heading_deg":87,"estimated":false,
      "battery_pct":76,"rssi_pct":88,"phase":"SEARCHING"}}

  {"type":"map_update","data":{
      "cells":[{"x":3,"y":1,"kind":"corridor"}, ...],
      "cell_size_m":1.0,
      "rooms":[{"id":"R1","x":6,"y":2,"label":"ROOM 1"}]}}

  {"type":"survivor","data":{
      "id":1,"grid_box":"C4","x":6.2,"y":3.1,"confidence":0.91,"t":142}}

  {"type":"waypoint","data":{
      "role":"entry"|"exit","x":1.0,"y":0.4,"t":30}}

  {"type":"object","data":{
      "id":1,"kind":"obj_crate"|"obj_rubble"|"obj_barrel","x":4.1,"y":2.6,"t":44}}

  {"type":"camera_frame","data":{
      "jpeg":"<base64 jpeg>","grid_box":"C4","room":"ROOM 2"}}
      (or a bare base64 jpeg string, for backward compatibility)

There is NO preloaded blueprint and NO known starting coordinate — see
state.py for why. Nothing is drawn until the bridge actually reports it.
"""

import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from . import theme
from .bridge_client import BridgeClient
from .camera_panel import CameraPanel
from .connection_bar import ConnectionBar
from .log_panel import LogPanel
from .map_canvas import MapCanvas
from .simulator import Simulator
from .state import MissionState
from .status_panel import StatusPanel
from .survivor_panel import SurvivorPanel


def fmt_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NIDAR // GROUND CONTROL")
        self.resize(1440, 860)
        self.setMinimumSize(1120, 680)  # below this the panels start to crush; keep everything legible
        self.setStyleSheet(f"background:{theme.BG_0}; color:{theme.GREY_HI};")

        self.state = MissionState()
        self.bridge = BridgeClient(self)
        self.simulator = Simulator(self)

        self._build_ui()
        self._wire_signals()

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.start(1000)

        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background:{theme.BG_1}; color:{theme.GREY_DIM}; "
            f"font-family:{theme.MONO}; font-size:10.5px; border-top:1px solid {theme.LINE_0}; "
            f"padding:3px 12px; }}"
        )
        self.statusBar().showMessage(
            "Click Simulate to preview the display without a drone connection."
        )

        self.log_panel.log(
            "GCS interface ready. No blueprint or starting position is preloaded \u2014 the "
            "map builds up live from what the drone reports via the PX4 companion bridge "
            "once connected. Enter the bridge's WebSocket address and connect, or click "
            "Simulate to bench-test the display. Use New Mission to wipe the board between flights."
        )

    # ---------------- layout ----------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.connection_bar = ConnectionBar()
        root.addWidget(self.connection_bar)

        body_splitter = QSplitter(Qt.Orientation.Vertical)
        root.addWidget(body_splitter, 1)

        main_split = QSplitter(Qt.Orientation.Horizontal)

        splitter_handle_style = f"""
            QSplitter::handle {{ background:{theme.LINE_0}; }}
            QSplitter::handle:hover {{ background:{theme.WINDOW_LINE}; }}
        """
        body_splitter.setStyleSheet(splitter_handle_style)
        main_split.setStyleSheet(splitter_handle_style)
        body_splitter.setHandleWidth(3)
        main_split.setHandleWidth(3)

        self.map_canvas = MapCanvas(self.state)
        main_split.addWidget(self.map_canvas)

        self.camera_panel = CameraPanel()
        main_split.addWidget(self.camera_panel)

        sidebar = QWidget()
        sidebar.setStyleSheet(f"background:{theme.BG_1};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)
        self.status_panel = StatusPanel()
        self.survivor_panel = SurvivorPanel()
        sb_layout.addWidget(self.status_panel)
        sb_layout.addWidget(self.survivor_panel, 1)
        main_split.addWidget(sidebar)

        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 1)
        main_split.setStretchFactor(2, 0)
        main_split.setSizes([560, 560, 340])
        body_splitter.addWidget(main_split)

        self.log_panel = LogPanel()
        self.log_panel.setMinimumHeight(90)
        self.log_panel.setMaximumHeight(220)
        body_splitter.addWidget(self.log_panel)
        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 0)
        body_splitter.setSizes([700, 120])

    def _wire_signals(self):
        self.connection_bar.connect_clicked.connect(self.on_connect_clicked)
        self.connection_bar.disconnect_clicked.connect(self.on_disconnect_clicked)
        self.connection_bar.simulate_clicked.connect(self.on_simulate_clicked)
        self.connection_bar.new_mission_clicked.connect(self.on_new_mission_clicked)

        self.bridge.connected.connect(self.on_bridge_connected)
        self.bridge.disconnected.connect(self.on_bridge_disconnected)
        self.bridge.message_received.connect(self.handle_message)
        self.bridge.error_occurred.connect(self._on_bridge_error)

        self.simulator.message.connect(self.handle_message)

    # ---------------- connection lifecycle ----------------
    def on_connect_clicked(self, url: str):
        if not url:
            self.statusBar().showMessage(
                "Enter the PX4 companion bridge's WebSocket address first (e.g. ws://192.168.4.1:8765).",
                5000,
            )
            self.log_panel.log("Connect pressed with no bridge address entered \u2014 nothing to connect to.", warn=True)
            return
        if self.simulator.running():
            self.simulator.stop()
            self.connection_bar.set_sim_running(False)
            self.log_panel.log("Simulation stopped \u2014 connecting to live link instead.", warn=True)
        self.log_panel.log(f"Connecting to PX4 companion bridge at {url} \u2026")
        self.connection_bar.set_link_state("connecting")
        self.bridge.connect_to(url)

    def on_disconnect_clicked(self):
        was_connecting = not self.bridge.is_open()
        self.bridge.close()
        # Reset the UI immediately rather than waiting on the socket's
        # `disconnected` signal — some Qt versions don't reliably emit it
        # for a connection that was aborted mid-handshake, which would
        # otherwise leave the bar stuck showing "CONNECTING…" forever.
        self.connection_bar.set_link_state("offline")
        self.camera_panel.reset()
        if was_connecting:
            self.log_panel.log("Connection attempt cancelled.", warn=True)
        else:
            self.log_panel.log("Manually disconnected.", warn=True)

    def on_bridge_connected(self):
        self.reset_mission()
        self.connection_bar.set_link_state("live")
        self.state.start_time = time.time()
        self.statusBar().showMessage("Connected to PX4 companion bridge.", 4000)
        self.log_panel.log("Link to PX4 companion bridge established \u2014 awaiting first telemetry fix.")

    def on_bridge_disconnected(self):
        self.connection_bar.set_link_state("offline")
        self.camera_panel.reset()
        self.log_panel.log("Bridge link closed.", warn=True)

    def _on_bridge_error(self, message: str):
        self.log_panel.log(message, warn=True)
        if not self.bridge.is_open():
            self.connection_bar.set_link_state("offline")
            self.statusBar().showMessage("Bridge connection failed \u2014 check the address and try again.", 6000)

    def on_simulate_clicked(self):
        if self.simulator.running():
            self.simulator.stop()
            self.connection_bar.set_sim_running(False)
            self.log_panel.log("Simulation stopped.", warn=True)
            return
        self.reset_mission()
        self.connection_bar.set_sim_running(True)
        self.state.start_time = time.time()
        self.statusBar().showMessage("Running local simulation \u2014 no drone required.", 4000)
        self.log_panel.log(
            "Running local simulation (no live bridge link) \u2014 the drone \"boots\" with an "
            "unknown position and localizes itself as it flies, same as a real GPS-denied run."
        )
        self.simulator.start()

    def on_new_mission_clicked(self):
        has_data = bool(self.state.cells or self.state.survivors or self.state.objects or self.state.waypoints)
        if has_data:
            reply = QMessageBox.question(
                self,
                "Start a new mission?",
                "This clears the current map, trail, and every tagged survivor and re-arms "
                "the display for a fresh flight. This can't be undone.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.reset_mission()
        self.log_panel.log("Map cleared \u2014 armed for a new local coordinate frame.", warn=True)

    def reset_mission(self):
        self.state.reset()
        self.status_panel.reset()
        self.survivor_panel.render({})
        self.camera_panel.reset()
        self.map_canvas.update()

    # ---------------- elapsed clock ----------------
    def _tick_elapsed(self):
        if not self.connection_bar.is_active():
            return
        if self.state.server_elapsed is not None:
            s = self.state.server_elapsed + (time.time() - self.state.server_elapsed_at)
        elif self.state.start_time is not None:
            s = time.time() - self.state.start_time
        else:
            return
        self.status_panel.set_elapsed_text(fmt_time(s))

    # ---------------- message dispatch ----------------
    def handle_message(self, msg: dict):
        """Top-level entry point for every message, whether it came from
        the real bridge or the local simulator. Wrapped so that one
        malformed/unexpected frame from real hardware over a flaky link
        logs an error instead of taking the whole GCS down."""
        try:
            self._dispatch_message(msg)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            self.log_panel.log(
                f"Error handling '{msg.get('type')}' message: {exc}", warn=True
            )

    def _dispatch_message(self, msg: dict):
        t = msg.get("type")
        raw_d = msg.get("data")

        # camera_frame alone is allowed to carry a bare base64 string
        # instead of a dict (see the schema note up top) — everything
        # else needs an actual dict, so a missing/null/malformed "data"
        # field safely becomes {} rather than crashing every handler.
        if t == "camera_frame":
            self.camera_panel.set_frame(raw_d)
            return
        d = raw_d if isinstance(raw_d, dict) else {}

        if t == "telemetry":
            self._on_telemetry(d)
        elif t == "map_update":
            self._on_map_update(d)
        elif t == "survivor":
            self._on_survivor(d)
        elif t == "waypoint":
            self._on_waypoint(d)
        elif t == "object":
            self._on_object(d)
        elif t == "mission_status":
            self._on_mission_status(d)
        else:
            self.log_panel.log(f"Unknown message type: {t}", warn=True)

    def _on_telemetry(self, d: dict):
        drone = self.state.drone
        first_fix = not drone.has_fix
        drone.x = d.get("x", drone.x)
        drone.y = d.get("y", drone.y)
        drone.heading = d.get("heading_deg") or 0
        drone.estimated = bool(d.get("estimated"))
        drone.has_fix = True
        drone.push_trail(drone.x, drone.y)

        if self.state.view.auto_fit:
            self.state.view.offset_x = drone.x
            self.state.view.offset_y = drone.y

        if first_fix:
            self.log_panel.log(
                "Local position estimator initialized \u2014 origin set at drone takeoff pose "
                f"({drone.x:.1f}, {drone.y:.1f} in its own frame)."
            )
        self.status_panel.update_telemetry(d)
        self.map_canvas.update()

    def _on_map_update(self, d: dict):
        if d.get("cell_size_m"):
            self.state.cell_size_m = d["cell_size_m"]
        for c in d.get("cells", []):
            self.state.cells[(c["x"], c["y"])] = c["kind"]
        for r in d.get("rooms", []):
            self.state.rooms[r["id"]] = r
        self.map_canvas.update()

    def _on_survivor(self, d: dict):
        if "id" not in d:
            return
        is_new = d["id"] not in self.state.survivors
        self.state.survivors[d["id"]] = d
        self.survivor_panel.render(self.state.survivors)
        self.map_canvas.update()
        if is_new:
            conf = round((d.get("confidence") or 0) * 100)
            self.log_panel.log(
                f"Survivor #{d['id']} tagged \u2014 grid box {d.get('grid_box')} (confidence {conf}%)"
            )

    def _on_waypoint(self, d: dict):
        role = d.get("role")
        if not role:
            return
        is_new = role not in self.state.waypoints
        self.state.waypoints[role] = d
        self.map_canvas.update()
        if is_new:
            self.log_panel.log(
                f"{role.upper()} point sighted at local ({d.get('x', 0):.1f}, {d.get('y', 0):.1f})."
            )

    def _on_object(self, d: dict):
        if d.get("id") is None:
            return
        is_new = d["id"] not in self.state.objects
        self.state.objects[d["id"]] = d
        self.map_canvas.update()
        if is_new:
            kind = (d.get("kind") or "object").replace("obj_", "")
            self.log_panel.log(
                f"Obstacle logged \u2014 {kind} at local ({d.get('x', 0):.1f}, {d.get('y', 0):.1f})."
            )

    def _on_mission_status(self, d: dict):
        self.status_panel.update_mission_status(d)
        if d.get("elapsed_s") is not None:
            self.state.server_elapsed = d["elapsed_s"]
            self.state.server_elapsed_at = time.time()
