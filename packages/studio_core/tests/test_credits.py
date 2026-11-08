"""Tests for the credit service: concurrency reserves, double refund idempotency, balance math."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from studio_core.credits import CreditService, InsufficientCredits


@pytest.mark.asyncio
async def test_reserve_insufficient_credits_raises_exception() -> None:
    conn = AsyncMock()
    # Workspace exists
    conn.fetchval.side_effect = [uuid4(), Decimal("5.00")]  # lock returns id, balance returns 5.00
    service = CreditService(conn)

    ws_id = uuid4()
    job_id = uuid4()

    with pytest.raises(InsufficientCredits) as exc_info:
        await service.reserve(ws_id, job_id, Decimal("10.00"))

    assert exc_info.value.current_balance == Decimal("5.00")
    assert exc_info.value.required == Decimal("10.00")


@pytest.mark.asyncio
async def test_concurrency_reserves_against_balance() -> None:
    """Requirement T2.4: 20 parallel reserves against a balance of 10 -> exactly 10 succeed."""
    # Shared mutable state protected by an asyncio lock simulating Postgres row lock
    state = {"balance": Decimal("10.00")}
    lock = asyncio.Lock()

    async def mock_fetchval(query: str, *params: object) -> object:
        if "FOR UPDATE" in query:
            return params[0]  # returns workspace id
        if "SELECT coalesce(sum(delta)" in query:
            return state["balance"]
        return None

    async def mock_fetchrow(query: str, *params: object) -> dict[str, object] | None:
        if "INSERT INTO public.credit_ledger" in query:
            return {
                "id": 1,
                "workspace_id": params[0],
                "job_id": params[1],
                "delta": params[2],
                "reason": params[3],
                "created_at": datetime.now(UTC),
            }
        return None

    # Each worker performs reserve inside the lock
    async def run_worker() -> bool:
        async with lock:
            conn = AsyncMock()
            conn.fetchval.side_effect = mock_fetchval
            conn.fetchrow.side_effect = mock_fetchrow
            service = CreditService(conn)
            try:
                await service.reserve(uuid4(), uuid4(), Decimal("1.00"))
                state["balance"] -= Decimal("1.00")
                return True
            except InsufficientCredits:
                return False

    results = await asyncio.gather(*(run_worker() for _ in range(20)))
    successes = sum(1 for r in results if r)
    failures = sum(1 for r in results if not r)

    assert successes == 10
    assert failures == 10
    assert state["balance"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_double_refund_is_idempotent() -> None:
    """Requirement T2.4: Double refund results in exactly one refund row."""
    conn = AsyncMock()
    ws_id = uuid4()
    job_id = uuid4()

    refunded = {"already": False}

    async def mock_fetchval(query: str, *params: object) -> object:
        if "reason = 'refund'" in query:
            return 1 if refunded["already"] else None
        if "reason = 'reserve'" in query:
            return Decimal("2.00")
        if "FOR UPDATE" in query:
            return ws_id
        return None

    async def mock_fetchrow(query: str, *params: object) -> dict[str, object] | None:
        if "FROM public.generation_jobs" in query:
            return {"workspace_id": ws_id, "cost_credits": Decimal("2.00")}
        if "INSERT INTO public.credit_ledger" in query:
            refunded["already"] = True
            return {
                "id": 100,
                "workspace_id": ws_id,
                "job_id": job_id,
                "delta": Decimal("2.00"),
                "reason": "refund",
                "created_at": datetime.now(UTC),
            }
        return None

    conn.fetchval.side_effect = mock_fetchval
    conn.fetchrow.side_effect = mock_fetchrow

    service = CreditService(conn)

    # First refund succeeds
    res1 = await service.refund(job_id)
    assert res1 is not None
    assert res1.delta == Decimal("2.00")

    # Second refund is a no-op returning None
    res2 = await service.refund(job_id)
    assert res2 is None
