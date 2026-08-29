# NIDAR AirMouse — Ground Control Station (GCS)

A single-file, browser-based Ground Control Station for the NIDAR AirMouse
indoor search-and-rescue drone. It shows a live 2D map, live camera feed,
mission status, and tagged survivors, all built up in real time from
whatever the drone reports over the field Wi‑Fi link — nothing is
preloaded or guessed.

File: `nidar_gcs.html` — pure HTML/CSS/JS, no build step, no server.

### What this satisfies (Track 1 mission brief)

Built against *"Track 1 — NIDAR AirMouse Autonomous GPS-Denied Indoor
Search, Mapping & Survivor Localisation Challenge."* The brief's GCS
requirements, and where each is met:

| Brief requirement | Where it's met |
|---|---|
| Continuously display a 2D map of the explored area while flying | §2.2 / §2.2b — map panel |
| Detect up to 6 survivors, ID their grid coordinate/box | §2.3 — Detected Survivors sidebar, `(N/6)` counter |
| Tag each survivor's location with a marker on the map | §2.3 — map markers |
| Live camera feed throughout the mission | §2.7 — camera panel |
| Enter/exit via designated entry & exit points | §2.4 — waypoint markers |
| GPS-denied indoor operation | §3 — local coordinate frame, no GPS assumption anywhere |

The brief doesn't require semantic wall/door/window/room classification
on the map — just an explored-area 2D map — which is why §2.2b exists:
a lower-effort path straight from Nav2/`slam_toolbox` output with no
custom classifier needed.

---

## 1. How to set it up

1. Copy `nidar_gcs.html` onto the laptop that will act as GCS.
2. Open it in any modern browser (Chrome/Edge/Firefox). Double-clicking
   the file works — there's no dev server or bundler involved.
3. **One-time internet dependency:** the page pulls two Google Fonts
   (`Big Shoulders Stencil`, `IBM Plex Mono`) from `fonts.googleapis.com`
   the first time it loads. After the browser has cached them, it will
   render fine with no internet at all — everything else runs locally
   and talks only to the drone over the closed field network.
4. Get the GCS laptop onto the **same local Wi‑Fi / ad-hoc network** as
   the drone/companion computer. There is no cloud relay — it's a direct
   WebSocket connection over LAN.
