from __future__ import annotations

from app.services.security import FixedWindowLimiter


def test_fixed_window_limiter_blocks_only_after_limit() -> None:
    limiter = FixedWindowLimiter(limit=2, window_seconds=60)

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False
    assert limiter.retry_after("client-a") >= 1
    assert limiter.allow("client-b") is True
