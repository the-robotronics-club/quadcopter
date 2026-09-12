"""
"Night ops" theme — a graphite / near-black palette instead of the
previous bright "jolly drone" look. Every widget still pulls its
colours from here, so re-theming the whole app is mostly this one
file.

Contrast rules this palette is built around (read this before adding
a new colour):
  - GREY_HI/WHITE are the "ink" colour and are now LIGHT (near-white),
    since every surface (BG_0..BG_3) is dark. Never pair GREY_HI text
    with a light/bright accent fill (SURVIVOR, DOOR_LINE, etc.) — use
    INK_ON_ACCENT for text that sits on top of a bright accent chip.
  - The map tiles (WALL/FLOOR/CORRIDOR/ROOM/DOOR/WINDOW) are all kept
    on the dark end so that GREY_HI/GREY_MID overlay text and labels
    stay legible on top of any of them. WALL is the lightest tile
    (structure should read as the most solid/opaque thing on the
    map); UNMAPPED matches BG_0 so unexplored space reads as "void".
  - Functional accent colours (door=amber, window=blue, entry=green,
    exit=red, survivor=amber, connecting=amber, live=teal) are kept
    distinct and saturated so status/semantics are never lost just
    because the rest of the UI went monochrome.
"""

# ---- core surfaces (graphite / near-black) ----
BG_0 = "#121316"      # app background — near-black
BG_1 = "#1b1d21"      # panel/card background — dark graphite
BG_2 = "#24262b"      # inputs / recessed surfaces
BG_3 = "#2f323a"      # hover state
LINE_0 = "#34363d"    # faint borders/dividers
LINE_1 = "#494c56"    # stronger borders

# ---- text ----
GREY_DIM = "#7d828d"  # least-emphasis text / captions
GREY_MID = "#a7acb8"  # secondary text, labels
GREY_HI = "#f2f3f5"   # primary "ink" — high-contrast text & solid icons (near-white now)
WHITE = GREY_HI        # kept for name-compatibility: "high emphasis" colour.
                        # Now genuinely near-white, since the app background
                        # is dark — still the most prominent text/marker colour.

# text colour for use ON TOP of a bright/light accent fill (badges, chips)
# where GREY_HI (light) would disappear — e.g. the survivor grid-box badge.
INK_ON_ACCENT = "#15171a"

# ---- connection-status accents ----
LIVE_ACCENT = "#2dd4a7"        # teal-green — "data is flowing" from a real bridge link
SIM_ACCENT = "#3aa0e0"         # blue — bench-test running, deliberately distinct from LIVE
CONNECTING_ACCENT = "#f7931e"  # warm amber — "in progress"
OFFLINE_ACCENT = GREY_DIM

# ---- the "viewfinder" — kept the darkest surface in the app, the
# same way a phone camera preview reads darker than its surrounding
# chrome even in a dark-mode app ----
SCREEN_BG = "#000000"
SCREEN_TEXT = "#eef2f5"
SCREEN_DIM = "#63676f"

# ---- map tiles (all kept dark so overlay text stays legible on any
# of them; ordered lightest-to-darkest: WALL > ROOM \u2248 CORRIDOR > FLOOR > UNMAPPED) ----
WALL = "#565b66"
WALL_LINE = "#2a2c33"
FLOOR = "#26282d"
CORRIDOR = "#2b2f38"
ROOM = "#3a3428"
UNMAPPED = "#121316"
DOOR = "#4a3620"
DOOR_LINE = "#f7931e"
WINDOW = "#1d3244"
WINDOW_LINE = "#3aa0e0"
ENTRY = "#2dd4a7"
EXIT = "#e5484d"
OBJ_CRATE = "#c98a4b"
OBJ_RUBBLE = "#8b8f99"
OBJ_BARREL = "#e0b03a"

# survivors get their own warm "found!" accent instead of a stark white
# flash — see the design note up top. Text drawn ON this fill must use
# INK_ON_ACCENT, not GREY_HI.
SURVIVOR = "#ffb703"
SURVIVOR_RING = "#fb8500"

# translucent overlay colours on the map canvas, as (r, g, b, a) tuples
# since QColor needs explicit alpha for these
TRAIL_RGBA = (242, 243, 245, 80)        # drone breadcrumb trail
COORD_LABEL_RGBA = (167, 172, 184, 150)  # per-cell A1-style coordinate tags
SURVIVOR_RING_RGBA_BASE = (251, 133, 0)  # alpha applied per-frame for the pulse

# map-canvas overlay "chips" (status tag strip / legend / zoom controls):
# these float over every kind of map tile, so they stay a deliberately
# near-black, translucent readability card regardless of what's under
# them — the same trick real map apps use for labels over photo imagery.
CHIP_BG_RGBA = (10, 11, 13, 220)
CHIP_BORDER = "#3aa0e0"
CHIP_TEXT = "#f4f9fc"

# data / telemetry readouts — fixed-width for alignment
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo"]
MONO = "'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', monospace"

# UI chrome (titles, buttons, brand) — a friendlier rounded sans
DISPLAY_FAMILIES = ["Trebuchet MS", "Segoe UI", "Verdana"]
DISPLAY = "'Trebuchet MS', 'Segoe UI', Verdana, sans-serif"
