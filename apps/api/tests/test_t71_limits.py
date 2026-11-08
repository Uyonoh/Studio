"""T7.1 — rate limits, quotas, and abuse controls."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from api.auth import CurrentUser
from api.rate_limit import TokenBucketRateLimiter, _enforce
from studio_core.credits import CreditService
from studio_core.generation import (
    ContentRejectedError,
    GenerationService,
    GenerationSubmitRequest,
    PromptTooLongError,
)
from studio_core.models import Project, TaskType, WorkspaceRole
from studio_core.moderation import StaticModerationService
from studio_core.repositories import JobRepository, ModelRepository, ProjectRepository

from .conftest import make_jwt


class FakeRedis:
    """Minimal Redis stub implementing the token-bucket Lua contract."""

    def __init__(self) -> None:
        self.buckets: dict[str, tuple[float, float]] = {}
        self.fail = False

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        capacity: float,
        refill_per_second: float,
        now: float,
        cost: float,
    ) -> list[int]:
        if self.fail:
            raise RuntimeError("redis unavailable")

        capacity = float(capacity)
        refill_per_second = float(refill_per_second)
        now = float(now)
        cost = float(cost)

        tokens, ts = self.buckets.get(key, (capacity, now))
        tokens = min(capacity, tokens + max(0.0, now - ts) * refill_per_second)

        if tokens >= cost:
            tokens -= cost
            allowed = 1
            retry_after_ms = 0
        else:
            allowed = 0
            retry_after_ms = math.ceil(((cost - tokens) / refill_per_second) * 1000)

        self.buckets[key] = (tokens, now)
        return [allowed, retry_after_ms]


def _make_app(conn: AsyncMock) -> FastAPI:
    from api.main import create_app

    app = create_app()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None
    return app


def _project_row(project_id: UUID, workspace_id: UUID, user_id: UUID) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": project_id,
        "workspace_id": workspace_id,
        "name": "Limit test project",
        "description": None,
        "cover_asset_id": None,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
    }


def _settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "rate_limit_enabled": True,
        "rate_limit_submit_per_minute": 20,
        "rate_limit_upload_per_minute": 30,
        "max_prompt_chars": 4000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# ── Token bucket ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_triggers_and_resets_after_refill() -> None:
    now = [1_000.0]
    limiter = TokenBucketRateLimiter(FakeRedis(), clock=lambda: now[0])

    for _ in range(2):
        result = await limiter.acquire("bucket:user:1", capacity=2, refill_per_second=1 / 60)
        assert result.allowed

    blocked = await limiter.acquire("bucket:user:1", capacity=2, refill_per_second=1 / 60)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 60

    # A full minute of refill restores one token.
    now[0] += 60
    recovered = await limiter.acquire("bucket:user:1", capacity=2, refill_per_second=1 / 60)
    assert recovered.allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_fails_open_when_redis_is_unavailable() -> None:
    redis = FakeRedis()
    redis.fail = True
    limiter = TokenBucketRateLimiter(redis)

    result = await limiter.acquire("bucket:user:1", capacity=1, refill_per_second=1 / 60)

    assert result.allowed is True
    assert result.retry_after_seconds == 0


@pytest.mark.asyncio
async def test_rate_limit_workspace_bucket_is_shared_across_users() -> None:
    limiter = TokenBucketRateLimiter(FakeRedis(), clock=lambda: 1_000.0)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(rate_limiter=limiter)))
    workspace_id = uuid.uuid4()

    await _enforce(
        request,  # type: ignore[arg-type]
        CurrentUser(id=uuid.uuid4()),
        bucket="submit",
        limit_per_minute=1,
        workspace_id=workspace_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _enforce(
            request,  # type: ignore[arg-type]
            CurrentUser(id=uuid.uuid4()),
            bucket="submit",
            limit_per_minute=1,
            workspace_id=workspace_id,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "60"}
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["error_code"] == "RATE_LIMITED"


# ── API integration ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_rate_limit_returns_429_with_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"workspace_id": ws_id})
    conn.fetchval = AsyncMock(return_value="editor")
    conn.fetch = AsyncMock(return_value=[])

    app = _make_app(conn)
    limiter = TokenBucketRateLimiter(FakeRedis(), clock=lambda: 1_000.0)
    # Exhaust the caller's personal submit bucket.
    await limiter.acquire(f"ratelimit:submit:user:{uid}", capacity=1, refill_per_second=1 / 60)
    app.state.rate_limiter = limiter

    monkeypatch.setattr(
        "api.rate_limit.get_settings",
        lambda: _settings(rate_limit_submit_per_minute=1),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/v1/projects/{proj_id}/generations",
            headers={
                "Authorization": f"Bearer {make_jwt(uid)}",
                "Idempotency-Key": "limit-test-key",
            },
            json={"model": "some-model", "task_type": "text_to_image", "prompt": "hello"},
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    body = response.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert body["retry_after_seconds"] == 60


@pytest.mark.asyncio
async def test_upload_rate_limit_returns_429_with_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"workspace_id": ws_id})
    conn.fetchval = AsyncMock(return_value="editor")
    conn.fetch = AsyncMock(return_value=[])

    app = _make_app(conn)
    limiter = TokenBucketRateLimiter(FakeRedis(), clock=lambda: 1_000.0)
    await limiter.acquire(f"ratelimit:upload:user:{uid}", capacity=1, refill_per_second=1 / 60)
    app.state.rate_limiter = limiter

    monkeypatch.setattr(
        "api.rate_limit.get_settings",
        lambda: _settings(rate_limit_upload_per_minute=1),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
            json={"filename": "photo.png", "mime_type": "image/png", "size_bytes": 1024},
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["error_code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_moderation_content_limit_rejects_prompt_without_reserving_credits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    project_row = _project_row(proj_id, ws_id, uid)

    conn = AsyncMock()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return project_row
        if "generation_jobs" in query and "idempotency_key" in query:
            return None
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    conn.fetch = AsyncMock(return_value=[])

    app = _make_app(conn)
    app.state.moderation_service = StaticModerationService(["forbidden"])

    monkeypatch.setattr(
        "studio_core.generation.get_settings",
        lambda: _settings(),
    )

    with patch.object(CreditService, "reserve", new_callable=AsyncMock) as reserve:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/v1/projects/{proj_id}/generations",
                headers={
                    "Authorization": f"Bearer {make_jwt(uid)}",
                    "Idempotency-Key": "moderation-test-key",
                },
                json={
                    "model": "some-model",
                    "task_type": "text_to_image",
                    "prompt": "a forbidden image",
                },
            )

    assert response.status_code == 422
    assert response.json()["error_code"] == "CONTENT_REJECTED"
    reserve.assert_not_awaited()


# ── Prompt length limits ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prompt_length_limit_rejects_before_model_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="Limit test project",
        created_by=uid,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    conn = AsyncMock()
    svc = GenerationService(conn)
    request = GenerationSubmitRequest(
        model="some-model",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="x" * 4001,
    )

    monkeypatch.setattr(
        "studio_core.generation.get_settings",
        lambda: _settings(max_prompt_chars=4000),
    )

    with (
        patch.object(ProjectRepository, "get_by_id", AsyncMock(return_value=project)),
        patch.object(
            ProjectRepository,
            "get_member_role",
            AsyncMock(return_value=WorkspaceRole.EDITOR),
        ),
        patch.object(JobRepository, "get_by_idempotency_key", AsyncMock(return_value=None)),
        patch.object(ModelRepository, "get_by_slug", new_callable=AsyncMock) as get_by_slug,
        patch.object(CreditService, "reserve", new_callable=AsyncMock) as reserve,
    ):
        with pytest.raises(PromptTooLongError) as exc_info:
            await svc.create_job(uid, proj_id, request, "too-long-key")

    assert exc_info.value.code == "PROMPT_TOO_LONG"
    assert "4000" in exc_info.value.message
    get_by_slug.assert_not_awaited()
    reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_moderation_service_rejects_before_credit_reservation() -> None:
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="Limit test project",
        created_by=uid,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    conn = AsyncMock()
    svc = GenerationService(conn, moderation_service=StaticModerationService(["blocked"]))
    request = GenerationSubmitRequest(
        model="some-model",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="blocked content",
    )

    with (
        patch.object(ProjectRepository, "get_by_id", AsyncMock(return_value=project)),
        patch.object(
            ProjectRepository,
            "get_member_role",
            AsyncMock(return_value=WorkspaceRole.EDITOR),
        ),
        patch.object(JobRepository, "get_by_idempotency_key", AsyncMock(return_value=None)),
        patch.object(CreditService, "reserve", new_callable=AsyncMock) as reserve,
    ):
        with pytest.raises(ContentRejectedError) as exc_info:
            await svc.create_job(uid, proj_id, request, "blocked-key")

    assert exc_info.value.code == "CONTENT_REJECTED"
    reserve.assert_not_awaited()
