# NIDAR GCS — Ground Control Station

A desktop app that shows a live map, camera feed, and status readout for a
search-and-rescue drone. No browser involved — it's a native app built with
PySide6 (Qt).

The drone flies indoors with no GPS, so it has no idea where it "actually"
is — it just tracks its own position relative to wherever it took off. That
means **the map starts completely blank every time**. Nothing is drawn until
the drone itself reports it.

---

## 1. Folder layout

```
your_project/
├── main.py                 ← run this to start the app
├── px4_bridge.py            ← connects the app to a real PX4 drone/sim
├── test_bridge_server.py    ← fake data generator, for testing
├── requirements.txt
├── README.md
└── gcs/                      ← the app itself lives in here
    ├── __init__.py
    ├── bridge_client.py
    ├── camera_panel.py
    ├── connection_bar.py
    ├── log_panel.py
    ├── main_window.py
    ├── map_canvas.py
    ├── simulator.py
    ├── state.py
    ├── status_panel.py
    ├── survivor_panel.py
    └── theme.py
```

**One rule to remember:** `main.py` must always sit *next to* the `gcs`
folder, never inside it. If you move `main.py` into `gcs/`, the app breaks
with `ModuleNotFoundError: No module named 'gcs'`. Same for `px4_bridge.py`
— keep it outside `gcs/` too.

---

## 2. Setup

```bash
pip install -r requirements.txt
```

⚠️ Make sure you install the **full** `PySide6` package, not
`PySide6-Essentials`. The essentials-only version is missing a piece
(`QtWebSockets`) that this app needs to talk to a drone.

---

## 3. Running it

```bash
python main.py
```

The app opens with a blank map — that's expected. You now have three ways
to get data flowing:

### Option A — Just click "Simulate"

The quickest way to see the app working. Click the **Simulate** button in
the top bar. No setup, no network, nothing else to run. Click **Stop Sim**
to end it.

### Option B — Test with fake network data

```bash
python test_bridge_server.py
```

This is the same fake flight as "Simulate," but sent over a real network
connection — useful for testing that the networking side of the app
actually works. In the GCS, type `ws://127.0.0.1:8765` into the address box
and click **Connect**.

### Option C — Connect to a real drone or PX4 simulation

```bash
python px4_bridge.py --mavlink udpin:0.0.0.0:14550
```

Then in the GCS, connect to `ws://127.0.0.1:8765`, same as Option B.

**Why you need this extra script:** the GCS app only understands one
"language" over the network — JSON messages over a WebSocket. A drone
running PX4 speaks a completely different language (MAVLink, over UDP).
`px4_bridge.py` is the translator that sits in between:

```
PX4 drone/sim  --(MAVLink)-->  px4_bridge.py  --(WebSocket)-->  GCS app
```

Pointing the GCS directly at a raw MAVLink address will never work, no
matter what IP or port you try — there's nothing there that speaks the
GCS's language until this bridge is running.

**One thing to watch for:** PX4 usually sends its data to port `14550` —
the same port QGroundControl listens on. Only one program can listen on a
port at a time, so if QGroundControl is open, close it before starting
`px4_bridge.py` (or point PX4 at a different port for the bridge).

---

## 4. If something goes wrong

| What you see | What's happening | What to do |
|---|---|---|
| `ModuleNotFoundError: No module named 'gcs'` | `main.py` is inside the `gcs` folder, or you ran it from inside `gcs` | Run `python main.py` from the folder *above* `gcs/` |
| "Address already in use" when starting `px4_bridge.py` | Something else (usually QGroundControl) already has that port open | Close it, or use a different port |
| GCS won't connect to a MAVLink/UDP address | The GCS can't speak MAVLink directly | Run `px4_bridge.py` in between (see Option C above) |
| Log panel text looks cut off or garbled | Was a bug — fixed, see changelog below | Update to the current `gcs/log_panel.py` |

---

## 5. The three problems your lead originally hit — status

| Reported problem | Status |
|---|---|
| `ModuleNotFoundError: No module named 'gcs'` | **Fixed.** `main.py` now also sets up its own path automatically, and the folder rule in section 1 prevents it from recurring. |
| `WebSocket error: Invalid socket descriptor` | **Fixed.** Every Connect attempt now uses a brand-new connection object instead of reusing a possibly-broken one. |
| "Not connecting to PX4 even with the udp4 bridge at port" | **Fixed.** `px4_bridge.py` is the missing translator — see Option C above. As a backstop, if the GCS is ever pointed at a raw MAVLink/UDP address by mistake, the error message it shows now says so directly and tells you to run `px4_bridge.py`, instead of a generic network error. |

