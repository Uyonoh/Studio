"""T4.1 tests — run_generation ARQ task."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from arq.worker import Retry

from worker.config import WorkerConfig
from worker.fixtures import MockDB, make_job_row, make_mock_pool, make_model_row
from worker.tasks.run_generation import run_generation


@pytest.mark.asyncio
async def test_run_generation_happy_path_fake_provider(test_config: WorkerConfig) -> None:
    """Test queued job transitions to submitting then running with provider_job_id set."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(job_id=job_id, model_id=model_id, status="queued")
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await run_generation(ctx, job_id)

    assert job_dict["status"] == "running"
    assert job_dict["provider_job_id"] is not None


@pytest.mark.asyncio
async def test_run_generation_transient_error_retries(test_config: WorkerConfig) -> None:
    """Transient error reverts submitting to queued with attempt incremented and Retry raised."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="queued",
        prompt="A TRANSIENT_FAIL prompt",
        attempt=0,
        max_attempts=3,
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    conn = db.make_conn()
    pool = make_mock_pool(conn)
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with pytest.raises(Retry):
        await run_generation(ctx, job_id)

    assert job_dict["status"] == "queued"
    assert job_dict["attempt"] == 1


@pytest.mark.asyncio
async def test_run_generation_permanent_error_fails_and_refunds(test_config: WorkerConfig) -> None:
    """Permanent error fails job and refunds credits."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="queued",
        prompt="A FAIL prompt",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Initial reserve entry
    db.ledger.append(
        {
            "id": 1,
            "workspace_id": job_dict["workspace_id"],
            "job_id": job_id,
            "delta": Decimal("-1.00"),
            "reason": "reserve",
        }
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await run_generation(ctx, job_id)

    assert job_dict["status"] == "failed"
    # Ensure refund entry was added to ledger
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1
    assert refunds[0]["delta"] == Decimal("1.00")


@pytest.mark.asyncio
async def test_run_generation_attempts_exhausted_fails(test_config: WorkerConfig) -> None:
    """Job at max attempts with transient failure transitions to failed and refunds."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="queued",
        prompt="A TRANSIENT_FAIL prompt",
        attempt=2,
        max_attempts=3,
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Initial reserve entry
    db.ledger.append(
        {
            "id": 1,
            "workspace_id": job_dict["workspace_id"],
            "job_id": job_id,
            "delta": Decimal("-1.00"),
            "reason": "reserve",
        }
    )

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await run_generation(ctx, job_id)

    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "ATTEMPTS_EXHAUSTED"
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_run_generation_with_inputs_resolves_signed_urls(test_config: WorkerConfig) -> None:
    """Test job with input assets resolves signed URLs and sends to provider."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id, model_id=model_id, status="queued", task_type="image_to_video"
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake", task_type="image_to_video")
    asset_dict = {
        "id": asset_id,
        "workspace_id": job_dict["workspace_id"],
        "project_id": job_dict["project_id"],
        "kind": "image",
        "origin": "upload",
        "storage_bucket": "media",
        "storage_path": (
            f"{job_dict['workspace_id']}/{job_dict['project_id']}/{asset_id}/original.png"
        ),
        "thumbnail_path": None,
        "mime_type": "image/png",
        "size_bytes": 1024,
        "width": 512,
        "height": 512,
        "duration_ms": None,
        "fps": None,
        "source_job_id": None,
        "parent_asset_id": None,
        "metadata": "{}",
        "created_by": job_dict["created_by"],
        "created_at": datetime.now(UTC),
        "deleted_at": None,
    }

    db.add_job(job_dict)
    db.add_model(model_dict)
    db.add_asset(asset_dict)
    db.add_input(job_id=job_id, asset_id=asset_id, role="first_frame")

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await run_generation(ctx, job_id)

    assert job_dict["status"] == "running"
    assert job_dict["provider_job_id"] is not None


@pytest.mark.asyncio
async def test_run_generation_second_delivery_already_has_provider_id(
    test_config: WorkerConfig,
) -> None:
    """Task with provider_job_id advances directly to running without re-submit."""
    db = MockDB()
    job_id = uuid.uuid4()
    job_dict = make_job_row(
        job_id=job_id,
        status="submitting",
        provider_job_id="existing_provider_job_123",
    )
    db.add_job(job_dict)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    await run_generation(ctx, job_id)

    assert job_dict["status"] == "running"
    assert job_dict["provider_job_id"] == "existing_provider_job_123"
