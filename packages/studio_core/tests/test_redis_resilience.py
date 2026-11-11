"""Tests for resilient Redis pools used by the API and worker."""

from __future__ import annotations

from arq.connections import ArqRedis
from redis.asyncio.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError

from studio_core.redis import (
    DEFAULT_HEALTH_CHECK_INTERVAL,
    create_redis_pool,
    create_redis_settings,
)


def test_pool_enables_health_checks_and_connection_retries() -> None:
    pool = create_redis_pool("redis://127.0.0.1:6379/0")

    assert isinstance(pool, ArqRedis)
    kwargs = pool.connection_pool.connection_kwargs
    assert kwargs["health_check_interval"] == DEFAULT_HEALTH_CHECK_INTERVAL
    assert kwargs["socket_keepalive"] is True
    assert RedisConnectionError in kwargs["retry_on_error"]
    assert isinstance(kwargs["retry"], Retry)


def test_settings_enable_connection_retries_for_arq_tooling() -> None:
    settings = create_redis_settings("rediss://user:pass@example.com:6379/1")

    assert settings.ssl is True
    assert settings.database == 1
    assert settings.retry_on_timeout is True
    assert settings.retry_on_error is not None
    assert RedisConnectionError in settings.retry_on_error
    assert isinstance(settings.retry, Retry)
