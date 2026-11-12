"""Workspace settings endpoints — rename and credit activity.

Covers role checks, ledger pagination, running balances, and the activity
summary backing the settings screen.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
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
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    return conn


def _transaction_row(
    entry_id: int,
    workspace_id: UUID,
    *,
    delta: str = "-4.00",
    reason: str = "reserve",
    balance_after: str = "96.00",
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "workspace_id": workspace_id,
        "job_id": uuid.uuid4(),
        "delta": Decimal(delta),
        "reason": reason,
        "created_at": datetime.now(UTC),
        "balance_after": Decimal(balance_after),
        "model_name": "Flux 1.1 Pro",
        "job_status": "succeeded",
        "prompt": "A neon cityscape",
    }


# ── Rename workspace ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_workspace_renames_for_owner() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value="owner")

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "UPDATE public.workspaces" in query:
            return {"id": ws_id, "name": "Renamed Lab", "owner_id": uid}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/v1/workspaces/{ws_id}",
            json={"name": "  Renamed Lab  "},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "id": str(ws_id),
        "name": "Renamed Lab",
        "owner_id": str(uid),
    }


@pytest.mark.asyncio
async def test_update_workspace_forbidden_for_editor() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/v1/workspaces/{ws_id}",
            json={"name": "Renamed Lab"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_workspace_rejects_blank_name() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value="admin")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/v1/workspaces/{ws_id}",
            json={"name": "   "},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 422
    conn.fetchrow.assert_not_called()


# ── Credit transactions ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_credit_transactions_paginates_and_includes_summary() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value="viewer")
    rows = [
        _transaction_row(3, ws_id),
        _transaction_row(2, ws_id, delta="4.00", reason="refund", balance_after="100.00"),
        _transaction_row(1, ws_id, delta="100.00", reason="grant", balance_after="96.00"),
    ]
    conn.fetch = AsyncMock(return_value=rows)
    conn.fetchrow = AsyncMock(
        return_value={
            "spent": Decimal("4.00"),
            "refunded": Decimal("4.00"),
            "granted": Decimal("100.00"),
            "transactions": 3,
        }
    )
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/workspaces/{ws_id}/credits/transactions?limit=2",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == 3
    assert body["items"][0]["balance_after"] == "96.00"
    assert body["items"][0]["model_name"] == "Flux 1.1 Pro"
    assert body["next_before_id"] == 2
    assert body["summary"] == {
        "window_days": 30,
        "spent": "4.00",
        "refunded": "4.00",
        "granted": "100.00",
        "transactions": 3,
    }


@pytest.mark.asyncio
async def test_list_credit_transactions_forbidden_for_non_member() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()
    conn.fetchval = AsyncMock(return_value=None)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/workspaces/{ws_id}/credits/transactions",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 403
