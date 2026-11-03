"""State machine governing job status transitions per Technical Design Document §5.2.

Allowed transitions:
  queued -> submitting
  queued -> failed (enqueue/infrastructure failure)
  submitting -> running
  submitting -> queued (transient retry)
  submitting -> failed (permanent failure)
  running -> finalizing
  running -> failed
  running -> canceled
  queued -> canceled
  finalizing -> succeeded
  finalizing -> failed

Terminal states (succeeded, failed, canceled) are immutable.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from studio_core.models import GenerationJob, JobStatus
from studio_core.observability import log_job_transition
from studio_core.repositories import EventRepository

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.SUBMITTING, JobStatus.CANCELED, JobStatus.FAILED},
    JobStatus.SUBMITTING: {JobStatus.RUNNING, JobStatus.QUEUED, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.FINALIZING, JobStatus.FAILED, JobStatus.CANCELED},
    JobStatus.FINALIZING: {JobStatus.SUCCEEDED, JobStatus.FAILED},
    JobStatus.SUCCEEDED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELED: set(),
}

TERMINAL_STATES = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}


def can_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
    """Check whether a transition between two job statuses is legal."""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, set())


class JobStateMachine:
    """Manages guarded database transitions of generation jobs."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn
        self.event_repo = EventRepository(conn)

    async def transition(
        self,
        job_id: UUID,
        expected: JobStatus,
        new: JobStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        provider_job_id: str | None = None,
        heartbeat_at: datetime | None = None,
        event_payload: dict[str, Any] | None = None,
        provider_id: str | None = None,
        model_slug: str | None = None,
    ) -> GenerationJob | None:
        """Perform a guarded transition.

        Executes:
          UPDATE generation_jobs SET status=$new, ... WHERE id=$1 AND status=$expected RETURNING *

        Also writes an append-only audit event in the same transaction.
        Returns the updated GenerationJob if the transition succeeded, or None if the guard failed.
        Raises ValueError if transition from expected to new is not allowed by the state machine.
        """
        if not can_transition(expected, new):
            raise ValueError(f"Illegal job status transition from {expected.value} to {new.value}")

        now = datetime.now(UTC)
        set_clauses = ["status = $2"]
        params: list[Any] = [job_id, new.value]

        if new == JobStatus.RUNNING:
            set_clauses.append(f"started_at = COALESCE(started_at, ${len(params) + 1})")
            params.append(now)

        if new in TERMINAL_STATES:
            set_clauses.append(f"completed_at = ${len(params) + 1}")
            params.append(now)

        if error_code is not None:
            set_clauses.append(f"error_code = ${len(params) + 1}")
            params.append(error_code)

        if error_message is not None:
            set_clauses.append(f"error_message = ${len(params) + 1}")
            params.append(error_message)

        if provider_job_id is not None:
            set_clauses.append(f"provider_job_id = ${len(params) + 1}")
            params.append(provider_job_id)

        if heartbeat_at is not None:
            set_clauses.append(f"heartbeat_at = ${len(params) + 1}")
            params.append(heartbeat_at)
        elif new in {JobStatus.SUBMITTING, JobStatus.RUNNING, JobStatus.FINALIZING}:
            set_clauses.append(f"heartbeat_at = ${len(params) + 1}")
            params.append(now)

        set_sql = ", ".join(set_clauses)
        query = f"""
            UPDATE public.generation_jobs
            SET {set_sql}
            WHERE id = $1 AND status = '{expected.value}'
            RETURNING id, workspace_id, project_id, created_by, model_id, task_type,
                      status, prompt, negative_prompt, params, idempotency_key,
                      provider_job_id, attempt, max_attempts, error_code, error_message,
                      cost_credits, parent_job_id, workflow_run_id, queued_at,
                      started_at, completed_at, heartbeat_at
        """
        row = await self.conn.fetchrow(query, *params)
        if not row:
            return None

        # Append state_change event in the same transaction
        await self.event_repo.append(
            job_id=job_id,
            event_type="state_change",
            from_status=expected,
            to_status=new,
            payload=event_payload or ({"error_code": error_code} if error_code else None),
        )

        import json

        data = dict(row)
        if isinstance(data["params"], str):
            data["params"] = json.loads(data["params"])

        queued_at = data.get("queued_at")
        duration_ms: float | None = None
        if isinstance(queued_at, datetime):
            duration_ms = (now - queued_at).total_seconds() * 1000

        log_job_transition(
            logger,
            job_id=str(job_id),
            from_status=expected.value,
            to_status=new.value,
            provider=provider_id,
            model=model_slug or str(data.get("model_id")),
            duration_ms=duration_ms,
            error_code=error_code,
        )

        return GenerationJob.model_validate(data)
