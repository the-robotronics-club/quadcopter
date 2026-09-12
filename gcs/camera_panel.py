"""Live camera feed panel. Frames arrive as base64 JPEG over the same
bridge link and are decoded straight into a QPixmap — no <img> tag,
no browser."""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from . import theme


class CameraPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # deliberately the one dark surface in the app — a camera
        # viewfinder, like a phone camera preview, reads naturally dark
        # even inside an otherwise bright, friendly UI
        self.setStyleSheet(f"background:{theme.SCREEN_BG};")

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.noise_label = QLabel(self)
        self.noise_label.setTextFormat(Qt.TextFormat.RichText)
        self.noise_label.setText(
            f"NO SIGNAL<br>"
            f"<span style='font-size:10px; color:{theme.SCREEN_DIM};'>waiting for camera_frame data\u2026</span>"
        )
        self.noise_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.noise_label.setStyleSheet(
            f"color:{theme.SCREEN_TEXT}; font-family:{theme.MONO}; font-size:13px; letter-spacing:2px;"
        )

        self.header_label = QLabel("LIVE CAMERA FEED", self)
        self.header_label.setStyleSheet(
            f"color:{theme.SCREEN_TEXT}; font-family:{theme.DISPLAY}; font-size:11px; letter-spacing:1px; "
            f"background: rgba(22,23,27,0.82); padding:5px 10px; border-radius:4px;"
        )
        self.header_label.adjustSize()
        self.header_label.move(10, 10)

        self.tag_label = QLabel("CAM \u00b7 \u2014", self)
        self.tag_label.setStyleSheet(
            f"color:{theme.SCREEN_TEXT}; font-family:{theme.MONO}; font-size:10.5px; "
            f"letter-spacing:1.5px; background: rgba(10,11,13,190); padding:7px 8px;"
        )

        self._pixmap = None  # type: Optional[QPixmap]
        self._layout_children()

    def resizeEvent(self, event):
        self._layout_children()
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _layout_children(self):
        self.image_label.setGeometry(0, 0, self.width(), self.height())
        self.noise_label.setGeometry(0, 0, self.width(), self.height())
        self.tag_label.setGeometry(0, self.height() - 24, self.width(), 24)
        self.header_label.raise_()
        self.tag_label.raise_()

    def set_frame(self, payload) -> None:
        """`payload` may be a bare base64 jpeg string, or an object
        carrying {jpeg, grid_box, room} — same backward-compatible shape
        as the original bridge contract."""
        b64 = payload.get("jpeg") if isinstance(payload, dict) else payload
        if not b64:
            return
        raw = QByteArray.fromBase64(b64.encode("ascii"))
        pix = QPixmap()
        if not pix.loadFromData(raw, "JPG"):
            return
        self._pixmap = pix
        self.noise_label.hide()
        self._rescale_pixmap()

        ts = datetime.now().strftime("%H:%M:%S")
        where = ""
        if isinstance(payload, dict):
            where = " \u00b7 ".join(v for v in (payload.get("grid_box"), payload.get("room")) if v)
        self.tag_label.setText(f"CAM \u00b7 {where} \u00b7 {ts}" if where else f"CAM \u00b7 {ts}")

    def _rescale_pixmap(self):
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def reset(self) -> None:
        self._pixmap = None
        self.image_label.clear()
        self.noise_label.show()
        self.tag_label.setText("CAM \u00b7 \u2014")
