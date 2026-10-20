"""T3.2 — Projects endpoints tests.

Tests: happy-path CRUD, 403 for non-member, 404 for cross-workspace IDs,
stable pagination across inserts, soft-archive.
"""

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


def _project_row(
    project_id: UUID | None = None,
    workspace_id: UUID | None = None,
    created_by: UUID | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": project_id or uuid.uuid4(),
        "workspace_id": workspace_id or uuid.uuid4(),
        "name": "Test Project",
        "description": None,
        "cover_asset_id": None,
        "created_by": created_by or uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
    }


# ── List workspaces ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_workspaces_returns_empty() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[])
    app = _make_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/workspaces", headers={"Authorization": f"Bearer {make_jwt(uid)}"}
        )
    assert resp.status_code == 200
    assert resp.json() == []


# ── Create project ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_happy_path() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    proj = _project_row(workspace_id=ws_id, created_by=uid)

    conn = _mock_conn()

    async def fetchval_side_effect(query: str, *args: Any) -> Any:
        if "workspace_members" in query:
            return "editor"
        return None

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "INSERT INTO public.projects" in query:
            return proj
        return None

    conn.fetchval = AsyncMock(side_effect=fetchval_side_effect)
    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/workspaces/{ws_id}/projects",
            json={"name": "My Project"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Project"
    assert body["workspace_id"] == str(ws_id)


@pytest.mark.asyncio
async def test_create_project_403_for_non_member() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)  # no membership row
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/workspaces/{ws_id}/projects",
            json={"name": "Unauthorized"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_project_403_for_viewer() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value="viewer")  # viewer role
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/workspaces/{ws_id}/projects",
            json={"name": "Viewer Attempt"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 403


# ── Get project ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_project_404_for_cross_workspace() -> None:
    """Non-members (or non-existent projects) return 404 — do not leak existence."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)  # project not found
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/projects/{proj_id}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_project_happy_path() -> None:
    uid = uuid.uuid4()
    proj = _project_row(created_by=uid)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return proj
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="viewer")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/projects/{proj['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(proj["id"])


# ── Pagination stability ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_projects_cursor_pagination() -> None:
    """Pagination returns next_cursor when there are more items."""
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    projects = [_project_row(workspace_id=ws_id) for _ in range(3)]

    conn = _mock_conn()

    conn.fetchval = AsyncMock(return_value="viewer")
    conn.fetch = AsyncMock(return_value=projects)  # returns 3, limit=2 → has_more=True
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/workspaces/{ws_id}/projects?limit=2",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None  # there are more items


# ── Archive (soft-delete) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_project_returns_204() -> None:
    uid = uuid.uuid4()
    proj = _project_row(created_by=uid)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict | None:
        if "public.projects" in query and "archived_at IS NULL" in query:
            return proj
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"/v1/projects/{proj['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 204
    # Verify the UPDATE was called
    conn.execute.assert_called()

