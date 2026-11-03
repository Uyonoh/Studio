"""T7.2 — Sentry context, structured transitions, and admin stats."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from api.auth import AuthUser
from studio_core.models import JobStatus
from studio_core.observability import init_sentry
from studio_core.state_machine import JobStateMachine

from .conftest import make_jwt


def _make_app(conn: AsyncMock) -> FastAPI:
    from api.main import create_app

    app = create_app()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None
    return app


def _admin_settings(user_id: uuid.UUID | None = None, raw: str = "") -> SimpleNamespace:
    value = raw or (str(user_id) if user_id else "")
    return SimpleNamespace(admin_user_ids=value)


# ── Sentry initialisation ─────────────────────────────────────────────────────


def test_init_sentry_is_a_noop_without_a_dsn() -> None:
    assert init_sentry(service="api", dsn=None, environment="local") is False
    assert init_sentry(service="api", dsn="", environment="local") is False


# ── Auth context ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_sets_request_state_and_sentry_user_context() -> None:
    uid = uuid.uuid4()
    app = _make_app(AsyncMock())

    @app.get("/v1/whoami")
    async def whoami(request: Request, user: AuthUser) -> dict[str, str]:
        return {"user_id": request.state.user_id, "email": user.email or ""}

    with patch("api.auth.set_request_context") as set_context:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/whoami", headers={"Authorization": f"Bearer {make_jwt(uid)}"}
            )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(uid)
    set_context.assert_called_once()
    assert set_context.call_args.kwargs["user_id"] == str(uid)
    assert set_context.call_args.kwargs["path"] == "/v1/whoami"


# ── 500 handler ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_error_handler_captures_exception_with_request_context() -> None:
    app = _make_app(AsyncMock())

    @app.get("/v1/boom")
    async def boom(request: Request) -> None:
        request.state.user_id = "user-123"
        raise RuntimeError("T7.2 forced error")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    with patch("api.errors.capture_exception") as capture:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/boom", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"
    capture.assert_called_once()
    kwargs = capture.call_args.kwargs
    assert kwargs["request_id"] == "req-123"
    assert kwargs["path"] == "/v1/boom"
    assert kwargs["method"] == "GET"
    assert kwargs["user_id"] == "user-123"


# ── Structured transition logs ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_transition_logs_job_provider_model_and_duration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": job_id,
        "workspace_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "created_by": uuid.uuid4(),
        "model_id": uuid.uuid4(),
        "task_type": "text_to_image",
        "status": "submitting",
        "prompt": None,
        "negative_prompt": None,
        "params": {},
        "idempotency_key": None,
        "provider_job_id": None,
        "attempt": 0,
        "max_attempts": 3,
        "error_code": None,
        "error_message": None,
        "cost_credits": Decimal("1.00"),
        "parent_job_id": None,
        "workflow_run_id": None,
        "queued_at": now - timedelta(seconds=2),
        "started_at": None,
        "completed_at": None,
        "heartbeat_at": now,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=row)
    machine = JobStateMachine(conn)
    machine.event_repo.append = AsyncMock()  # type: ignore[method-assign]

    with caplog.at_level(logging.INFO, logger="studio_core.state_machine"):
        job = await machine.transition(
            job_id,
            expected=JobStatus.QUEUED,
            new=JobStatus.SUBMITTING,
            provider_id="fake",
            model_slug="img-fast-v1",
        )

    assert job is not None
    record = next(
        record for record in caplog.records if getattr(record, "event", None) == "job_transition"
    )
    assert record.job_id == str(job_id)  # type: ignore[attr-defined]
    assert record.provider == "fake"  # type: ignore[attr-defined]
    assert record.model == "img-fast-v1"  # type: ignore[attr-defined]
    assert record.from_status == "queued"  # type: ignore[attr-defined]
    assert record.status == "submitting"  # type: ignore[attr-defined]
    assert record.duration_ms is not None  # type: ignore[attr-defined]
    assert record.duration_ms >= 2000  # type: ignore[attr-defined]


# ── Admin stats ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_stats_forbidden_for_non_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()
    app = _make_app(AsyncMock())
    monkeypatch.setattr("api.routers.admin.get_settings", lambda: _admin_settings(raw=""))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/stats", headers={"Authorization": f"Bearer {make_jwt(uid)}"}
        )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_stats_returns_aggregates_for_allowlisted_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()

    async def fetchrow(query: str, *args: Any) -> dict[str, Any] | None:
        if "WHERE status = 'queued'" in query:
            return {"depth": 3, "oldest_age_seconds": 42.5}
        if "interval '15 minutes'" in query:
            return {"failed": 2, "completed": 40}
        if "interval '24 hours'" in query:
            return {
                "avg_total_seconds": 41.7,
                "avg_queue_seconds": 3.1,
                "avg_run_seconds": 35.9,
                "completed_jobs": 300,
            }
        return None

    async def fetch(query: str, *args: Any) -> list[dict[str, Any]]:
        if "WITH transitions" in query:
            return [{"status": "queued", "avg_seconds": 4.2, "samples": 120}]
        if "JOIN public.models" in query:
            return [
                {
                    "provider_id": "replicate",
                    "jobs": 120,
                    "failed": 3,
                    "avg_latency_seconds": 28.4,
                    "cost_credits": Decimal("120.00"),
                }
            ]
        return []

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=fetchrow)
    conn.fetch = AsyncMock(side_effect=fetch)

    app = _make_app(conn)
    monkeypatch.setattr(
        "api.routers.admin.get_settings",
        lambda: _admin_settings(raw=f"someone-else, {uid}"),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/admin/stats", headers={"Authorization": f"Bearer {make_jwt(uid)}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["queue"] == {"depth": 3, "oldest_age_seconds": 42.5}
    assert body["failures"]["failure_rate"] == 0.05
    assert body["time_in_state"][0]["status"] == "queued"
    assert body["durations"]["avg_total_seconds"] == 41.7
    assert body["providers"][0]["provider_id"] == "replicate"
    assert body["providers"][0]["error_rate"] == 0.025
    assert body["providers"][0]["cost_credits"] == 120.0
