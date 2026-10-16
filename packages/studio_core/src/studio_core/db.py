"""Database connection pool management and transaction utilities using asyncpg."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg


async def create_pool(
    dsn: str,
    min_size: int = 1,
    max_size: int = 10,
    **kwargs: Any,
) -> asyncpg.Pool[asyncpg.Record]:
    """Create and return an asyncpg connection pool."""
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        **kwargs,
    )
    assert pool is not None
    return pool


@asynccontextmanager
async def transaction(
    conn_or_pool: asyncpg.Connection[asyncpg.Record] | asyncpg.Pool[asyncpg.Record],
) -> AsyncIterator[asyncpg.Connection[asyncpg.Record]]:
    """Yield a connection inside an active transaction.

    If given a pool, acquires a connection, opens a transaction, yields the connection,
    and commits or rolls back before releasing the connection back to the pool.
    If given a connection, simply manages the transaction block on that connection.
    """
    if isinstance(conn_or_pool, asyncpg.Pool):
        async with conn_or_pool.acquire() as connection:
            async with connection.transaction():
                # connection is a PoolConnectionProxy, which is a Connection subclass/duck type
                yield connection  # type: ignore[misc]
    else:
        async with conn_or_pool.transaction():
            yield conn_or_pool
