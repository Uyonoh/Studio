"""FastAPI dependency helpers shared across routers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import asyncpg
from fastapi import Depends, Request

from studio_core.moderation import ModerationService


async def get_db(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquire a DB connection from the application pool for the duration of the request."""
    pool: asyncpg.Pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        yield conn  # type: ignore[misc]


DBConn = Annotated[asyncpg.Connection, Depends(get_db)]


def get_moderation_service(request: Request) -> ModerationService:
    """Return the app-scoped moderation service, defaulting to the no-op implementation."""
    service = getattr(request.app.state, "moderation_service", None)
    if service is not None and callable(getattr(service, "check", None)):
        return service  # type: ignore[no-any-return]
    return ModerationService()


ModerationDep = Annotated[ModerationService, Depends(get_moderation_service)]
