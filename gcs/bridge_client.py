"""
Native client for the PX4 companion bridge link. No browser, no
JavaScript WebSocket — this uses Qt's own QWebSocket, integrated
directly into the app's event loop via signals.

The bridge is expected to speak the same JSON-over-WebSocket contract
the original GCS used (see main_window.py's docstring for the full
message schema: telemetry / map_update / survivor / waypoint / object /
mission_status / camera_frame). If your companion-computer bridge uses
a different framing (e.g. raw MAVLink, protobuf, etc.) this is the one
file to adapt — everything downstream just consumes plain dicts.
"""

import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket


class BridgeClient(QObject):
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._socket = QWebSocket()
        self._socket.connected.connect(self.connected.emit)
        self._socket.disconnected.connect(self.disconnected.emit)
        self._socket.textMessageReceived.connect(self._on_text)
        self._socket.errorOccurred.connect(self._on_error)

    def connect_to(self, url: str) -> None:
        self._socket.open(QUrl(url))

    def close(self) -> None:
        self._socket.close()

    def is_open(self) -> bool:
        return self._socket.state() == QAbstractSocket.SocketState.ConnectedState

    def _on_text(self, text: str) -> None:
        try:
            msg = json.loads(text)
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Malformed message dropped: {e}")
            return
        if not isinstance(msg, dict) or "type" not in msg:
            self.error_occurred.emit("Malformed message dropped: missing 'type' field")
            return
        self.message_received.emit(msg)

    def _on_error(self, _socket_error) -> None:
        self.error_occurred.emit(
            f"WebSocket error: {self._socket.errorString()} "
            f"\u2014 check the bridge IP/port and that this machine is on the same local network."
        )
