"""T3.1 — FastAPI skeleton, auth, errors, and health endpoint tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.main import create_app

from .conftest import make_jwt

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_app_with_db(mock_conn: AsyncMock) -> FastAPI:
    """Build a test app where the DB pool always yields mock_conn."""
    app = create_app()
    # Patch the pool acquire context manager
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.close = AsyncMock()
    app.state.db_pool = mock_pool
    app.state.redis_pool = None
    return app


# ── Auth tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_jwt_is_accepted() -> None:
    """A valid JWT returns the CurrentUser."""
    uid = uuid.uuid4()
    token = make_jwt(uid)

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    app = _make_app_with_db(mock_conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    # Workspaces endpoint returns 200 with empty list — auth passed
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_auth_returns_401() -> None:
    """Requests without Authorization header get 401."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/workspaces")
    assert resp.status_code == 401
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["error_code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_expired_jwt_returns_401() -> None:
    """An expired token returns 401 with TOKEN_EXPIRED error code."""
    token = make_jwt(expired=True)
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_invalid_jwt_returns_401() -> None:
    """A garbage token returns 401 with INVALID_TOKEN."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/workspaces", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "INVALID_TOKEN"


# ── Problem+JSON shape ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_problem_json_shape() -> None:
    """Error responses must conform to RFC 7807 shape."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/workspaces")  # missing auth
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    required_fields = {"type", "title", "status", "detail", "error_code"}
    assert required_fields.issubset(body.keys())
    assert body["status"] == resp.status_code


# ── Request ID ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_id_is_propagated() -> None:
    """X-Request-ID sent by the client is echoed back in the response headers."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    custom_rid = "my-request-id-abc"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz", headers={"X-Request-ID": custom_rid})
    assert resp.headers.get("x-request-id") == custom_rid


@pytest.mark.asyncio
async def test_request_id_generated_when_absent() -> None:
    """When no X-Request-ID is sent, the server generates one."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
    rid = resp.headers.get("x-request-id")
    assert rid is not None and len(rid) > 8


# ── Health endpoints ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_healthz_always_200() -> None:
    """/healthz returns 200 with status ok."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_ok_when_db_reachable() -> None:
    """/readyz returns 200 when DB is reachable."""
    app = create_app()

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["checks"]["db"] == "ok"


@pytest.mark.asyncio
async def test_readyz_503_when_db_unreachable() -> None:
    """/readyz returns 503 when DB connection fails."""
    app = create_app()

    mock_pool = MagicMock()
    enter_mock = AsyncMock(side_effect=ConnectionRefusedError("no DB"))
    mock_pool.acquire.return_value.__aenter__ = enter_mock
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["checks"]["db"] == "error"


# ── /docs renders ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openapi_docs_render() -> None:
    """/docs returns HTML (uvicorn starts and /docs renders)."""
    app = create_app()
    app.state.db_pool = MagicMock()
    app.state.redis_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
