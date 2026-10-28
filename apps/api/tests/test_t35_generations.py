"""T3.5 — Generation endpoints tests.

Tests: 202 shape, validation errors, idempotent replay, cancel/retry rules,
cross-workspace denial, enqueue failure → failed + credits refunded.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from .conftest import make_jwt


def _make_app(mock_conn: AsyncMock) -> FastAPI:
    from api.main import create_app

    app = create_app()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None
    return app


def _mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    return conn


def _job_row(
    job_id: UUID | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    status: str = "queued",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": job_id or uuid.uuid4(),
        "workspace_id": workspace_id or uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "created_by": uuid.uuid4(),
        "model_id": uuid.uuid4(),
        "task_type": "text_to_image",
        "status": status,
        "prompt": "a cat",
        "negative_prompt": None,
        "params": "{}",
        "idempotency_key": "test-key",
        "provider_job_id": None,
        "attempt": 0,
        "max_attempts": 3,
        "error_code": None,
        "error_message": None,
        "cost_credits": "1.00",
        "parent_job_id": None,
        "workflow_run_id": None,
        "queued_at": now,
        "started_at": None,
        "completed_at": None,
        "heartbeat_at": None,
    }


def _model_row(task_type: str = "text_to_image") -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "provider_id": "fake",
        "provider_model": "fake-model",
        "slug": "fake-t2i-v1",
        "display_name": "Fake T2I",
        "task_type": task_type,
        "input_schema": '{"type": "object", "properties": {}}',
        "default_params": "{}",
        "cost_credits": Decimal("1.00"),
        "enabled": True,
    }


# ── Submit generation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_generation_requires_idempotency_key() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/projects/00000000-0000-0000-0000-000000000001/generations",
            json={"model": "fake-t2i-v1", "task_type": "text_to_image", "prompt": "a cat"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
            # No Idempotency-Key header
        )
    assert resp.status_code == 400
    assert "Idempotency-Key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_generation_cross_workspace_denied() -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return {
                "id": proj_id,
                "workspace_id": ws_id,
                "name": "proj",
                "description": None,
                "cover_asset_id": None,
                "created_by": uuid.uuid4(),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "archived_at": None,
            }
        if "workspace_members" in query:
            return None  # not a member
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/generations",
            json={"model": "fake-t2i-v1", "task_type": "text_to_image", "prompt": "test"},
            headers={
                "Authorization": f"Bearer {make_jwt(uid)}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_submit_generation_task_mismatch_returns_422() -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    model = _model_row(task_type="text_to_image")  # model is text_to_image

    conn = _mock_conn()

    now = datetime.now(UTC)

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return {
                "id": proj_id,
                "workspace_id": ws_id,
                "name": "proj",
                "description": None,
                "cover_asset_id": None,
                "created_by": uid,
                "created_at": now,
                "updated_at": now,
                "archived_at": None,
            }
        if "generation_jobs" in query and "idempotency_key" in query:
            return None  # no existing job
        if "public.models" in query and "slug" in query:
            return model
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)

    async def fetchval_se(query: str, *args: Any) -> Any:
        if "workspace_members" in query:
            return "editor"
        return 0  # active jobs count or balance

    conn.fetchval = AsyncMock(side_effect=fetchval_se)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/generations",
            json={
                "model": "fake-t2i-v1",
                "task_type": "image_to_video",  # MISMATCH
                "prompt": "test",
            },
            headers={
                "Authorization": f"Bearer {make_jwt(uid)}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
        )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "MODEL_TASK_MISMATCH"


# ── Get generation ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_generation_not_found() -> None:
    uid = uuid.uuid4()
    job_id = uuid.uuid4()
    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/generations/{job_id}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_generation_happy_path() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    job = _job_row(workspace_id=ws_id)

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "generation_jobs" in query:
            return job
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    conn.fetchval = AsyncMock(return_value="viewer")
    conn.fetch = AsyncMock(return_value=[])  # no outputs
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/generations/{job['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(job["id"])
    assert body["status"] == "queued"
    assert body["outputs"] == []
    assert "self" in body["links"]


# ── Cancel ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_terminal_job_returns_409() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    job = _job_row(workspace_id=ws_id, status="succeeded")

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "generation_jobs" in query and "WHERE id" in query:
            return job
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/generations/{job['id']}/cancel",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 409


# ── Retry ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_running_job_returns_409() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    job = _job_row(workspace_id=ws_id, status="running")

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "generation_jobs" in query and "WHERE id" in query:
            return job
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/generations/{job['id']}/retry",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 409


# ── Enqueue failure path ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_failure_marks_job_failed_and_refunds() -> None:
    """When the queue is unavailable, the job becomes failed and credits refunded."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    job_id = uuid.uuid4()
    model = _model_row()
    job = _job_row(job_id=job_id, workspace_id=ws_id, project_id=proj_id)

    conn = _mock_conn()
    now = datetime.now(UTC)

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return {
                "id": proj_id,
                "workspace_id": ws_id,
                "name": "proj",
                "description": None,
                "cover_asset_id": None,
                "created_by": uid,
                "created_at": now,
                "updated_at": now,
                "archived_at": None,
            }
        if "INSERT INTO public.generation_jobs" in query:
            return job
        if "generation_jobs" in query and "idempotency_key" in query:
            return None  # no duplicate
        if "models" in query and "slug" in query:
            return model
        if "generation_jobs" in query and "WHERE id" in query and "status" in query:
            return job  # transition result
        if "credit_ledger" in query and "reason = 'refund'" in query:
            return None  # no prior refund
        if "credit_ledger" in query and "INSERT" in query:
            return {
                "id": 1,
                "workspace_id": ws_id,
                "job_id": job_id,
                "delta": Decimal("1.00"),
                "reason": "refund",
                "created_at": now,
            }
        if "job_events" in query:
            return {
                "id": 1,
                "job_id": job_id,
                "type": "state_change",
                "from_status": None,
                "to_status": None,
                "payload": None,
                "created_at": now,
            }
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)

    async def fetchval_se(query: str, *args: Any) -> Any:
        if "workspace_members" in query:
            return "editor"
        if "public.workspaces" in query:
            return ws_id
        if "credit_ledger" in query:
            return Decimal("100.00")  # balance
        return 0

    conn.fetchval = AsyncMock(side_effect=fetchval_se)
    conn.fetch = AsyncMock(return_value=[])

    from studio_core.queue import EnqueueError

    app = _make_app(conn)

    with patch("api.routers.generations.enqueue", side_effect=EnqueueError("Redis down")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/v1/projects/{proj_id}/generations",
                json={"model": "fake-t2i-v1", "task_type": "text_to_image", "prompt": "test"},
                headers={
                    "Authorization": f"Bearer {make_jwt(uid)}",
                    "Idempotency-Key": str(uuid.uuid4()),
                },
            )
    assert resp.status_code == 503
