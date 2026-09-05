"""
The map panel. Everything here is drawn by hand with QPainter (no web
canvas, no browser) directly onto a QWidget, driven purely by
`MissionState` — which itself is populated purely by whatever the PX4
companion bridge has actually reported. Nothing is assumed or
preloaded; see state.py for why.
"""

import math
import time as _time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from . import theme

KIND_FILL = {
    "wall": theme.WALL,
    "door": theme.DOOR,
    "window": theme.WINDOW,
    "corridor": theme.CORRIDOR,
    "room": theme.ROOM,
    "floor": theme.FLOOR,
    "free": theme.FLOOR,
}
KIND_LINE = {
    "wall": theme.WALL_LINE,
    "door": theme.DOOR_LINE,
    "window": theme.WINDOW_LINE,
}
OBJ_COLOR = {
    "obj_crate": theme.OBJ_CRATE,
    "obj_rubble": theme.OBJ_RUBBLE,
    "obj_barrel": theme.OBJ_BARREL,
}

LEGEND_ITEMS = [
    ("WALL", theme.WALL, theme.WALL_LINE),
    ("DOOR", theme.DOOR, theme.DOOR_LINE),
    ("WINDOW", theme.WINDOW, theme.WINDOW_LINE),
    ("CORRIDOR", theme.CORRIDOR, theme.LINE_0),
    ("ROOM", theme.ROOM, theme.LINE_0),
    ("OPEN / FLOOR", theme.FLOOR, theme.LINE_0),
    ("UNMAPPED", theme.UNMAPPED, theme.LINE_0),
    ("ENTRY POINT", theme.ENTRY, theme.ENTRY),
    ("EXIT POINT", theme.EXIT, theme.EXIT),
    ("OBSTACLE", theme.OBJ_CRATE, theme.OBJ_CRATE),
]


def grid_label(cx: int, cy: int) -> str:
    """A1-style label: column letters, row numbers. cx/cy can go negative
    (drone drifts left of / above its own origin), so the column-letter
    math runs on abs(cx) with a sign prefix rather than risking negative
    modulo weirdness."""
    neg = cx < 0
    n = abs(cx)
    col = ""
    while True:
        col = chr(65 + (n % 26)) + col
        n = n // 26 - 1
        if n < 0:
            break
    return f"{'-' if neg else ''}{col}{cy}"


