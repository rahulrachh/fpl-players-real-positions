"""Small in-memory TTL cache for live FPL calls.

Per process only: on Vercel each function instance has its own cache, which
is fine for short-lived data.
"""

import threading
import time
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

V = TypeVar("V")

_MISSING = object()


class TTLCache(Generic[V]):
    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._data: dict[Hashable, tuple[float, V]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable, default=None):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return default
            expires_at, value = entry
            if self._clock() >= expires_at:
                del self._data[key]
                return default
            return value

    def set(self, key: Hashable, value: V) -> None:
        with self._lock:
            if len(self._data) >= self.max_entries and key not in self._data:
                self._evict()
            self._data[key] = (self._clock() + self.ttl_seconds, value)

    def get_or_set(self, key: Hashable, factory: Callable[[], V]) -> V:
        """Return the cached value, or call `factory` and cache its result.

        `factory` runs outside the lock, so two concurrent misses may both
        call it; the last result wins. Acceptable for idempotent GETs.
        """
        value = self.get(key, _MISSING)
        if value is _MISSING:
            value = factory()
            self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def _evict(self) -> None:
        # Drop expired entries; if still full, drop the soonest-to-expire one.
        now = self._clock()
        for k in [k for k, (exp, _) in self._data.items() if now >= exp]:
            del self._data[k]
        if len(self._data) >= self.max_entries:
            del self._data[min(self._data, key=lambda k: self._data[k][0])]
