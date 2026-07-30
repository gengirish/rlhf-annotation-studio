"""Sliding-window rate limiting with proxy-aware client identification.

The API runs behind Fly's edge proxy, so ``request.client.host`` is the proxy
address rather than the caller's. Every request would land in the same bucket,
turning a per-client limit into a single global one. ``client_ip`` resolves the
real caller from the proxy headers instead.
"""

from __future__ import annotations

import time
from collections import OrderedDict

# Keep the bucket map bounded: an unbounded map grows one entry per unique IP
# for the lifetime of the process, which is a slow memory leak on a small VM.
DEFAULT_MAX_KEYS = 10_000


def client_ip(request) -> str:
    """Best-effort real client IP.

    Fly sets ``Fly-Client-IP`` to the true peer address, so prefer it. Otherwise
    fall back to the left-most ``X-Forwarded-For`` entry (the original client;
    later entries are intermediate proxies), then to the socket address.
    """
    fly_ip = request.headers.get("Fly-Client-IP")
    if fly_ip:
        return fly_ip.strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first

    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    """Fixed-memory sliding-window limiter.

    Buckets are held in an ``OrderedDict`` ordered by last use, so the
    least-recently-seen key is evicted once ``max_keys`` is reached.

    Note: state is per-process. With more than one machine each gets its own
    allowance; move to a shared store (e.g. Redis) before scaling out.
    """

    def __init__(self, max_events: int, window_seconds: float, max_keys: int = DEFAULT_MAX_KEYS):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, list[float]] = OrderedDict()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record a hit for ``key``; return False if it exceeds the limit."""
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds

        events = self._buckets.get(key)
        if events is None:
            events = []
            self._buckets[key] = events

        events[:] = [t for t in events if t > cutoff]
        self._buckets.move_to_end(key)

        if len(events) >= self.max_events:
            return False

        events.append(now)
        self._evict(cutoff)
        return True

    def _evict(self, cutoff: float) -> None:
        # Sweep from the least-recently-touched end, pruning aged-out events and
        # dropping buckets that empty out. Stop at the first bucket still holding
        # a live event: buckets are ordered by last touch, so everything after it
        # was touched more recently and is necessarily live too.
        while self._buckets:
            oldest_key = next(iter(self._buckets))
            events = self._buckets[oldest_key]
            events[:] = [t for t in events if t > cutoff]
            if events:
                break
            del self._buckets[oldest_key]

        # Hard ceiling regardless of activity.
        while len(self._buckets) > self.max_keys:
            self._buckets.popitem(last=False)

    def reset(self) -> None:
        self._buckets.clear()

    @property
    def tracked_keys(self) -> int:
        return len(self._buckets)
