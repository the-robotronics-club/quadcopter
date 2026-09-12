from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget,
)

from . import theme


class SurvivorItem(QFrame):
    def __init__(self, sv: dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                border:1.5px solid {theme.LINE_1};
                border-left:4px solid {theme.SURVIVOR};
                background:{theme.BG_1};
                border-radius:4px;
            }}
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(13, 11, 13, 11)
        v.setSpacing(6)

        row1 = QHBoxLayout()
        id_lbl = QLabel(f"SURVIVOR #{sv.get('id')}")
        id_lbl.setStyleSheet(f"color:{theme.GREY_HI}; font-family:{theme.DISPLAY}; font-size:13px; font-weight:700;")
        box_lbl = QLabel(str(sv.get("grid_box") or "\u2014"))
        box_lbl.setStyleSheet(
            f"color:{theme.INK_ON_ACCENT}; font-family:{theme.MONO}; font-size:12.5px; font-weight:700; "
            f"background:{theme.SURVIVOR}; padding:1px 8px; border-radius:5px;"
        )
        row1.addWidget(id_lbl)
        row1.addStretch()
        row1.addWidget(box_lbl)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        conf = round((sv.get("confidence") or 0) * 100)
        pos_lbl = QLabel(f"x:{sv.get('x', 0):.1f}  y:{sv.get('y', 0):.1f}")
        pos_lbl.setStyleSheet(f"color:{theme.GREY_MID}; font-family:{theme.MONO}; font-size:11px;")
        conf_lbl = QLabel(f"{conf}% confidence")
        conf_lbl.setStyleSheet(f"color:{theme.GREY_MID}; font-family:{theme.MONO}; font-size:11px;")
        row2.addWidget(pos_lbl)
        row2.addStretch()
        row2.addWidget(conf_lbl)
        v.addLayout(row2)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(conf)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(f"""
            QProgressBar {{ background:{theme.BG_2}; border:none; border-radius:2px; }}
            QProgressBar::chunk {{ background:{theme.SURVIVOR_RING}; border-radius:2px; }}
        """)
        v.addWidget(bar)


class SurvivorPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{theme.BG_1};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(10)

        self.title = QLabel("DETECTED SURVIVORS (0)")
        self.title.setStyleSheet(
            f"color:{theme.GREY_HI}; font-family:{theme.DISPLAY}; font-size:13px; font-weight:700; letter-spacing:0.5px;"
        )
        outer.addWidget(self.title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border:none; background:transparent;")
        self.inner = QWidget()
        self.inner_layout = QVBoxLayout(self.inner)
        self.inner_layout.setSpacing(9)
        self.scroll.setWidget(self.inner)
        outer.addWidget(self.scroll, 1)

        self.render({})

    def _clear_inner(self) -> None:
        """Empty the list. Every widget currently in the layout gets
        deleteLater()'d — so nothing here may be a persistent, reused
        attribute (that was the bug: a stored `self.empty_note` label
        got deleted on the first clear, then reused-after-delete on the
        next render() call, crashing with 'Internal C++ object already
        deleted'). Build the empty-state label fresh each time instead."""
        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def render(self, survivors: dict) -> None:
        self.title.setText(f"DETECTED SURVIVORS ({len(survivors)})")
        self._clear_inner()

        if not survivors:
            empty_note = QLabel("No survivors tagged yet")
            empty_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_note.setStyleSheet(
                f"color:{theme.GREY_DIM}; font-family:{theme.DISPLAY}; font-size:12px; padding:12px 0;"
            )
            self.inner_layout.addWidget(empty_note)
            self.inner_layout.addStretch()
            return

        for sv in sorted(survivors.values(), key=lambda s: s.get("t", 0)):
            self.inner_layout.addWidget(SurvivorItem(sv))
        self.inner_layout.addStretch()
