"""Worker entrypoint and ARQ WorkerSettings definition."""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import create_pool
from arq.cron import cron

from studio_core.db import create_pool as create_db_pool
from studio_core.observability import init_sentry
from worker.config import WorkerConfig, get_worker_config
from worker.tasks.cancel_generation import cancel_generation
from worker.tasks.finalize_generation import finalize_generation
from worker.tasks.reconciler import reconcile_jobs
from worker.tasks.run_generation import run_generation

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize DB connection pool, redis, and run startup reconciliation pass."""
    config: WorkerConfig = ctx.get("config") or get_worker_config()
    ctx["config"] = config

    logging.basicConfig(level=config.log_level)
    logger.info("Starting ARQ Worker in %s environment", config.environment)

    sentry_active = init_sentry(
        service="worker",
        dsn=config.sentry_dsn,
        environment=config.environment,
        release=config.sentry_release,
        traces_sample_rate=config.sentry_traces_sample_rate,
    )
    logger.info("Sentry %s for worker", "enabled" if sentry_active else "disabled")

    # Database pool
    db_pool = await create_db_pool(
        config.database_url,
        min_size=2,
        max_size=config.worker_max_jobs + 2,
    )
    ctx["db_pool"] = db_pool

    # Redis pool for enqueuing deferred or downstream tasks
    redis_pool = await create_pool(config.get_redis_settings())
    ctx["redis_pool"] = redis_pool

    # Run startup reconciliation pass (covers Redis loss/restarts)
    try:
        reconciled = await reconcile_jobs(ctx)
        logger.info("Startup reconciliation pass completed: %d jobs checked/reconciled", reconciled)
    except Exception as exc:
        logger.warning("Startup reconciliation pass encountered error: %s", exc)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close DB pool and Redis connections gracefully."""
    logger.info("Shutting down ARQ Worker...")
    db_pool = ctx.get("db_pool")
    if db_pool:
        await db_pool.close()

    redis_pool = ctx.get("redis_pool")
    if redis_pool:
        await redis_pool.close()
    logger.info("ARQ Worker shutdown complete")


def get_worker_settings() -> type[Any]:
    config = get_worker_config()

    class WorkerSettings:
        functions = [
            run_generation,
            finalize_generation,
            cancel_generation,
        ]
        cron_jobs = [
            cron(
                reconcile_jobs,
                second=0,  # runs every minute at :00
                unique=True,
                timeout=config.worker_job_timeout,
            )
        ]
        on_startup = startup
        on_shutdown = shutdown
        redis_settings = config.get_redis_settings()
        max_jobs = config.worker_max_jobs
        job_timeout = config.worker_job_timeout
        handle_signals = True

    return WorkerSettings


WorkerSettings = get_worker_settings()


def main() -> None:
    """CLI runner for local development (python -m worker.main)."""
    from arq import run_worker

    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
