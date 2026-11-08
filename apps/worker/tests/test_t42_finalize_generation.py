"""T4.2 tests — finalize_generation ARQ task."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from studio_core.models import AssetKind
from studio_media.media import VideoMetadata
from studio_providers.base import (
    ProviderJobState,
    ProviderOutput,
    ProviderStatus,
)
from worker.config import WorkerConfig
from worker.fixtures import MockDB, make_job_row, make_mock_pool, make_model_row
from worker.tasks.finalize_generation import derive_asset_id, finalize_generation


def _create_sample_png_bytes(width: int = 120, height: int = 80) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(0, 128, 255))
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_finalize_generation_image_happy_path(test_config: WorkerConfig) -> None:
    """Image output is downloaded, probed, thumbnailed, stored, and job succeeds."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        task_type="text_to_image",
        prompt="a glowing neon cyberpunk city",
        provider_job_id="fake_pred_img_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    png_bytes = _create_sample_png_bytes(200, 150)

    provider_status = ProviderStatus(
        state=ProviderJobState.SUCCEEDED,
        outputs=[
            ProviderOutput(
                url="https://mock.storage.local/out.png",
                mime_type="image/png",
                kind=AssetKind.IMAGE,
            )
        ],
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with (
        patch(
            "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
        ),
        patch(
            "worker.tasks.finalize_generation.StorageClient.download_file",
            AsyncMock(return_value=png_bytes),
        ),
        patch(
            "worker.tasks.finalize_generation.StorageClient.upload_file",
            AsyncMock(return_value="path"),
        ),
    ):
        await finalize_generation(ctx, job_id)

    assert job_dict["status"] == "succeeded"
    assert job_dict["completed_at"] is not None

    expected_asset_id = derive_asset_id(job_id, 0)
    assert expected_asset_id in db.assets
    created_asset = db.assets[expected_asset_id]
    assert created_asset["kind"] == "image"
    assert created_asset["origin"] == "generated"
    assert created_asset["source_job_id"] == job_id
    assert created_asset["width"] == 200
    assert created_asset["height"] == 150


@pytest.mark.asyncio
async def test_finalize_generation_video_happy_path(test_config: WorkerConfig) -> None:
    """Test video output from provider is probed, poster framed, stored, and job succeeds."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        task_type="text_to_video",
        prompt="a cinematic waterfall",
        provider_job_id="fake_pred_vid_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake", task_type="text_to_video")
    db.add_job(job_dict)
    db.add_model(model_dict)

    video_bytes = b"fake_mp4_bytes_12345"

    provider_status = ProviderStatus(
        state=ProviderJobState.SUCCEEDED,
        outputs=[
            ProviderOutput(
                url="https://mock.storage.local/out.mp4",
                mime_type="video/mp4",
                kind=AssetKind.VIDEO,
            )
        ],
    )

    mock_vmeta = VideoMetadata(
        width=1280,
        height=720,
        duration_ms=5000,
        fps=Decimal("30.0"),
        mime_type="video/mp4",
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    def fake_make_poster_frame(src: Any, dst: Any) -> None:
        Image.new("RGB", (640, 360), color=(10, 10, 10)).save(dst, format="JPEG")

    with (
        patch(
            "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
        ),
        patch(
            "worker.tasks.finalize_generation.StorageClient.download_file",
            AsyncMock(return_value=video_bytes),
        ),
        patch(
            "worker.tasks.finalize_generation.StorageClient.upload_file",
            AsyncMock(return_value="path"),
        ),
        patch("worker.tasks.finalize_generation.probe_video", return_value=mock_vmeta),
        patch(
            "worker.tasks.finalize_generation.make_poster_frame", side_effect=fake_make_poster_frame
        ),
    ):
        await finalize_generation(ctx, job_id)

    assert job_dict["status"] == "succeeded"
    expected_asset_id = derive_asset_id(job_id, 0)
    assert expected_asset_id in db.assets
    created_asset = db.assets[expected_asset_id]
    assert created_asset["kind"] == "video"
    assert created_asset["width"] == 1280
    assert created_asset["height"] == 720
    assert created_asset["duration_ms"] == 5000
    assert created_asset["fps"] == Decimal("30.0")


@pytest.mark.asyncio
async def test_finalize_generation_rerun_on_finished_job_is_noop(test_config: WorkerConfig) -> None:
    """Re-running finalize on already succeeded job is a no-op."""
    db = MockDB()
    job_id = uuid.uuid4()
    job_dict = make_job_row(job_id=job_id, status="succeeded")
    db.add_job(job_dict)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await finalize_generation(ctx, job_id)
    assert job_dict["status"] == "succeeded"
    assert len(db.assets) == 0


@pytest.mark.asyncio
async def test_finalize_generation_rerun_mid_failure_no_duplicates(
    test_config: WorkerConfig,
) -> None:
    """If an asset was already inserted in a previous finalize attempt, it is not recreated."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="finalizing",
        provider_job_id="fake_pred_img_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Pre-existing asset for output 0
    asset_id = derive_asset_id(job_id, 0)
    db.add_asset(
        {
            "id": asset_id,
            "workspace_id": job_dict["workspace_id"],
            "project_id": job_dict["project_id"],
            "kind": "image",
            "origin": "generated",
            "storage_bucket": "media",
            "storage_path": "existing_path",
            "thumbnail_path": None,
            "mime_type": "image/png",
            "size_bytes": 100,
            "width": 100,
            "height": 100,
            "duration_ms": None,
            "fps": None,
            "source_job_id": job_id,
            "parent_asset_id": None,
            "metadata": "{}",
            "created_by": job_dict["created_by"],
            "created_at": datetime.now(UTC),
            "deleted_at": None,
        }
    )

    provider_status = ProviderStatus(
        state=ProviderJobState.SUCCEEDED,
        outputs=[
            ProviderOutput(
                url="https://mock.storage.local/out.png",
                mime_type="image/png",
                kind=AssetKind.IMAGE,
            )
        ],
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    mock_download = AsyncMock()
    with (
        patch(
            "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
        ),
        patch("worker.tasks.finalize_generation.StorageClient.download_file", mock_download),
    ):
        await finalize_generation(ctx, job_id)

    # Download should have been skipped because asset already existed
    mock_download.assert_not_called()
    assert job_dict["status"] == "succeeded"


@pytest.mark.asyncio
async def test_finalize_generation_early_webhook_reverts_to_running(
    test_config: WorkerConfig,
) -> None:
    """If provider is still RUNNING, finalize reverts job back to running."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_img_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    provider_status = ProviderStatus(state=ProviderJobState.RUNNING)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with patch(
        "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
    ):
        await finalize_generation(ctx, job_id)

    assert job_dict["status"] == "running"


@pytest.mark.asyncio
async def test_finalize_generation_provider_failure_fails_and_refunds(
    test_config: WorkerConfig,
) -> None:
    """If provider reports FAILED, finalize marks job failed and refunds credits."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_img_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Initial reserve
    db.ledger.append(
        {
            "id": 1,
            "workspace_id": job_dict["workspace_id"],
            "job_id": job_id,
            "delta": Decimal("-1.00"),
            "reason": "reserve",
        }
    )

    provider_status = ProviderStatus(
        state=ProviderJobState.FAILED,
        error_code="NSFW_DETECTED",
        error_message="Safety filter triggered",
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with patch(
        "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
    ):
        await finalize_generation(ctx, job_id)

    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "NSFW_DETECTED"
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_finalize_generation_corrupt_media_rejected_with_output_invalid(
    test_config: WorkerConfig,
) -> None:
    """Corrupt/non-media outputs fail job with OUTPUT_INVALID and refund credits."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        task_type="text_to_image",
        provider_job_id="fake_pred_img_123",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Initial reserve
    db.ledger.append(
        {
            "id": 1,
            "workspace_id": job_dict["workspace_id"],
            "job_id": job_id,
            "delta": Decimal("-1.00"),
            "reason": "reserve",
        }
    )

    provider_status = ProviderStatus(
        state=ProviderJobState.SUCCEEDED,
        outputs=[
            ProviderOutput(
                url="https://mock.storage.local/corrupt.png",
                mime_type="image/png",
                kind=AssetKind.IMAGE,
            )
        ],
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with (
        patch(
            "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
        ),
        patch(
            "worker.tasks.finalize_generation.StorageClient.download_file",
            AsyncMock(return_value=b"NOT_A_VALID_IMAGE_DATA"),
        ),
    ):
        await finalize_generation(ctx, job_id)

    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "OUTPUT_INVALID"
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1
