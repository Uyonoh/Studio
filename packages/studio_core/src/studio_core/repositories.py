"""Repositories for accessing projects, models, assets, jobs, ledger, and events.

Strict adherence to parameterization: no string formatting or interpolation in SQL queries.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from studio_core.models import (
    Asset,
    AssetKind,
    AssetOrigin,
    CreditLedger,
    GenerationJob,
    JobEvent,
    JobInput,
    JobStatus,
    Model,
    Project,
    TaskType,
    WorkspaceRole,
)


class ProjectRepository:
    """Data access for projects and workspace membership checks."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def get_by_id(self, project_id: UUID) -> Project | None:
        query = """
            SELECT id, workspace_id, name, description, cover_asset_id,
                   created_by, created_at, updated_at, archived_at
            FROM public.projects
            WHERE id = $1 AND archived_at IS NULL
        """
        row = await self.conn.fetchrow(query, project_id)
        return Project.model_validate(dict(row)) if row else None

    async def create(
        self,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        description: str | None = None,
    ) -> Project:
        query = """
            INSERT INTO public.projects (workspace_id, name, created_by, description)
            VALUES ($1, $2, $3, $4)
            RETURNING id, workspace_id, name, description, cover_asset_id,
                      created_by, created_at, updated_at, archived_at
        """
        row = await self.conn.fetchrow(query, workspace_id, name, created_by, description)
        assert row is not None
        return Project.model_validate(dict(row))

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Project]:
        if before:
            query = """
                SELECT id, workspace_id, name, description, cover_asset_id,
                       created_by, created_at, updated_at, archived_at
                FROM public.projects
                WHERE workspace_id = $1 AND archived_at IS NULL AND created_at < $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await self.conn.fetch(query, workspace_id, before, limit)
        else:
            query = """
                SELECT id, workspace_id, name, description, cover_asset_id,
                       created_by, created_at, updated_at, archived_at
                FROM public.projects
                WHERE workspace_id = $1 AND archived_at IS NULL
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await self.conn.fetch(query, workspace_id, limit)
        return [Project.model_validate(dict(r)) for r in rows]

    async def get_member_role(self, workspace_id: UUID, user_id: UUID) -> WorkspaceRole | None:
        query = """
            SELECT role
            FROM public.workspace_members
            WHERE workspace_id = $1 AND user_id = $2
        """
        val = await self.conn.fetchval(query, workspace_id, user_id)
        return WorkspaceRole(val) if val else None


