# NIDAR GCS — Ground Control Station

A native desktop Ground Control Station (GCS) for a GPS-denied search-and-rescue
drone. Built with PySide6/Qt — no browser, no web canvas. Everything (the map,
the camera feed, the telemetry log) is a real Qt widget drawn straight to
screen.

The drone has no GPS — its onboard VIO/SLAM estimator invents its own local
(x, y) coordinate frame anchored wherever it was powered on. There is no
preloaded blueprint and no known starting position: the map is built up live,
cell by cell, purely from what the drone reports over its companion-computer
link. Nothing is drawn until the bridge actually says it's there.

## What it shows

- **Live map** — walls, doors, windows, corridors, rooms, and unexplored
  space, drawn cell-by-cell as the drone reports them, plus the drone's
  breadcrumb trail, logged obstacles, entry/exit waypoints, and tagged
  survivors (with a pulsing beacon).
- **Live camera feed** — JPEG frames decoded straight to a `QPixmap`.
- **Mission status** — phase, elapsed time, position, heading, battery,
  link quality, and search coverage.
- **Detected survivors** — a running, scrollable list with grid box and
  confidence for each detection.
- **Telemetry log** — a timestamped scrolling log of everything that happens.
- **Connection bar** — shows **LIVE** (real bridge link), **SIMULATED**
  (bench-testing with the built-in Simulate button, no drone), **CONNECTING**,
  or **OFFLINE**, each with its own color so they're never confused with
  one another.

## Requirements

- Python 3.9+
- Dependencies in `requirements.txt` (PySide6, and `websockets` if you want
  to run the mock bridge server described below)

## Install

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the app

```bash
python main.py
```

## Try it with no drone at all

Click **Simulate** in the app. This runs `gcs/simulator.py`, a local scripted
flight that feeds the exact same message shapes a real bridge would, so you
can see the whole UI (map, camera placeholder, survivors, log) come to life
with zero hardware. The status bar will read **SIMULATED**, not **LIVE**, so
it's always clear this isn't a real drone link. Click **Stop Sim** or
**New Mission** to reset.

## Test the real connection path (still no drone required)

`Simulate` only exercises the app's internal logic — it never touches the
network. To actually test `gcs/bridge_client.py` and the WebSocket connect
path, run the included mock bridge server instead:

```bash
python test_bridge_server.py
```

This starts a WebSocket server at `ws://127.0.0.1:8765` and plays back the
same scripted flight over a real socket. Then, in the GCS:

1. Enter `ws://127.0.0.1:8765` in the address field.
2. Click **Connect**.

The status bar should go **CONNECTING…** then **LIVE**.

## Connect to a real drone

Enter the PX4 companion bridge's WebSocket address (e.g.
`ws://192.168.4.1:8765`) in the address field and click **Connect**. The
bridge must speak the JSON-over-WebSocket message schema below.

## Message schema (bridge → GCS)

Every message is `{"type": "...", "data": {...}}`:

| type | data |
|---|---|
| `telemetry` | `x`, `y`, `heading_deg`, `estimated` (bool), `battery_pct`, `rssi_pct` |
| `map_update` | `cell_size_m`, `cells: [{x, y, kind}]` (`kind` ∈ wall/door/window/corridor/room/floor), optional `rooms: [{id, x, y, label}]` |
| `survivor` | `id`, `grid_box`, `x`, `y`, `confidence` (0–1), `t` |
| `waypoint` | `role` (`"entry"` or `"exit"`), `x`, `y`, `t` |
| `object` | `id`, `kind` (`obj_crate` / `obj_rubble` / `obj_barrel`), `x`, `y`, `t` |
| `camera_frame` | `{"jpeg": "<base64 jpeg>", "grid_box": "...", "room": "..."}`, or a bare base64 JPEG string |
| `mission_status` | `phase`, `coverage_pct`, `elapsed_s` |

If your companion-computer bridge speaks something else (raw MAVLink,
protobuf, etc.), `gcs/bridge_client.py` is the one file to adapt —
everything downstream just consumes plain Python dicts.

## Data flow — where data comes in, and how it ends up on screen

**1. Where it comes in.** There are exactly two entry points, and both end
up producing the same shape of message:

