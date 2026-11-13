"""Generations router — submit, get, list, cancel, retry, and events.

Endpoints:
  POST   /v1/projects/{id}/generations          → 202 Accepted
  GET    /v1/generations/{id}                   → job + outputs + error
  GET    /v1/projects/{id}/generations?status=  → cursor-paginated job list
  POST   /v1/generations/{id}/cancel
  POST   /v1/generations/{id}/retry
  GET    /v1/generations/{id}/events            → debug timeline (admin+)
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from api.auth import AuthUser
from api.deps import DBConn, ModerationDep
from api.pagination import decode_cursor, encode_cursor
from api.rate_limit import retry_rate_limit, submit_rate_limit
from api.routers.assets import _asset_response  # reuse signed-URL logic
from studio_core.generation import (
    GenerationService,
    GenerationSubmitRequest,
    InputItem,
)
from studio_core.models import (
    Asset,
    GenerationJob,
    JobStatus,
    TaskType,
    WorkspaceRole,
)
from studio_core.queue import TASK_CANCEL_GENERATION, TASK_RUN_GENERATION, EnqueueError, enqueue
from studio_core.repositories import (
    AssetRepository,
    EventRepository,
    JobRepository,
    ProjectRepository,
)
from studio_core.state_machine import JobStateMachine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generations"])

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100

TERMINAL_STATUSES = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}


# ── Schemas ────────────────────────────────────────────────────────────────────


class GenerationSubmitBody(BaseModel):
    """Request body for POST /v1/projects/{id}/generations."""

    model: str
    task_type: str
    prompt: str | None = None
    negative_prompt: str | None = None
    inputs: list[dict[str, Any]] = []
    params: dict[str, Any] = {}


class GenerationOutputResponse(BaseModel):
    """A single generated output asset."""

    asset_id: UUID
    kind: str
    mime_type: str | None
    signed_url: str | None
    thumbnail_url: str | None


class GenerationJobResponse(BaseModel):
    """Job representation returned to clients."""

    id: UUID
    project_id: UUID
    workspace_id: UUID
    status: str
    task_type: str
    prompt: str | None
    params: dict[str, Any]
    error_code: str | None
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    outputs: list[GenerationOutputResponse]
    links: dict[str, str]


class JobListResponse(BaseModel):
    items: list[GenerationJobResponse]
    next_cursor: str | None


class JobEventResponse(BaseModel):
    id: int
    type: str
    from_status: str | None
    to_status: str | None
    payload: dict[str, Any] | None
    created_at: datetime


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_job_outputs(
    db: DBConn,
    job_id: UUID,
    asset_repo: AssetRepository,
) -> list[GenerationOutputResponse]:
    """Fetch assets produced by the given job."""
    rows = await db.fetch(
        """
        SELECT id, workspace_id, project_id, kind, origin, storage_bucket,
               storage_path, thumbnail_path, mime_type, size_bytes, width,
               height, duration_ms, fps, source_job_id, parent_asset_id,
               metadata, created_by, created_at, deleted_at
        FROM public.assets
        WHERE source_job_id = $1 AND deleted_at IS NULL
        ORDER BY created_at ASC
        """,
        job_id,
    )
    outputs = []
    for r in rows:
        data = dict(r)
        if isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        asset = Asset.model_validate(data)
        ar = _asset_response(asset)
        outputs.append(
            GenerationOutputResponse(
                asset_id=asset.id,
                kind=asset.kind,
                mime_type=asset.mime_type,
                signed_url=ar.signed_url,
                thumbnail_url=ar.thumbnail_url,
            )
        )
    return outputs


def _job_links(job_id: UUID) -> dict[str, str]:
    return {"self": f"/v1/generations/{job_id}"}


async def _build_job_response(
    job: GenerationJob,
    db: DBConn,
    asset_repo: AssetRepository,
) -> GenerationJobResponse:
    outputs = await _get_job_outputs(db, job.id, asset_repo)
    return GenerationJobResponse(
        id=job.id,
        project_id=job.project_id,
        workspace_id=job.workspace_id,
        status=job.status,
        task_type=job.task_type,
        prompt=job.prompt,
        params=job.params,
        error_code=job.error_code,
        error_message=job.error_message,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        outputs=outputs,
        links=_job_links(job.id),
    )


async def _require_project_member(
    db: DBConn,
    project_id: UUID,
    user_id: UUID,
    min_role: WorkspaceRole = WorkspaceRole.VIEWER,
) -> UUID:
    """Verify membership and return workspace_id."""
    row = await db.fetchrow(
        "SELECT workspace_id FROM public.projects WHERE id = $1 AND archived_at IS NULL",
        project_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")
    workspace_id: UUID = row["workspace_id"]
    repo = ProjectRepository(db)
    role = await repo.get_member_role(workspace_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    role_order = [
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
        WorkspaceRole.VIEWER,
    ]
    if role_order.index(role) > role_order.index(min_role):
        raise HTTPException(status_code=403, detail="Insufficient role")
    return workspace_id


async def _get_job_checked(
    db: DBConn,
    job_id: UUID,
    user_id: UUID,
) -> GenerationJob:
    """Fetch a job and verify the user is a member of its workspace."""
    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    proj_repo = ProjectRepository(db)
    role = await proj_repo.get_member_role(job.workspace_id, user_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    return job


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/generations",
    response_model=GenerationJobResponse,
    status_code=202,
    dependencies=[Depends(submit_rate_limit)],
)
async def submit_generation(
    project_id: UUID,
    body: GenerationSubmitBody,
    user: AuthUser,
    db: DBConn,
    moderation: ModerationDep,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> GenerationJobResponse:
    """Submit a generation job (202 Accepted).

    Requires an ``Idempotency-Key`` header.  Replaying the same key + payload
    returns the existing job without re-enqueuing.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for all generation submissions",
        )

    # Parse inputs
    parsed_inputs: list[InputItem] = []
    for inp in body.inputs:
        from studio_core.models import InputRole

        parsed_inputs.append(
            InputItem(asset_id=UUID(str(inp["asset_id"])), role=InputRole(inp["role"]))
        )

    submit_req = GenerationSubmitRequest(
        model=body.model,
        task_type=TaskType(body.task_type),
        prompt=body.prompt,
        negative_prompt=body.negative_prompt,
        inputs=parsed_inputs,
        params=body.params,
    )

    svc = GenerationService(db, moderation_service=moderation)
    # This may raise domain errors that are mapped by the exception handlers
    job = await svc.create_job(
        user_id=user.id,
        project_id=project_id,
        request=submit_req,
        idempotency_key=idempotency_key,
    )

    # Enqueue; on failure: mark job failed + refund
    redis_pool = getattr(request.app.state, "redis_pool", None)
    try:
        await enqueue(redis_pool, TASK_RUN_GENERATION, job.id)
    except EnqueueError as exc:
        logger.error("Enqueue failed for job %s: %s", job.id, exc)
        # Mark job failed so it doesn't orphan in queued state
        state_machine = JobStateMachine(db)
        from studio_core.credits import CreditService

        await state_machine.transition(
            job.id,
            expected=JobStatus.QUEUED,
            new=JobStatus.FAILED,
            error_code="ENQUEUE_FAILED",
            error_message="Failed to enqueue generation job",
        )
        credit_svc = CreditService(db)
        await credit_svc.refund(job.id)
        raise HTTPException(
            status_code=503,
            detail="Failed to queue generation job. Credits have been refunded.",
        ) from exc

    asset_repo = AssetRepository(db)
    response = await _build_job_response(job, db, asset_repo)
    # Add Location header
    # We return the Pydantic model directly; FastAPI handles serialization
    return response


