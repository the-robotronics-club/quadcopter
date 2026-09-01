"""
fps_counter.py
--------------
Small rolling-average FPS tracker so the on-screen number doesn't
jitter wildly frame to frame.
"""

import time
from collections import deque

import config


class FPSCounter:
    def __init__(self, window=config.FPS_SMOOTHING_WINDOW):
        self._timestamps = deque(maxlen=window)

    def tick(self):
        """Call once per processed frame. Returns the current smoothed FPS."""
        now = time.perf_counter()
        self._timestamps.append(now)
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed
