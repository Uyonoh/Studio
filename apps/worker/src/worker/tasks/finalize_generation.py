"""finalize_generation ARQ task.

Transitions job from running to finalizing, fetches provider status,
downloads outputs, probes metadata, generates thumbnails/posters,
stores assets deterministically, and marks job succeeded (or failed).
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from studio_core.credits import CreditService
from studio_core.models import AssetKind, AssetOrigin, JobStatus
from studio_core.repositories import (
    AssetRepository,
    EventRepository,
    JobRepository,
    ModelRepository,
)
from studio_core.state_machine import JobStateMachine
from studio_media.media import make_poster_frame, make_thumbnail, probe_image, probe_video
from studio_providers.base import (
    ProviderJobRef,
    ProviderJobState,
    ProviderOutput,
)
from studio_providers.registry import get_provider
from worker.config import WorkerConfig, get_worker_config
from worker.storage import StorageClient, make_storage_path

logger = logging.getLogger(__name__)


def derive_asset_id(job_id: UUID, output_index: int) -> UUID:
    """Generate a deterministic UUIDv5 for an output asset to prevent duplicates on retries."""
    return uuid.uuid5(job_id, f"output_{output_index}")


async def finalize_generation(ctx: dict[str, Any], job_id_raw: str | UUID) -> None:
    """ARQ task entrypoint for finalizing a generation job."""
    job_id = UUID(str(job_id_raw))
    db_pool = ctx["db_pool"]
    config: WorkerConfig = ctx.get("config") or get_worker_config()
    storage_client = StorageClient(config)

    async with db_pool.acquire() as conn:
        job_repo = JobRepository(conn)
        state_machine = JobStateMachine(conn)
        credit_svc = CreditService(conn)
        event_repo = EventRepository(conn)
        model_repo = ModelRepository(conn)
        asset_repo = AssetRepository(conn)

        job = await job_repo.get_by_id(job_id)
        if job is None:
            logger.error("Job %s not found for finalization", job_id)
            return

        # 1. Guarded transition: running -> finalizing
        # If already finalizing, we may be recovering a stalled finalization.
        if job.status == JobStatus.RUNNING:
            updated = await state_machine.transition(
                job.id,
                expected=JobStatus.RUNNING,
                new=JobStatus.FINALIZING,
            )
            if updated is None:
                logger.info(
                    "Job %s transition to finalizing failed (concurrent modification)", job_id
                )
                return
            job = updated
        elif job.status == JobStatus.FINALIZING:
            logger.info(
                "Job %s is already in finalizing; proceeding with finalization recovery", job_id
            )
        else:
            logger.info("Job %s is in state %s; ignoring finalize_generation", job_id, job.status)
            return

        # 2. Re-fetch status from provider
        model = await model_repo.get_by_id(job.model_id)
        if model is None:
            logger.error("Model %s for job %s not found", job.model_id, job_id)
            await state_machine.transition(
                job.id,
                expected=JobStatus.FINALIZING,
                new=JobStatus.FAILED,
                error_code="MODEL_NOT_FOUND",
                error_message="Model not found in catalog",
            )
            await credit_svc.refund(job_id)
            return

        try:
            provider = get_provider(model.provider_id)
        except KeyError:
            logger.error("Provider %s not found", model.provider_id)
            await state_machine.transition(
                job.id,
                expected=JobStatus.FINALIZING,
                new=JobStatus.FAILED,
                error_code="PROVIDER_NOT_FOUND",
                error_message=f"Provider {model.provider_id} not available",
            )
            await credit_svc.refund(job_id)
            return

        provider_job_id = job.provider_job_id or ""
        ref = ProviderJobRef(provider_id=model.provider_id, provider_job_id=provider_job_id)

        try:
            provider_status = await provider.get_status(ref)
        except Exception as exc:
            logger.error("Failed to query provider status for job %s: %s", job_id, exc)
            await state_machine.transition(
                job.id,
                expected=JobStatus.FINALIZING,
                new=JobStatus.FAILED,
                error_code="PROVIDER_STATUS_ERROR",
                error_message=f"Failed to check status with provider: {exc}",
            )
            await credit_svc.refund(job_id)
            return

        # If provider says still running (early webhook), revert to running
        if provider_status.state in (ProviderJobState.PENDING, ProviderJobState.RUNNING):
            logger.info("Provider reports job %s still running; reverting to running", job_id)
            # Revert guarded transition back: finalizing -> running
            await conn.execute(
                """
                UPDATE public.generation_jobs
                SET status = 'running', heartbeat_at = now()
                WHERE id = $1 AND status = 'finalizing'
                """,
                job.id,
            )
            await event_repo.append(
                job_id=job.id,
                event_type="early_webhook_revert",
                from_status=JobStatus.FINALIZING,
                to_status=JobStatus.RUNNING,
            )
            return

        if provider_status.state in (ProviderJobState.FAILED, ProviderJobState.CANCELED):
            logger.info("Provider reported job %s state %s", job_id, provider_status.state)
            await state_machine.transition(
                job.id,
                expected=JobStatus.FINALIZING,
                new=JobStatus.FAILED
                if provider_status.state == ProviderJobState.FAILED
                else JobStatus.CANCELED,
                error_code=provider_status.error_code or "PROVIDER_FAILURE",
                error_message=provider_status.error_message
                or f"Provider ended in state {provider_status.state}",
            )
            await credit_svc.refund(job_id)
            return

        # 3. Process outputs: provider status is SUCCEEDED
        outputs: list[ProviderOutput] = provider_status.outputs
        if not outputs:
            logger.error("Job %s succeeded at provider but returned no outputs", job_id)
            await state_machine.transition(
                job.id,
                expected=JobStatus.FINALIZING,
                new=JobStatus.FAILED,
                error_code="OUTPUT_EMPTY",
                error_message="Provider completed with no outputs",
            )
            await credit_svc.refund(job_id)
            return

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            for idx, out in enumerate(outputs):
                asset_id = derive_asset_id(job.id, idx)

                # Check if asset already exists (from earlier partial finalize attempt)
                existing_asset = await asset_repo.get_by_id(asset_id)
                if existing_asset is not None:
                    logger.info(
                        "Asset %s already created for job %s output %d; skipping",
                        asset_id,
                        job.id,
                        idx,
                    )
                    continue

                # Download content
                try:
                    data = await storage_client.download_file(out.url)
                except Exception as exc:
                    logger.error(
                        "Failed to download output %s for job %s: %s", out.url, job.id, exc
                    )
                    await state_machine.transition(
                        job.id,
                        expected=JobStatus.FINALIZING,
                        new=JobStatus.FAILED,
                        error_code="OUTPUT_DOWNLOAD_FAILED",
                        error_message=f"Failed to download provider output: {exc}",
                    )
                    await credit_svc.refund(job_id)
                    return

                # Guess extension based on mime or kind
                is_video = (out.kind == AssetKind.VIDEO) or (
                    out.mime_type and "video" in out.mime_type
                )
                ext = "mp4" if is_video else "png"
                local_file = tmp_dir / f"original_{idx}.{ext}"
                local_file.write_bytes(data)

                # Probe metadata and validate
                width: int | None = None
                height: int | None = None
                duration_ms: int | None = None
                fps: Decimal | None = None
                mime_type = out.mime_type or ("video/mp4" if is_video else "image/png")

                thumb_path: str | None = None
                try:
                    if is_video:
                        vmeta = probe_video(local_file)
                        width, height = vmeta.width, vmeta.height
                        duration_ms, fps = vmeta.duration_ms, vmeta.fps
                        mime_type = vmeta.mime_type

                        # Make poster frame
                        thumb_local = tmp_dir / f"thumb_{idx}.jpg"
                        make_poster_frame(local_file, thumb_local)
                        thumb_storage_path = make_storage_path(
                            job.workspace_id, job.project_id, asset_id, "thumbnail.jpg"
                        )
                        await storage_client.upload_file(
                            thumb_storage_path, thumb_local.read_bytes(), content_type="image/jpeg"
                        )
                        thumb_path = thumb_storage_path
                    else:
                        imeta = probe_image(local_file)
                        width, height = imeta.width, imeta.height
                        mime_type = imeta.mime_type

                        # Make thumbnail
                        thumb_local = tmp_dir / f"thumb_{idx}.jpg"
                        make_thumbnail(local_file, thumb_local)
                        thumb_storage_path = make_storage_path(
                            job.workspace_id, job.project_id, asset_id, "thumbnail.jpg"
                        )
                        await storage_client.upload_file(
                            thumb_storage_path, thumb_local.read_bytes(), content_type="image/jpeg"
                        )
                        thumb_path = thumb_storage_path
                except Exception as exc:
                    logger.error("Invalid media output for job %s: %s", job.id, exc)
                    await state_machine.transition(
                        job.id,
                        expected=JobStatus.FINALIZING,
                        new=JobStatus.FAILED,
                        error_code="OUTPUT_INVALID",
                        error_message=f"Output media is corrupt or invalid: {exc}",
                    )
                    await credit_svc.refund(job_id)
                    return

                # Upload original to storage
                orig_storage_path = make_storage_path(
                    job.workspace_id, job.project_id, asset_id, f"original.{ext}"
                )
                await storage_client.upload_file(orig_storage_path, data, content_type=mime_type)

                # Insert asset row with deterministic asset_id
                asset_metadata = {
                    "prompt": job.prompt,
                    "model": model.slug,
                    "params": job.params,
                    "seed": job.params.get("seed"),
                    "output_index": idx,
                    "status": "ready",
                }

                # We can execute INSERT with explicit id
                await conn.execute(
                    """
                    INSERT INTO public.assets (
                        id, workspace_id, project_id, kind, origin, storage_bucket,
                        storage_path, thumbnail_path, mime_type, size_bytes, width,
                        height, duration_ms, fps, source_job_id, metadata, created_by
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16, $17
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    asset_id,
                    job.workspace_id,
                    job.project_id,
                    AssetKind.VIDEO.value if is_video else AssetKind.IMAGE.value,
                    AssetOrigin.GENERATED.value,
                    config.storage_bucket,
                    orig_storage_path,
                    thumb_path,
                    mime_type,
                    len(data),
                    width,
                    height,
                    duration_ms,
                    fps,
                    job.id,
                    __import__("json").dumps(asset_metadata),
                    job.created_by,
                )

        # 4. Transition finalizing -> succeeded
        await state_machine.transition(
            job.id,
            expected=JobStatus.FINALIZING,
            new=JobStatus.SUCCEEDED,
            event_payload={"asset_count": len(outputs)},
        )
        logger.info("Job %s successfully finalized with %d outputs", job_id, len(outputs))
