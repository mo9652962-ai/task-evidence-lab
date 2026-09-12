from __future__ import annotations


class RateLimitBackendUnavailable(RuntimeError):
    pass


class RedisRateLimiter:
    """Small fixed-window Redis adapter; the Redis server provides cross-worker state."""

    def __init__(self, client, *, prefix: str = "task-evidence-lab") -> None:
        self.client = client
        self.prefix = prefix

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        redis_key = f"{self.prefix}:rate:{key}"
        try:
            count = int(self.client.incr(redis_key))
            if count == 1:
                self.client.expire(redis_key, window_seconds)
            return count <= limit
        except Exception as exc:  # Redis client implementations expose different connection errors.
            raise RateLimitBackendUnavailable("rate limit backend unavailable") from exc


def create_redis_limiter(url: str, *, prefix: str) -> RedisRateLimiter:
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
    except Exception as exc:
        raise RateLimitBackendUnavailable("rate limit backend unavailable") from exc
    return RedisRateLimiter(client, prefix=prefix)
