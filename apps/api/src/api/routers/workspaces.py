"""Workspaces router — GET /v1/workspaces."""

import logging
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from api.auth import AuthUser
from api.deps import DBConn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    """Workspace representation returned to clients."""

    id: UUID
    name: str
    owner_id: UUID


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
