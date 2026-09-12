from __future__ import annotations

import time
from threading import Lock


class FixedWindowLimiter:
    """Small process-local limiter for an optional single-host deployment."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = Lock()

    def _window(self, key: str, current: float) -> tuple[float, int]:
        start, count = self._windows.get(key, (current, 0))
        if current - start >= self.window_seconds:
            start, count = current, 0
        self._windows[key] = (start, count)
        return start, count

    def allow(self, key: str) -> bool:
        current = time.monotonic()
        with self._lock:
            self._prune(current)
            start, count = self._window(key, current)
            if count >= self.limit:
                return False
            self._windows[key] = (start, count + 1)
            return True

    def retry_after(self, key: str) -> int:
        current = time.monotonic()
        with self._lock:
            start, _ = self._window(key, current)
            return max(1, int(self.window_seconds - (current - start)))

    def _prune(self, current: float) -> None:
        stale = [key for key, (start, _) in self._windows.items() if current - start >= self.window_seconds]
        for key in stale:
            self._windows.pop(key, None)
