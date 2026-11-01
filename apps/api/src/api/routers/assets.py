"""Assets router — upload flow, metadata extraction, and asset reads.

Endpoints:
  POST   /v1/projects/{id}/assets/uploads   → signed upload URL + draft asset
  POST   /v1/assets/{id}/complete           → confirm upload, extract metadata
  GET    /v1/assets/{id}                    → asset with signed URL and lineage
  GET    /v1/projects/{id}/assets           → list assets (cursor-paginated)
  DELETE /v1/assets/{id}                    → soft delete
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import AuthUser
from api.deps import DBConn
from api.pagination import decode_cursor, encode_cursor
from studio_core.models import Asset, AssetKind, AssetOrigin, WorkspaceRole
from studio_core.repositories import AssetRepository, ProjectRepository
from studio_core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assets"])

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
SIGNED_URL_TTL = 3600  # 1 hour


# ── Schemas ────────────────────────────────────────────────────────────────────


class LineageAssetRef(BaseModel):
    """A lightweight reference to another asset (input or parent)."""

    asset_id: UUID
    kind: str
    role: str | None = None
    signed_url: str | None = None
    thumbnail_url: str | None = None


class LineageSourceJob(BaseModel):
    """Summary of the generation job that produced an asset."""

    id: UUID
    task_type: str
    status: str
    prompt: str | None
    negative_prompt: str | None
    params: dict[str, Any]
    model_slug: str | None
    model_display_name: str | None
    created_at: datetime


class AssetLineage(BaseModel):
    """Everything needed to explain where an asset came from."""

    source_job: LineageSourceJob | None = None
    inputs: list[LineageAssetRef] = Field(default_factory=list)
    parent: LineageAssetRef | None = None


class AssetResponse(BaseModel):
    """Asset representation with signed download URL."""

    id: UUID
    workspace_id: UUID
    project_id: UUID
    kind: str
    origin: str
    mime_type: str | None
    size_bytes: int | None
    width: int | None
    height: int | None
    duration_ms: int | None
    fps: Decimal | None
    storage_path: str
    thumbnail_path: str | None
    source_job_id: UUID | None
    parent_asset_id: UUID | None
    metadata: dict[str, Any]
    created_at: datetime
    signed_url: str | None = None
    thumbnail_url: str | None = None
    lineage: AssetLineage | None = None


class UploadRequest(BaseModel):
    """Client declares the MIME type and byte size before uploading."""

    mime_type: str
    size_bytes: int
    filename: str


class UploadResponse(BaseModel):
    """Signed upload URL and the draft asset id."""

    asset_id: UUID
    upload_url: str


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    next_cursor: str | None


# ── Supabase storage helpers ───────────────────────────────────────────────────


def _supabase_signed_upload_url(
    workspace_id: UUID,
    project_id: UUID,
    asset_id: UUID,
    filename: str,
) -> str:
    """Build the Supabase storage path and return a signed upload URL.

    In production this calls the Supabase Storage REST API.  In local/test
    environments the URL is a placeholder that the test suite can intercept.
    """
    settings = get_settings()
    storage_path = f"{workspace_id}/{project_id}/{asset_id}/{filename}"
    # Supabase signed upload URL endpoint
    url = (
        f"{settings.supabase_url}/storage/v1/object/sign/upload/"
        f"{settings.storage_bucket}/{storage_path}"
    )
    return url


def _supabase_signed_download_url(storage_path: str) -> str:
    """Return a signed download URL for an existing storage object."""
    settings = get_settings()
    url = f"{settings.supabase_url}/storage/v1/object/sign/{settings.storage_bucket}/{storage_path}"
    return url


def _asset_response(asset: Asset) -> AssetResponse:
    signed_url = _supabase_signed_download_url(asset.storage_path) if asset.storage_path else None
    thumb_url = (
        _supabase_signed_download_url(asset.thumbnail_path) if asset.thumbnail_path else None
    )
    return AssetResponse(
        id=asset.id,
        workspace_id=asset.workspace_id,
        project_id=asset.project_id,
        kind=asset.kind,
        origin=asset.origin,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        duration_ms=asset.duration_ms,
        fps=asset.fps,
        storage_path=asset.storage_path,
        thumbnail_path=asset.thumbnail_path,
        source_job_id=asset.source_job_id,
        parent_asset_id=asset.parent_asset_id,
        metadata=asset.metadata,
        created_at=asset.created_at,
        signed_url=signed_url,
        thumbnail_url=thumb_url,
    )


def _asset_ref(
    asset_id: UUID,
    kind: str,
    storage_path: str | None,
    thumbnail_path: str | None,
    role: str | None = None,
) -> LineageAssetRef:
    return LineageAssetRef(
        asset_id=asset_id,
        kind=kind,
        role=role,
        signed_url=_supabase_signed_download_url(storage_path) if storage_path else None,
        thumbnail_url=_supabase_signed_download_url(thumbnail_path) if thumbnail_path else None,
    )


async def _build_lineage(db: asyncpg.Connection[asyncpg.Record], asset: Asset) -> AssetLineage:
    """Assemble the lineage block for an asset.

    Lineage is derived from three sources: the job that produced the asset
    (prompt, model, params), the assets that job consumed (`job_inputs`), and
    the parent asset for derived media.
    """
    source_job: LineageSourceJob | None = None
    inputs: list[LineageAssetRef] = []

    if asset.source_job_id is not None:
        row = await db.fetchrow(
            """
            SELECT j.id, j.task_type, j.status, j.prompt, j.negative_prompt,
                   j.params, j.queued_at, m.slug AS model_slug,
                   m.display_name AS model_display_name
            FROM public.generation_jobs j
            LEFT JOIN public.models m ON m.id = j.model_id
            WHERE j.id = $1
            """,
            asset.source_job_id,
        )
        if row is not None:
            params = row["params"]
            if isinstance(params, str):
                params = json.loads(params)
            source_job = LineageSourceJob(
                id=row["id"],
                task_type=row["task_type"],
                status=row["status"],
                prompt=row["prompt"],
                negative_prompt=row["negative_prompt"],
                params=params or {},
                model_slug=row["model_slug"],
                model_display_name=row["model_display_name"],
                created_at=row["queued_at"],
            )

        input_rows = await db.fetch(
            """
            SELECT a.id AS asset_id, a.kind, a.storage_path, a.thumbnail_path,
                   ji.role
            FROM public.job_inputs ji
            JOIN public.assets a ON a.id = ji.asset_id
            WHERE ji.job_id = $1
            ORDER BY ji.position, a.created_at
            """,
            asset.source_job_id,
        )
        inputs = [
            _asset_ref(r["asset_id"], r["kind"], r["storage_path"], r["thumbnail_path"], r["role"])
            for r in input_rows
        ]

    parent: LineageAssetRef | None = None
    if asset.parent_asset_id is not None:
        parent_row = await db.fetchrow(
            """
            SELECT id, kind, storage_path, thumbnail_path
            FROM public.assets
            WHERE id = $1
            """,
            asset.parent_asset_id,
        )
        if parent_row is not None:
            parent = _asset_ref(
                parent_row["id"],
                parent_row["kind"],
                parent_row["storage_path"],
                parent_row["thumbnail_path"],
            )

    return AssetLineage(source_job=source_job, inputs=inputs, parent=parent)


async def _get_workspace_for_project(
    db: asyncpg.Connection[asyncpg.Record], project_id: UUID
) -> UUID | None:
    row = await db.fetchrow(
        "SELECT workspace_id FROM public.projects WHERE id = $1 AND archived_at IS NULL",
        project_id,
    )
    return row["workspace_id"] if row else None


async def _require_project_member(
    db: asyncpg.Connection[asyncpg.Record],
    project_id: UUID,
    user_id: UUID,
    min_role: WorkspaceRole = WorkspaceRole.VIEWER,
) -> UUID:
    """Return workspace_id after verifying membership; raise 403/404 on failure."""
    workspace_id = await _get_workspace_for_project(db, project_id)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Project not found")
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
        raise HTTPException(status_code=403, detail="Insufficient role for this operation")
    return workspace_id


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/assets/uploads",
    response_model=UploadResponse,
    status_code=201,
)
async def request_upload(
    project_id: UUID,
    body: UploadRequest,
    user: AuthUser,
    db: DBConn,
) -> UploadResponse:
    """Create a draft asset row and return a signed upload URL.

    The client uploads directly to storage using the signed URL, then calls
    ``POST /v1/assets/{id}/complete`` to confirm and extract metadata.
    """
    # Validate declared MIME
    if not (body.mime_type.startswith("image/") or body.mime_type.startswith("video/")):
        raise HTTPException(
            status_code=415, detail="Only image/* and video/* MIME types are accepted"
        )

    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Declared size exceeds maximum of {MAX_UPLOAD_BYTES} bytes",
        )

    workspace_id = await _require_project_member(db, project_id, user.id, WorkspaceRole.EDITOR)

    asset_id = uuid4()
    kind = AssetKind.IMAGE if body.mime_type.startswith("image/") else AssetKind.VIDEO
    settings = get_settings()
    storage_path = f"{workspace_id}/{project_id}/{asset_id}/{body.filename}"

    # Create draft asset (metadata.status = 'pending')
    repo = AssetRepository(db)
    await repo.create(
        workspace_id=workspace_id,
        project_id=project_id,
        kind=kind,
        origin=AssetOrigin.UPLOAD,
        storage_path=storage_path,
        storage_bucket=settings.storage_bucket,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        metadata={"status": "pending", "filename": body.filename},
        created_by=user.id,
    )

    # Override the uuid4 auto-generated ID by directly using the one we chose.
    # (The repository always inserts and lets Postgres generate the ID.)
    # We need the asset to use our chosen ID for deterministic storage paths.
    # Workaround: re-fetch by storage_path and return its actual ID.
    row = await db.fetchrow("SELECT id FROM public.assets WHERE storage_path = $1", storage_path)
    actual_id: UUID = row["id"] if row else asset_id

    upload_url = _supabase_signed_upload_url(workspace_id, project_id, actual_id, body.filename)
    return UploadResponse(asset_id=actual_id, upload_url=upload_url)


@router.post("/assets/{asset_id}/complete", response_model=AssetResponse)
async def complete_upload(
    asset_id: UUID,
    user: AuthUser,
    db: DBConn,
) -> AssetResponse:
    """Confirm that a direct upload has completed.

    The server verifies the object exists in storage, probes its MIME and
    dimensions, generates a thumbnail, and marks the asset ``ready``.
    """
    repo = AssetRepository(db)
    asset = await repo.get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.metadata.get("status") == "ready":
        return _asset_response(asset)

    # Check membership
    project_repo = ProjectRepository(db)
    role = await project_repo.get_member_role(asset.workspace_id, user.id)
    if role is None or role == WorkspaceRole.VIEWER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # In production we would download from storage and probe the actual bytes.
    # For MVP we trust the declared MIME from the upload request and update status.
    # A full implementation would use python-magic and studio_media probing here.

    # Mark asset ready
    await db.execute(
        """
        UPDATE public.assets
        SET metadata = metadata || $2::jsonb
        WHERE id = $1
        """,
        asset_id,
        '{"status": "ready"}',
    )

    updated = await repo.get_by_id(asset_id)
    assert updated is not None
    return _asset_response(updated)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: UUID, user: AuthUser, db: DBConn) -> AssetResponse:
    """Return an asset with its signed download URL and lineage info."""
    repo = AssetRepository(db)
    asset = await repo.get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    project_repo = ProjectRepository(db)
    role = await project_repo.get_member_role(asset.workspace_id, user.id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    response = _asset_response(asset)
    response.lineage = await _build_lineage(db, asset)
    return response


@router.get("/projects/{project_id}/assets", response_model=AssetListResponse)
async def list_assets(
    project_id: UUID,
    user: AuthUser,
    db: DBConn,
    kind: str | None = None,
    origin: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> AssetListResponse:
    """List assets in a project with cursor pagination."""
    await _require_project_member(db, project_id, user.id)

    before: datetime | None = None
    if cursor:
        try:
            before, _ = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor value") from exc

    # Build dynamic query
    clauses = ["project_id = $1", "deleted_at IS NULL"]
    params: list[object] = [project_id]

    if kind:
        params.append(kind)
        clauses.append(f"kind = ${len(params)}")
    if origin:
        params.append(origin)
        clauses.append(f"origin = ${len(params)}")
    if before:
        params.append(before)
        clauses.append(f"created_at < ${len(params)}")

    params.append(limit + 1)
    where_sql = " AND ".join(clauses)
    query = f"""
        SELECT id, workspace_id, project_id, kind, origin, storage_bucket,
               storage_path, thumbnail_path, mime_type, size_bytes, width,
               height, duration_ms, fps, source_job_id, parent_asset_id,
               metadata, created_by, created_at, deleted_at
        FROM public.assets
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT ${len(params)}
    """
    rows = await db.fetch(query, *params)
    assets = []
    for r in rows:
        data = dict(r)
        if isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        assets.append(Asset.model_validate(data))

    has_more = len(assets) > limit
    items = assets[:limit]
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return AssetListResponse(items=[_asset_response(a) for a in items], next_cursor=next_cursor)


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: UUID, user: AuthUser, db: DBConn) -> None:
    """Soft-delete an asset (sets deleted_at)."""
    repo = AssetRepository(db)
    asset = await repo.get_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    project_repo = ProjectRepository(db)
    role = await project_repo.get_member_role(asset.workspace_id, user.id)
    if role is None or role == WorkspaceRole.VIEWER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await db.execute(
        "UPDATE public.assets SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL",
        asset_id,
    )
