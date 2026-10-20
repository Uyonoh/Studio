"""ARQ queue helpers for enqueuing generation and finalize tasks.

Tasks carry only the job_id (a UUID string); workers re-read from Postgres.
ARQ deduplicates enqueues by ``_job_id`` when the same string is enqueued twice.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# Task names must match function names registered in the ARQ WorkerSettings
TASK_RUN_GENERATION = "run_generation"
TASK_FINALIZE_GENERATION = "finalize_generation"
TASK_CANCEL_GENERATION = "cancel_generation"


async def enqueue(
    redis_pool: Any,
    task_name: str,
    job_id: UUID,
    *,
    defer_by: float | None = None,
) -> None:
    """Enqueue a task with the given job_id onto the ARQ Redis pool.

    Args:
        redis_pool: An ARQ ``ArqRedis`` pool instance (or None for testing).
        task_name:  Name of the ARQ function to enqueue (must match a registered task).
        job_id:     Generation job UUID. Used as the ARQ ``_job_id`` so duplicate
                    enqueues for the same job are idempotent.
        defer_by:   Optional delay in seconds (used for retry back-off).

    Raises:
        ``EnqueueError`` if the enqueue call fails.
    """
    if redis_pool is None:
        logger.warning(
            "Redis pool not available; skipping enqueue of %s for job %s", task_name, job_id
        )
        return

    arq_job_id = str(job_id)
    kwargs: dict[str, object] = {"_job_id": arq_job_id}
    if defer_by is not None:
        from datetime import timedelta
        kwargs["_defer_by"] = timedelta(seconds=defer_by)

    try:
        await redis_pool.enqueue_job(task_name, str(job_id), **kwargs)
        logger.info("Enqueued task=%s job_id=%s", task_name, job_id)
    except Exception as exc:
        logger.error("Failed to enqueue task=%s job_id=%s: %s", task_name, job_id, exc)
        raise EnqueueError(f"Failed to enqueue {task_name} for job {job_id}: {exc}") from exc


class EnqueueError(RuntimeError):
    """Raised when an ARQ enqueue call fails."""
