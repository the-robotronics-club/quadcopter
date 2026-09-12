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

Note: this client only ever speaks WebSocket + JSON. Pointing it at a
raw MAVLink/UDP endpoint (e.g. a udp4 bridge straight off PX4) will
never connect — there's no WebSocket handshake to complete and nothing
there understands this JSON schema. Something has to sit between PX4
and this app to translate; see px4_bridge.py for that piece.
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
        self._socket = None
        self._make_socket()

    def _make_socket(self) -> None:
        """Build a brand-new QWebSocket and wire its signals.

        This used to be done once in __init__ and reused across every
        connect attempt. That's what produced the "Invalid socket
        descriptor" error reported against real PX4 hardware: after a
        failed or aborted handshake, the QWebSocket's internal native
        descriptor is left in a state Qt won't cleanly reopen on the
        same instance. Building a fresh QWebSocket for every connect_to()
        call guarantees a clean slate each time, regardless of how the
        previous attempt ended.
        """
        self._socket = QWebSocket()
        self._socket.setParent(self)
        self._socket.connected.connect(self.connected.emit)
        self._socket.disconnected.connect(self.disconnected.emit)
        self._socket.textMessageReceived.connect(self._on_text)
        self._socket.errorOccurred.connect(self._on_error)

    def connect_to(self, url: str) -> None:
        qurl = QUrl(url)
        # A malformed or scheme-less address (e.g. "192.168.4.1:8765"
        # instead of "ws://192.168.4.1:8765") doesn't fail loudly on
        # its own — QWebSocket just emits a vague/misleading socket
        # error later. Catching it here gives an actionable message
        # immediately instead of leaving the person to guess.
        if not qurl.isValid() or qurl.scheme() not in ("ws", "wss"):
            self.error_occurred.emit(
                f"Invalid bridge address '{url}' \u2014 expected something like "
                f"ws://192.168.4.1:8765 (must start with ws:// or wss://)."
            )
            return
        self._teardown_socket()
        self._make_socket()
        self._socket.open(qurl)

    def close(self) -> None:
        if self._socket is None:
            return
        # Block signals before tearing down: abort() on a socket that was
        # actually connected (or mid-handshake) can itself fire
        # `disconnected` or `errorOccurred` internally. main_window.py
        # already resets its own UI state and logs "Manually
        # disconnected"/"Connection attempt cancelled" the moment the
        # user clicks Disconnect/Cancel — without this, that click could
        # also re-trigger on_bridge_disconnected() or _on_bridge_error(),
        # producing a second, confusing log line for something the user
        # did on purpose. Signals are only needed for *unexpected* drops,
        # which never go through this method.
        self._socket.blockSignals(True)
        # abort() rather than close(): close() only performs a graceful
        # WebSocket close handshake on an already-open connection, and
        # does nothing useful (or can hang) on a socket that's still
        # mid-handshake ("Cancel" while CONNECTING). abort() tears the
        # underlying socket down immediately in either case.
        self._socket.abort()

    def is_open(self) -> bool:
        return (
            self._socket is not None
            and self._socket.state() == QAbstractSocket.SocketState.ConnectedState
        )

    def _teardown_socket(self) -> None:
        if self._socket is None:
            return
        old = self._socket
        self._socket = None
        old.blockSignals(True)
        old.abort()
        old.deleteLater()

    def _on_text(self, text: str) -> None:
        if self.sender() is not self._socket:
            return  # stale signal from a socket that's since been replaced
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
        if self._socket is None or self.sender() is not self._socket:
            return  # stale signal from a socket that's since been replaced
        # This is the exact message the lead hit when pointing the GCS
        # straight at a raw MAVLink/udp4 address instead of a WebSocket
        # bridge. Baking the px4_bridge.py hint into the message itself
        # (rather than only in docs someone has to go find) means that
        # specific confusion can't repeat silently.
        self.error_occurred.emit(
            f"WebSocket error: {self._socket.errorString()} "
            f"\u2014 check the bridge IP/port and that this machine is on the same local network. "
            f"If you're pointing this at a raw MAVLink/UDP address (e.g. straight off PX4), "
            f"that won't work \u2014 this app only speaks WebSocket/JSON. Run px4_bridge.py in "
            f"between and connect to that instead."
        )