class MapCanvas(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setMinimumSize(240, 240)
        self.setStyleSheet(f"background:{theme.BG_0};")
        self.setMouseTracking(True)
        self._dragging = False
        self._last_pos = None

        # redraw loop, mainly so the survivor pulse ring animates
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self.update)
        self._anim_timer.start(33)

        self.zoom_in_btn = QPushButton("+", self)
        self.zoom_out_btn = QPushButton("\u2212", self)
        self.recenter_btn = QPushButton("\u2299", self)
        self.zoom_in_btn.setToolTip("Zoom in")
        self.zoom_out_btn.setToolTip("Zoom out")
        self.recenter_btn.setToolTip("Recenter on the drone and resume auto-follow")
        for b in (self.zoom_in_btn, self.zoom_out_btn, self.recenter_btn):
            b.setFixedSize(32, 32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(10,11,13,0.92); border:1.5px solid {theme.LINE_1};
                    color:{theme.GREY_HI}; font-family:{theme.MONO}; font-size:15px;
                    border-radius:16px;
                }}
                QPushButton:hover {{ background:{theme.BG_3}; border-color:{theme.WINDOW_LINE}; }}
                QPushButton:pressed {{ background:{theme.LINE_0}; }}
            """)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.recenter_btn.clicked.connect(self.recenter)
        self._layout_buttons()

    # ---------------- layout ----------------
    def resizeEvent(self, event):
        self._layout_buttons()
        super().resizeEvent(event)

    def _layout_buttons(self):
        y = self.height() - 42
        self.zoom_in_btn.move(10, y)
        self.zoom_out_btn.move(48, y)
        self.recenter_btn.move(86, y)

    # ---------------- world <-> screen ----------------
    def world_to_screen(self, x: float, y: float):
        s = self.state.view.scale
        sx = self.width() / 2 + (x - self.state.view.offset_x) * s
        sy = self.height() / 2 + (y - self.state.view.offset_y) * s
        return sx, sy

    def zoom_in(self):
        self.state.view.auto_fit = False
        self.state.view.scale = min(120, self.state.view.scale * 1.2)
        self.update()

    def zoom_out(self):
        self.state.view.auto_fit = False
        self.state.view.scale = max(6, self.state.view.scale / 1.2)
        self.update()

    def recenter(self):
        self.state.view.auto_fit = True
        self.state.view.offset_x = self.state.drone.x
        self.state.view.offset_y = self.state.drone.y
        self.update()

    # ---------------- pan / zoom input ----------------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.state.view.auto_fit = False
            self._last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_pos is not None:
            delta = event.position() - self._last_pos
            self.state.view.offset_x -= delta.x() / self.state.view.scale
            self.state.view.offset_y -= delta.y() / self.state.view.scale
            self._last_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._last_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def wheelEvent(self, event):
        self.state.view.auto_fit = False
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.state.view.scale = max(6, min(120, self.state.view.scale * factor))
        self.update()
        event.accept()

    # ---------------- painting ----------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BG_0))

        s = self.state.view.scale
        font = QFont(theme.MONO_FAMILIES[0])
        font.setStyleHint(QFont.StyleHint.Monospace)

        # -- cells --
        for (cx, cy), kind in self.state.cells.items():
            sx, sy = self.world_to_screen(cx, cy)
            p.fillRect(QRectF(sx, sy, s, s), QColor(KIND_FILL.get(kind, theme.UNMAPPED)))
            pen = QPen(QColor(KIND_LINE.get(kind, theme.LINE_0)))
            pen.setWidthF(1.5 if kind in ("door", "window") else 1.0)
            p.setPen(pen)
            p.drawRect(QRectF(sx + 0.5, sy + 0.5, s - 1, s - 1))

        # -- room labels --
        p.setPen(QColor(theme.GREY_MID))
        for room in self.state.rooms.values():
            sx, sy = self.world_to_screen(room["x"], room["y"])
            font.setPixelSize(max(9, int(s * 0.28)))
            p.setFont(font)
            p.drawText(QRectF(sx, sy, s, s), Qt.AlignmentFlag.AlignCenter,
                       room.get("label", room.get("id", "")))

        # -- per-cell coordinate tags, only once zoomed in enough to read --
        if s > 22:
            p.setPen(QColor(*theme.COORD_LABEL_RGBA))
            for (cx, cy) in self.state.cells.keys():
                sx, sy = self.world_to_screen(cx, cy)
                font.setPixelSize(max(7, int(s * 0.16)))
                p.setFont(font)
                p.drawText(QPointF(sx + 3, sy + 10), grid_label(cx, cy))

        drone = self.state.drone

        # from here on, everything drawn is curved/rotated (trail, obstacles,
        # waypoint diamonds, survivor rings, the drone marker) — antialiasing
        # makes those noticeably cleaner without softening the crisp pixel
        # grid of cell rectangles drawn above.
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # -- drone breadcrumb trail (nothing to show before first fix) --
        if drone.has_fix and len(drone.trail) > 1:
            path = QPainterPath()
            for i, (tx, ty) in enumerate(drone.trail):
                sx, sy = self.world_to_screen(tx, ty)
                sx += s / 2
                sy += s / 2
                path.moveTo(sx, sy) if i == 0 else path.lineTo(sx, sy)
            pen = QPen(QColor(*theme.TRAIL_RGBA))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # -- logged obstacles / clutter --
        for obj in self.state.objects.values():
            sx, sy = self.world_to_screen(obj["x"], obj["y"])
            cxp, cyp = sx + s / 2, sy + s / 2
            r = s * 0.18
            p.setBrush(QBrush(QColor(OBJ_COLOR.get(obj.get("kind"), theme.GREY_DIM))))
            p.setPen(QPen(QColor(theme.GREY_HI), 1))
            p.drawRect(QRectF(cxp - r, cyp - r, r * 2, r * 2))

        # -- entry / exit waypoints (only known once physically sighted) --
        for role, wp in self.state.waypoints.items():
            sx, sy = self.world_to_screen(wp["x"], wp["y"])
            cxp, cyp = sx + s / 2, sy + s / 2
            r = max(7, s * 0.3)
            color = theme.ENTRY if role == "entry" else theme.EXIT
            p.save()
            p.translate(cxp, cyp)
            p.rotate(45)
            p.setBrush(QBrush(QColor(color)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(-r / 2, -r / 2, r, r))
            p.restore()
            p.setPen(QColor(theme.GREY_HI))
            font.setBold(True)
            font.setPixelSize(max(9, int(s * 0.22)))
            p.setFont(font)
            p.drawText(QPointF(cxp + s * 0.4, cyp + s * 0.35), role.upper())
            font.setBold(False)

        # -- survivors: a warm "found!" beacon, drawn from the same
        # palette as the rest of the app (SURVIVOR/SURVIVOR_RING) rather
        # than a stark flash of pure white — that mismatch was the
        # "something changes the theme" report: a colour appearing out
        # of nowhere that didn't belong to the rest of the UI.
        now_ms = _time.time() * 1000
        for sv in self.state.survivors.values():
            sx, sy = self.world_to_screen(sv["x"], sv["y"])
            cxp, cyp = sx + s / 2, sy + s / 2
            pulse = (math.sin(now_ms / 450) + 1) / 2
            alpha = max(0, min(255, int((0.55 - pulse * 0.35) * 255)))
            pen = QPen(QColor(*theme.SURVIVOR_RING_RGBA_BASE, alpha))
            pen.setWidthF(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cxp, cyp), s * 0.35 + pulse * 6, s * 0.35 + pulse * 6)

            p.setBrush(QBrush(QColor(theme.SURVIVOR)))
            p.setPen(QPen(QColor(theme.GREY_HI), 1.5))
            p.drawEllipse(QPointF(cxp, cyp), s * 0.24, s * 0.24)

            p.setPen(QColor(theme.GREY_HI))
            font.setBold(True)
            font.setPixelSize(max(9, int(s * 0.22)))
            p.setFont(font)
            p.drawText(QPointF(cxp + s * 0.4, cyp - s * 0.25),
                       f"#{sv['id']} {sv.get('grid_box', '')}")
            font.setBold(False)

        # -- drone marker: hollow + dashed while position is only estimated --
        if drone.has_fix:
            sx, sy = self.world_to_screen(drone.x, drone.y)
            cxp, cyp = sx + s / 2, sy + s / 2
            size = max(9, s * 0.32)
            p.save()
            p.translate(cxp, cyp)
            p.rotate(drone.heading)
            path = QPainterPath()
            path.moveTo(0, -size)
            path.lineTo(size * 0.62, size * 0.72)
            path.lineTo(-size * 0.62, size * 0.72)
            path.closeSubpath()
            if drone.estimated:
                pen = QPen(QColor(theme.GREY_HI))
                pen.setWidthF(1.5)
                pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(theme.WHITE)))
                p.drawPath(path)
            p.restore()

        self._draw_overlays(p, font)
        p.end()

    def _draw_overlays(self, p: QPainter, font: QFont):
        # viewfinder-style corner brackets
        pen = QPen(QColor(theme.GREY_MID))
        pen.setWidthF(1.5)
        p.setPen(pen)
        L = 16
        w, h = self.width(), self.height()
        for origin, hend, vend in (
            ((8, 8), (8 + L, 8), (8, 8 + L)),
            ((w - 8, 8), (w - 8 - L, 8), (w - 8, 8 + L)),
            ((8, h - 8), (8 + L, h - 8), (8, h - 8 - L)),
            ((w - 8, h - 8), (w - 8 - L, h - 8), (w - 8, h - 8 - L)),
        ):
            p.drawLine(QPointF(*origin), QPointF(*hend))
            p.drawLine(QPointF(*origin), QPointF(*vend))

        # top-left status tag strip — a dark "readability chip" floating
        # over the map, so its text is always CHIP_TEXT (near-white),
        # never the theme's dark "ink" colour, regardless of what's
        # underneath. (Using the ink colour here was actually unreadable
        # — dark text on a near-black chip — a real bug, not just style.)
        font.setPixelSize(11)
        font.setBold(False)
        p.setFont(font)
        tags = [
            f"MAPPED CELLS: {len(self.state.cells)}",
            f"GRID: {self.state.cell_size_m:.1f} m/box",
            "FIX ACQUIRED" if self.state.drone.has_fix else "NO FIX",
            "LOCAL FRAME \u00b7 ORIGIN = TAKEOFF",
        ]
        tx = 10
        for tag in tags:
            tw = p.fontMetrics().horizontalAdvance(tag) + 18
            rect = QRectF(tx, 10, tw, 24)
            p.setBrush(QBrush(QColor(*theme.CHIP_BG_RGBA)))
            p.setPen(QPen(QColor(theme.CHIP_BORDER)))
            p.drawRoundedRect(rect, 6, 6)
            p.setPen(QColor(theme.CHIP_TEXT))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, tag)
            tx += tw + 8

        # legend, bottom-right — sized from the actual text so nothing clips
        row_h = 17
        font.setBold(False)
        font.setPixelSize(10.5)
        p.setFont(font)
        fm = p.fontMetrics()
        swatch_col_w = 26  # swatch + gap before the label starts
        label_w = max(fm.horizontalAdvance(label) for label, _, _ in LEGEND_ITEMS)
        legend_w = swatch_col_w + label_w + 16
        legend_h = len(LEGEND_ITEMS) * row_h + 12
        lx = self.width() - legend_w - 10
        ly = self.height() - legend_h - 46
        p.setBrush(QBrush(QColor(*theme.CHIP_BG_RGBA)))
        p.setPen(QPen(QColor(theme.CHIP_BORDER)))
        p.drawRoundedRect(QRectF(lx, ly, legend_w, legend_h), 8, 8)
        for i, (label, fill, line) in enumerate(LEGEND_ITEMS):
            ry = ly + 6 + i * row_h
            p.setBrush(QBrush(QColor(fill)))
            p.setPen(QPen(QColor(line)))
            p.drawRoundedRect(QRectF(lx + 8, ry + 2, 12, 12), 3, 3)
            p.setPen(QColor(theme.CHIP_TEXT))
            p.drawText(QPointF(lx + swatch_col_w, ry + 12), label)
