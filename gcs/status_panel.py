from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from . import theme


class StatusPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ border-bottom: 1px solid {theme.LINE_0}; background:{theme.BG_1}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        title = QLabel("MISSION STATUS")
        title.setStyleSheet(f"color:{theme.GREY_HI}; font-family:{theme.DISPLAY}; font-size:13px; font-weight:700; letter-spacing:0.5px;")
        outer.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        def add_stat(row, col, key, attr_name):
            k = QLabel(key)
            k.setStyleSheet(f"color:{theme.GREY_MID}; font-family:{theme.MONO}; font-size:10px; letter-spacing:1px;")
            k.setToolTip(key)
            v = QLabel("\u2014")
            v.setStyleSheet(f"color:{theme.WHITE}; font-family:{theme.MONO}; font-size:15px; font-weight:600;")
            box = QVBoxLayout()
            box.setSpacing(2)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(k)
            box.addWidget(v)
            wrap = QWidget()
            wrap.setLayout(box)
            grid.addWidget(wrap, row, col)
            setattr(self, attr_name, v)

        add_stat(0, 0, "PHASE", "phase_val")
        add_stat(0, 1, "ELAPSED", "elapsed_val")
        add_stat(1, 0, "DRONE POS (LOCAL X,Y m)", "pos_val")
        add_stat(1, 1, "HEADING", "heading_val")
        add_stat(2, 0, "BATTERY", "battery_val")
        add_stat(2, 1, "LINK", "link_val")
        outer.addLayout(grid)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background:{theme.BG_2}; border:1px solid {theme.LINE_0}; border-radius:4px; }}
            QProgressBar::chunk {{ background:{theme.LIVE_ACCENT}; border-radius:4px; }}
        """)
        outer.addWidget(self.progress)

        prog_row = QGridLayout()
        left = QLabel("SEARCH COVERAGE")
        left.setStyleSheet(f"color:{theme.GREY_MID}; font-family:{theme.MONO}; font-size:10px;")
        self.progress_pct = QLabel("0%")
        self.progress_pct.setStyleSheet(f"color:{theme.GREY_HI}; font-family:{theme.MONO}; font-size:10px; font-weight:600;")
        prog_row.addWidget(left, 0, 0, Qt.AlignmentFlag.AlignLeft)
        prog_row.addWidget(self.progress_pct, 0, 1, Qt.AlignmentFlag.AlignRight)
        outer.addLayout(prog_row)

        self.reset()

    def update_telemetry(self, d: dict) -> None:
        if "x" in d and "y" in d:
            self.pos_val.setText(f"{d['x']:.1f}, {d['y']:.1f}")
        if "heading_deg" in d:
            self.heading_val.setText(f"{round(d.get('heading_deg') or 0)}\u00b0")
        if d.get("battery_pct") is not None:
            self.battery_val.setText(f"{round(d['battery_pct'])}%")
        if d.get("rssi_pct") is not None:
            self.link_val.setText(f"{round(d['rssi_pct'])}% RSSI")
        if d.get("phase"):
            self.phase_val.setText(d["phase"])

    def update_mission_status(self, d: dict) -> None:
        if d.get("phase"):
            self.phase_val.setText(d["phase"])
        if d.get("coverage_pct") is not None:
            pct = max(0, min(100, d["coverage_pct"]))
            self.progress.setValue(int(pct))
            self.progress_pct.setText(f"{round(pct)}%")

    def set_elapsed_text(self, text: str) -> None:
        self.elapsed_val.setText(text)

    def reset(self) -> None:
        self.phase_val.setText("STANDBY")
        self.elapsed_val.setText("00:00")
        self.pos_val.setText("NO FIX")
        self.heading_val.setText("\u2014\u00b0")
        self.battery_val.setText("\u2014%")
        self.link_val.setText("\u2014")
        self.progress.setValue(0)
        self.progress_pct.setText("0%")
