"""FastAPI application factory with lifespan, middleware, and route registration."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.errors import problem_response, register_exception_handlers
from api.routers import (
    admin,
    assets,
    generations,
    models,
    projects,
    webhooks,
    workspaces,
)
from studio_core.db import create_pool
from studio_core.observability import init_sentry, set_request_context
from studio_core.settings import get_settings

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    """Set up structured JSON-compatible logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup (pool open) and shutdown (pool close) of shared resources."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger.info("Starting AI Content Studio API", extra={"environment": settings.environment})

    # Open DB pool
    pool: asyncpg.Pool[asyncpg.Record] = await create_pool(settings.database_url)
    app.state.db_pool = pool
    logger.info("Database pool opened")

    # ARQ Redis pool (lazy — imported here to avoid hard dep at import time)
    try:
        from arq import create_pool as arq_create_pool
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        redis_pool = await arq_create_pool(redis_settings)
        app.state.redis_pool = redis_pool
        logger.info("Redis pool opened")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not connect to Redis at startup: %s", exc)
        app.state.redis_pool = None

    yield

    # Shutdown
    await pool.close()
    logger.info("Database pool closed")
    if app.state.redis_pool is not None:
        await app.state.redis_pool.aclose()
        logger.info("Redis pool closed")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = get_settings()

    init_sentry(
        service="api",
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.sentry_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )

    app = FastAPI(
        title="AI Content Studio API",
        version="0.1.0",
        description="REST API for AI-powered content generation.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    web_origins = getattr(settings, "web_origins", "http://localhost:3000")
    allow_origins = [o.strip().rstrip("/") for o in raw_origins.split(", ") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID middleware ─────────────────────────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        """Attach a request ID to every request and propagate it in the response."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_context(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Body-size guard ───────────────────────────────────────────────────────
    MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB limit for JSON payloads

    @app.middleware("http")
    async def body_size_limit(request: Request, call_next: Any) -> Any:
        """Reject requests whose declared Content-Length exceeds the limit."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return problem_response(
                413,
                "PAYLOAD_TOO_LARGE",
                f"Request body must not exceed {MAX_BODY_BYTES} bytes.",
            )
        return await call_next(request)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Health endpoints ──────────────────────────────────────────────────────
    @app.get("/healthz", tags=["health"], summary="Liveness probe")
    async def healthz() -> dict[str, str]:
        """Always returns 200 when the process is alive."""
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"], summary="Readiness probe")
    async def readyz(request: Request) -> JSONResponse:
        """Returns 200 when both the DB pool and Redis are reachable."""
        checks: dict[str, str] = {}
        ok = True

        # DB check
        try:
            pool: asyncpg.Pool[asyncpg.Record] = request.app.state.db_pool
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["db"] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.error("Readiness DB check failed: %s", exc)
            checks["db"] = "error"
            ok = False

        # Redis check
        redis = request.app.state.redis_pool
        if redis is not None:
            try:
                await redis.ping()
                checks["redis"] = "ok"
            except Exception as exc:  # noqa: BLE001
                logger.error("Readiness Redis check failed: %s", exc)
                checks["redis"] = "error"
                ok = False
        else:
            checks["redis"] = "unavailable"

        status = 200 if ok else 503
        return JSONResponse(
            status_code=status,
            content={"status": "ok" if ok else "degraded", "checks": checks},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(workspaces.router, prefix="/v1")
    app.include_router(projects.router, prefix="/v1")
    app.include_router(assets.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(generations.router, prefix="/v1")
    app.include_router(admin.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/internal")

    return app


app = create_app()
