"""Login rate limit: five attempts per 60 seconds per key."""
from __future__ import annotations

from app.auth.rate_limit import LoginRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_sixth_attempt_is_blocked_and_retry_after_positive() -> None:
    clock = FakeClock()
    limiter = LoginRateLimiter(clock=clock)
    key = "127.0.0.1:demo@example.test"
    for _ in range(5):
        allowed, retry = limiter.allow(key)
        assert allowed is True
        assert retry == 0
    allowed, retry = limiter.allow(key)
    assert allowed is False
    assert retry > 0


def test_window_expires_and_allows_again() -> None:
    clock = FakeClock()
    limiter = LoginRateLimiter(clock=clock)
    key = "ip:email"
    for _ in range(5):
        assert limiter.allow(key)[0] is True
    assert limiter.allow(key)[0] is False
    clock.now += 61
    assert limiter.allow(key)[0] is True
