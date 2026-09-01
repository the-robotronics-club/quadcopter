"""
video_stream.py
----------------
Threaded frame grabber.

OpenCV's cap.read() is blocking and I/O bound (camera driver, USB bus,
network for RTSP, etc). If you read frames in the same loop as
inference, the GPU/CPU sits idle while waiting on the camera. Reading
frames on a separate thread and always keeping only the latest one
overlaps I/O wait with inference time, which is what actually gets you
into the 22-23 FPS range instead of being camera-latency bound.
"""

import threading
import time
import cv2

import config


class VideoStream:
    def __init__(self, source=config.VIDEO_SOURCE,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # Keep the driver's internal buffer as small as possible so we
        # always get the freshest frame, not a stale queued one.
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._lock = threading.Lock()
        self._frame = None
        self._ok = False
        self._stopped = False

        # Prime the first frame synchronously so callers never race
        # against an empty buffer on startup.
        self._ok, self._frame = self.cap.read()

        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _update(self):
        while not self._stopped:
            ok, frame = self.cap.read()
            if not ok:
                # Camera glitch / end of file — back off briefly instead
                # of busy-looping.
                time.sleep(0.01)
                continue
            with self._lock:
                self._ok = ok
                self._frame = frame

    def read(self):
        """Returns (ok, frame) — the most recently captured frame."""
        with self._lock:
            if self._frame is None:
                return False, None
            return self._ok, self._frame.copy()

    def stop(self):
        self._stopped = True
        self._thread.join(timeout=1.0)
        self.cap.release()
