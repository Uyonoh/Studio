"""Shared test utilities and fixtures for worker tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from worker.config import WorkerConfig


class MockDB:
    """In-memory database stub for testing worker tasks."""

    def __init__(self) -> None:
        self.jobs: dict[UUID, dict[str, Any]] = {}
        self.models: dict[UUID, dict[str, Any]] = {}
        self.assets: dict[UUID, dict[str, Any]] = {}
        self.inputs: dict[UUID, list[dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []
        self.ledger: list[dict[str, Any]] = []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def add_job(self, job_dict: dict[str, Any]) -> None:
        self.jobs[job_dict["id"]] = job_dict

    def add_model(self, model_dict: dict[str, Any]) -> None:
        self.models[model_dict["id"]] = model_dict

    def add_asset(self, asset_dict: dict[str, Any]) -> None:
        self.assets[asset_dict["id"]] = asset_dict

    def add_input(self, job_id: UUID, asset_id: UUID, role: str) -> None:
        self.inputs.setdefault(job_id, []).append(
            {"job_id": job_id, "asset_id": asset_id, "role": role, "position": 0}
        )

    def make_conn(self) -> AsyncMock:
        conn = AsyncMock()

        async def fetchrow(query: str, *params: Any) -> dict[str, Any] | None:
            now = datetime.now(UTC)

            if "FROM public.generation_jobs" in query:
                if params and isinstance(params[0], UUID):
                    job = self.jobs.get(params[0])
                    if job:
                        return dict(job)
                if self.jobs:
                    return dict(next(iter(self.jobs.values())))
                return None

            if "UPDATE public.generation_jobs" in query and "RETURNING" in query:
                # StateMachine transition
                import re

                job_id: UUID = params[0]
                job = self.jobs.get(job_id)
                if not job:
                    return None

                # Check status guard in query
                for st in (
                    "queued",
                    "submitting",
                    "running",
                    "finalizing",
                    "succeeded",
                    "failed",
                    "canceled",
                ):
                    if f"status = '{st}'" in query:
                        if job["status"] != st:
                            return None
                        break

                # Parse SET clauses dynamically from query
                set_part = query.split("SET ")[1].split(" WHERE ")[0]
                for clause in set_part.split(", "):
                    clause = clause.strip()
                    m = re.search(r"(\w+)\s*=\s*(?:COALESCE\([^,]+,\s*)?\$(\d+)", clause)
                    if m:
                        col_name, idx_str = m.group(1), m.group(2)
                        p_val = params[int(idx_str) - 1]
                        if hasattr(p_val, "value"):
                            p_val = p_val.value
                        job[col_name] = p_val

                return dict(job)

            if "INSERT INTO public.job_events" in query:
                event = {
                    "id": len(self.events) + 1,
                    "job_id": params[0],
                    "type": params[1],
                    "from_status": params[2],
                    "to_status": params[3],
                    "payload": params[4],
                    "created_at": now,
                }
                self.events.append(event)
                return event

            if "FROM public.models" in query:
                if params and isinstance(params[0], UUID):
                    model = self.models.get(params[0])
                    if model:
                        return dict(model)
                if self.models:
                    return dict(next(iter(self.models.values())))
                return None

            if "INSERT INTO public.credit_ledger" in query:
                entry = {
                    "id": len(self.ledger) + 1,
                    "workspace_id": params[0],
                    "job_id": params[1],
                    "delta": params[2],
                    "reason": params[3],
                    "created_at": now,
                }
                self.ledger.append(entry)
                return entry

            if "FROM public.assets" in query:
                if params and isinstance(params[0], UUID):
                    asset = self.assets.get(params[0])
                    if asset:
                        return dict(asset)
                return None

            return None

        async def fetch(query: str, *params: Any) -> list[dict[str, Any]]:
            if "FROM public.job_inputs" in query:
                if params and isinstance(params[0], UUID):
                    return self.inputs.get(params[0], [])
                return []

            if "FROM public.assets" in query and ("ANY" in query or "WHERE id =" in query):
                if params and isinstance(params[0], (list, tuple)):
                    return [dict(self.assets[aid]) for aid in params[0] if aid in self.assets]
                return []

            # Reconciler queries
            if "FROM public.generation_jobs" in query and "FOR UPDATE SKIP LOCKED" in query:
                if "status = 'running'" in query:
                    return [dict(j) for j in self.jobs.values() if j["status"] == "running"]
                if "status = 'submitting'" in query:
                    return [dict(j) for j in self.jobs.values() if j["status"] == "submitting"]
                if "status = 'queued'" in query:
                    cutoff = params[0] if params else None
                    matching = []
                    for j in self.jobs.values():
                        if j["status"] == "queued":
                            hb = j.get("heartbeat_at")
                            qa = j.get("queued_at")
                            if cutoff:
                                if hb and hb < cutoff:
                                    matching.append(dict(j))
                                elif not hb and qa and qa < cutoff:
                                    matching.append(dict(j))
                            else:
                                matching.append(dict(j))
                    return matching
                if "status = 'finalizing'" in query:
                    return [dict(j) for j in self.jobs.values() if j["status"] == "finalizing"]

            return []

        async def fetchval(query: str, *params: Any) -> Any:
            if "FROM public.credit_ledger" in query:
                if "reason = 'refund'" in query:
                    job_id = params[0]
                    has_ref = any(
                        e.get("job_id") == job_id and e.get("reason") == "refund"
                        for e in self.ledger
                    )
                    return 1 if has_ref else None
                if "reason = 'reserve'" in query:
                    job_id = params[0]
                    res = next(
                        (
                            e
                            for e in reversed(self.ledger)
                            if e.get("job_id") == job_id and e.get("reason") == "reserve"
                        ),
                        None,
                    )
                    return abs(res["delta"]) if res else Decimal("1.00")
                if "sum(delta)" in query:
                    ws_id = params[0]
                    total = sum(
                        (e["delta"] for e in self.ledger if e.get("workspace_id") == ws_id),
                        Decimal("0.00"),
                    )
                    return total

            if "FROM public.workspaces" in query and "FOR UPDATE" in query:
                return params[0]

            return None

        async def execute(query: str, *params: Any) -> str:
            self.executed.append((query, params))

            if "UPDATE public.generation_jobs" in query and "SET status = 'queued'" in query:
                job_id = params[0]
                if job_id in self.jobs:
                    self.jobs[job_id]["status"] = "queued"
                    if len(params) > 1:
                        self.jobs[job_id]["attempt"] = params[1]
                    if "heartbeat_at" in query:
                        self.jobs[job_id]["heartbeat_at"] = datetime.now(UTC)
                return "UPDATE 1"

            if "UPDATE public.generation_jobs" in query and "SET status = 'running'" in query:
                job_id = params[0]
                if job_id in self.jobs:
                    self.jobs[job_id]["status"] = "running"
                return "UPDATE 1"

            if "INSERT INTO public.assets" in query:
                asset_id = params[0]
                self.assets[asset_id] = {
                    "id": asset_id,
                    "workspace_id": params[1],
                    "project_id": params[2],
                    "kind": params[3],
                    "origin": params[4],
                    "storage_bucket": params[5],
                    "storage_path": params[6],
                    "thumbnail_path": params[7],
                    "mime_type": params[8],
                    "size_bytes": params[9],
                    "width": params[10],
                    "height": params[11],
                    "duration_ms": params[12],
                    "fps": params[13],
                    "source_job_id": params[14],
                    "parent_asset_id": None,
                    "metadata": params[15],
                    "created_by": params[16],
                    "created_at": datetime.now(UTC),
                    "deleted_at": None,
                }
                return "INSERT 1"

            return "OK"

        conn.fetchrow = AsyncMock(side_effect=fetchrow)
        conn.fetch = AsyncMock(side_effect=fetch)
        conn.fetchval = AsyncMock(side_effect=fetchval)
        conn.execute = AsyncMock(side_effect=execute)
        conn.executemany = AsyncMock(return_value=None)
        conn.transaction = MagicMock()
        conn.transaction.return_value.__aenter__ = AsyncMock(return_value=conn)
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        return conn


def make_mock_conn() -> AsyncMock:
    db = MockDB()
    return db.make_conn()


def make_mock_pool(mock_conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool


def make_job_row(
    job_id: UUID | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    model_id: UUID | None = None,
    status: str = "queued",
    task_type: str = "text_to_image",
    prompt: str = "a cute red panda in a forest",
    provider_job_id: str | None = None,
    attempt: int = 0,
    max_attempts: int = 3,
    queued_at: datetime | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": job_id or uuid.uuid4(),
        "workspace_id": workspace_id or uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "created_by": uuid.uuid4(),
        "model_id": model_id or uuid.uuid4(),
        "task_type": task_type,
        "status": status,
        "prompt": prompt,
        "negative_prompt": None,
        "params": "{}",
        "idempotency_key": "idem-key-1",
        "provider_job_id": provider_job_id,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "error_code": None,
        "error_message": None,
        "cost_credits": Decimal("1.00"),
        "parent_job_id": None,
        "workflow_run_id": None,
        "queued_at": queued_at or now,
        "started_at": started_at,
        "completed_at": None,
        "heartbeat_at": heartbeat_at,
    }


def make_model_row(
    model_id: UUID | None = None,
    provider_id: str = "fake",
    slug: str = "fake-model-1",
    task_type: str = "text_to_image",
) -> dict[str, Any]:
    return {
        "id": model_id or uuid.uuid4(),
        "provider_id": provider_id,
        "provider_model": "test-provider-model",
        "slug": slug,
        "display_name": "Test Model",
        "task_type": task_type,
        "input_schema": "{}",
        "default_params": "{}",
        "cost_credits": Decimal("1.00"),
        "enabled": True,
    }


@pytest.fixture()
def test_config() -> WorkerConfig:
    return WorkerConfig(
        environment="local",
        storage_bucket="media",
        webhook_signing_secret="test_webhook_secret_key_32_bytes_min",
        public_api_url="http://127.0.0.1:8000",
        redis_url="redis://127.0.0.1:6379/0",
        provider_concurrency_fake=10,
    )
