"""Regression tests for worker Redis connection resilience."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from arq.connections import ArqRedis
from arq.worker import Worker
from redis.exceptions import ConnectionError as RedisConnectionError

import worker.main as worker_main
from studio_core.redis import DEFAULT_HEALTH_CHECK_INTERVAL
from worker.config import WorkerConfig


async def test_startup_reuses_arq_pool_and_shutdown_leaves_it_open(
    monkeypatch: pytest.MonkeyPatch,
    test_config: WorkerConfig,
) -> None:
    fake_db_pool = AsyncMock()
    fake_redis_pool = AsyncMock()

    async def fake_create_db_pool(*args: Any, **kwargs: Any) -> AsyncMock:
        return fake_db_pool

    monkeypatch.setattr(worker_main, "create_db_pool", fake_create_db_pool)
    monkeypatch.setattr(worker_main, "init_sentry", lambda **kwargs: False)
    monkeypatch.setattr(worker_main, "reconcile_jobs", AsyncMock(return_value=0))

    ctx: dict[str, Any] = {"redis": fake_redis_pool, "config": test_config}
    await worker_main.startup(ctx)

    assert ctx["redis_pool"] is fake_redis_pool
    assert "_owns_redis_pool" not in ctx

    await worker_main.shutdown(ctx)

    fake_db_pool.close.assert_awaited_once()
    fake_redis_pool.aclose.assert_not_awaited()


def test_worker_settings_use_health_checked_pool() -> None:
    settings = worker_main.WorkerSettings

    assert isinstance(settings.redis_pool, ArqRedis)
    kwargs = settings.redis_pool.connection_pool.connection_kwargs
    assert kwargs["health_check_interval"] == DEFAULT_HEALTH_CHECK_INTERVAL
    assert settings.redis_settings is not None


async def test_poll_iteration_survives_redis_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def flaky_poll(self: Worker) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RedisConnectionError("Connection closed by server.")

    monkeypatch.setattr(Worker, "_poll_iteration", flaky_poll)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)

    worker = object.__new__(worker_main.ResilientWorker)
    worker.poll_delay_s = 0

    # ARQ's run loop calls _poll_iteration repeatedly; the first call backs off
    # on the connection error instead of raising, the next one succeeds.
    await worker._poll_iteration()
    assert worker._redis_poll_failures == 1
    sleep.assert_awaited_once()

    await worker._poll_iteration()

    assert calls == 2
    assert worker._redis_poll_failures == 0
