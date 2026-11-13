"""Worker entrypoint and ARQ WorkerSettings definition."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from arq.cron import cron
from arq.worker import Worker, get_kwargs
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from studio_core.db import create_pool as create_db_pool
from studio_core.observability import init_sentry
from worker.config import WorkerConfig, get_worker_config
from worker.tasks.cancel_generation import cancel_generation
from worker.tasks.finalize_generation import finalize_generation
from worker.tasks.reconciler import reconcile_jobs
from worker.tasks.run_generation import run_generation

logger = logging.getLogger(__name__)

# Cap the retry delay when Redis is unreachable for an extended period.
_MAX_REDIS_RETRY_DELAY_SECONDS = 30.0


class ResilientWorker(Worker):
    """ARQ worker that keeps polling through transient Redis outages.

    ARQ's stock poll loop does not catch Redis connection errors, so a single
    dropped connection terminates the process. Jobs are already recoverable
    from Postgres (see the reconciler), so staying alive and reconnecting is
    preferable to crashing.
    """

    async def _poll_iteration(self) -> None:
        try:
            await super()._poll_iteration()
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            failures = getattr(self, "_redis_poll_failures", 0) + 1
            self._redis_poll_failures = failures
            delay = min(
                _MAX_REDIS_RETRY_DELAY_SECONDS,
                max(self.poll_delay_s, 0.5) * (2 ** min(failures, 6)),
            )
            logger.warning(
                "Redis unavailable during poll (attempt %d): %s; retrying in %.1fs",
                failures,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
        else:
            if getattr(self, "_redis_poll_failures", 0):
                logger.info("Redis connection recovered; resuming polling")
                self._redis_poll_failures = 0


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

    # Reuse ARQ's own pool (configured with health checks + retries in
    # WorkerSettings) so tasks enqueue through the same resilient connection.
    redis_pool = ctx.get("redis")
    if redis_pool is None:
        # Startup invoked outside an ARQ worker (e.g. a test harness).
        redis_pool = config.get_redis_pool()
        ctx["_owns_redis_pool"] = True
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

    # ARQ owns and closes its own pool after this hook; only close a pool we
    # created ourselves.
    redis_pool = ctx.get("redis_pool")
    if redis_pool and ctx.get("_owns_redis_pool"):
        await redis_pool.aclose()
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
        # Provide a pre-built pool so ARQ uses our health-checked/retrying
        # connection pool instead of its default RedisSettings pool.
        redis_pool = config.get_redis_pool()
        # Keep settings for tooling such as ``arq --check``.
        redis_settings = config.get_redis_settings()
        max_jobs = config.worker_max_jobs
        job_timeout = config.worker_job_timeout
        # Tasks are fire-and-forget and all durable state lives in Postgres.
        # ARQ's default keep_result (1h) leaves `arq:result:<id>` keys behind,
        # and those keys block any later enqueue that reuses the same id.
        keep_result = 0
        handle_signals = True

    return WorkerSettings


WorkerSettings = get_worker_settings()


def main() -> None:
    """CLI runner used by local development and the worker container."""
    config = get_worker_config()
    logging.basicConfig(level=config.log_level)
    worker_kwargs: dict[str, Any] = get_kwargs(WorkerSettings)
    ResilientWorker(**worker_kwargs).run()


if __name__ == "__main__":
    main()
