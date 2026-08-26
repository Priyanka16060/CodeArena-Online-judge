"""
Sliding-window rate limiter backed by Redis.

Why a Lua script instead of separate ZADD/ZREMRANGEBYSCORE/ZCARD calls?
Those three calls executed back-to-back are NOT atomic — two concurrent
requests from the same user could both read a stale count and both get
admitted, blowing past the limit. Running the whole check-and-increment
as a single Lua script makes Redis execute it atomically (single-threaded
event loop), which closes that race without needing a distributed lock.
"""

from fastapi import HTTPException, status

from app.config import get_settings
from app.redis_client import get_redis

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)

if count >= limit then
    return count
end

redis.call('ZADD', key, now, now .. '-' .. math.random())
redis.call('EXPIRE', key, window)
return count + 1
"""


async def _enforce_sliding_window(key: str, window_seconds: int, limit: int, what: str) -> None:
    redis = get_redis()
    script = redis.register_script(_SLIDING_WINDOW_LUA)

    import time

    now = time.time()
    new_count = await script(keys=[key], args=[now, window_seconds, limit])

    if int(new_count) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {limit} {what} per {window_seconds}s. Try again shortly.",
        )


async def enforce_submit_rate_limit(user_id: str) -> None:
    settings = get_settings()
    await _enforce_sliding_window(
        key=f"ratelimit:submit:{user_id}",
        window_seconds=settings.submit_rate_window_seconds,
        limit=settings.submit_rate_limit,
        what="submissions",
    )


async def enforce_run_rate_limit(user_id: str) -> None:
    """Separate, more generous budget from real submissions — trial runs
    against sample tests shouldn't eat into the graded-submission quota."""
    settings = get_settings()
    await _enforce_sliding_window(
        key=f"ratelimit:run:{user_id}",
        window_seconds=settings.run_rate_window_seconds,
        limit=settings.run_rate_limit,
        what="trial runs",
    )
