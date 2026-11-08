"""Tests for pooler-aware asyncpg pool creation (T7.3)."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from studio_core import db


class _FakePool:
    pass


async def test_transaction_pooler_disables_statement_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_pool(**kwargs: Any) -> _FakePool:
        captured.update(kwargs)
        return _FakePool()

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    pool = await db.create_pool("postgresql://user:pass@host.pooler.supabase.com:6543/postgres")

    assert isinstance(pool, _FakePool)
    assert captured["statement_cache_size"] == 0


async def test_direct_connection_keeps_default_statement_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_pool(**kwargs: Any) -> _FakePool:
        captured.update(kwargs)
        return _FakePool()

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    await db.create_pool("postgresql://user:pass@db.example.com:5432/postgres")

    assert "statement_cache_size" not in captured


async def test_explicit_statement_cache_setting_is_respected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_pool(**kwargs: Any) -> _FakePool:
        captured.update(kwargs)
        return _FakePool()

    monkeypatch.setattr(asyncpg, "create_pool", fake_create_pool)

    await db.create_pool(
        "postgresql://user:pass@host.pooler.supabase.com:6543/postgres",
        statement_cache_size=64,
    )

    assert captured["statement_cache_size"] == 64