## 6. What's been fixed (changelog)

Everything below has already been fixed in this version of the code.

**Startup / packaging**
- Fixed `ModuleNotFoundError: No module named 'gcs'` — caused by `main.py`
  living inside the `gcs` package instead of next to it. `main.py` now also
  sets up its own file path automatically, so it works reliably no matter
  how it's launched.

**Connecting to a drone**
- Fixed a `WebSocket error: Invalid socket descriptor` crash — the app was
  re-using the same network connection object across attempts, which Qt
  doesn't handle well after a failed attempt. Every connection attempt now
  starts with a completely fresh one.
- Typing in a broken address (missing `ws://`, etc.) now shows a clear,
  specific error immediately, instead of a confusing generic failure.
- Added `px4_bridge.py` — a new script that translates a real drone/PX4
  simulation's data into the format the GCS understands. Without it, the
  GCS had no way to talk to an actual drone at all.
- If the GCS is ever pointed at a raw MAVLink/UDP address by mistake, the
  error it shows now explicitly says that won't work and tells you to run
  `px4_bridge.py` instead — this is the exact mix-up that caused "not
  connecting to PX4 even with the udp4 bridge."
- The connection bar no longer spams repeated "connection failed" messages
  when one failed attempt produces several error events internally.
- Manually clicking Disconnect no longer produces a confusing *second*,
  contradictory log line right after the first one.

**Stability — the app could freeze or crash on bad data**
- The map-drawing code could crash the *entire app* if a drone/bridge ever
  sent an unexpected or badly-typed value (e.g. text where a number was
  expected). It's now wrapped so a bad frame is safely skipped and logged
  instead of taking the whole window down.
- The A1-style grid labels on the map (`"D1"`, `"C4"`, etc.) would crash if
  a coordinate ever arrived as a decimal number instead of a whole number
  (very possible over JSON) — now handled correctly either way. Verified
  directly: the old version raises an error on a decimal coordinate, the
  fixed version doesn't.
- The on-screen clock (elapsed mission time) could get stuck or crash if a
  drone ever sent a non-numeric time value — it's now validated before
  being stored.
- Drone position *and heading* updates now check that incoming values are
  actually numbers before using them, so one bad reading can't silently
  corrupt the drone's position or rotation for every frame afterward.
- Found along the way: if a telemetry update ever didn't include a heading
  value, the drone's on-map arrow used to snap back to pointing due "east"
  even if the drone hadn't actually turned. It now just keeps pointing the
  way it last knew, which is what should have happened all along.
- A bad map cell or room (bad coordinates, or a room with no ID) used to
  get stuck in memory permanently, quietly breaking the on-screen grid
  label forever. Bad entries are now skipped individually instead of
  corrupting the whole map.
- Messages missing required fields (like a survivor with no coordinates)
  are now rejected up front instead of being stored half-complete and
  causing problems later.
- `px4_bridge.py`'s connection to the drone now automatically retries if it
  drops or fails, instead of silently dying and never recovering.

**Display bugs**
- The telemetry log could render broken or garbled text if a message
  happened to contain characters like `&` or `<` (for example, inside a
  URL). Log text is now always displayed exactly as received.
- A few on-screen labels that display live data from the drone/bridge
  (camera tag, survivor grid-box badge, mission phase) had the same
  potential issue — they now always show the raw text as-is.

---

## 7. Message format (for reference)

If you're writing your own bridge (instead of using `px4_bridge.py`), it
needs to send JSON messages that look like this over the WebSocket:

```jsonc
{"type":"telemetry","data":{
    "x":3.4,"y":1.2,"heading_deg":87,"estimated":false,
    "battery_pct":76,"rssi_pct":88}}

{"type":"map_update","data":{
    "cells":[{"x":3,"y":1,"kind":"corridor"}],
    "cell_size_m":1.0,
    "rooms":[{"id":"R1","x":6,"y":2,"label":"ROOM 1"}]}}

{"type":"survivor","data":{
    "id":1,"grid_box":"C4","x":6.2,"y":3.1,"confidence":0.91,"t":142}}

{"type":"waypoint","data":{
    "role":"entry","x":1.0,"y":0.4,"t":30}}

{"type":"object","data":{
    "id":1,"kind":"obj_crate","x":4.1,"y":2.6,"t":44}}

{"type":"camera_frame","data":{
    "jpeg":"<base64 jpeg>","grid_box":"C4","room":"ROOM 2"}}

{"type":"mission_status","data":{
    "phase":"SEARCHING","coverage_pct":42,"elapsed_s":118}}
```

`x`/`y` are metres in the drone's own local frame — not GPS coordinates.
