"""reconcile_jobs ARQ cron task.

Recovers from lost webhooks and crashed workers:
  - queued older than 2 min and not in Redis -> re-enqueue
  - submitting with stale heartbeat_at (> 3 min) -> back to queued (attempt+1) or fail
  - running older than min_poll_age -> poll provider get_status; if terminal enqueue finalize
  - jobs exceeding per-task max runtime -> failed with TIMEOUT, cancel provider, refund
  - finalizing stale > 5 min -> re-enqueue finalize
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from studio_core.credits import CreditService
from studio_core.models import JobStatus, TaskType
from studio_core.queue import (
    TASK_FINALIZE_GENERATION,
    TASK_RUN_GENERATION,
    enqueue,
)
from studio_core.repositories import EventRepository, ModelRepository
from studio_core.state_machine import JobStateMachine
from studio_providers.base import ProviderJobRef, ProviderJobState
from studio_providers.registry import get_provider
from worker.config import WorkerConfig, get_worker_config

logger = logging.getLogger(__name__)


async def reconcile_jobs(
    ctx: dict[str, Any],
    now: datetime | None = None,
    batch_size: int = 50,
) -> int:
    """Cron task that reconciles stuck or orphan generation jobs.

    Returns the count of reconciled jobs.
    """
    db_pool = ctx["db_pool"]
    redis_pool = ctx.get("redis_pool")
    config: WorkerConfig = ctx.get("config") or get_worker_config()
    current_time = now or datetime.now(UTC)

    reconciled_count = 0

    async with db_pool.acquire() as conn:
        state_machine = JobStateMachine(conn)
        credit_svc = CreditService(conn)
        event_repo = EventRepository(conn)
        model_repo = ModelRepository(conn)

        # 1. Check max runtime timeouts for 'running' jobs
        # Task type video vs image max runtimes
        # Query active running jobs
        running_jobs_query = """
            SELECT id, workspace_id, project_id, model_id, task_type, status,
                   provider_job_id, started_at, queued_at, attempt, max_attempts
            FROM public.generation_jobs
            WHERE status = 'running'
            ORDER BY queued_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        """
        running_rows = await conn.fetch(running_jobs_query, batch_size)
        for row in running_rows:
            job_id: UUID = row["id"]
            task_type: str = row["task_type"]
            started_at: datetime = row["started_at"] or row["queued_at"]

            is_video = task_type in (TaskType.TEXT_TO_VIDEO.value, TaskType.IMAGE_TO_VIDEO.value)
            max_runtime = (
                config.max_runtime_video_seconds if is_video else config.max_runtime_image_seconds
            )

            # Check if job exceeded max runtime
            if (current_time - started_at).total_seconds() > max_runtime:
                logger.warning(
                    "Job %s timed out after %s seconds",
                    job_id,
                    (current_time - started_at).total_seconds(),
                )
                await state_machine.transition(
                    job_id,
                    expected=JobStatus.RUNNING,
                    new=JobStatus.FAILED,
                    error_code="TIMEOUT",
                    error_message=f"Job exceeded max runtime of {max_runtime}s",
                )
                await credit_svc.refund(job_id)

                # Attempt provider cancel
                if row["provider_job_id"]:
                    model = await model_repo.get_by_id(row["model_id"])
                    if model:
                        try:
                            provider = get_provider(model.provider_id)
                            await provider.cancel(
                                ProviderJobRef(
                                    provider_id=model.provider_id,
                                    provider_job_id=row["provider_job_id"],
                                )
                            )
                        except Exception as exc:
                            logger.warning(
                                "Failed to cancel timed out job %s with provider: %s", job_id, exc
                            )

                reconciled_count += 1
                continue

            # Check running jobs older than min_poll_age (e.g. 30s) -> poll provider get_status
            if (current_time - started_at).total_seconds() >= 30 and row["provider_job_id"]:
                model = await model_repo.get_by_id(row["model_id"])
                if model:
                    try:
                        provider = get_provider(model.provider_id)
                        p_status = await provider.get_status(
                            ProviderJobRef(
                                provider_id=model.provider_id,
                                provider_job_id=row["provider_job_id"],
                            )
                        )
                        if p_status.state == ProviderJobState.SUCCEEDED:
                            logger.info(
                                "Reconciler detected completed job %s; enqueuing finalize", job_id
                            )
                            if redis_pool:
                                await enqueue(redis_pool, TASK_FINALIZE_GENERATION, job_id)
                            reconciled_count += 1
                        elif p_status.state in (ProviderJobState.FAILED, ProviderJobState.CANCELED):
                            logger.info("Reconciler detected terminal failure for job %s", job_id)
                            await state_machine.transition(
                                job_id,
                                expected=JobStatus.RUNNING,
                                new=JobStatus.FAILED
                                if p_status.state == ProviderJobState.FAILED
                                else JobStatus.CANCELED,
                                error_code=p_status.error_code or "PROVIDER_FAILURE",
                                error_message=p_status.error_message or "Provider failed",
                            )
                            await credit_svc.refund(job_id)
                            reconciled_count += 1
                    except Exception as exc:
                        logger.warning("Reconciler poll error for job %s: %s", job_id, exc)

        # 2. Check stale 'submitting' jobs (heartbeat_at > 3 minutes ago)
        stale_submitting_query = """
            SELECT id, attempt, max_attempts, heartbeat_at, queued_at
            FROM public.generation_jobs
            WHERE status = 'submitting'
              AND (heartbeat_at < $1 OR (heartbeat_at IS NULL AND queued_at < $1))
            ORDER BY queued_at ASC
            LIMIT $2
            FOR UPDATE SKIP LOCKED
        """
        three_min_ago = current_time - timedelta(minutes=3)
        stale_submitting_rows = await conn.fetch(stale_submitting_query, three_min_ago, batch_size)
        for row in stale_submitting_rows:
            job_id = row["id"]
            attempt = row["attempt"] + 1
            max_attempts = row["max_attempts"]

            if attempt >= max_attempts:
                logger.error("Job %s stuck in submitting exhausted max attempts", job_id)
                await state_machine.transition(
                    job_id,
                    expected=JobStatus.SUBMITTING,
                    new=JobStatus.FAILED,
                    error_code="SUBMIT_TIMEOUT",
                    error_message="Worker stalled during submission and exceeded max attempts",
                )
                await credit_svc.refund(job_id)
            else:
                logger.info(
                    "Recovering stale submitting job %s back to queued (attempt %d)",
                    job_id,
                    attempt,
                )
                await conn.execute(
                    """
                    UPDATE public.generation_jobs
                    SET status = 'queued', attempt = $2, heartbeat_at = now()
                    WHERE id = $1
                    """,
                    job_id,
                    attempt,
                )
                await event_repo.append(
                    job_id=job_id,
                    event_type="reconciled_stale_submitting",
                    from_status=JobStatus.SUBMITTING,
                    to_status=JobStatus.QUEUED,
                    payload={"attempt": attempt},
                )
                if redis_pool:
                    await enqueue(redis_pool, TASK_RUN_GENERATION, job_id)

            reconciled_count += 1

        # 3. Check 'queued' jobs older than 2 minutes -> re-enqueue
        queued_stuck_query = """
            SELECT id, queued_at
            FROM public.generation_jobs
            WHERE status = 'queued'
              AND (heartbeat_at < $1 OR (heartbeat_at IS NULL AND queued_at < $1))
            ORDER BY queued_at ASC
            LIMIT $2
            FOR UPDATE SKIP LOCKED
        """
        two_min_ago = current_time - timedelta(minutes=2)
        queued_stuck_rows = await conn.fetch(queued_stuck_query, two_min_ago, batch_size)
        for row in queued_stuck_rows:
            job_id = row["id"]
            logger.info("Re-enqueuing stuck queued job %s", job_id)
            if redis_pool:
                await enqueue(redis_pool, TASK_RUN_GENERATION, job_id)
            reconciled_count += 1

        # 4. Check 'finalizing' jobs stale > 5 minutes -> re-enqueue finalize
        finalizing_stale_query = """
            SELECT id, heartbeat_at, queued_at
            FROM public.generation_jobs
            WHERE status = 'finalizing'
              AND (heartbeat_at < $1 OR (heartbeat_at IS NULL AND queued_at < $1))
            ORDER BY queued_at ASC
            LIMIT $2
            FOR UPDATE SKIP LOCKED
        """
        five_min_ago = current_time - timedelta(minutes=5)
        finalizing_rows = await conn.fetch(finalizing_stale_query, five_min_ago, batch_size)
        for row in finalizing_rows:
            job_id = row["id"]
            logger.info("Re-enqueuing stale finalizing job %s", job_id)
            if redis_pool:
                await enqueue(redis_pool, TASK_FINALIZE_GENERATION, job_id)
            reconciled_count += 1

    return reconciled_count
