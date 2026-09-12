from __future__ import annotations

import time

import pytest

from app.services.rate_limit import RedisRateLimiter, RateLimitBackendUnavailable


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiry: dict[str, float] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> bool:
        self.expiry[key] = time.monotonic() + seconds
        return True


class BrokenRedis:
    def incr(self, key: str) -> int:
        raise ConnectionError("redis down")


def test_redis_limiter_counts_shared_windows() -> None:
    limiter = RedisRateLimiter(FakeRedis(), prefix="test")

    assert limiter.allow("user:1", limit=2, window_seconds=60) is True
    assert limiter.allow("user:1", limit=2, window_seconds=60) is True
    assert limiter.allow("user:1", limit=2, window_seconds=60) is False


def test_redis_limiter_fails_closed_when_backend_is_unavailable() -> None:
    limiter = RedisRateLimiter(BrokenRedis(), prefix="test")

    with pytest.raises(RateLimitBackendUnavailable):
        limiter.allow("user:1", limit=2, window_seconds=60)