@router.get("/generations/{job_id}", response_model=GenerationJobResponse)
async def get_generation(job_id: UUID, user: AuthUser, db: DBConn) -> GenerationJobResponse:
    """Retrieve a generation job with its outputs."""
    job = await _get_job_checked(db, job_id, user.id)
    asset_repo = AssetRepository(db)
    return await _build_job_response(job, db, asset_repo)


@router.get("/projects/{project_id}/generations", response_model=JobListResponse)
async def list_generations(
    project_id: UUID,
    user: AuthUser,
    db: DBConn,
    status: str | None = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> JobListResponse:
    """List generation jobs in a project with optional status/time filters."""
    await _require_project_member(db, project_id, user.id)

    before: datetime | None = None
    if cursor:
        try:
            before, _ = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor value") from exc

    clauses = ["project_id = $1"]
    params: list[object] = [project_id]

    if status:
        try:
            JobStatus(status)  # validate
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status value: {status}") from exc
        params.append(status)
        clauses.append(f"status = ${len(params)}")

    if before:
        params.append(before)
        clauses.append(f"queued_at < ${len(params)}")

    if since:
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        params.append(since)
        clauses.append(f"queued_at >= ${len(params)}")

    params.append(limit + 1)
    where_sql = " AND ".join(clauses)
    query = f"""
        SELECT id, workspace_id, project_id, created_by, model_id, task_type,
               status, prompt, negative_prompt, params, idempotency_key,
               provider_job_id, attempt, max_attempts, error_code, error_message,
               cost_credits, parent_job_id, workflow_run_id, queued_at,
               started_at, completed_at, heartbeat_at
        FROM public.generation_jobs
        WHERE {where_sql}
        ORDER BY queued_at DESC
        LIMIT ${len(params)}
    """
    rows = await db.fetch(query, *params)
    jobs = []
    for r in rows:
        data = dict(r)
        if isinstance(data["params"], str):
            data["params"] = json.loads(data["params"])
        jobs.append(GenerationJob.model_validate(data))

    has_more = len(jobs) > limit
    items = jobs[:limit]
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.queued_at, last.id)

    asset_repo = AssetRepository(db)
    item_responses = [await _build_job_response(j, db, asset_repo) for j in items]
    return JobListResponse(items=item_responses, next_cursor=next_cursor)