5. In the top bar, set the **WS URL** field to the drone's WebSocket
   address (default placeholder: `ws://192.168.4.1:8765` — change this
   to match your companion computer's actual IP/port) and click
   **Connect**.
6. Don't have a drone up yet? Click **Simulate** instead — it feeds
   itself fake telemetry/map/survivor data over the same code path, so
   you can bench-test the whole display with zero hardware. Simulate is
   only available while **disconnected** — see §5.

No installation, no npm, no Python server. Just the HTML file and a browser.

---

## 2. How data comes in — the protocol

The GCS expects a stream of **JSON text messages over a WebSocket**,
each shaped like:

```json
{ "type": "<message-type>", "data": { ... } }
```

The drone/companion computer is the WebSocket **server**; the GCS is the
**client** that connects to it. Every message is handled the instant it
arrives — there's no batching or polling.

> ⚠️ This schema is a **placeholder contract** (see the comment block at
> the top of the `<script>` section). Adjust the drone-side sender to
> match this, or tell me the real format and I'll update the GCS parser
> to match it instead.

### 2.1 `telemetry` — drone position/status (send frequently, e.g. every 100–400ms)

```json
{ "type": "telemetry", "data": {
  "x": 3.4, "y": 1.2,
  "heading_deg": 87,
  "estimated": false,
  "battery_pct": 76,
  "rssi_pct": 88,
  "phase": "SEARCHING"
} }
```

| field | meaning |
|---|---|
| `x`, `y` | Drone position in the drone's own **local frame**, meters. **Not GPS** — see §3. |
| `heading_deg` | Compass-style heading, degrees, used to rotate the drone marker. |
| `estimated` | `true` if this is a VIO/SLAM *estimate* rather than a confident fix — draws the drone marker hollow/dashed instead of solid. |
| `battery_pct` | Optional. Shown in the sidebar. |
| `rssi_pct` | Optional. Shown as link quality in the sidebar. |
| `phase` | Optional. Also settable via `mission_status` — see below. |

The **very first** `telemetry` message received after a (re)connect is
what "acquires fix" — nothing is drawn at a fake `(0,0)` before that.

### 2.2 `map_update` — newly explored map cells

```json
{ "type": "map_update", "data": {
  "cell_size_m": 1.0,
  "cells": [
    {"x":3,"y":1,"kind":"corridor"},
    {"x":4,"y":1,"kind":"wall"},
    {"x":5,"y":1,"kind":"door"},
    {"x":6,"y":1,"kind":"window"}
  ],
  "rooms": [ {"id":"R1","x":6,"y":2,"label":"ROOM 1"} ]
} }
```

- Send this **incrementally** — only the newly-seen cells, not the whole
  map each time. The GCS merges cells into its running map (keyed by
  `x,y`); it never clears them itself except on **New Mission**.
- `kind` must be one of: `wall`, `door`, `window`, `corridor`, `room`,
  `floor` (aliases: `free`). Anything else falls back to the "unmapped"
  color.
- `cell_size_m` is optional per-message; send it once cells start
  coming in (or every time, harmless either way) — it's just used to
  label the grid legend.
- `rooms` is optional — labels drawn at a cell's center.

### 2.2b `occupancy_grid` — alternative to `map_update`, for Nav2/SLAM pipelines

If your mapping stack is **Nav2 / `slam_toolbox`**, you don't need to
write a wall/door/window/room classifier at all — the mission brief
only requires an explored/unexplored 2D map with survivor markers on
it, not semantic room labeling. Send this instead of `map_update` and
a thin ROS2 bridge node can forward `nav_msgs/OccupancyGrid`
(`/map` topic) almost verbatim:

```json
{ "type": "occupancy_grid", "data": {
  "width": 40, "height": 40, "resolution": 0.2,
  "origin": { "x": -4.0, "y": -4.0 },
  "data": [-1, -1, 0, 0, 100, 0, "... width*height values, row-major ..."]
} }
```

| field | meaning |
|---|---|
| `width`, `height` | Grid dimensions, in cells. |
| `resolution` | Meters per cell (matches `nav_msgs/OccupancyGrid.info.resolution`). |
| `origin.x`, `origin.y` | World position (drone's local frame, meters) of grid cell `(0,0)`. |
| `data` | Row-major array, length `width*height`. Each value: `-1` = unknown, `0–100` = occupancy probability. |

The GCS converts this itself: cells with value **≥ 65 become `wall`**,
everything else **becomes `floor`**, and `-1` (unknown) cells are
simply **left unmapped** — same visual result as never reporting that
cell at all. You can still send `map_update` messages alongside this
for anything with real semantic meaning you *do* want to show (e.g. a
door/window your vision pipeline separately detected, or `rooms`
labels) — both message types write into the same underlying map, so
they layer together without conflict.

This is deliberately the **lower-effort integration path**: point a
bridge node at `/map`, reshape the message, and you have a live map in
the GCS with no custom classification logic to write or debug.

### 2.3 `survivor` — a detected survivor

```json
{ "type": "survivor", "data": {
  "id": 1, "grid_box": "C4", "x": 6.2, "y": 3.1,
  "confidence": 0.91, "t": 142
} }
```

- `id` should be **stable** per survivor (re-sending the same `id` with
  updated `confidence`/position just updates that entry, doesn't
  duplicate it).
- `grid_box` is a human-readable label (e.g. from `gridLabel()` — see
  §4) shown in the sidebar list and on the map.
- `confidence` is 0–1, rendered as a percentage bar.
- There is **no manual/post-flight tagging** in this GCS by design —
  every survivor marker must come from the drone live.
- The mission brief caps survivors at **6** ("locate up to 6
  survivors"). The sidebar counter reflects this directly as `(N/6)`
  and switches to an underlined "complete" state once all 6 have been
  tagged — nothing stops you from sending more than 6 `survivor`
  messages, but only 6 is what the mission expects to find.

### 2.4 `waypoint` — the entry or exit marker, once physically seen

```json
{ "type": "waypoint", "data": { "role": "entry", "x": 1.0, "y": 0.4, "t": 30 } }
```

- `role` is `"entry"` or `"exit"` — exactly one of each per mission.
  These only appear on the map once the drone has actually seen the
  physical marker (matches `MAT_ENTRY`/`MAT_EXIT` in
  `floorplan_generator.py`) — never assumed from a blueprint.

### 2.5 `object` — logged obstacle/clutter

```json
{ "type": "object", "data": {
  "id": 1, "kind": "obj_crate", "x": 4.1, "y": 2.6, "t": 44
} }
```

- `kind` is one of `obj_crate`, `obj_rubble`, `obj_barrel`.
- `id` should be stable per physical object for the same reason as
  survivors.

### 2.6 `mission_status` — phase / coverage / elapsed time

```json
{ "type": "mission_status", "data": {
  "phase": "SEARCHING", "coverage_pct": 42.5, "elapsed_s": 88
} }
```

- Send this periodically (e.g. once a second). All fields optional —
  only the ones present are updated.
- `elapsed_s` drives the on-screen mission clock, which keeps
  ticking locally between messages by extrapolating from the last
  value received (falls back to GCS wall-clock time if never sent).

### 2.7 `camera_frame` — live camera feed

```json
{ "type": "camera_frame", "data": {
  "jpeg": "<base64-encoded JPEG>",
  "grid_box": "C4",
  "room": "ROOM 2"
} }
```

- `data` can also just be a **bare base64 JPEG string** instead of an
  object, for a simpler sender — `grid_box`/`room` are optional extras
  that get shown as a caption tag under the video.
- Frames are shown as they arrive — there's no buffering/frame-rate
  logic, so send at whatever cadence your link can sustain (JPEG over a
  WebSocket text frame is not bandwidth-cheap — keep frames small).

### 2.8 Unknown message types

Anything with a `type` not in the list above is logged as
`Unknown message type: ...` in the telemetry log and otherwise ignored
— it won't crash the GCS.

---

## 3. Important concept: there is no GPS and no known map

The arena is fully enclosed and **GPS-denied**. The drone's onboard
estimator (VIO/SLAM) invents its own local `(x, y)` coordinate frame
anchored wherever it happened to power on — every coordinate it ever
reports is relative to **that** origin, never to the building's real
footprint. Practical implications baked into the GCS:

- Nothing is drawn — not even at `(0,0)` — until the **first**
  `telemetry` message actually arrives (`hasFix`).
- The map is built up **live**, purely from cells/objects/survivors the
  drone has personally flown past and reported. There's no
  preloaded blueprint to fall back on.
- A fresh connection = a fresh drone boot = a fresh, unrelated local
  origin. See §5, **New Mission**.

---

## 4. What's on screen

| Area | Shows |
|---|---|
| **Map panel** (left) | Live 2D map: walls/doors/windows/corridors/rooms, drone position + heading + breadcrumb trail, entry/exit markers, obstacles, survivor markers with grid-box labels. Pan by dragging, zoom with scroll wheel or the `+`/`−`/`⊙` (recenter) buttons. |
| **Camera panel** (middle) | Live camera feed (grayscale-filtered), captioned with grid box / room / timestamp if provided. Shows "NO SIGNAL" until the first frame arrives. |
| **Mission Status** (sidebar) | Phase, elapsed time, drone position, heading, battery, link quality, and a search-coverage progress bar. |
| **Detected Survivors** (sidebar) | Running list of tagged survivors with grid box, position, and confidence bar — sorted by detection time. Header shows a live `(N/6)` count against the mission brief's cap of 6 survivors. |
| **Telemetry Log** (footer) | Timestamped human-readable log of every significant event (fix acquired, survivor tagged, waypoint sighted, connect/disconnect, errors). Capped at the last 300 lines. |

Grid coordinate labels (e.g. `A0`, `B4`) appear on individual cells once
you're zoomed in enough — same `gridLabel()` scheme you'd use for
`grid_box` values in `survivor` messages.

---

## 5. Controls

| Control | Behavior |
|---|---|
| **Connect / Disconnect** | Opens (or closes) a WebSocket to the URL in the address field. Automatically stops **Simulate** first if it was running. |
| **Simulate** | Bench-tests the whole GCS with synthetic data — no drone needed. **Greyed out and unclickable whenever a real drone link is connected** — simulated data is never mixed with real telemetry. Re-enables automatically as soon as you disconnect. Click again ("Stop Sim") to stop. |
| **New Mission** | Wipes the map, trail, survivors, objects, and waypoints, and re-arms for a fresh local coordinate frame — use this **between flights**, since a new drone boot means an unrelated origin. If Simulate is running, this also restarts the simulated flight from scratch rather than leaving it flying over an already-cleared map. |
| **Map `+` / `−`** | Zoom in/out (bounded, so you can't zoom into nothing or out to nothing). |
| **Map `⊙` (recenter)** | Re-enables auto-follow (map re-centers on the drone) and jumps to its current position. Dragging or scrolling the map disables auto-follow until you hit recenter again. |

Connection status is shown top-left as a pulsing dot + `LIVE`/`OFFLINE`
label.

---

## 6. Design constraints worth knowing about

- **Strictly grayscale UI** (grey/black/off-white only) — intentional,
  not a styling gap. Color is reserved for meaningful signal: entry
  (green), exit (red), door/window accents, and obstacle-kind tags.
- **No manual correction or post-flight tagging** anywhere in the
  interface — every marker on the map is only ever placed from a live
  drone report, by design, to match the mission rules.
- Single HTML file, zero dependencies beyond the two Google Fonts —
  meant to be trivially copyable to any GCS laptop without a setup step.

---

## 7. Known-fixed issues (for context, not action items)

A few bugs were fixed in this build and are worth knowing about if you
touch the code:

- **Connect vs. Simulate used to fight over shared state** — clicking
  Connect while a simulation was running used to silently kill the sim
  and report "disconnected" instead of opening a real link. Fixed by
  having each button check its own actual state (live socket vs. sim
  timer) instead of one shared flag.
- **Simulate is now hard-locked out while a real drone is connected** —
  earlier it was possible to click Simulate mid-flight and have it
  silently close the real connection and start feeding fake data. That
  auto-switch has been removed entirely: the **Simulate button is
  disabled (greyed out) for the whole time a live WebSocket link is
  open**, so simulated and real data can never mix. It re-enables the
  moment you disconnect.
- **A dropped WebSocket left a dangling reference** — after the fix
  above, a connection that closed on its own (network drop, server-side
  close) needed to null out its reference, or the next Connect click
  would misfire as a disconnect instead of reconnecting. Fixed.
- **New Mission during an active simulation didn't fully reset it** —
  the simulator's internal progress (position, heading, which cells
  it had already "seeded") lived outside the app's shared state, so
  clearing the map wouldn't let the sim re-populate cells it had
  already visited before the reset. Fixed by moving that progress into
  the shared state object so New Mission resets it too.

---

## 8. Quick start checklist

- [ ] Open `nidar_gcs.html` in a browser (once, with internet, to
      cache the fonts).
- [ ] Get GCS laptop on the same local Wi‑Fi/ad-hoc network as the drone.
- [ ] Set the WS URL to the companion computer's real address.
- [ ] Click **Connect** (or **Simulate** to bench-test first).
- [ ] Click **New Mission** before every physical flight to reset the
      coordinate frame.
