"""cancel_generation ARQ task.

Best-effort cancellation with external provider, recording event,
and ensuring credits are refunded.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from studio_core.credits import CreditService
from studio_core.models import JobStatus
from studio_core.repositories import EventRepository, JobRepository, ModelRepository
from studio_core.state_machine import JobStateMachine
from studio_providers.base import ProviderJobRef
from studio_providers.registry import get_provider

logger = logging.getLogger(__name__)


async def cancel_generation(ctx: dict[str, Any], job_id_raw: str | UUID) -> None:
    """ARQ task entrypoint for canceling a generation job with its provider."""
    job_id = UUID(str(job_id_raw))
    db_pool = ctx["db_pool"]

    async with db_pool.acquire() as conn:
        job_repo = JobRepository(conn)
        state_machine = JobStateMachine(conn)
        credit_svc = CreditService(conn)
        event_repo = EventRepository(conn)
        model_repo = ModelRepository(conn)

        job = await job_repo.get_by_id(job_id)
        if job is None:
            logger.warning("Job %s not found for cancel_generation", job_id)
            return

        # Ensure status is canceled
        if job.status not in (JobStatus.CANCELED, JobStatus.FAILED):
            if job.status in (JobStatus.QUEUED, JobStatus.SUBMITTING, JobStatus.RUNNING):
                await state_machine.transition(
                    job.id,
                    expected=job.status,
                    new=JobStatus.CANCELED,
                )

        # Ensure refund is issued (idempotent)
        await credit_svc.refund(job.id)

        # If provider_job_id is set, call provider.cancel
        if job.provider_job_id:
            model = await model_repo.get_by_id(job.model_id)
            if model:
                try:
                    provider = get_provider(model.provider_id)
                    ref = ProviderJobRef(
                        provider_id=model.provider_id,
                        provider_job_id=job.provider_job_id,
                    )
                    await provider.cancel(ref)
                    logger.info(
                        "Provider cancel succeeded for job %s ref %s", job.id, job.provider_job_id
                    )
                except Exception as exc:
                    logger.warning("Provider cancel swallowed error for job %s: %s", job.id, exc)

        await event_repo.append(
            job_id=job.id,
            event_type="provider_cancel",
            payload={"provider_job_id": job.provider_job_id},
        )