@router.post("/generations/{job_id}/cancel", response_model=GenerationJobResponse)
async def cancel_generation(
    job_id: UUID,
    user: AuthUser,
    db: DBConn,
    request: Request,
) -> GenerationJobResponse:
    """Cancel a queued or running generation job."""
    job = await _get_job_checked(db, job_id, user.id)
    proj_repo = ProjectRepository(db)
    role = await proj_repo.get_member_role(job.workspace_id, user.id)
    if role is None or role == WorkspaceRole.VIEWER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if job.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Job is already in terminal status '{job.status.value}'",
        )

    state_machine = JobStateMachine(db)
    updated = await state_machine.transition(job.id, expected=job.status, new=JobStatus.CANCELED)
    if updated is None:
        # Guard failed — job changed concurrently
        raise HTTPException(status_code=409, detail="Job status changed concurrently; try again")

    # Refund credits
    from studio_core.credits import CreditService

    credit_svc = CreditService(db)
    await credit_svc.refund(job_id)

    # Ask worker to cancel with provider if running
    if job.status == JobStatus.RUNNING:
        redis_pool = getattr(request.app.state, "redis_pool", None)
        try:
            await enqueue(redis_pool, TASK_CANCEL_GENERATION, job_id)
        except EnqueueError:
            logger.warning("Could not enqueue cancel task for job %s", job_id)

    asset_repo = AssetRepository(db)
    return await _build_job_response(updated, db, asset_repo)


@router.post(
    "/generations/{job_id}/retry",
    response_model=GenerationJobResponse,
    status_code=202,
    dependencies=[Depends(retry_rate_limit)],
)
async def retry_generation(
    job_id: UUID,
    user: AuthUser,
    db: DBConn,
    moderation: ModerationDep,
    request: Request,
) -> GenerationJobResponse:
    """Retry a failed or canceled job by creating a new job with the same inputs."""
    original = await _get_job_checked(db, job_id, user.id)
    proj_repo = ProjectRepository(db)
    role = await proj_repo.get_member_role(original.workspace_id, user.id)
    if role is None or role == WorkspaceRole.VIEWER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if original.status not in {JobStatus.FAILED, JobStatus.CANCELED}:
        raise HTTPException(
            status_code=409,
            detail="Only failed or canceled jobs can be retried",
        )

    # Fetch original inputs
    job_repo = JobRepository(db)
    inputs = await job_repo.get_inputs(job_id)

    # Build a new submit request

    parsed_inputs = [InputItem(asset_id=inp.asset_id, role=inp.role) for inp in inputs]
    submit_req = GenerationSubmitRequest(
        model=str(original.model_id),  # pass UUID; GenerationService accepts it
        task_type=original.task_type,
        prompt=original.prompt,
        negative_prompt=original.negative_prompt,
        inputs=parsed_inputs,
        params=original.params,
    )

    # Derive a fresh idempotency key server-side
    new_idempotency_key = f"retry-{original.id}-{uuid.uuid4()}"

    svc = GenerationService(db, moderation_service=moderation)
    new_job = await svc.create_job(
        user_id=user.id,
        project_id=original.project_id,
        request=submit_req,
        idempotency_key=new_idempotency_key,
        parent_job_id=original.id,
    )

    redis_pool = getattr(request.app.state, "redis_pool", None)
    try:
        await enqueue(redis_pool, TASK_RUN_GENERATION, new_job.id)
    except EnqueueError as exc:
        state_machine = JobStateMachine(db)
        await state_machine.transition(
            new_job.id,
            expected=JobStatus.QUEUED,
            new=JobStatus.FAILED,
            error_code="ENQUEUE_FAILED",
            error_message="Failed to enqueue retry job",
        )
        from studio_core.credits import CreditService

        await CreditService(db).refund(new_job.id)
        raise HTTPException(
            status_code=503, detail="Failed to queue retry. Credits refunded."
        ) from exc

    asset_repo = AssetRepository(db)
    return await _build_job_response(new_job, db, asset_repo)


@router.get("/generations/{job_id}/events", response_model=list[JobEventResponse])
async def list_job_events(job_id: UUID, user: AuthUser, db: DBConn) -> list[JobEventResponse]:
    """Return the debug event timeline for a job (admin/owner only)."""
    job = await _get_job_checked(db, job_id, user.id)
    proj_repo = ProjectRepository(db)
    role = await proj_repo.get_member_role(job.workspace_id, user.id)
    if role not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Only workspace admins can view job events")

    event_repo = EventRepository(db)
    events = await event_repo.list_by_job(job_id)
    return [
        JobEventResponse(
            id=e.id,
            type=e.type,
            from_status=e.from_status,
            to_status=e.to_status,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]
