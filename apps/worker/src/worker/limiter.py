"""Redis distributed semaphore / concurrency limiter for external providers."""

from __future__ import annotations

import logging
import time
import uuid
from types import TracebackType
from typing import Any

logger = logging.getLogger(__name__)

# Lua script to acquire semaphore with TTL
# KEYS[1]: semaphore set key
# ARGV[1]: identifier
# ARGV[2]: max_concurrency
# ARGV[3]: current_timestamp
# ARGV[4]: timeout_seconds
ACQUIRE_LUA = """
local sem_key = KEYS[1]
local identifier = ARGV[1]
local max_concurrency = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local timeout = tonumber(ARGV[4])

-- Clean up expired tokens
local clear_before = now - timeout
redis.call('ZREMRANGEBYSCORE', sem_key, '-inf', clear_before)

-- Check current count
local current_count = redis.call('ZCARD', sem_key)
if current_count < max_concurrency then
    redis.call('ZADD', sem_key, now, identifier)
    redis.call('EXPIRE', sem_key, timeout)
    return 1
else
    return 0
end
"""

RELEASE_LUA = """
local sem_key = KEYS[1]
local identifier = ARGV[1]
return redis.call('ZREM', sem_key, identifier)
"""


class ProviderConcurrencyLimiter:
    """Async context manager that throttles concurrent jobs per provider using Redis."""

    def __init__(
        self,
        redis_client: Any,
        provider_id: str,
        max_concurrency: int = 5,
        timeout: int = 300,
        wait_timeout: float = 120.0,
        poll_interval: float = 1.0,
    ) -> None:
        self.redis = redis_client
        self.provider_id = provider_id
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.wait_timeout = wait_timeout
        self.poll_interval = poll_interval
        self.identifier = f"{provider_id}:{uuid.uuid4().hex}"
        self.key = f"limiter:provider:{provider_id}"
        self._acquired = False

    async def acquire(self) -> bool:
        if self.redis is None or not hasattr(self.redis, "eval"):
            # Redis not configured or bypassed
            self._acquired = True
            return True

        start = time.time()
        while time.time() - start < self.wait_timeout:
            now = time.time()
            try:
                res = await self.redis.eval(
                    ACQUIRE_LUA,
                    1,
                    self.key,
                    self.identifier,
                    self.max_concurrency,
                    now,
                    self.timeout,
                )
                if res == 1:
                    self._acquired = True
                    return True
            except Exception as exc:
                logger.warning(
                    "Error acquiring provider semaphore %s: %s; proceeding without lock",
                    self.provider_id,
                    exc,
                )
                self._acquired = False
                return True

            import asyncio

            await asyncio.sleep(self.poll_interval)

        return False

    async def release(self) -> None:
        if not self._acquired or self.redis is None:
            return
        try:
            await self.redis.eval(RELEASE_LUA, 1, self.key, self.identifier)
        except Exception as exc:
            logger.warning("Error releasing provider semaphore %s: %s", self.provider_id, exc)
        finally:
            self._acquired = False

    async def __aenter__(self) -> ProviderConcurrencyLimiter:
        success = await self.acquire()
        if not success:
            raise TimeoutError(
                f"Timed out waiting for concurrency slot for provider {self.provider_id}"
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.release()
