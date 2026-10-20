"""T3.3 / T3.4 — Asset endpoints and models endpoint tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from .conftest import make_jwt


def _make_app(mock_conn: AsyncMock):
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


def _asset_row(
    asset_id: UUID | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    kind: str = "image",
    origin: str = "upload",
    mime_type: str = "image/png",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": asset_id or uuid.uuid4(),
        "workspace_id": workspace_id or uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "kind": kind,
        "origin": origin,
        "storage_bucket": "media",
        "storage_path": "ws/proj/asset/file.png",
        "thumbnail_path": None,
        "mime_type": mime_type,
        "size_bytes": 12345,
        "width": 512,
        "height": 512,
        "duration_ms": None,
        "fps": None,
        "source_job_id": None,
        "parent_asset_id": None,
        "metadata": '{"status": "ready"}',
        "created_by": uuid.uuid4(),
        "created_at": now,
        "deleted_at": None,
    }


# ── Upload request ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_request_upload_returns_201_and_url() -> None:
    """POST /assets/uploads creates draft and returns signed URL."""
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id, project_id=proj_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "projects" in query and "archived_at IS NULL" in query:
            return {"workspace_id": ws_id}
        if "INSERT INTO public.assets" in query:
            return asset
        if "assets" in query and "storage_path" in query:
            return {"id": asset["id"]}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={"mime_type": "image/png", "size_bytes": 1024, "filename": "test.png"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "asset_id" in body
    assert "upload_url" in body


@pytest.mark.asyncio
async def test_request_upload_rejects_non_media_mime() -> None:
    """Non image/* or video/* MIME types get 415."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "projects" in query:
            return {"workspace_id": ws_id}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={"mime_type": "application/pdf", "size_bytes": 1024, "filename": "doc.pdf"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_request_upload_rejects_oversized() -> None:
    """Files exceeding 500 MB get 413."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "projects" in query:
            return {"workspace_id": ws_id}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={
                "mime_type": "image/png",
                "size_bytes": 600 * 1024 * 1024,  # 600 MB
                "filename": "huge.png",
            },
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 413


# ── Get asset ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_asset_happy_path() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "public.assets" in query:
            return asset
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="viewer")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/assets/{asset['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(asset["id"])
    assert body["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_get_asset_404_if_not_found() -> None:
    uid = uuid.uuid4()
    asset_id = uuid.uuid4()
    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 404


# ── Soft delete ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_asset_returns_204() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "public.assets" in query:
            return asset
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"/v1/assets/{asset['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 204


# ── Models endpoint ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_models_returns_enabled_models() -> None:
    uid = uuid.uuid4()
    model_row = {
        "id": uuid.uuid4(),
        "provider_id": "fake",
        "provider_model": "fake-t2i",
        "slug": "fake-img-v1",
        "display_name": "Fake Image v1",
        "task_type": "text_to_image",
        "input_schema": '{"type": "object", "properties": {}}',
        "default_params": "{}",
        "cost_credits": "1.00",
        "enabled": True,
    }

    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[model_row])
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) == 1
    assert models[0]["slug"] == "fake-img-v1"
    assert models[0]["task_type"] == "text_to_image"
    assert "Cache-Control" in resp.headers


@pytest.mark.asyncio
async def test_list_models_filter_by_task_type() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[])  # filtered result
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models?task_type=text_to_image",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_models_rejects_invalid_task_type() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models?task_type=invalid_type",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 400
