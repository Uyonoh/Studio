"""Tests for the ARQ queue helpers.

Regression guard: ARQ deduplicates on ``_job_id`` across the whole queue and
also blocks ids that still have a stored result. The same generation job id is
used by several tasks, so the id must be namespaced per task.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from studio_core.queue import (
    TASK_FINALIZE_GENERATION,
    TASK_RUN_GENERATION,
    EnqueueError,
    arq_job_id,
    enqueue,
)


class FakeArqPool:
    """Minimal stand-in for ``arq.connections.ArqRedis``."""

    def __init__(self, result: object = object(), error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> object:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def test_arq_job_id_namespaces_by_task() -> None:
    job_id = uuid4()

    assert arq_job_id(TASK_RUN_GENERATION, job_id) == f"run_generation:{job_id}"
    assert arq_job_id(TASK_FINALIZE_GENERATION, job_id) == f"finalize_generation:{job_id}"


async def test_enqueue_uses_distinct_arq_ids_for_run_and_finalize() -> None:
    job_id = uuid4()
    pool = FakeArqPool()

    assert await enqueue(pool, TASK_RUN_GENERATION, job_id) is True
    assert await enqueue(pool, TASK_FINALIZE_GENERATION, job_id) is True

    run_args, run_kwargs = pool.calls[0]
    finalize_args, finalize_kwargs = pool.calls[1]

    assert run_args == (TASK_RUN_GENERATION, str(job_id))
    assert finalize_args == (TASK_FINALIZE_GENERATION, str(job_id))
    assert run_kwargs["_job_id"] == f"run_generation:{job_id}"
    assert finalize_kwargs["_job_id"] == f"finalize_generation:{job_id}"


async def test_enqueue_reports_deduplicated_job() -> None:
    """ARQ returns None when the id already exists; that must not look like success."""
    job_id = uuid4()

    assert await enqueue(FakeArqPool(result=None), TASK_FINALIZE_GENERATION, job_id) is False


async def test_enqueue_returns_false_without_redis_pool() -> None:
    assert await enqueue(None, TASK_RUN_GENERATION, uuid4()) is False


async def test_enqueue_passes_defer_by() -> None:
    pool = FakeArqPool()
    job_id: UUID = uuid4()

    assert await enqueue(pool, TASK_RUN_GENERATION, job_id, defer_by=30.0) is True

    _, kwargs = pool.calls[0]
    assert kwargs["_defer_by"] == timedelta(seconds=30.0)


async def test_enqueue_wraps_pool_errors() -> None:
    pool = FakeArqPool(error=ConnectionError("redis down"))

    with pytest.raises(EnqueueError):
        await enqueue(pool, TASK_RUN_GENERATION, uuid4())
