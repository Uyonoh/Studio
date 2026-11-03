"""Sentry and structured-logging helpers shared by the API and worker.

Sentry is optional at runtime: when ``SENTRY_DSN`` is unset or the SDK is not
installed, every helper is a no-op. This keeps local development and unit
tests free of network calls while production services report exceptions with
consistent request/job context.
"""

from __future__ import annotations

import importlib
import logging
import os
from contextvars import ContextVar
from typing import Any, cast

try:  # pragma: no cover - exercised through the no-op path in tests
    _sentry_module: Any = importlib.import_module("sentry_sdk")
except ImportError:  # pragma: no cover
    _sentry_module = None

sentry: Any = _sentry_module

_current_job_context: ContextVar[dict[str, str | None] | None] = ContextVar(
    "current_job_context", default=None
)


def get_release() -> str | None:
    """Resolve the release tag from the deployment environment.

    Render, Vercel, and GitHub Actions expose the commit under different
    names; ``SENTRY_RELEASE`` wins so operators can override it.
    """
    return (
        os.getenv("SENTRY_RELEASE")
        or os.getenv("GIT_SHA")
        or os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("VERCEL_GIT_COMMIT_SHA")
        or None
    )


def init_sentry(
    *,
    service: str,
    dsn: str | None,
    environment: str,
    release: str | None = None,
    traces_sample_rate: float = 0.1,
) -> bool:
    """Initialize Sentry once per process. Returns whether it is active."""
    if sentry is None or not dsn:
        return False

    if sentry.is_initialized():
        return True

    sentry.init(
        dsn=dsn,
        environment=environment,
        release=release or get_release(),
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        server_name=service,
    )
    sentry.set_tag("service", service)
    return True


def set_request_context(
    *,
    request_id: str,
    path: str,
    method: str,
    user_id: str | None = None,
) -> None:
    """Attach HTTP request metadata to the current Sentry scope."""
    if sentry is None:
        return

    sentry.set_tag("request_id", request_id)
    sentry.set_context(
        "request",
        {
            "request_id": request_id,
            "path": path,
            "method": method,
            "user_id": user_id,
        },
    )
    if user_id:
        sentry.set_user({"id": user_id})


def set_job_context(
    *,
    job_id: str,
    provider: str | None = None,
    model: str | None = None,
    status: str | None = None,
) -> None:
    """Attach generation-job metadata to the current Sentry scope."""
    if sentry is None:
        return

    sentry.set_tag("job_id", job_id)
    if provider:
        sentry.set_tag("provider", provider)
    if model:
        sentry.set_tag("model", model)
    if status:
        sentry.set_tag("job_status", status)
    sentry.set_context(
        "generation_job",
        {
            "job_id": job_id,
            "provider": provider,
            "model": model,
            "status": status,
        },
    )


def set_current_job_context(
    *,
    job_id: str,
    provider: str | None = None,
    model: str | None = None,
    status: str | None = None,
) -> None:
    """Remember job metadata for the current async task and Sentry scope."""
    _current_job_context.set(
        {"job_id": job_id, "provider": provider, "model": model, "status": status}
    )
    set_job_context(job_id=job_id, provider=provider, model=model, status=status)


def clear_current_job_context() -> None:
    """Clear job metadata when a worker task finishes."""
    _current_job_context.set(None)


def capture_exception(
    exc: BaseException,
    *,
    request_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
    user_id: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    status: str | None = None,
    **extra: Any,
) -> str | None:
    """Report an exception to Sentry with optional request/job context."""
    if sentry is None:
        return None

    if request_id and path and method:
        set_request_context(
            request_id=request_id,
            path=path,
            method=method,
            user_id=user_id,
        )
    elif user_id:
        sentry.set_user({"id": user_id})

    if job_id:
        set_job_context(job_id=job_id, provider=provider, model=model, status=status)
    elif provider or model or status:
        sentry.set_context(
            "generation_job",
            {"provider": provider, "model": model, "status": status},
        )

    if extra:
        sentry.set_context("extra", extra)

    return cast("str | None", sentry.capture_exception(exc))


def log_job_transition(
    logger: logging.Logger,
    *,
    job_id: str,
    from_status: str,
    to_status: str,
    provider: str | None = None,
    model: str | None = None,
    duration_ms: float | None = None,
    error_code: str | None = None,
) -> None:
    """Emit one structured log line per job state transition."""
    current = _current_job_context.get() or {}
    logger.info(
        "job_transition %s -> %s",
        from_status,
        to_status,
        extra={
            "event": "job_transition",
            "job_id": job_id or current.get("job_id"),
            "provider": provider or current.get("provider"),
            "model": model or current.get("model"),
            "status": to_status,
            "from_status": from_status,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "error_code": error_code,
        },
    )
