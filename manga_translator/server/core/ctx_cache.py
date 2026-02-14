"""In-memory ctx cache for split translation pipeline."""

from __future__ import annotations

import threading
import time
from typing import Any


class CtxCache:
    """Thread-safe TTL cache keyed by task id."""

    def __init__(self, max_size: int = 32, default_ttl: int = 300) -> None:
        self._max_size = max(1, int(max_size))
        self._default_ttl = max(1, int(default_ttl))
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, str, Any]] = {}

    def _evict_expired(self, now: float | None = None) -> None:
        current = time.time() if now is None else float(now)
        expired = [task_id for task_id, (expire_at, _, _) in self._store.items() if expire_at <= current]
        for task_id in expired:
            self._store.pop(task_id, None)

    def put(self, task_id: str, image_hash: str, ctx: Any) -> int:
        """Store ctx and return ttl seconds."""
        with self._lock:
            now = time.time()
            self._evict_expired(now)
            if len(self._store) >= self._max_size:
                oldest_task = min(self._store, key=lambda key: self._store[key][0])
                self._store.pop(oldest_task, None)
            expire_at = now + self._default_ttl
            self._store[str(task_id)] = (expire_at, str(image_hash), ctx)
        return self._default_ttl

    def get(self, task_id: str, image_hash: str) -> tuple[Any | None, str]:
        """Get cached ctx and reason."""
        with self._lock:
            key = str(task_id)
            now = time.time()
            item = self._store.get(key)
            if item is None:
                self._evict_expired(now)
                return None, "CACHE_MISS"
            expire_at, cached_hash, cached_ctx = item
            if expire_at <= now:
                self._store.pop(key, None)
                return None, "TASK_EXPIRED"
            if str(cached_hash) != str(image_hash):
                return None, "IMAGE_HASH_MISMATCH"
            return cached_ctx, "OK"

    def pop(self, task_id: str) -> None:
        with self._lock:
            self._store.pop(str(task_id), None)
