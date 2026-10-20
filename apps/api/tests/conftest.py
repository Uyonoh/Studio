"""Shared fixtures for API integration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import jwt
import pytest

from api.main import create_app
from studio_core.settings import get_settings


def make_jwt(user_id: UUID | None = None, expired: bool = False) -> str:
    """Create a Supabase-style HS256 JWT for testing."""
    settings = get_settings()
    uid = user_id or uuid.uuid4()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(uid),
        "email": f"{uid}@example.com",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + (timedelta(seconds=-1) if expired else timedelta(hours=1))).timestamp()),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture()
def app():
    """Create a test FastAPI application with mocked lifespan state."""
    application = create_app()

    # Inject mock state without running lifespan
    application.state.db_pool = None  # will be overridden per test
    application.state.redis_pool = None

    return application


@pytest.fixture()
def mock_db():
    """Return a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=conn)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    return conn


@pytest.fixture()
def user_id() -> UUID:
    return uuid.uuid4()


@pytest.fixture()
def auth_header(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_jwt(user_id)}"}
