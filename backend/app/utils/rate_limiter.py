"""
In-memory sliding-window rate limiter.

No Redis, no external dependencies.  Uses a simple dict of timestamps
with automatic eviction of expired entries.

Usage as FastAPI dependency::

    from app.utils.rate_limiter import rate_limit

    @router.post("/login", dependencies=[Depends(rate_limit(5, 60))])
    def login(...): ...
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Callable

from fastapi import Depends, HTTPException, Request


class _SlidingWindowLimiter:
    """Thread-safe sliding-window counter keyed by (path, client_ip)."""

    __slots__ = ("_store", "_lock", "_last_gc")

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_gc: float = 0.0

    def is_allowed(self, key: str, max_requests: int, window: int) -> bool:
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            # Periodic GC: prune dead keys every 60s
            if now - self._last_gc > 60:
                dead = [k for k, v in self._store.items() if not v or v[-1] < cutoff]
                for k in dead:
                    del self._store[k]
                self._last_gc = now

            timestamps = self._store[key]
            # Remove expired entries
            while timestamps and timestamps[0] <= cutoff:
                timestamps.pop(0)

            if len(timestamps) >= max_requests:
                return False

            timestamps.append(now)
            return True


_limiter = _SlidingWindowLimiter()


def rate_limit(max_requests: int, window_seconds: int = 60) -> Callable:
    """
    Return a FastAPI dependency that enforces rate limiting.

    Parameters
    ----------
    max_requests : int
        Maximum number of requests allowed within *window_seconds*.
    window_seconds : int
        Sliding window duration in seconds (default 60).

    Returns
    -------
    Callable
        A FastAPI dependency. Raises HTTP 429 when the limit is exceeded.
    """

    def _dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{client_ip}"
        if not _limiter.is_allowed(key, max_requests, window_seconds):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": (
                        f"Too many requests. Maximum {max_requests} "
                        f"per {window_seconds}s."
                    ),
                    "retry_after_seconds": window_seconds,
                },
            )

    return _dependency