| Source | File / class | How it enters |
|---|---|---|
| Real drone | `gcs/bridge_client.py` → `BridgeClient` | A `QWebSocket` receives a JSON text frame from the PX4 companion bridge over the network. It's parsed in `BridgeClient._on_text()` and re-emitted as the Qt signal `message_received(dict)`. |
| Bench test (**Simulate** button) | `gcs/simulator.py` → `Simulator` | No network at all — a `QTimer` fires every 400ms in `Simulator._tick()`, fabricating the same message shapes locally and emitting them as the Qt signal `message(dict)`. |

Both signals are wired in `main_window.py`'s `_wire_signals()` to the same
slot:

```python
self.bridge.message_received.connect(self.handle_message)
self.simulator.message.connect(self.handle_message)
```

So everything past this point is identical whether the data came from a
real drone or the simulator — the rest of the app can't tell the difference.

**2. Where it's interpreted and stored.** `MainWindow.handle_message()` →
`_dispatch_message()` in `main_window.py` looks at the message's `"type"`
and routes it to a handler, which writes the payload into `MissionState`
(`gcs/state.py`) — the one dependency-free object every panel reads from:

| `type` | Handler | Stored in |
|---|---|---|
| `telemetry` | `_on_telemetry` | `state.drone` (x, y, heading, battery, RSSI, fix status, trail) |
| `map_update` | `_on_map_update` | `state.cells` (dict keyed by `(x, y)`), `state.rooms` |
| `survivor` | `_on_survivor` | `state.survivors` (dict keyed by id) |
| `waypoint` | `_on_waypoint` | `state.waypoints` (dict keyed by `"entry"`/`"exit"`) |
| `object` | `_on_object` | `state.objects` (dict keyed by id) |
| `mission_status` | `_on_mission_status` | `state.server_elapsed`, mission phase/coverage |
| `camera_frame` | handled directly, no state store | passed straight to `CameraPanel.set_frame()` |

**3. Where and how it's displayed.** Each handler above, after updating
`state`, tells the relevant widget to redraw:

| Widget | File | What it draws, and from where |
|---|---|---|
| Map | `map_canvas.py` → `MapCanvas.paintEvent` | Everything in `state` — cells, room labels, drone trail, obstacles, waypoints, survivor beacons, the drone marker — drawn by hand with `QPainter`. Triggered by `self.map_canvas.update()` after almost every handler. |
| Camera feed | `camera_panel.py` → `CameraPanel.set_frame` | Decodes the incoming base64 JPEG straight into a `QPixmap` — no image file, no browser `<img>`. |
| Mission status | `status_panel.py` → `StatusPanel.update_telemetry` / `update_mission_status` | Reads straight off the incoming `telemetry`/`mission_status` payload (position, heading, battery, link %, phase, coverage bar). |
| Survivor list | `survivor_panel.py` → `SurvivorPanel.render` | Rebuilt from `state.survivors` every time a new survivor arrives. |
| Telemetry log | `log_panel.py` → `LogPanel.log` | Appended to directly by the handlers in `main_window.py` (e.g. "Survivor #1 tagged…", "ENTRY point sighted…") — this one doesn't read from `state`, it's a live narration of events as they're handled. |
| Connection bar | `connection_bar.py` → `ConnectionBar` | Doesn't touch mission data at all — only reflects the link state (`OFFLINE` / `CONNECTING` / `LIVE` / `SIMULATED`) set by `main_window.py`'s connection-lifecycle methods. |

## Project structure

```
main.py                  # entry point — python main.py
test_bridge_server.py    # standalone mock PX4 bridge for testing the real WebSocket path
requirements.txt
gcs/
    main_window.py        # main window, message dispatch, connection lifecycle
    bridge_client.py       # QWebSocket client — the real drone link
    simulator.py           # local scripted flight, no network — powers the Simulate button
    state.py               # MissionState — dependency-free, unit-testable mission data model
    map_canvas.py           # hand-drawn (QPainter) map: cells, trail, waypoints, survivors, legend
    camera_panel.py         # live camera feed panel
    connection_bar.py       # header: address field, Connect/Simulate/New Mission, status indicator
    status_panel.py         # phase / elapsed / position / heading / battery / link / coverage
    survivor_panel.py       # scrollable list of detected survivors
    log_panel.py            # timestamped telemetry log
    theme.py                # single source of truth for every color in the app
```

## Notes

- **New Mission** wipes the map, trail, waypoints, survivors, and obstacles
  and re-arms for a fresh local coordinate frame — use it between flights.
- The whole app's color scheme lives in `gcs/theme.py`; re-theming is
  mostly editing that one file.
