"""T3.6 — Webhook receiver tests.

Tests: bad token → 401, duplicate delivery → 200 no-op, unknown job → 404,
terminal job → 200 no-op, valid webhook enqueues finalize exactly once.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from studio_core.settings import get_settings


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
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    return conn


def _make_token(job_id: UUID) -> str:
    """Compute the expected HMAC token for a job ID."""
    settings = get_settings()
    return hmac.new(
        settings.webhook_signing_secret.encode(),
        msg=str(job_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _job_row(job_id: UUID, status: str = "running") -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": job_id,
        "workspace_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
        "model_id": uuid.uuid4(),
        "task_type": "text_to_image",
        "status": status,
        "prompt": "test",
        "negative_prompt": None,
        "params": "{}",
        "idempotency_key": None,
        "provider_job_id": "prov-123",
        "attempt": 0,
        "max_attempts": 3,
        "error_code": None,
        "error_message": None,
        "cost_credits": "1.00",
        "parent_job_id": None,
        "workflow_run_id": None,
        "queued_at": now,
        "started_at": now,
        "completed_at": None,
        "heartbeat_at": now,
    }


@pytest.fixture()
def fake_provider_patch() -> Any:
    """Patch studio_providers.registry.get_provider to return a mock adapter."""
    mock_adapter = MagicMock()
    mock_event = MagicMock()
    mock_event.provider_id = "fake"
    mock_event.provider_job_id = "prov-123"
    mock_adapter.verify_webhook = MagicMock(return_value=mock_event)

    with patch("api.routers.webhooks.get_provider", return_value=mock_adapter) as p:
        yield p


# ── Bad token ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_bad_token_returns_401(fake_provider_patch: Any) -> None:
    job_id = uuid.uuid4()
    conn = _mock_conn()
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/internal/webhooks/fake/{job_id}?token=badtoken",
            content=b'{"status": "succeeded"}',
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 401


# ── Unknown job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_unknown_job_returns_404(fake_provider_patch: Any) -> None:
    job_id = uuid.uuid4()
    token = _make_token(job_id)
    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)  # job not found
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/internal/webhooks/fake/{job_id}?token={token}",
            content=b'{"status": "succeeded"}',
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 404


# ── Terminal job (no-op) ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_terminal_job_returns_200_noop(fake_provider_patch: Any) -> None:
    job_id = uuid.uuid4()
    token = _make_token(job_id)
    job = _job_row(job_id, status="succeeded")

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "generation_jobs" in query and "WHERE id" in query:
            return job
        if "job_events" in query and "INSERT" in query:
            return {
                "id": 1,
                "job_id": job_id,
                "type": "webhook",
                "from_status": None,
                "to_status": None,
                "payload": None,
                "created_at": datetime.now(UTC),
            }
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/internal/webhooks/fake/{job_id}?token={token}",
            content=b'{"status": "succeeded"}',
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "no-op"


# ── Valid webhook (running → finalizing) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_valid_enqueues_finalize_once(fake_provider_patch: Any) -> None:
    """A valid webhook for a running job transitions to finalizing and enqueues finalize."""
    job_id = uuid.uuid4()
    token = _make_token(job_id)
    job = _job_row(job_id, status="running")
    updated_job = dict(job)
    updated_job["status"] = "finalizing"

    enqueue_calls: list[str] = []

    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "UPDATE public.generation_jobs" in query:
            return updated_job  # transition succeeded
        if "SELECT" in query and "generation_jobs" in query:
            return job
        if "job_events" in query and "INSERT" in query:
            return {
                "id": 1,
                "job_id": job_id,
                "type": "state_change",
                "from_status": None,
                "to_status": None,
                "payload": None,
                "created_at": datetime.now(UTC),
            }
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    app = _make_app(conn)

    async def mock_enqueue(pool: Any, task_name: str, jid: UUID, **kwargs: Any) -> None:
        enqueue_calls.append(task_name)

    with patch("api.routers.webhooks.enqueue", side_effect=mock_enqueue):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/internal/webhooks/fake/{job_id}?token={token}",
                content=b'{"status": "succeeded"}',
                headers={"Content-Type": "application/json"},
            )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    # finalize should have been enqueued exactly once
    assert enqueue_calls.count("finalize_generation") == 1


# ── Duplicate delivery (idempotent via ARQ dedup) ─────────────────────────────


@pytest.mark.asyncio
async def test_webhook_duplicate_delivery_is_noop(fake_provider_patch: Any) -> None:
    """Second delivery for a finalizing job results in 200 with no additional enqueue."""
    job_id = uuid.uuid4()
    token = _make_token(job_id)
    # Job is already finalizing (transition already done)
    job = _job_row(job_id, status="finalizing")

    enqueue_calls: list[str] = []
    conn = _mock_conn()

    async def fetchrow_se(query: str, *args: Any) -> dict[str, Any] | None:
        if "generation_jobs" in query and "WHERE id =" in query:
            return job
        if "job_events" in query and "INSERT" in query:
            return {
                "id": 2,
                "job_id": job_id,
                "type": "webhook",
                "from_status": None,
                "to_status": None,
                "payload": None,
                "created_at": datetime.now(UTC),
            }
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_se)
    app = _make_app(conn)

    async def mock_enqueue(pool: Any, task_name: str, jid: UUID, **kwargs: Any) -> None:
        enqueue_calls.append(task_name)

    with patch("api.routers.webhooks.enqueue", side_effect=mock_enqueue):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(2):
                resp = await client.post(
                    f"/internal/webhooks/fake/{job_id}?token={token}",
                    content=b'{"status": "succeeded"}',
                    headers={"Content-Type": "application/json"},
                )
                assert resp.status_code == 200

    # No finalize should have been enqueued (job was already finalizing)
    assert "finalize_generation" not in enqueue_calls
