"""T4.4 tests — cancel_generation ARQ task."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from worker.config import WorkerConfig
from worker.fixtures import MockDB, make_job_row, make_mock_pool, make_model_row
from worker.tasks.cancel_generation import cancel_generation
from worker.tasks.finalize_generation import finalize_generation


@pytest.mark.asyncio
async def test_cancel_generation_while_running_cancels_and_refunds(
    test_config: WorkerConfig,
) -> None:
    """Canceling running job transitions to canceled, calls provider.cancel, and refunds credits."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_cancel_123",
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

    with patch("studio_providers.fake.FakeProvider.cancel", AsyncMock()) as mock_cancel:
        await cancel_generation(ctx, job_id)

    assert job_dict["status"] == "canceled"
    mock_cancel.assert_called_once()
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1

    # Verify provider_cancel event recorded
    cancel_events = [e for e in db.events if e.get("type") == "provider_cancel"]
    assert len(cancel_events) == 1


@pytest.mark.asyncio
async def test_finalize_after_cancel_is_noop(test_config: WorkerConfig) -> None:
    """If provider finished anyway, finalize after cancel is a no-op and creates no assets."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_cancel_234",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

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

    # 1. Cancel the job
    await cancel_generation(ctx, job_id)
    assert job_dict["status"] == "canceled"

    # 2. Late webhook or finalize called
    mock_download = AsyncMock()
    with patch("worker.tasks.finalize_generation.StorageClient.download_file", mock_download):
        await finalize_generation(ctx, job_id)

    # Finalize should not process or download anything
    mock_download.assert_not_called()
    assert len(db.assets) == 0
    assert job_dict["status"] == "canceled"


@pytest.mark.asyncio
async def test_cancel_generation_provider_error_swallowed(test_config: WorkerConfig) -> None:
    """If provider.cancel raises an error (e.g. already finished), it is swallowed gracefully."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_err_345",
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with patch(
        "studio_providers.fake.FakeProvider.cancel",
        AsyncMock(side_effect=RuntimeError("Provider already finished")),
    ):
        # Should not raise
        await cancel_generation(ctx, job_id)

    assert job_dict["status"] == "canceled"
