"""Workspaces router — CRUD helpers, credits, and credit activity.

Endpoints:
  GET   /v1/workspaces
  POST  /v1/workspaces
  PATCH /v1/workspaces/{workspace_id}
  GET   /v1/workspaces/{workspace_id}/credits
  GET   /v1/workspaces/{workspace_id}/credits/transactions
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import AuthUser
from api.deps import DBConn
from studio_core.models import CreditTransaction, WorkspaceRole
from studio_core.repositories import LedgerRepository, ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspaces"])

DEFAULT_TRANSACTION_PAGE_SIZE = 20
MAX_TRANSACTION_PAGE_SIZE = 100
ACTIVITY_WINDOW_DAYS = 30

_MANAGER_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}


class WorkspaceResponse(BaseModel):
    """Workspace representation returned to clients."""

    id: UUID
    name: str
    owner_id: UUID


class CreateWorkspaceRequest(BaseModel):
    """Request to create a new workspace."""

    name: str = Field(min_length=1, max_length=100)


class UpdateWorkspaceRequest(BaseModel):
    """Request to rename an existing workspace."""

    name: str = Field(min_length=1, max_length=100)


class CreditBalanceResponse(BaseModel):
    """Current credit balance for a workspace."""

    workspace_id: UUID
    balance: Decimal


class CreditTransactionResponse(BaseModel):
    """A single credit ledger entry enriched with job context."""

    id: int
    workspace_id: UUID
    job_id: UUID | None
    delta: Decimal
    reason: str
    created_at: datetime
    balance_after: Decimal
    model_name: str | None
    job_status: str | None
    prompt: str | None


class CreditActivitySummary(BaseModel):
    """Aggregated credit activity over the recent window."""

    window_days: int
    spent: Decimal
    refunded: Decimal
    granted: Decimal
    transactions: int


class CreditTransactionsResponse(BaseModel):
    """A page of credit transactions plus recent aggregate activity."""

    items: list[CreditTransactionResponse]
    next_before_id: int | None
    summary: CreditActivitySummary


def _transaction_response(tx: CreditTransaction) -> CreditTransactionResponse:
    return CreditTransactionResponse(
        id=tx.id,
        workspace_id=tx.workspace_id,
        job_id=tx.job_id,
        delta=tx.delta,
        reason=tx.reason,
        created_at=tx.created_at,
        balance_after=tx.balance_after,
        model_name=tx.model_name,
        job_status=tx.job_status,
        prompt=tx.prompt,
    )


async def _member_role(db: DBConn, workspace_id: UUID, user_id: UUID) -> WorkspaceRole | None:
    return await ProjectRepository(db).get_member_role(workspace_id, user_id)


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


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    body: UpdateWorkspaceRequest,
    user: AuthUser,
    db: DBConn,
) -> WorkspaceResponse:
    """Rename a workspace. Requires the owner or admin role."""
    role = await _member_role(db, workspace_id, user.id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if role not in _MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient role for this operation")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Workspace name cannot be blank")

    row = await db.fetchrow(
        """
        UPDATE public.workspaces
        SET name = $2
        WHERE id = $1
        RETURNING id, name, owner_id
        """,
        workspace_id,
        name,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse(id=row["id"], name=row["name"], owner_id=row["owner_id"])


@router.get("/workspaces/{workspace_id}/credits", response_model=CreditBalanceResponse)
async def get_credit_balance(
    workspace_id: UUID,
    user: AuthUser,
    db: DBConn,
) -> CreditBalanceResponse:
    """Return the current credit balance for a workspace the caller belongs to.

    The balance is derived from the append-only ``credit_ledger`` so it always
    reflects reservations, refunds, grants, and purchases.
    """
    role = await _member_role(db, workspace_id, user.id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    balance = await LedgerRepository(db).get_balance(workspace_id)
    return CreditBalanceResponse(workspace_id=workspace_id, balance=balance)


@router.get(
    "/workspaces/{workspace_id}/credits/transactions",
    response_model=CreditTransactionsResponse,
)
async def list_credit_transactions(
    workspace_id: UUID,
    user: AuthUser,
    db: DBConn,
    limit: Annotated[
        int, Query(ge=1, le=MAX_TRANSACTION_PAGE_SIZE)
    ] = DEFAULT_TRANSACTION_PAGE_SIZE,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> CreditTransactionsResponse:
    """List credit ledger activity for a workspace with backward pagination.

    Each entry includes the balance after that entry. The response also carries
    a summary of the last 30 days so the usage screen can render headline
    numbers without a second request.
    """
    role = await _member_role(db, workspace_id, user.id)
    if role is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    repo = LedgerRepository(db)
    # Fetch one extra row to determine whether another page exists.
    transactions = await repo.list_transactions(workspace_id, limit=limit + 1, before_id=before_id)
    has_more = len(transactions) > limit
    page = transactions[:limit]
    next_before_id = page[-1].id if has_more and page else None

    summary = await repo.get_activity_summary(workspace_id, days=ACTIVITY_WINDOW_DAYS)

    return CreditTransactionsResponse(
        items=[_transaction_response(tx) for tx in page],
        next_before_id=next_before_id,
        summary=CreditActivitySummary(
            window_days=ACTIVITY_WINDOW_DAYS,
            spent=Decimal(str(summary["spent"])),
            refunded=Decimal(str(summary["refunded"])),
            granted=Decimal(str(summary["granted"])),
            transactions=int(summary["transactions"]),
        ),
    )
