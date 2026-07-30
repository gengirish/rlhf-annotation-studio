"""Unit tests for the sliding-window limiter and proxy-aware client IP."""

from __future__ import annotations

from types import SimpleNamespace

from app.middleware.rate_limit import SlidingWindowLimiter, client_ip


def _request(headers: dict[str, str] | None = None, peer: str | None = None):
    """Minimal stand-in for a Starlette Request (headers + client only)."""
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=peer) if peer else None,
    )


# --- client_ip -------------------------------------------------------------


def test_prefers_fly_client_ip_over_socket_peer() -> None:
    req = _request({"Fly-Client-IP": "203.0.113.7"}, peer="172.16.0.1")
    assert client_ip(req) == "203.0.113.7"


def test_falls_back_to_leftmost_forwarded_for() -> None:
    # Left-most entry is the original client; the rest are proxies.
    req = _request({"X-Forwarded-For": "203.0.113.7, 70.41.3.18"}, peer="172.16.0.1")
    assert client_ip(req) == "203.0.113.7"


def test_falls_back_to_socket_peer_without_proxy_headers() -> None:
    assert client_ip(_request(peer="192.0.2.5")) == "192.0.2.5"


def test_unknown_when_no_client() -> None:
    assert client_ip(_request()) == "unknown"


def test_distinct_clients_get_distinct_keys() -> None:
    """Regression guard: the bug this replaced bucketed everyone together."""
    a = client_ip(_request({"Fly-Client-IP": "203.0.113.7"}, peer="172.16.0.1"))
    b = client_ip(_request({"Fly-Client-IP": "203.0.113.8"}, peer="172.16.0.1"))
    assert a != b


# --- SlidingWindowLimiter --------------------------------------------------


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=60)
    assert [limiter.allow("ip", now=100.0) for _ in range(3)] == [True, True, True]
    assert limiter.allow("ip", now=100.0) is False


def test_window_slides_so_old_events_expire() -> None:
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60)
    assert limiter.allow("ip", now=100.0) is True
    assert limiter.allow("ip", now=100.0) is True
    assert limiter.allow("ip", now=130.0) is False  # still inside the window
    assert limiter.allow("ip", now=161.0) is True  # first two aged out


def test_keys_are_independent() -> None:
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60)
    assert limiter.allow("a", now=100.0) is True
    assert limiter.allow("a", now=100.0) is False
    assert limiter.allow("b", now=100.0) is True


def test_expired_buckets_are_evicted() -> None:
    """The original store leaked one dict entry per unique IP, forever."""
    limiter = SlidingWindowLimiter(max_events=5, window_seconds=60)
    for i in range(50):
        limiter.allow(f"ip-{i}", now=100.0)
    assert limiter.tracked_keys == 50

    # Well past the window: touching one key sweeps the aged-out buckets.
    limiter.allow("fresh", now=1000.0)
    assert limiter.tracked_keys < 50


def test_key_count_stays_bounded_under_unique_ip_flood() -> None:
    limiter = SlidingWindowLimiter(max_events=5, window_seconds=3600, max_keys=100)
    for i in range(1000):
        limiter.allow(f"ip-{i}", now=100.0)
    assert limiter.tracked_keys <= 100


def test_reset_clears_state() -> None:
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60)
    limiter.allow("ip", now=100.0)
    limiter.reset()
    assert limiter.tracked_keys == 0
    assert limiter.allow("ip", now=100.0) is True
