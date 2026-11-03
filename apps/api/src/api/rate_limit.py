"""Redis token-bucket rate limiting for generation and upload endpoints.

The limiter is intentionally fail-open: if Redis is unavailable (local dev,
a transient outage) requests are allowed through and a warning is logged. The
token bucket itself is evaluated atomically in Lua so concurrent API workers
share the same budget.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request

from api.auth import AuthUser
from api.deps import DBConn
from studio_core.settings import get_settings

logger = logging.getLogger(__name__)

# KEYS[1] = bucket key
# ARGV[1] = capacity (max tokens, i.e. burst allowance)
# ARGV[2] = refill rate in tokens per second
# ARGV[3] = current unix timestamp in seconds
# ARGV[4] = token cost of this request
#
# Returns {allowed, retry_after_ms}.
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_per_second = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil or ts == nil then
  tokens = capacity
  ts = now
else
  local elapsed = math.max(0, now - ts)
  tokens = math.min(capacity, tokens + elapsed * refill_per_second)
end

local allowed = 0
local retry_after_ms = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after_ms = math.ceil(((cost - tokens) / refill_per_second) * 1000)
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
-- Keep the key around until a full bucket would have refilled.
redis.call('EXPIRE', key, math.ceil(capacity / refill_per_second) + 60)
return {allowed, retry_after_ms}
"""


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single token-bucket acquisition."""

    allowed: bool
    retry_after_seconds: int = 0


class TokenBucketRateLimiter:
    """Token-bucket limiter backed by a Redis-compatible client."""

    def __init__(
        self,
        redis: Any,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.redis = redis
        self.clock = clock

    async def acquire(
        self,
        key: str,
        *,
        capacity: int,
        refill_per_second: float,
        cost: int = 1,
    ) -> RateLimitResult:
        """Consume ``cost`` tokens from ``key``, refilling based on elapsed time."""
        if capacity <= 0 or refill_per_second <= 0:
            return RateLimitResult(allowed=True)

        try:
            raw = await self.redis.eval(
                TOKEN_BUCKET_LUA,
                1,
                key,
                capacity,
                refill_per_second,
                self.clock(),
                cost,
            )
        except Exception as exc:  # noqa: BLE001 - fail open by design
            logger.warning("Rate limiter unavailable for key %s: %s", key, exc)
            return RateLimitResult(allowed=True)

        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            allowed = bool(int(raw[0]))
            retry_after_ms = int(raw[1])
        else:  # pragma: no cover - defensive against unexpected Redis replies
            logger.warning("Unexpected rate limiter reply for key %s: %r", key, raw)
            return RateLimitResult(allowed=True)

        retry_after = max(1, math.ceil(retry_after_ms / 1000)) if not allowed else 0
        return RateLimitResult(allowed=allowed, retry_after_seconds=retry_after)


def _get_limiter(request: Request) -> TokenBucketRateLimiter | None:
    """Return the app-scoped limiter, or build one from the ARQ Redis pool."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        return cast(TokenBucketRateLimiter, limiter)

    redis = getattr(request.app.state, "redis_pool", None)
    if redis is None:
        return None

    limiter = TokenBucketRateLimiter(redis)
    request.app.state.rate_limiter = limiter
    return limiter


def _rate_limited(scope: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error_code": "RATE_LIMITED",
            "title": "Rate Limited",
            "detail": f"Too many requests for this {scope}. Retry after {retry_after} second(s).",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


async def _enforce(
    request: Request,
    user: AuthUser,
    *,
    bucket: str,
    limit_per_minute: int,
    workspace_id: UUID | None,
) -> None:
    """Consume one token from the per-user and per-workspace buckets."""
    limiter = _get_limiter(request)
    if limiter is None:
        return

    refill_per_second = limit_per_minute / 60.0

    user_result = await limiter.acquire(
        f"ratelimit:{bucket}:user:{user.id}",
        capacity=limit_per_minute,
        refill_per_second=refill_per_second,
    )
    if not user_result.allowed:
        raise _rate_limited("user", user_result.retry_after_seconds)

    if workspace_id is None:
        return

    workspace_result = await limiter.acquire(
        f"ratelimit:{bucket}:workspace:{workspace_id}",
        capacity=limit_per_minute,
        refill_per_second=refill_per_second,
    )
    if not workspace_result.allowed:
        raise _rate_limited("workspace", workspace_result.retry_after_seconds)


async def _workspace_for_project(db: DBConn, project_id: UUID) -> UUID | None:
    row = await db.fetchrow(
        "SELECT workspace_id FROM public.projects WHERE id = $1 AND archived_at IS NULL",
        project_id,
    )
    if row is None:
        return None
    return dict(row).get("workspace_id")


async def _workspace_for_job(db: DBConn, job_id: UUID) -> UUID | None:
    row = await db.fetchrow(
        "SELECT workspace_id FROM public.generation_jobs WHERE id = $1",
        job_id,
    )
    if row is None:
        return None
    return dict(row).get("workspace_id")


async def submit_rate_limit(
    request: Request,
    user: AuthUser,
    db: DBConn,
    project_id: UUID,
) -> None:
    """Rate-limit generation submissions per user and per workspace."""
    settings = get_settings()
    if not settings.rate_limit_enabled or _get_limiter(request) is None:
        return
    workspace_id = await _workspace_for_project(db, project_id)
    await _enforce(
        request,
        user,
        bucket="submit",
        limit_per_minute=settings.rate_limit_submit_per_minute,
        workspace_id=workspace_id,
    )


async def retry_rate_limit(
    request: Request,
    user: AuthUser,
    db: DBConn,
    job_id: UUID,
) -> None:
    """Rate-limit retries per user and per workspace."""
    settings = get_settings()
    if not settings.rate_limit_enabled or _get_limiter(request) is None:
        return
    workspace_id = await _workspace_for_job(db, job_id)
    await _enforce(
        request,
        user,
        bucket="submit",
        limit_per_minute=settings.rate_limit_submit_per_minute,
        workspace_id=workspace_id,
    )


async def upload_rate_limit(
    request: Request,
    user: AuthUser,
    db: DBConn,
    project_id: UUID,
) -> None:
    """Rate-limit upload-URL requests per user and per workspace."""
    settings = get_settings()
    if not settings.rate_limit_enabled or _get_limiter(request) is None:
        return
    workspace_id = await _workspace_for_project(db, project_id)
    await _enforce(
        request,
        user,
        bucket="upload",
        limit_per_minute=settings.rate_limit_upload_per_minute,
        workspace_id=workspace_id,
    )


SubmitRateLimit = Annotated[None, Depends(submit_rate_limit)]
RetryRateLimit = Annotated[None, Depends(retry_rate_limit)]
UploadRateLimit = Annotated[None, Depends(upload_rate_limit)]
