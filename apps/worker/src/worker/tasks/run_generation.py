"""run_generation ARQ task.

Claims a queued job, resolves inputs, submits to the provider,
and transitions job to running (or retries/fails).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import random
from typing import Any
from uuid import UUID

from arq.worker import Retry

from studio_core.credits import CreditService
from studio_core.models import AssetKind, JobStatus
from studio_core.observability import (
    capture_exception,
    set_current_job_context,
)
from studio_core.queue import TASK_FINALIZE_GENERATION, TASK_RUN_GENERATION, enqueue
from studio_core.repositories import (
    AssetRepository,
    EventRepository,
    JobRepository,
    ModelRepository,
)
from studio_core.state_machine import JobStateMachine
from studio_providers.base import (
    PermanentProviderError,
    ProviderInput,
    ProviderJobState,
    ProviderRequest,
    RateLimitedError,
    TransientProviderError,
)
from studio_providers.registry import get_provider
from worker.config import WorkerConfig, get_worker_config
from worker.limiter import ProviderConcurrencyLimiter
from worker.storage import get_signed_download_url

logger = logging.getLogger(__name__)


def compute_job_token(job_id: UUID, signing_secret: str) -> str:
    """Derive a per-job HMAC token from the webhook signing secret."""
    return hmac.new(
        signing_secret.encode(),
        msg=str(job_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


async def run_generation(ctx: dict[str, Any], job_id_raw: str | UUID) -> None:
    """ARQ task entrypoint for submitting a generation job to its provider."""
    job_id = UUID(str(job_id_raw))
    db_pool = ctx["db_pool"]
    redis_pool = ctx.get("redis_pool")
    config: WorkerConfig = ctx.get("config") or get_worker_config()

    async with db_pool.acquire() as conn:
        job_repo = JobRepository(conn)
        state_machine = JobStateMachine(conn)
        credit_svc = CreditService(conn)
        event_repo = EventRepository(conn)
        model_repo = ModelRepository(conn)
        asset_repo = AssetRepository(conn)

        job = await job_repo.get_by_id(job_id)
        if job is None:
            logger.error("Job %s not found", job_id)
            return

        set_current_job_context(job_id=str(job_id), status=job.status.value)

        # 1. Guarded transition: queued -> submitting
        if job.status == JobStatus.QUEUED:
            updated = await state_machine.transition(
                job.id,
                expected=JobStatus.QUEUED,
                new=JobStatus.SUBMITTING,
                event_payload={"attempt": job.attempt},
            )
            if updated is None:
                logger.info("Job %s already claimed or transitioned concurrently", job_id)
                return
            job = updated
        elif job.status == JobStatus.SUBMITTING:
            # Re-delivery or retry while in submitting
            pass
        else:
            logger.info("Job %s is in state %s; ignoring run_generation", job_id, job.status)
            return

        # 2. If provider_job_id is already set, skip submit and transition to running
        if job.provider_job_id:
            logger.info(
                "Job %s already has provider_job_id %s; advancing to running",
                job_id,
                job.provider_job_id,
            )
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.RUNNING,
            )
            return

        # 3. Load model and provider adapter
        model = await model_repo.get_by_id(job.model_id)
        if model is None:
            logger.error("Model %s for job %s not found", job.model_id, job_id)
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.FAILED,
                error_code="MODEL_NOT_FOUND",
                error_message="Model not found in catalog",
            )
            await credit_svc.refund(job_id)
            return

        set_current_job_context(
            job_id=str(job_id),
            provider=model.provider_id,
            model=model.slug,
            status=job.status.value,
        )

        try:
            provider = get_provider(model.provider_id)
        except KeyError:
            logger.error("Provider %s not found in registry", model.provider_id)
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.FAILED,
                error_code="PROVIDER_NOT_FOUND",
                error_message=f"Provider {model.provider_id} is not enabled or configured",
            )
            await credit_svc.refund(job_id)
            return

        # 4. Resolve input assets to signed URLs
        raw_inputs = await job_repo.get_inputs(job_id)
        provider_inputs: list[ProviderInput] = []
        if raw_inputs:
            asset_ids = [inp.asset_id for inp in raw_inputs]
            assets = await asset_repo.get_many(asset_ids)
            asset_by_id = {a.id: a for a in assets}

            for inp in raw_inputs:
                asset = asset_by_id.get(inp.asset_id)
                if asset:
                    signed_url = get_signed_download_url(asset.storage_path, config)
                    provider_inputs.append(
                        ProviderInput(
                            role=inp.role.value if hasattr(inp.role, "value") else str(inp.role),
                            url=signed_url,
                            kind=asset.kind
                            if hasattr(asset.kind, "value")
                            else AssetKind(asset.kind),
                        )
                    )

        # 5. Build webhook URL
        webhook_token = compute_job_token(job_id, config.webhook_signing_secret)
        webhook_url = (
            f"{config.public_api_url.rstrip('/')}/internal/webhooks/{model.provider_id}/{job_id}"
            f"?token={webhook_token}"
        )

        provider_req = ProviderRequest(
            task_type=job.task_type,
            model=model.provider_model,
            prompt=job.prompt,
            negative_prompt=job.negative_prompt,
            inputs=provider_inputs,
            params=job.params,
            webhook_url=webhook_url,
        )

        # 6. Submit with per-provider concurrency limiter
        max_concurrency = getattr(
            config,
            f"provider_concurrency_{model.provider_id}",
            5,
        )
        limiter = ProviderConcurrencyLimiter(
            redis_client=redis_pool,
            provider_id=model.provider_id,
            max_concurrency=max_concurrency,
        )

        try:
            async with limiter:
                job_ref = await provider.submit(provider_req)

            logger.info(
                "Job %s submitted to provider %s with ref %s",
                job_id,
                model.provider_id,
                job_ref.provider_job_id,
            )

            # Record event
            await event_repo.append(
                job_id=job.id,
                event_type="provider_submit",
                payload={
                    "provider_job_id": job_ref.provider_job_id,
                    "provider_id": model.provider_id,
                },
            )

            # Transition submitting -> running
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.RUNNING,
                provider_job_id=job_ref.provider_job_id,
            )

            # Check if job completed synchronously (e.g. Google Imagen),
            # and enqueue finalize immediately without waiting for reconciler
            try:
                initial_status = await provider.get_status(job_ref)
                if initial_status.state == ProviderJobState.SUCCEEDED:
                    logger.info(
                        "Job %s completed synchronously; enqueuing finalize immediately", job_id
                    )
                    if redis_pool:
                        await enqueue(redis_pool, TASK_FINALIZE_GENERATION, job_id)
            except Exception as exc:
                logger.debug("Immediate status check skipped for job %s: %s", job_id, exc)

        except (RateLimitedError, TransientProviderError) as exc:
            logger.warning("Transient error submitting job %s: %s", job_id, exc)
            next_attempt = job.attempt + 1
            if next_attempt >= job.max_attempts:
                logger.error("Job %s exhausted max attempts (%s)", job_id, job.max_attempts)
                await state_machine.transition(
                    job.id,
                    expected=JobStatus.SUBMITTING,
                    new=JobStatus.FAILED,
                    error_code="ATTEMPTS_EXHAUSTED",
                    error_message=f"Provider transient error after max attempts: {exc}",
                )
                await credit_svc.refund(job_id)
                return

            # Revert submitting -> queued with attempt+1
            backoff_base = getattr(exc, "retry_after", 5.0) or 5.0
            jitter = random.uniform(0.5, 1.5)
            defer_seconds = min(300.0, backoff_base * (2**job.attempt) * jitter)

            await conn.execute(
                "UPDATE public.generation_jobs SET status = 'queued', attempt = $2 WHERE id = $1",
                job.id,
                next_attempt,
            )
            await event_repo.append(
                job_id=job.id,
                event_type="retry_deferred",
                from_status=JobStatus.SUBMITTING,
                to_status=JobStatus.QUEUED,
                payload={
                    "attempt": next_attempt,
                    "defer_seconds": defer_seconds,
                    "reason": str(exc),
                },
            )

            if redis_pool:
                try:
                    await enqueue(
                        redis_pool,
                        TASK_RUN_GENERATION,
                        job.id,
                        defer_by=defer_seconds,
                    )
                except Exception as enq_exc:
                    logger.warning("Failed to defer enqueue via helper: %s", enq_exc)

            raise Retry(defer=int(defer_seconds)) from exc

        except PermanentProviderError as exc:
            logger.error("Permanent error submitting job %s: %s", job_id, exc)
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.FAILED,
                error_code=getattr(exc, "code", "PERMANENT_PROVIDER_ERROR"),
                error_message=str(exc),
            )
            await credit_svc.refund(job_id)
            return

        except Exception as exc:
            logger.exception("Unexpected error submitting job %s: %s", job_id, exc)
            capture_exception(
                exc,
                job_id=str(job_id),
                provider=model.provider_id,
                model=model.slug,
                status=JobStatus.FAILED.value,
            )
            await state_machine.transition(
                job.id,
                expected=JobStatus.SUBMITTING,
                new=JobStatus.FAILED,
                error_code="INTERNAL_ERROR",
                error_message=str(exc),
            )
            await credit_svc.refund(job_id)
            return
