"""ARQ queue helpers for enqueuing generation and finalize tasks.

Tasks carry only the job_id (a UUID string); workers re-read from Postgres.
ARQ deduplicates enqueues by ``_job_id``, and that check covers both queued jobs
and stored results. The ARQ id is therefore namespaced per task, otherwise a
finished ``run_generation`` would block ``finalize_generation`` for the same
generation job for as long as its result is kept.
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


def arq_job_id(task_name: str, job_id: UUID) -> str:
    """Return the ARQ ``_job_id`` for a task acting on a generation job.

    The task name is part of the id because ARQ enforces uniqueness across the
    whole queue, not per function. Without it, ``finalize_generation`` would
    collide with the ``run_generation`` job that produced the same generation
    job id and be silently rejected.
    """
    return f"{task_name}:{job_id}"


async def enqueue(
    redis_pool: Any,
    task_name: str,
    job_id: UUID,
    *,
    defer_by: float | None = None,
) -> bool:
    """Enqueue a task with the given job_id onto the ARQ Redis pool.

    Args:
        redis_pool: An ARQ ``ArqRedis`` pool instance (or None for testing).
        task_name:  Name of the ARQ function to enqueue (must match a registered task).
        job_id:     Generation job UUID. Combined with the task name to form the
                    ARQ ``_job_id`` so duplicate enqueues for the same
                    (task, job) pair are idempotent.
        defer_by:   Optional delay in seconds (used for retry back-off).

    Returns:
        ``True`` if the task was queued, ``False`` if ARQ ignored it because an
        equivalent task is already queued/running or Redis is unavailable.

    Raises:
        ``EnqueueError`` if the enqueue call fails.
    """
    if redis_pool is None:
        logger.warning(
            "Redis pool not available; skipping enqueue of %s for job %s", task_name, job_id
        )
        return False

    arq_id = arq_job_id(task_name, job_id)
    kwargs: dict[str, object] = {"_job_id": arq_id}
    if defer_by is not None:
        from datetime import timedelta

        kwargs["_defer_by"] = timedelta(seconds=defer_by)

    try:
        arq_job = await redis_pool.enqueue_job(task_name, str(job_id), **kwargs)
    except Exception as exc:
        logger.error("Failed to enqueue task=%s job_id=%s: %s", task_name, job_id, exc)
        raise EnqueueError(f"Failed to enqueue {task_name} for job {job_id}: {exc}") from exc

    if arq_job is None:
        logger.info(
            "Task=%s job_id=%s arq_job_id=%s is already queued or running; duplicate ignored",
            task_name,
            job_id,
            arq_id,
        )
        return False

    logger.info("Enqueued task=%s job_id=%s arq_job_id=%s", task_name, job_id, arq_id)
    return True


class EnqueueError(RuntimeError):
    """Raised when an ARQ enqueue call fails."""
