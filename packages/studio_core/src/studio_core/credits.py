"""Credit service managing atomic reservation, idempotent refunds, and balances."""

from decimal import Decimal
from uuid import UUID

import asyncpg

from studio_core.models import CreditLedger
from studio_core.repositories import LedgerRepository


class InsufficientCredits(Exception):
    """Raised when a workspace balance is insufficient to reserve credits."""

    def __init__(self, current_balance: Decimal, required: Decimal) -> None:
        super().__init__(f"Insufficient credits: available {current_balance}, required {required}")
        self.current_balance = current_balance
        self.required = required


class CreditService:
    """Atomic operations on credit balances."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn
        self.ledger_repo = LedgerRepository(conn)

    async def get_balance(self, workspace_id: UUID) -> Decimal:
        """Get the current credit balance of a workspace."""
        return await self.ledger_repo.get_balance(workspace_id)

    async def reserve(
        self,
        workspace_id: UUID,
        job_id: UUID,
        amount: Decimal,
    ) -> CreditLedger:
        """Reserve credits for a job.

        Acquires a row-level lock on the workspace (`SELECT ... FOR UPDATE`),
        checks that the current balance >= amount, and inserts a negative ledger entry.
        Raises `InsufficientCredits` if the balance is too low.
        """
        if amount < Decimal("0.00"):
            raise ValueError("Reserve amount must be non-negative")

        # 1. Lock workspace row to serialize credit operations for this workspace
        lock_query = "SELECT id FROM public.workspaces WHERE id = $1 FOR UPDATE"
        workspace_exists = await self.conn.fetchval(lock_query, workspace_id)
        if not workspace_exists:
            raise ValueError(f"Workspace {workspace_id} not found")

        # 2. Check balance
        current_balance = await self.ledger_repo.get_balance(workspace_id)
        if current_balance < amount:
            raise InsufficientCredits(current_balance, amount)

        # 3. Insert negative entry
        delta = -abs(amount)
        return await self.ledger_repo.insert_entry(
            workspace_id=workspace_id,
            job_id=job_id,
            delta=delta,
            reason="reserve",
        )

    async def refund(self, job_id: UUID) -> CreditLedger | None:
        """Idempotently refund reserved credits for a job.

        If a refund entry already exists for this job, returns None (no-op).
        Otherwise finds the reserved amount, locks the workspace, and inserts
        a positive ledger entry equal to the reserved amount.
        """
        # Idempotency check: has it already been refunded?
        if await self.ledger_repo.has_refund_for_job(job_id):
            return None

        # Find the job details and reserved amount
        job_query = """
            SELECT workspace_id, cost_credits
            FROM public.generation_jobs
            WHERE id = $1
        """
        job_row = await self.conn.fetchrow(job_query, job_id)
        if not job_row:
            return None

        workspace_id: UUID = job_row["workspace_id"]
        # Look up exact reserved delta in ledger or fall back to job.cost_credits
        reserved_amount = await self.ledger_repo.get_reserved_amount_for_job(job_id)
        if reserved_amount is None:
            reserved_amount = Decimal(str(job_row["cost_credits"]))

        if reserved_amount <= Decimal("0.00"):
            return None

        # Lock workspace row for update
        lock_ws_sql = "SELECT id FROM public.workspaces WHERE id = $1 FOR UPDATE"
        await self.conn.fetchval(lock_ws_sql, workspace_id)

        # Double check after lock
        if await self.ledger_repo.has_refund_for_job(job_id):
            return None

        return await self.ledger_repo.insert_entry(
            workspace_id=workspace_id,
            job_id=job_id,
            delta=reserved_amount,
            reason="refund",
        )
