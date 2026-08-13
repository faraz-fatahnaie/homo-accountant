"""Rate limiting (in-memory sliding window) for authentication endpoints.

Single-process MVP: an in-memory store is sufficient and testable. A Redis-backed
limiter can replace this implementation later without changing the interface.
"""

from __future__ import annotations

import threading
import time


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> None:
        self._events[key] = [t for t in self._events.get(key, []) if now - t < self.window]

    def allow(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            events = self._events.setdefault(key, [])
            if len(events) >= self.max_events:
                retry_after = self.window - (now - events[0])
                return False, max(retry_after, 1.0)
            events.append(now)
            return True, 0.0

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


# Shared instances (configured from Settings at import time)
def _build_limiter() -> SlidingWindowLimiter:
    from app.core.config import get_settings

    s = get_settings()
    return SlidingWindowLimiter(s.login_rate_limit_per_minute, 60.0)


login_limiter = _build_limiter()
