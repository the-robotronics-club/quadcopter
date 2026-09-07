# AEROXMD Website

Project site for the **AEROXMD Autonomous Quadcopter Framework** (Robotronics Club, IIT Mandi).
Static, zero-backend, mission-control styled: live GitHub data, auto-syncing gallery,
environment telemetry, and a debug terminal — all in the browser, no tokens, no build step beyond one Python script.

> **Sources → Build → Deploy**
> `website.html` + `css/styles.css` + `js/main.js` → (`python3 build.py`) → `index.html` → GitHub Pages (serves `./website/`)

> **Golden rule: never edit `index.html` directly.** It is generated output.
> Edit the three sources, then re-run `build.py`.

## Structure

```
website/
├── website.html          ← SOURCE OF TRUTH (edit me)
├── build.py              ← compiler: inlines CSS+JS into index.html
├── index.html            ← GENERATED deploy artifact (do NOT edit)
├── README.md             ← this file
├── css/styles.css        ← SOURCE (edit me): theme + live-systems layer
├── js/main.js            ← SOURCE (edit me): static UX + live modules
└── assets/gallery/       ← DROP PHOTOS HERE → auto-discovered wall after push
```

## Quick Start

```bash
cd website

# Preview editable sources
python3 -m http.server 8080
# → http://localhost:8080/website.html   (edit + preview this)
# → http://localhost:8080/index.html     (built output)

# After any edit, rebuild
python3 build.py
# → OK: website.html + css/styles.css + js/main.js -> index.html (N bytes)

# Push → gallery + missions go live
git add . && git commit -m "website" && git push
```

Must use `http://`, not `file://` (ES `fetch` and inline-module assumptions break on `file://`).

## Typography

Deliberate aerospace type system (Google Fonts, external `<link>` — never inlined):

| Role | Face | Usage |
|---|---|---|
| Display | **Oxanium** 700/600 | H1 hero, H2 section heads (uppercase, compact) |
| Technical headings | **Rajdhani** 600/700 | H3/H4 card titles, nav, buttons (uppercase) |
| Body | **Inter** 400/500/600 | Paragraphs, docs, supporting text |
| Telemetry | **JetBrains Mono** 400–600 | Strip, stats meta, readouts, code, `ALT/VEL/GPS/BAT` values |
| Micro labels | **IBM Plex Mono** 500 | Eyebrows (`AERIAL ROBOTICS / …`), corner coords, `[01]`-style markers |

Single technical accent: aviation amber `#ffa02e` (deep orange `#ff6b1a` secondary)
on near-black charcoal. Flat engineering controls (3px radius, no gradient fills);
thin borders, restrained motion, no neon excess.

## Sections

| # | `id` | Content | Rendered by |
|---|---|---|---|
| — | `#home` | Hero, particle canvas, drone SVG, ticker | Static + `Particles` + `Telemetry` |
| 01–04 | `#about #features #architecture #specs` | Static docs | Static HTML |
| 05 | `#missions` | Filter toolbar + mission card grid + SHOW MORE + dossier modal | `Missions` (fed by `GitHub`) |
| 06 | `#gallery` | Masonry photo wall + fullscreen `#viewer` | `Gallery` (Contents API) |
| 07 | `#live` | Stat tiles, language bars, last transmission, recent repos, contribution chart | `GitHub` |
| 08 | `#telemetry` | Real device-data panel + opt-in motion + event log | `EnvTelemetry` |
| 09 | `#stack` | Interactive skill → mission graph | `SkillGraph` |
| 10–11 | `#get-started #sponsors` | Static docs | Static HTML |
| — | `#contact` | Links + `mailto:` transmission form + copy-handle | `initContact` |

