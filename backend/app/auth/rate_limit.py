"""Small fixed-window login rate limiter (per worker)."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). A denied attempt is not recorded."""
        now = self._clock()
        attempts = self._attempts[key]
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= self.max_attempts:
            retry_after = max(1, int(self.window_seconds - (now - attempts[0])))
            return False, retry_after
        attempts.append(now)
        return True, 0

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)
