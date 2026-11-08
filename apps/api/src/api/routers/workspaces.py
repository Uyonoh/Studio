"""Workspaces router — GET /v1/workspaces, POST /v1/workspaces."""

import logging
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.auth import AuthUser
from api.deps import DBConn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    """Workspace representation returned to clients."""

    id: UUID
    name: str
    owner_id: UUID


class CreateWorkspaceRequest(BaseModel):
    """Request to create a new workspace."""

    name: str = Field(min_length=1, max_length=100)


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(user: AuthUser, db: DBConn) -> list[WorkspaceResponse]:
    """Return all workspaces where the authenticated user is a member."""
    rows = await db.fetch(
        """
        SELECT w.id, w.name, w.owner_id
        FROM public.workspaces w
        JOIN public.workspace_members wm ON wm.workspace_id = w.id
        WHERE wm.user_id = $1
        ORDER BY w.created_at DESC
        """,
        user.id,
    )
    return [WorkspaceResponse(id=r["id"], name=r["name"], owner_id=r["owner_id"]) for r in rows]


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    user: AuthUser,
    db: DBConn,
) -> WorkspaceResponse:
    """Create a new workspace and make the caller the owner."""
    async with db.transaction():
        # Ensure profile exists
        await db.execute(
            """
            INSERT INTO public.profiles (id, display_name, created_at)
            VALUES ($1, $2, now())
            ON CONFLICT (id) DO NOTHING
            """,
            user.id,
            user.email.split("@")[0] if user.email else "User",
        )

        ws_row = await db.fetchrow(
            """
            INSERT INTO public.workspaces (name, owner_id, created_at)
            VALUES ($1, $2, now())
            RETURNING id, name, owner_id
            """,
            body.name,
            user.id,
        )
        if not ws_row:
            raise RuntimeError("Failed to insert workspace")

        await db.execute(
            """
            INSERT INTO public.workspace_members (workspace_id, user_id, role, created_at)
            VALUES ($1, $2, 'owner', now())
            """,
            ws_row["id"],
            user.id,
        )

    return WorkspaceResponse(id=ws_row["id"], name=ws_row["name"], owner_id=ws_row["owner_id"])