Overlays: `#topstrip` (CPU/MEM/FPS/NET/ROS/GH), `#progress` (scroll bar),
`#boot` (init sequence), `#terminal` (`` ` `` debug console), `#toast`,
`#mission-modal`, `#viewer`.

## How Live GitHub Sync Works

No server, no token. The visitor's browser calls `https://api.github.com` directly
(org-adapted endpoints — an org has no `/users/{user}/events/public`, so the
latest commit stands in for "last transmission"):

```
GET /orgs/the-robotronics-club
GET /orgs/the-robotronics-club/repos?per_page=100&sort=updated
GET /repos/the-robotronics-club/quadcopter/commits?per_page=5
GET /repos/the-robotronics-club/<repo>/topics   (× up to 6 featured repos)
```

* **Cache:** `localStorage` keys `aeroxmd_gh_v1` / `aeroxmd_gallery_v1`, 15-min TTL
  (`cacheDuration`). Fresh cache → zero network calls, painted with a `CACHED …` label.
* **Resync:** `Force resync` button, terminal `github resync`, or `GitHub.refresh(true)`.
* **Fallback chain:** `LIVE ✓` → cached (`CACHED … · RATE_LIMITED`) → curated
  (`OFFLINE — CURATED FALLBACK` from `FALLBACK_REPOS`). The page never renders empty.
* **Status:** header `GH ●/○` dot, `#gh-sync-state`, `#gh-cache-note`
  (`unauthenticated, 60 req/hr shared`).
* **Chart:** `<img src="https://ghchart.rshah.org/the-robotronics-club">` with an
  `onerror` fallback link (org charts are often empty — expected).

## How the Gallery Auto-Syncs

No filenames to register, no JSON to edit:

```bash
cp ~/photos/flight-01.jpg assets/gallery/
python3 build.py
git add assets/gallery/flight-01.jpg index.html
git commit -m "gallery: flight 01" && git push
# → reload the live site → photo appears
```

1. **Listing:** `GET /repos/the-robotronics-club/quadcopter/contents/website/assets/gallery`,
   filtered to `jpg|jpeg|png|webp|avif`, sorted by name.
2. **Localhost note:** local previews show a `LOCAL PREVIEW`-style hint because the wall
   reads GitHub, not your disk — local-only files appear after push.
3. **Viewer:** click opens fullscreen (`#viewer`) with arrows/Esc/swipe; full-res loads on open.
4. **Naming tip:** `flight-01.jpg` renders alt text `flight 01`; avoid `Screenshot from …` names.

## Missions Pipeline

Every repo becomes a mission card via `Missions.enrich()`:

1. **Curated override:** names matching `CURATED` (e.g. `quadcopter`, `vio-ekf`,
   `planner`, `yolov8-edge`, `failsafe-rtl`, `sitl-gazebo`) get hand-written
   dossiers (number, objective, architecture, results). Others get a generated
   number + heuristic domain guess.
2. **Domains:** GitHub topics → domain via `topicsToDomain`
   (`ros2 → autonomy`, `px4 → flight`, `yolo/opencv → vision`, `gazebo → sim`, …).
3. **UX:** domain `<select>` filter, 10-at-a-time paging, click → dossier modal,
   skill-graph click highlights matching missions (`data-tech` match).

## Other Live Systems

* **Top strip (SIMULATED):** CPU/MEM are random-walk flavor; FPS is a real rAF counter;
  clock is real; NET mirrors `navigator.onLine`. Footer + specs page state this explicitly.
* **Environment panel (REAL):** resolution, viewport, DPR, orientation, CPU threads,
  WebGL, network, locale, color scheme, load time + throttled event log. Motion is an
  **opt-in button** (handles iOS `requestPermission`); once live, tilt steers the hero
  particle field (`Particles.ptr`). Nothing leaves the browser.
* **Particles + section FX:** hero canvas (drift + cursor repulsion + link lines,
  DPR ≤ 1.5, 40–160 particles, pauses off-screen) + six `data-fx` canvases
  (`scan/embers/trace/waves/radar/ping`) on one shared rAF loop. Idle under
  `prefers-reduced-motion` or the `Reduce motion` toggle.
* **Terminal:** press `` ` `` — `help status missions mission <name> lab skills
  gallery [sync] github [resync] env telemetry ls open <section> motion boot [replay]
  clear sudo`, plus Konami-code clearance easter egg.
* **Contact:** `data-copy` clipboard handle + `mailto:` form builder (no backend).

## Configuration

Top of `js/main.js` — the only place you need for identity:

```js
const AEROXMD_CONFIG = {
  org: "the-robotronics-club",
  primaryRepo: "quadcopter",       // last-transmission source
  galleryRepo: "quadcopter",       // repo hosting website/assets/gallery
  galleryPath: "website/assets/gallery",
  featuredRepositories: ["quadcopter"],  // pinned first + ◆ FEATURED
  cacheDuration: 900000            // 15 min
};
```

Then update: `CURATED` dossiers, `EXPERIMENTS` (terminal `lab`), `SKILL_TREE` nodes,
`topicsToDomain`, profile links in `website.html`, and the `ghchart` image `src`.

## Build System (`build.py`)

```bash
python3 build.py                    # website.html + css/styles.css + js/main.js -> index.html
python3 build.py [src] [css] [js] [out]   # custom paths
```

Regex-based, stdlib only (`re`, `sys`, `pathlib`): replaces the stylesheet `<link>`
with `<style>…</style>` and the `js/main.js` `<script>` with inline code
(lambda replacements so JS backslashes survive). Refuses to run on missing sources,
literal `</style` / `</script` in payloads, or output == source. Google Fonts links
stay external on purpose. Re-running overwrites only `index.html`.

## Deploy

GitHub Pages deploys `./website/` on push to `main` (see `.github/workflows/deploy.yml`).
Any static host works too — upload `index.html` + `assets/` only.

## Privacy, Limits & Offline

* No trackers, cookies, or backend. Outbound requests only: `api.github.com`,
  `ghchart.rshah.org`, Google Fonts.
* Env-panel values are computed locally, never stored or sent.
* Unauthenticated limit is 60 req/hr/IP; design uses ~4–10 req/load max, then caches.
  Heavy traffic degrades to cached/curated data, never a blank page.
* Offline degrades gracefully with explicit status labels everywhere.

## Troubleshooting

| Symptom | Cause → Fix |
|---|---|
| Gallery says UNREACHABLE / NOT pushed | Folder not pushed or wrong `galleryRepo` — push `assets/gallery/` / set `galleryRepo` |
| Missions show curated only, GH ○ | Offline or rate-limited — `#gh-sync-state` names the reason; live data returns automatically |
| Chart missing | `ghchart` down or empty for orgs — fallback profile link appears; nothing else breaks |
| `file://` blank / no data | Browsers block `fetch` on `file://` — serve via `python3 -m http.server` |
| `build.py` refuses output | Output equals a source, or CSS/JS contains a literal closing tag — rename output / remove the tag string |
| Boot shows every visit | Uncheck "remember this terminal", or clear `aeroxmd_boot_seen` in devtools |
| `localStorage` stale during dev | Terminal `github resync` / `gallery sync`, or clear `aeroxmd_gh_v1` / `aeroxmd_gallery_v1` |

*AEROXMD · Robotronics Club, IIT Mandi · Static build · No trackers ·
Telemetry strip is interface simulation; environment panel is real device data.*
