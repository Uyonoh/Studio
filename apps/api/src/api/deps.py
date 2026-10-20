"""FastAPI dependency helpers shared across routers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import asyncpg
from fastapi import Depends, Request


async def get_db(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquire a DB connection from the application pool for the duration of the request."""
    pool: asyncpg.Pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        yield conn  # type: ignore[misc]


DBConn = Annotated[asyncpg.Connection, Depends(get_db)]
