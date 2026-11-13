"""Projects router — CRUD for projects within a workspace.

Endpoints:
  POST   /v1/workspaces/{ws}/projects
  GET    /v1/workspaces/{ws}/projects
  GET    /v1/projects/{id}
  PATCH  /v1/projects/{id}
  DELETE /v1/projects/{id}  (soft-archive)
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import AuthUser
from api.deps import DBConn
from api.pagination import decode_cursor, encode_cursor
from api.routers.assets import _supabase_signed_download_url
from studio_core.models import Project, WorkspaceRole
from studio_core.repositories import ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100


# ── Schemas ────────────────────────────────────────────────────────────────────


class ProjectPreviewAsset(BaseModel):
    """A thumbnail-sized asset used to preview a project on its card."""

    asset_id: UUID
    kind: str
    origin: str
    thumbnail_url: str | None = None
    signed_url: str | None = None


class ProjectResponse(BaseModel):
    """Project as returned to clients."""

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    cover_asset_id: UUID | None
    previews: list[ProjectPreviewAsset] = Field(default_factory=list)
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    next_cursor: str | None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _project_response(
    p: Project,
    previews: list[ProjectPreviewAsset] | None = None,
) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        workspace_id=p.workspace_id,
        name=p.name,
        description=p.description,
        cover_asset_id=p.cover_asset_id,
        previews=previews or [],
        created_by=p.created_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
        archived_at=p.archived_at,
    )


async def _fetch_project_previews(
    db: DBConn,
    project_ids: list[UUID],
    limit_per_project: int = 4,
) -> dict[UUID, list[ProjectPreviewAsset]]:
    """Return ready thumbnails for each project, generated media first.

    One window-function query covers every project on the page so the project
    list stays a single round-trip regardless of how many cards are shown.
    """
    if not project_ids:
        return {}

    rows = await db.fetch(
        """
        SELECT asset_id, project_id, kind, origin, storage_path, thumbnail_path
        FROM (
            SELECT a.id AS asset_id, a.project_id, a.kind, a.origin,
                   a.storage_path, a.thumbnail_path,
                   row_number() OVER (
                       PARTITION BY a.project_id
                       ORDER BY
                           CASE a.origin
                               WHEN 'generated' THEN 0
                               WHEN 'derived' THEN 1
                               ELSE 2
                           END,
                           a.created_at DESC,
                           a.id DESC
                   ) AS position
            FROM public.assets a
            WHERE a.project_id = ANY($1::uuid[])
              AND a.deleted_at IS NULL
              AND COALESCE(a.metadata->>'status', 'ready') = 'ready'
              AND (a.thumbnail_path IS NOT NULL OR a.kind = 'image')
        ) ranked
        WHERE position <= $2
        ORDER BY project_id, position
        """,
        project_ids,
        limit_per_project,
    )

    previews: dict[UUID, list[ProjectPreviewAsset]] = {project_id: [] for project_id in project_ids}
    for row in rows:
        thumbnail_path = row["thumbnail_path"]
        storage_path = row["storage_path"]
        previews[row["project_id"]].append(
            ProjectPreviewAsset(
                asset_id=row["asset_id"],
                kind=str(row["kind"]),
                origin=str(row["origin"]),
                thumbnail_url=(
                    _supabase_signed_download_url(thumbnail_path) if thumbnail_path else None
                ),
                signed_url=_supabase_signed_download_url(storage_path) if storage_path else None,
            )
        )
    return previews


async def _require_workspace_member(
    db: DBConn,
    workspace_id: UUID,
    user_id: UUID,
    min_role: WorkspaceRole = WorkspaceRole.VIEWER,
) -> WorkspaceRole:
    """Verify membership and return the user's role; raise 403 if denied."""
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
    return role


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=201,
)
async def create_project(
    workspace_id: UUID,
    body: CreateProjectRequest,
    user: AuthUser,
    db: DBConn,
) -> ProjectResponse:
    """Create a new project in the workspace."""
    await _require_workspace_member(db, workspace_id, user.id, WorkspaceRole.EDITOR)
    repo = ProjectRepository(db)
    project = await repo.create(
        workspace_id=workspace_id,
        name=body.name,
        created_by=user.id,
        description=body.description,
    )
    return _project_response(project)


@router.get("/workspaces/{workspace_id}/projects", response_model=ProjectListResponse)
async def list_projects(
    workspace_id: UUID,
    user: AuthUser,
    db: DBConn,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> ProjectListResponse:
    """List projects in the workspace with cursor pagination."""
    await _require_workspace_member(db, workspace_id, user.id)
    before: datetime | None = None
    if cursor:
        try:
            before, _ = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor value") from exc

    repo = ProjectRepository(db)
    # Fetch one extra to determine if there's a next page
    projects = await repo.list_by_workspace(workspace_id, limit=limit + 1, before=before)
    has_more = len(projects) > limit
    items = projects[:limit]

    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    previews = await _fetch_project_previews(db, [p.id for p in items])
    return ProjectListResponse(
        items=[_project_response(p, previews.get(p.id, [])) for p in items],
        next_cursor=next_cursor,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, user: AuthUser, db: DBConn) -> ProjectResponse:
    """Retrieve a single project by ID."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await _require_workspace_member(db, project.workspace_id, user.id)
    previews = await _fetch_project_previews(db, [project.id])
    return _project_response(project, previews.get(project.id, []))


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: UpdateProjectRequest,
    user: AuthUser,
    db: DBConn,
) -> ProjectResponse:
    """Rename or update description of a project."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await _require_workspace_member(db, project.workspace_id, user.id, WorkspaceRole.EDITOR)

    # Build update dynamically
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description

    if not updates:
        return _project_response(project)

    set_parts = []
    params: list[object] = [project_id]
    for field, value in updates.items():
        params.append(value)
        set_parts.append(f"{field} = ${len(params)}")
    set_parts.append("updated_at = now()")

    set_sql = ", ".join(set_parts)
    row = await db.fetchrow(
        f"""
        UPDATE public.projects
        SET {set_sql}
        WHERE id = $1 AND archived_at IS NULL
        RETURNING id, workspace_id, name, description, cover_asset_id,
                  created_by, created_at, updated_at, archived_at
        """,
        *params,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found or already archived")
    return _project_response(Project.model_validate(dict(row)))


@router.delete("/projects/{project_id}", status_code=204)
async def archive_project(project_id: UUID, user: AuthUser, db: DBConn) -> None:
    """Soft-archive a project (sets archived_at)."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await _require_workspace_member(db, project.workspace_id, user.id, WorkspaceRole.EDITOR)

    await db.execute(
        "UPDATE public.projects SET archived_at = now() WHERE id = $1 AND archived_at IS NULL",
        project_id,
    )
