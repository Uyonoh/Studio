"""Admin-only operational stats for dashboards and alerting.

The endpoint aggregates the last 24 hours of job activity (and a 15-minute
failure window) directly from Postgres. It is intentionally cheap enough to
poll from a dashboard every minute, and every query is parameterised.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from api.auth import AuthUser
from api.deps import DBConn
from studio_core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


async def require_admin(user: AuthUser) -> AuthUser:
    """Allow only user IDs listed in ``ADMIN_USER_IDS``.

    An empty allow-list denies everyone, so the endpoint is closed by default
    until an operator explicitly configures an administrator.
    """
    raw = get_settings().admin_user_ids or ""
    allowed = {value.strip() for value in raw.split(",") if value.strip()}
    if str(user.id) not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "type": "https://studio.example.com/errors/forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": "Admin access is required for this endpoint.",
                "error_code": "FORBIDDEN",
            },
        )
    return user


AdminUser = Annotated[AuthUser, Depends(require_admin)]


# ── Response models ────────────────────────────────────────────────────────────


def _num(value: Any) -> float:
    """Coerce asyncpg numeric/Decimal/None values to a rounded float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _int(value: Any) -> int:
    return int(value or 0)


async def _queue_stats(db: DBConn) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT count(*) AS depth,
               COALESCE(EXTRACT(EPOCH FROM (now() - min(queued_at))), 0) AS oldest_age_seconds
        FROM public.generation_jobs
        WHERE status = 'queued'
        """
    )
    data = dict(row) if row is not None else {}
    return {
        "depth": _int(data.get("depth")),
        "oldest_age_seconds": round(_num(data.get("oldest_age_seconds")), 2),
    }


async def _failure_stats(db: DBConn) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT count(*) FILTER (WHERE status = 'failed') AS failed,
               count(*) FILTER (WHERE status IN ('succeeded', 'failed')) AS completed
        FROM public.generation_jobs
        WHERE completed_at >= now() - interval '15 minutes'
        """
    )
    data = dict(row) if row is not None else {}
    failed = _int(data.get("failed"))
    completed = _int(data.get("completed"))
    rate = (failed / completed) if completed else 0.0
    return {
        "window_minutes": 15,
        "failed": failed,
        "completed": completed,
        "failure_rate": round(rate, 4),
    }


async def _time_in_state(db: DBConn) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        WITH transitions AS (
            SELECT from_status,
                   created_at,
                   lag(created_at) OVER (PARTITION BY job_id ORDER BY id) AS prev_at
            FROM public.job_events
            WHERE type = 'state_change'
              AND from_status IS NOT NULL
              AND created_at >= now() - interval '24 hours'
        )
        SELECT from_status AS status,
               avg(EXTRACT(EPOCH FROM (created_at - prev_at))) AS avg_seconds,
               count(*) AS samples
        FROM transitions
        WHERE prev_at IS NOT NULL
        GROUP BY from_status
        ORDER BY from_status
        """
    )
    return [
        {
            "status": str(dict(row).get("status")),
            "avg_seconds": round(_num(dict(row).get("avg_seconds")), 2),
            "samples": _int(dict(row).get("samples")),
        }
        for row in rows
    ]


async def _durations(db: DBConn) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT avg(EXTRACT(EPOCH FROM (completed_at - queued_at))) AS avg_total_seconds,
               avg(EXTRACT(EPOCH FROM (started_at - queued_at))) AS avg_queue_seconds,
               avg(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_run_seconds,
               count(*) AS completed_jobs
        FROM public.generation_jobs
        WHERE completed_at >= now() - interval '24 hours'
        """
    )
    data = dict(row) if row is not None else {}
    return {
        "window_hours": 24,
        "completed_jobs": _int(data.get("completed_jobs")),
        "avg_total_seconds": round(_num(data.get("avg_total_seconds")), 2),
        "avg_queue_seconds": round(_num(data.get("avg_queue_seconds")), 2),
        "avg_run_seconds": round(_num(data.get("avg_run_seconds")), 2),
    }


async def _provider_stats(db: DBConn) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT m.provider_id,
               count(*) AS jobs,
               count(*) FILTER (WHERE j.status = 'failed') AS failed,
               avg(EXTRACT(EPOCH FROM (j.completed_at - j.started_at)))
                   FILTER (WHERE j.completed_at IS NOT NULL AND j.started_at IS NOT NULL)
                   AS avg_latency_seconds,
               COALESCE(
                   sum(j.cost_credits) FILTER (WHERE j.status = 'succeeded'), 0
               ) AS cost_credits
        FROM public.generation_jobs j
        JOIN public.models m ON m.id = j.model_id
        WHERE j.queued_at >= now() - interval '24 hours'
        GROUP BY m.provider_id
        ORDER BY m.provider_id
        """
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        jobs = _int(data.get("jobs"))
        failed = _int(data.get("failed"))
        result.append(
            {
                "provider_id": str(data.get("provider_id")),
                "jobs": jobs,
                "failed": failed,
                "error_rate": round(failed / jobs, 4) if jobs else 0.0,
                "avg_latency_seconds": round(_num(data.get("avg_latency_seconds")), 2),
                "cost_credits": round(_num(data.get("cost_credits")), 2),
            }
        )
    return result


@router.get("/admin/stats")
async def admin_stats(user: AdminUser, db: DBConn) -> dict[str, Any]:
    """Return queue, failure, duration, and provider aggregates.

    Access is restricted to ``ADMIN_USER_IDS``. The response is deliberately a
    single object so a dashboard can fetch everything in one request.
    """
    queue = await _queue_stats(db)
    failures = await _failure_stats(db)
    time_in_state = await _time_in_state(db)
    durations = await _durations(db)
    providers = await _provider_stats(db)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "queue": queue,
        "failures": failures,
        "time_in_state": time_in_state,
        "durations": durations,
        "providers": providers,
    }
