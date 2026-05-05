"""Thread-safe TTL cache shared by market-data and LLM-dedupe layers."""

import threading
import time
from typing import Any


class TTLCache:
    """Minimal locked dict with separate positive/negative TTLs.

    Negative entries (errors) get a shorter TTL so transient upstream failures
    don't poison the cache for the full positive window, but a flapping key
    still gets some backoff.
    """

    def __init__(self, positive_ttl: float, negative_ttl: float) -> None:
        self._positive_ttl = positive_ttl
        self._negative_ttl = negative_ttl
        self._data: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: Any, value: Any, *, is_error: bool = False) -> None:
        ttl = self._negative_ttl if is_error else self._positive_ttl
        with self._lock:
            self._data[key] = (time.monotonic() + ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
