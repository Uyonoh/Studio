"""T7.2 — worker Sentry capture and job context."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from worker.config import WorkerConfig
from worker.fixtures import MockDB, make_job_row, make_mock_pool, make_model_row
from worker.tasks.run_generation import run_generation


class _FailingProvider:
    """Provider stub that raises an unexpected (non-domain) error."""

    async def submit(self, request: Any) -> None:
        raise RuntimeError("T7.2 forced worker error")

    async def cancel(self, ref: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_unexpected_provider_error_is_captured_with_job_context(
    test_config: WorkerConfig,
) -> None:
    db = MockDB()
    job_id = uuid.uuid4()
    model_id = uuid.uuid4()

    job_dict = make_job_row(job_id=job_id, model_id=model_id, status="queued")
    model_dict = make_model_row(model_id=model_id, provider_id="fake")
    db.add_job(job_dict)
    db.add_model(model_dict)

    pool = make_mock_pool(db.make_conn())
    ctx = {"db_pool": pool, "redis_pool": None, "config": test_config}

    with (
        patch(
            "worker.tasks.run_generation.get_provider",
            return_value=_FailingProvider(),
        ),
        patch("worker.tasks.run_generation.capture_exception") as capture,
    ):
        await run_generation(ctx, job_id)

    assert job_dict["status"] == "failed"
    capture.assert_called_once()
    kwargs = capture.call_args.kwargs
    assert kwargs["job_id"] == str(job_id)
    assert kwargs["provider"] == "fake"
    assert kwargs["model"] == model_dict["slug"]
    assert kwargs["status"] == "failed"