class ModelRepository:
    """Data access for models and providers."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def get_by_id(self, model_id: UUID) -> Model | None:
        query = """
            SELECT id, provider_id, provider_model, slug, display_name,
                   task_type, input_schema, default_params, cost_credits, enabled
            FROM public.models
            WHERE id = $1
        """
        row = await self.conn.fetchrow(query, model_id)
        if not row:
            return None
        data = dict(row)
        if isinstance(data["input_schema"], str):
            data["input_schema"] = json.loads(data["input_schema"])
        if isinstance(data["default_params"], str):
            data["default_params"] = json.loads(data["default_params"])
        return Model.model_validate(data)

    async def get_by_slug(self, slug: str) -> Model | None:
        query = """
            SELECT id, provider_id, provider_model, slug, display_name,
                   task_type, input_schema, default_params, cost_credits, enabled
            FROM public.models
            WHERE slug = $1
        """
        row = await self.conn.fetchrow(query, slug)
        if not row:
            return None
        data = dict(row)
        if isinstance(data["input_schema"], str):
            data["input_schema"] = json.loads(data["input_schema"])
        if isinstance(data["default_params"], str):
            data["default_params"] = json.loads(data["default_params"])
        return Model.model_validate(data)

    async def list_models(
        self,
        task_type: TaskType | None = None,
        only_enabled: bool = True,
    ) -> list[Model]:
        clauses = []
        params: list[Any] = []
        if only_enabled:
            clauses.append("enabled = TRUE")
        if task_type:
            params.append(task_type.value)
            clauses.append(f"task_type = ${len(params)}")

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"""
            SELECT id, provider_id, provider_model, slug, display_name,
                   task_type, input_schema, default_params, cost_credits, enabled
            FROM public.models
            {where_sql}
            ORDER BY display_name ASC
        """
        rows = await self.conn.fetch(query, *params)
        results: list[Model] = []
        for r in rows:
            data = dict(r)
            if isinstance(data["input_schema"], str):
                data["input_schema"] = json.loads(data["input_schema"])
            if isinstance(data["default_params"], str):
                data["default_params"] = json.loads(data["default_params"])
            results.append(Model.model_validate(data))
        return results


class AssetRepository:
    """Data access for media assets."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def get_by_id(self, asset_id: UUID) -> Asset | None:
        query = """
            SELECT id, workspace_id, project_id, kind, origin, storage_bucket,
                   storage_path, thumbnail_path, mime_type, size_bytes, width,
                   height, duration_ms, fps, source_job_id, parent_asset_id,
                   metadata, created_by, created_at, deleted_at
            FROM public.assets
            WHERE id = $1 AND deleted_at IS NULL
        """
        row = await self.conn.fetchrow(query, asset_id)
        if not row:
            return None
        data = dict(row)
        if isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        return Asset.model_validate(data)

    async def get_many(self, asset_ids: Sequence[UUID]) -> list[Asset]:
        if not asset_ids:
            return []
        query = """
            SELECT id, workspace_id, project_id, kind, origin, storage_bucket,
                   storage_path, thumbnail_path, mime_type, size_bytes, width,
                   height, duration_ms, fps, source_job_id, parent_asset_id,
                   metadata, created_by, created_at, deleted_at
            FROM public.assets
            WHERE id = ANY($1) AND deleted_at IS NULL
        """
        rows = await self.conn.fetch(query, list(asset_ids))
        assets: list[Asset] = []
        for r in rows:
            data = dict(r)
            if isinstance(data["metadata"], str):
                data["metadata"] = json.loads(data["metadata"])
            assets.append(Asset.model_validate(data))
        return assets

    async def create(
        self,
        workspace_id: UUID,
        project_id: UUID,
        kind: AssetKind,
        origin: AssetOrigin,
        storage_path: str,
        storage_bucket: str = "media",
        thumbnail_path: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        width: int | None = None,
        height: int | None = None,
        duration_ms: int | None = None,
        fps: Decimal | None = None,
        source_job_id: UUID | None = None,
        parent_asset_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> Asset:
        query = """
            INSERT INTO public.assets (
                workspace_id, project_id, kind, origin, storage_bucket,
                storage_path, thumbnail_path, mime_type, size_bytes, width,
                height, duration_ms, fps, source_job_id, parent_asset_id,
                metadata, created_by
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17
            )
            RETURNING id, workspace_id, project_id, kind, origin, storage_bucket,
                      storage_path, thumbnail_path, mime_type, size_bytes, width,
                      height, duration_ms, fps, source_job_id, parent_asset_id,
                      metadata, created_by, created_at, deleted_at
        """
        row = await self.conn.fetchrow(
            query,
            workspace_id,
            project_id,
            kind.value,
            origin.value,
            storage_bucket,
            storage_path,
            thumbnail_path,
            mime_type,
            size_bytes,
            width,
            height,
            duration_ms,
            fps,
            source_job_id,
            parent_asset_id,
            json.dumps(metadata or {}),
            created_by,
        )
        assert row is not None
        data = dict(row)
        if isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        return Asset.model_validate(data)


class JobRepository:
    """Data access for generation jobs and job inputs."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def get_by_id(self, job_id: UUID) -> GenerationJob | None:
        query = """
            SELECT id, workspace_id, project_id, created_by, model_id, task_type,
                   status, prompt, negative_prompt, params, idempotency_key,
                   provider_job_id, attempt, max_attempts, error_code, error_message,
                   cost_credits, parent_job_id, workflow_run_id, queued_at,
                   started_at, completed_at, heartbeat_at
            FROM public.generation_jobs
            WHERE id = $1
        """
        row = await self.conn.fetchrow(query, job_id)
        if not row:
            return None
        data = dict(row)
        if isinstance(data["params"], str):
            data["params"] = json.loads(data["params"])
        return GenerationJob.model_validate(data)

    async def get_by_idempotency_key(
        self, workspace_id: UUID, idempotency_key: str
    ) -> GenerationJob | None:
        query = """
            SELECT id, workspace_id, project_id, created_by, model_id, task_type,
                   status, prompt, negative_prompt, params, idempotency_key,
                   provider_job_id, attempt, max_attempts, error_code, error_message,
                   cost_credits, parent_job_id, workflow_run_id, queued_at,
                   started_at, completed_at, heartbeat_at
            FROM public.generation_jobs
            WHERE workspace_id = $1 AND idempotency_key = $2
        """
        row = await self.conn.fetchrow(query, workspace_id, idempotency_key)
        if not row:
            return None
        data = dict(row)
        if isinstance(data["params"], str):
            data["params"] = json.loads(data["params"])
        return GenerationJob.model_validate(data)

    async def count_active_jobs_for_workspace(self, workspace_id: UUID) -> int:
        query = """
            SELECT count(*)
            FROM public.generation_jobs
            WHERE workspace_id = $1
              AND status IN ('queued', 'submitting', 'running', 'finalizing')
        """
        val = await self.conn.fetchval(query, workspace_id)
        return int(val) if val is not None else 0

    async def create(
        self,
        workspace_id: UUID,
        project_id: UUID,
        created_by: UUID,
        model_id: UUID,
        task_type: TaskType,
        prompt: str | None,
        negative_prompt: str | None,
        params: dict[str, Any],
        cost_credits: Decimal,
        idempotency_key: str | None = None,
        parent_job_id: UUID | None = None,
    ) -> GenerationJob:
        query = """
            INSERT INTO public.generation_jobs (
                workspace_id, project_id, created_by, model_id, task_type,
                status, prompt, negative_prompt, params, cost_credits,
                idempotency_key, parent_job_id
            ) VALUES (
                $1, $2, $3, $4, $5,
                'queued', $6, $7, $8, $9,
                $10, $11
            )
            RETURNING id, workspace_id, project_id, created_by, model_id, task_type,
                      status, prompt, negative_prompt, params, idempotency_key,
                      provider_job_id, attempt, max_attempts, error_code, error_message,
                      cost_credits, parent_job_id, workflow_run_id, queued_at,
                      started_at, completed_at, heartbeat_at
        """
        row = await self.conn.fetchrow(
            query,
            workspace_id,
            project_id,
            created_by,
            model_id,
            task_type.value,
            prompt,
            negative_prompt,
            json.dumps(params),
            cost_credits,
            idempotency_key,
            parent_job_id,
        )
        assert row is not None
        data = dict(row)
        if isinstance(data["params"], str):
            data["params"] = json.loads(data["params"])
        return GenerationJob.model_validate(data)

    async def add_inputs(
        self,
        job_id: UUID,
        inputs: Sequence[tuple[UUID, str, int]],  # (asset_id, role, position)
    ) -> None:
        if not inputs:
            return
        query = """
            INSERT INTO public.job_inputs (job_id, asset_id, role, position)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (job_id, asset_id, role) DO NOTHING
        """
        records = [(job_id, asset_id, role, pos) for asset_id, role, pos in inputs]
        await self.conn.executemany(query, records)

    async def get_inputs(self, job_id: UUID) -> list[JobInput]:
        query = """
            SELECT job_id, asset_id, role, position
            FROM public.job_inputs
            WHERE job_id = $1
            ORDER BY position ASC
        """
        rows = await self.conn.fetch(query, job_id)
        return [JobInput.model_validate(dict(r)) for r in rows]


class EventRepository:
    """Append-only audit and debug log for job events."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def append(
        self,
        job_id: UUID,
        event_type: str,
        from_status: JobStatus | None = None,
        to_status: JobStatus | None = None,
        payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        query = """
            INSERT INTO public.job_events (job_id, type, from_status, to_status, payload)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, job_id, type, from_status, to_status, payload, created_at
        """
        row = await self.conn.fetchrow(
            query,
            job_id,
            event_type,
            from_status.value if from_status else None,
            to_status.value if to_status else None,
            json.dumps(payload) if payload else None,
        )
        assert row is not None
        data = dict(row)
        if isinstance(data["payload"], str):
            data["payload"] = json.loads(data["payload"])
        return JobEvent.model_validate(data)

    async def list_by_job(self, job_id: UUID) -> list[JobEvent]:
        query = """
            SELECT id, job_id, type, from_status, to_status, payload, created_at
            FROM public.job_events
            WHERE job_id = $1
            ORDER BY id ASC
        """
        rows = await self.conn.fetch(query, job_id)
        events: list[JobEvent] = []
        for r in rows:
            data = dict(r)
            if isinstance(data["payload"], str):
                data["payload"] = json.loads(data["payload"])
            events.append(JobEvent.model_validate(data))
        return events


class LedgerRepository:
    """Credit balance ledger repository with atomic reserve and refund."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def get_balance(self, workspace_id: UUID) -> Decimal:
        query = """
            SELECT coalesce(sum(delta), 0)::numeric(10,2)
            FROM public.credit_ledger
            WHERE workspace_id = $1
        """
        val = await self.conn.fetchval(query, workspace_id)
        return Decimal(str(val)) if val is not None else Decimal("0.00")

    async def has_refund_for_job(self, job_id: UUID) -> bool:
        query = """
            SELECT 1
            FROM public.credit_ledger
            WHERE job_id = $1 AND reason = 'refund'
            LIMIT 1
        """
        val = await self.conn.fetchval(query, job_id)
        return val is not None

    async def get_reserved_amount_for_job(self, job_id: UUID) -> Decimal | None:
        query = """
            SELECT abs(delta)
            FROM public.credit_ledger
            WHERE job_id = $1 AND reason = 'reserve'
            ORDER BY id DESC
            LIMIT 1
        """
        val = await self.conn.fetchval(query, job_id)
        return Decimal(str(val)) if val is not None else None

    async def insert_entry(
        self,
        workspace_id: UUID,
        delta: Decimal,
        reason: str,
        job_id: UUID | None = None,
    ) -> CreditLedger:
        query = """
            INSERT INTO public.credit_ledger (workspace_id, job_id, delta, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING id, workspace_id, job_id, delta, reason, created_at
        """
        row = await self.conn.fetchrow(query, workspace_id, job_id, delta, reason)
        assert row is not None
        return CreditLedger.model_validate(dict(row))
