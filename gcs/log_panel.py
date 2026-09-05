from datetime import datetime

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from . import theme

MAX_LINES = 300


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{theme.BG_1};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("TELEMETRY LOG")
        title.setStyleSheet(
            f"color:{theme.GREY_MID}; font-family:{theme.DISPLAY}; font-size:11px; font-weight:700; "
            f"letter-spacing:0.5px; padding:8px 16px; border-bottom:1px solid {theme.LINE_0};"
        )
        layout.addWidget(title)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet(
            f"QTextEdit {{ background:{theme.BG_1}; border:none; color:{theme.GREY_MID}; "
            f"font-family:{theme.MONO}; font-size:11.5px; padding:8px 16px; }}"
        )
        layout.addWidget(self.text, 1)
        self._n_lines = 0

    def log(self, message: str, warn: bool = False) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        # warnings get the amber "heads up" accent rather than a generic
        # "brighter" shade, so they're colour-coded distinctly from
        # ordinary lines instead of just varying in intensity
        color = theme.CONNECTING_ACCENT if warn else theme.GREY_MID
        self.text.append(
            f'<span style="color:{theme.GREY_DIM};">{ts}&nbsp;&nbsp;</span>'
            f'<span style="color:{color};">{message}</span>'
        )
        self._n_lines += 1
        if self._n_lines > MAX_LINES:
            cursor = self.text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
            self._n_lines -= 1
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())
