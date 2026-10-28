"""T4.3 tests — reconcile_jobs ARQ cron task."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from studio_core.queue import TASK_FINALIZE_GENERATION, TASK_RUN_GENERATION
from studio_providers.base import (
    ProviderJobState,
    ProviderStatus,
)
from worker.config import WorkerConfig
from worker.fixtures import MockDB, make_job_row, make_mock_pool, make_model_row
from worker.tasks.reconciler import reconcile_jobs


@pytest.mark.asyncio
async def test_reconcile_running_job_exceeds_max_runtime_fails_and_refunds(
    test_config: WorkerConfig,
) -> None:
    """Running image job older than 10 mins times out, attempts cancel, and refunds."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        task_type="text_to_image",
        provider_job_id="fake_pred_timeout_123",
        started_at=t0,
        queued_at=t0,
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    # Reserve entry
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
    mock_redis = AsyncMock()
    ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": test_config}

    # Time travel 11 minutes later
    now = t0 + timedelta(minutes=11)

    with patch("studio_providers.fake.FakeProvider.cancel", AsyncMock()) as mock_cancel:
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "TIMEOUT"
    mock_cancel.assert_called_once()
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_reconcile_running_job_poll_succeeded_enqueues_finalize(
    test_config: WorkerConfig,
) -> None:
    """Running job older than 30s polled as SUCCEEDED enqueues finalize_generation."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_poll_123",
        started_at=t0,
    )
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    pool = make_mock_pool(db.make_conn())
    mock_redis = AsyncMock()
    ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": test_config}

    now = t0 + timedelta(seconds=45)
    provider_status = ProviderStatus(state=ProviderJobState.SUCCEEDED, outputs=[])

    with (
        patch(
            "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
        ),
        patch("worker.tasks.reconciler.enqueue", AsyncMock()) as mock_enqueue,
    ):
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    mock_enqueue.assert_called_once_with(mock_redis, TASK_FINALIZE_GENERATION, job_id)


@pytest.mark.asyncio
async def test_reconcile_running_job_poll_failed_marks_failed_and_refunds(
    test_config: WorkerConfig,
) -> None:
    """Running job older than 30s polled as FAILED transitions to failed and refunds."""
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        model_id=model_id,
        status="running",
        provider_job_id="fake_pred_poll_fail_123",
        started_at=t0,
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

    now = t0 + timedelta(seconds=45)
    provider_status = ProviderStatus(
        state=ProviderJobState.FAILED,
        error_code="PROVIDER_CRASH",
        error_message="OOM killed",
    )

    with patch(
        "studio_providers.fake.FakeProvider.get_status", AsyncMock(return_value=provider_status)
    ):
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "PROVIDER_CRASH"
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_reconcile_stale_submitting_reverts_to_queued(test_config: WorkerConfig) -> None:
    """Submitting job with stale heartbeat (> 3 min) reverts to queued and increments attempt."""
    db = MockDB()
    job_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        status="submitting",
        attempt=0,
        max_attempts=3,
        heartbeat_at=t0,
        queued_at=t0,
    )
    db.add_job(job_dict)

    pool = make_mock_pool(db.make_conn())
    mock_redis = AsyncMock()
    ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": test_config}

    now = t0 + timedelta(minutes=4)

    with patch("worker.tasks.reconciler.enqueue", AsyncMock()) as mock_enqueue:
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    assert job_dict["status"] == "queued"
    assert job_dict["attempt"] == 1
    mock_enqueue.assert_called_once_with(mock_redis, TASK_RUN_GENERATION, job_id)


@pytest.mark.asyncio
async def test_reconcile_stale_submitting_exhausted_attempts_fails(
    test_config: WorkerConfig,
) -> None:
    """Submitting job with stale heartbeat that exhausted max_attempts transitions to failed."""
    db = MockDB()
    job_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        status="submitting",
        attempt=2,
        max_attempts=3,
        heartbeat_at=t0,
        queued_at=t0,
    )
    db.add_job(job_dict)

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

    now = t0 + timedelta(minutes=4)

    reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    assert job_dict["status"] == "failed"
    assert job_dict["error_code"] == "SUBMIT_TIMEOUT"
    refunds = [e for e in db.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"]
    assert len(refunds) == 1


@pytest.mark.asyncio
async def test_reconcile_stuck_queued_reenqueues(test_config: WorkerConfig) -> None:
    """Queued job older than 2 minutes gets re-enqueued to Redis."""
    db = MockDB()
    job_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        status="queued",
        queued_at=t0,
    )
    db.add_job(job_dict)

    pool = make_mock_pool(db.make_conn())
    mock_redis = AsyncMock()
    ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": test_config}

    now = t0 + timedelta(minutes=3)

    with patch("worker.tasks.reconciler.enqueue", AsyncMock()) as mock_enqueue:
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    mock_enqueue.assert_called_once_with(mock_redis, TASK_RUN_GENERATION, job_id)


@pytest.mark.asyncio
async def test_reconcile_stale_finalizing_reenqueues(test_config: WorkerConfig) -> None:
    """Finalizing job stale for > 5 minutes gets re-enqueued to finalize_generation."""
    db = MockDB()
    job_id = uuid.uuid4()
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    job_dict = make_job_row(
        job_id=job_id,
        status="finalizing",
        heartbeat_at=t0,
        queued_at=t0,
    )
    db.add_job(job_dict)

    pool = make_mock_pool(db.make_conn())
    mock_redis = AsyncMock()
    ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": test_config}

    now = t0 + timedelta(minutes=6)

    with patch("worker.tasks.reconciler.enqueue", AsyncMock()) as mock_enqueue:
        reconciled = await reconcile_jobs(ctx, now=now)

    assert reconciled >= 1
    mock_enqueue.assert_called_once_with(mock_redis, TASK_FINALIZE_GENERATION, job_id)


@pytest.mark.asyncio
async def test_reconcile_skip_locked_query_syntax(test_config: WorkerConfig) -> None:
    """Verify reconciliation queries use FOR UPDATE SKIP LOCKED to prevent races."""
    db = MockDB()
    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    queries_run: list[str] = []

    # Intercept queries
    async def intercept_fetch(query: str, *params: Any) -> list[dict[str, Any]]:
        queries_run.append(query)
        return []

    conn = db.make_conn()
    conn.fetch.side_effect = intercept_fetch
    pool.acquire.return_value.__aenter__.return_value = conn

    await reconcile_jobs(ctx)

    assert len(queries_run) >= 4
    for q in queries_run:
        assert "FOR UPDATE SKIP LOCKED" in q
