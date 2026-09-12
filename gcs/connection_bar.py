"""
Header connection bar.

Rewritten around a single source of truth for the bridge link's state
(_link_state: "offline" / "connecting" / "live") plus a separate
_sim_running flag, both funnelled through one _refresh() call. This is
what makes "Simulate only works when there's no connection" a hard
guarantee rather than something several call sites have to remember to
enforce individually: the button's enabled state is *computed* from
_link_state on every refresh, not toggled by hand.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from . import theme

OFFLINE = "offline"
CONNECTING = "connecting"
LIVE = "live"


class ConnectionBar(QWidget):
    connect_clicked = Signal(str)
    disconnect_clicked = Signal()   # also used to cancel a pending connection attempt
    simulate_clicked = Signal()
    new_mission_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{theme.BG_1}; border-bottom:1px solid {theme.LINE_0};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        brand = QLabel(
            "GCS&nbsp;&nbsp;<span style='color:%s; font-size:10.5px; letter-spacing:1.5px;'>"
            "NIDAR &middot; AIRMOUSE &middot; GROUND CONTROL STATION</span>" % theme.GREY_MID
        )
        brand.setTextFormat(Qt.TextFormat.RichText)
        brand.setStyleSheet(
            f"color:{theme.GREY_HI}; font-family:{theme.DISPLAY}; font-size:21px; font-weight:800; letter-spacing:1px;"
        )
        layout.addWidget(brand)
        layout.addStretch()

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(12, 12)
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("OFFLINE")
        layout.addWidget(self.status_label)

        self.url_edit = QLineEdit("ws://192.168.4.1:8765")
        self.url_edit.setFixedWidth(230)
        self.url_edit.setToolTip(
            "WebSocket address of the PX4 companion bridge (the drone's onboard computer).\n"
            "Only editable while offline."
        )
        self.url_edit.setStyleSheet(
            f"QLineEdit {{ background:{theme.BG_2}; border:1.5px solid {theme.LINE_1}; color:{theme.GREY_HI}; "
            f"font-family:{theme.MONO}; font-size:12px; padding:7px 10px; border-radius:4px; }}"
            f"QLineEdit:focus {{ border-color:{theme.WINDOW_LINE}; }}"
            f"QLineEdit:disabled {{ color:{theme.GREY_DIM}; background:{theme.BG_1}; }}"
        )
        layout.addWidget(self.url_edit)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setToolTip("Connect to the PX4 companion bridge at the address on the left.")
        self.connect_btn.setStyleSheet(self._btn_style())
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self.connect_btn)

        self.simulate_btn = QPushButton("Simulate")
        self.simulate_btn.setStyleSheet(self._btn_style())
        self.simulate_btn.clicked.connect(self.simulate_clicked.emit)
        layout.addWidget(self.simulate_btn)

        self.new_mission_btn = QPushButton("New Mission")
        self.new_mission_btn.setToolTip(
            "Wipe the map/trail/detections and re-arm for a fresh local coordinate frame."
        )
        self.new_mission_btn.setStyleSheet(self._btn_style())
        self.new_mission_btn.clicked.connect(self.new_mission_clicked.emit)
        layout.addWidget(self.new_mission_btn)

        self._link_state = OFFLINE
        self._sim_running = False
        self._refresh()

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:{theme.BG_2}; border:1.5px solid {theme.LINE_1}; color:{theme.GREY_HI};
                font-family:{theme.DISPLAY}; font-size:12.5px; font-weight:600; letter-spacing:0.5px;
                padding:9px 18px; border-radius:4px;
            }}
            QPushButton:hover:!disabled {{ background:{theme.BG_3}; border-color:{theme.WINDOW_LINE}; }}
            QPushButton:pressed:!disabled {{ background:{theme.LINE_0}; }}
            QPushButton:disabled {{
                background:{theme.BG_1}; color:{theme.GREY_DIM}; border-color:{theme.LINE_0};
            }}
        """

    def _on_connect_clicked(self):
        if self._link_state in (CONNECTING, LIVE):
            self.disconnect_clicked.emit()
        else:
            self.connect_clicked.emit(self.url_edit.text().strip())

    # ---------------- public API ----------------
    def set_link_state(self, state: str) -> None:
        assert state in (OFFLINE, CONNECTING, LIVE)
        self._link_state = state
        self._refresh()

    def set_sim_running(self, running: bool) -> None:
        self._sim_running = running
        self._refresh()

    def is_link_open(self) -> bool:
        return self._link_state == LIVE

    def is_active(self) -> bool:
        """True whenever data should be flowing — live bridge link OR
        local simulation running. Used to drive the elapsed-time clock."""
        return self._link_state == LIVE or self._sim_running

    # ---------------- single-source-of-truth redraw ----------------
    def _refresh(self) -> None:
        connecting = self._link_state == CONNECTING
        live = self._link_state == LIVE
        simulating = self._sim_running and self._link_state == OFFLINE

        if connecting:
            dot_color, text, text_color = theme.CONNECTING_ACCENT, "CONNECTING\u2026", theme.CONNECTING_ACCENT
        elif live:
            dot_color, text, text_color = theme.LIVE_ACCENT, "LIVE", theme.LIVE_ACCENT
        elif simulating:
            dot_color, text, text_color = theme.SIM_ACCENT, "SIMULATED", theme.SIM_ACCENT
        else:
            dot_color, text, text_color = "transparent", "OFFLINE", theme.GREY_MID
        border = dot_color if dot_color != "transparent" else theme.GREY_DIM
        self.status_dot.setStyleSheet(f"background:{dot_color}; border:1.5px solid {border}; border-radius:6px;")
        self.status_dot.setToolTip(
            "Bench-testing with simulated data \u2014 no drone connected" if simulating
            else {"offline": "No drone link", "connecting": "Connecting to the bridge\u2026",
                  "live": "Live drone link"}[self._link_state]
        )
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color:{text_color}; font-family:{theme.DISPLAY}; font-size:12px; "
            f"letter-spacing:0.5px; min-width:92px; font-weight:700;"
        )

        if connecting:
            self.connect_btn.setText("Cancel")
        elif self._link_state == LIVE:
            self.connect_btn.setText("Disconnect")
        else:
            self.connect_btn.setText("Connect")
        self.url_edit.setEnabled(self._link_state == OFFLINE)

        # THE rule: Simulate is only ever enabled while the bridge link
        # is fully offline — computed here, every refresh, from the one
        # _link_state field, so it can't drift out of sync.
        sim_locked = self._link_state != OFFLINE
        self.simulate_btn.setEnabled(not sim_locked)
        self.simulate_btn.setToolTip(
            "Disabled while a drone link is connecting or connected \u2014 "
            "simulated data is never mixed with real telemetry."
            if sim_locked else
            "Feed simulated data for bench testing without a drone link."
        )
        self.simulate_btn.setText("Stop Sim" if self._sim_running else "Simulate")
