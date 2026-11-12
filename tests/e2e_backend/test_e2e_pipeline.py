"""End-to-end backend tests proving the entire pipeline without the UI.

Covers:
  - API (httpx ASGI)
  - Worker tasks (run_generation, finalize_generation)
  - Model validation & credit reservation
  - Direct upload & completion flow
  - Provider submission (FakeProvider) & signed input resolution
  - Provider webhook verification & ingestion
  - Finalization into owned assets (metadata & poster frame)
  - Output retrieval with signed download URLs and lineage
  - Failure variant (prompt with FAIL) leading to error status and credit refund.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from studio_core.models import AssetKind
from studio_core.queue import TASK_FINALIZE_GENERATION, TASK_RUN_GENERATION
from studio_core.settings import get_settings
from studio_media.media import VideoMetadata
from studio_providers.base import (
    ProviderJobState,
    ProviderOutput,
    ProviderStatus,
)
from worker.config import WorkerConfig
from worker.tasks.finalize_generation import finalize_generation
from worker.tasks.run_generation import run_generation


def _make_jwt(user_id: UUID) -> str:
    """Create a valid Supabase HS256 JWT for testing."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": f"{user_id}@example.com",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def _compute_job_token(job_id: UUID) -> str:
    settings = get_settings()
    return hmac.new(
        settings.webhook_signing_secret.encode(),
        msg=str(job_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


class E2EState:
    """In-memory state and mock connection for end-to-end backend pipeline."""

    def __init__(self, user_id: UUID, workspace_id: UUID, project_id: UUID) -> None:
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.project_id = project_id

        now = datetime.now(UTC)
        self.projects = {
            project_id: {
                "id": project_id,
                "workspace_id": workspace_id,
                "name": "E2E Studio Project",
                "description": "Integration test project",
                "cover_asset_id": None,
                "created_by": user_id,
                "created_at": now,
                "updated_at": now,
                "archived_at": None,
            }
        }
        self.members = {(workspace_id, user_id): "owner"}
        self.models: dict[str, dict[str, Any]] = {
            "fake-i2v-v1": {
                "id": uuid4(),
                "provider_id": "fake",
                "provider_model": "fake-i2v-model",
                "slug": "fake-i2v-v1",
                "display_name": "Fake Image to Video",
                "task_type": "image_to_video",
                "input_schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "duration_s": {"type": "integer", "default": 5},
                            "seed": {"type": "integer"},
                        },
                    }
                ),
                "default_params": json.dumps({"duration_s": 5}),
                "cost_credits": Decimal("5.00"),
                "enabled": True,
            }
        }
        self.ledger: list[dict[str, Any]] = [
            {
                "id": 1,
                "workspace_id": workspace_id,
                "job_id": None,
                "delta": Decimal("100.00"),
                "reason": "purchase",
                "created_at": now,
            }
        ]
        self.assets: dict[UUID, dict[str, Any]] = {}
        self.jobs: dict[UUID, dict[str, Any]] = {}
        self.inputs: dict[UUID, list[dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []
        self.enqueued_tasks: list[tuple[str, UUID]] = []

    def make_conn(self) -> AsyncMock:
        conn = AsyncMock()

        async def fetchrow(query: str, *params: Any) -> dict[str, Any] | None:
            now = datetime.now(UTC)

            if "public.projects" in query and "archived_at IS NULL" in query:
                proj_id = params[0]
                proj = self.projects.get(proj_id)
                return dict(proj) if proj else None

            if "FROM public.generation_jobs" in query and (
                "WHERE id = $1" in query or "WHERE j.id = $1" in query
            ):
                job_found = self.jobs.get(params[0])
                if not job_found:
                    return None
                res = dict(job_found)
                # Attach model info if joined
                for model_val in self.models.values():
                    if model_val.get("id") == res.get("model_id"):
                        res["model_slug"] = model_val.get("slug")
                        res["model_display_name"] = model_val.get("display_name")
                        break
                return res

            if "public.models" in query:
                if "slug =" in query:
                    model_found = self.models.get(params[0])
                    return dict(model_found) if model_found else None
                if "id =" in query:
                    for model_val in self.models.values():
                        if model_val["id"] == params[0]:
                            return dict(model_val)
                    return dict(next(iter(self.models.values())))
                return None

            if "FROM public.assets" in query and "storage_path =" in query:
                for asset_val in self.assets.values():
                    if asset_val["storage_path"] == params[0]:
                        return dict(asset_val)
                return None

            if "FROM public.assets" in query and "WHERE id =" in query:
                asset_found = self.assets.get(params[0])
                return dict(asset_found) if asset_found else None

            if "FROM public.generation_jobs" in query and "idempotency_key = $2" in query:
                ws_id, key = params[0], params[1]
                for job_val in self.jobs.values():
                    if job_val["workspace_id"] == ws_id and job_val["idempotency_key"] == key:
                        return dict(job_val)
                return None

            if "FROM public.generation_jobs" in query and "WHERE id = $1" in query:
                job_found = self.jobs.get(params[0])
                return dict(job_found) if job_found else None

            if "SELECT workspace_id, cost_credits FROM public.generation_jobs" in query:
                job_target = self.jobs.get(params[0])
                if job_target:
                    return {
                        "workspace_id": job_target["workspace_id"],
                        "cost_credits": job_target["cost_credits"],
                    }
                return None

            if "INSERT INTO public.generation_jobs" in query:
                # job_id is generated or passed
                job_id = uuid4()
                job = {
                    "id": job_id,
                    "workspace_id": params[0],
                    "project_id": params[1],
                    "created_by": params[2],
                    "model_id": params[3],
                    "task_type": params[4],
                    "status": "queued",
                    "prompt": params[5],
                    "negative_prompt": params[6],
                    "params": params[7] if isinstance(params[7], dict) else json.loads(params[7]),
                    "cost_credits": params[8],
                    "idempotency_key": params[9],
                    "parent_job_id": params[10] if len(params) > 10 else None,
                    "provider_job_id": None,
                    "attempt": 0,
                    "max_attempts": 3,
                    "error_code": None,
                    "error_message": None,
                    "workflow_run_id": None,
                    "queued_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "heartbeat_at": None,
                }
                self.jobs[job_id] = job
                return dict(job)

            if "UPDATE public.generation_jobs" in query and "RETURNING" in query:
                import re

                job_id = params[0]
                existing_job = self.jobs.get(job_id)
                if not existing_job:
                    return None

                for st in (
                    "queued",
                    "submitting",
                    "running",
                    "finalizing",
                    "succeeded",
                    "failed",
                    "canceled",
                ):
                    if f"status = '{st}'" in query and existing_job["status"] != st:
                        return None

                set_part = query.split("SET ")[1].split(" WHERE ")[0]
                for clause in set_part.split(", "):
                    clause = clause.strip()
                    regex_match = re.search(r"(\w+)\s*=\s*(?:COALESCE\([^,]+,\s*)?\$(\d+)", clause)
                    if regex_match:
                        col_name, idx_str = regex_match.group(1), regex_match.group(2)
                        p_val = params[int(idx_str) - 1]
                        if hasattr(p_val, "value"):
                            p_val = p_val.value
                        existing_job[col_name] = p_val

                return dict(existing_job)

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

            if "INSERT INTO public.assets" in query and "RETURNING" in query:
                asset_id = uuid4()
                raw_meta = params[15] if len(params) > 15 else {}
                asset = {
                    "id": asset_id,
                    "workspace_id": params[0],
                    "project_id": params[1],
                    "kind": params[2],
                    "origin": params[3],
                    "storage_bucket": params[4],
                    "storage_path": params[5],
                    "thumbnail_path": params[6],
                    "mime_type": params[7],
                    "size_bytes": params[8],
                    "width": params[9] if len(params) > 9 else None,
                    "height": params[10] if len(params) > 10 else None,
                    "duration_ms": params[11] if len(params) > 11 else None,
                    "fps": params[12] if len(params) > 12 else None,
                    "source_job_id": params[13] if len(params) > 13 else None,
                    "parent_asset_id": params[14] if len(params) > 14 else None,
                    "metadata": json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta,
                    "created_by": params[16] if len(params) > 16 else None,
                    "created_at": now,
                    "deleted_at": None,
                }
                self.assets[asset_id] = asset
                return dict(asset)

            return None

        async def fetchval(query: str, *params: Any) -> Any:
            if "workspace_members" in query:
                ws_id = params[0]
                u_id = params[1]
                return self.members.get((ws_id, u_id))

            if "SELECT id FROM public.workspaces WHERE id = $1 FOR UPDATE" in query:
                return params[0]

            if "credit_ledger" in query:
                if "sum(delta)" in query:
                    ws_id = params[0]
                    return sum(
                        (e["delta"] for e in self.ledger if e["workspace_id"] == ws_id),
                        Decimal("0.00"),
                    )
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
                    return abs(res["delta"]) if res else Decimal("5.00")

            if "FROM public.generation_jobs" in query and "count(*)" in query:
                return 0  # concurrency count

            return None

        async def fetch(query: str, *params: Any) -> list[dict[str, Any]]:
            if "FROM public.assets" in query and "source_job_id = $1" in query:
                job_id = params[0]
                return [dict(a) for a in self.assets.values() if a.get("source_job_id") == job_id]

            if "FROM public.assets" in query and "ANY($1)" in query:
                ids = params[0]
                return [dict(self.assets[aid]) for aid in ids if aid in self.assets]

            if "FROM public.job_inputs" in query:
                job_id = params[0]
                return self.inputs.get(job_id, [])

            return []

        async def execute(query: str, *params: Any) -> str:
            now = datetime.now(UTC)

            if "INSERT INTO public.job_inputs" in query:
                # job_id, asset_id, role, position
                job_id = params[0]
                self.inputs.setdefault(job_id, []).append(
                    {
                        "job_id": job_id,
                        "asset_id": params[1],
                        "role": params[2],
                        "position": params[3],
                    }
                )
                return "INSERT 1"

            if "UPDATE public.assets" in query and "SET mime_type = $2" in query:
                asset_id = params[0]
                asset = self.assets.get(asset_id)
                if asset is not None:
                    asset["mime_type"] = params[1]
                    asset["size_bytes"] = params[2]
                    asset["width"] = params[3]
                    asset["height"] = params[4]
                    asset["duration_ms"] = params[5]
                    asset["fps"] = params[6]
                    asset["thumbnail_path"] = params[7]
                    meta_patch = json.loads(params[8]) if isinstance(params[8], str) else params[8]
                    asset["metadata"].update(meta_patch)
                return "UPDATE 1"

            if "UPDATE public.assets" in query and "metadata" in query:
                asset_id = params[0]
                if asset_id in self.assets:
                    meta_patch = json.loads(params[1]) if isinstance(params[1], str) else params[1]
                    self.assets[asset_id]["metadata"].update(meta_patch)
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
                    "metadata": json.loads(params[15])
                    if isinstance(params[15], str)
                    else params[15],
                    "created_by": params[16],
                    "created_at": now,
                    "deleted_at": None,
                }
                return "INSERT 1"

            return "OK"

        conn.fetchrow = AsyncMock(side_effect=fetchrow)
        conn.fetchval = AsyncMock(side_effect=fetchval)
        conn.fetch = AsyncMock(side_effect=fetch)
        conn.execute = AsyncMock(side_effect=execute)
        conn.executemany = AsyncMock(return_value=None)
        conn.transaction = MagicMock()
        conn.transaction.return_value.__aenter__ = AsyncMock(return_value=conn)
        conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        return conn


def _make_pool(mock_conn: AsyncMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_e2e_backend_pipeline_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Full end-to-end integration test:

    1. Client uploads an image asset
    2. Client submits image_to_video generation job (202 Accepted)
    3. Worker executes run_generation -> submits to FakeProvider, status becomes running
    4. Provider sends webhook -> verified and finalize enqueued
    5. Worker executes finalize_generation -> output downloaded, probed, stored, status succeeded
    6. Client fetches generation from API -> status succeeded, output asset with signed URL
    """
    from api.main import create_app

    user_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()

    state = E2EState(user_id, workspace_id, project_id)
    mock_conn = state.make_conn()
    pool = _make_pool(mock_conn)

    # Upload completion downloads and probes the object from storage, so serve
    # a real PNG from an in-memory storage stub instead of calling Supabase.
    png_buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color=(200, 40, 40)).save(png_buffer, format="PNG")
    uploaded_png = png_buffer.getvalue()

    class FakeUploadStorage:
        async def download_file(self, storage_path: str, max_size_bytes: int = 0) -> bytes:
            return uploaded_png

        async def upload_file(self, storage_path: str, data: bytes, content_type: str = "") -> str:
            return storage_path

        async def delete_file(self, storage_path: str) -> None:
            return None

    monkeypatch.setattr("api.routers.assets.StorageClient", FakeUploadStorage)

    # In-memory Redis queue stub
    mock_redis = MagicMock()
    mock_redis.eval = AsyncMock(return_value=1)

    async def mock_enqueue_job(task_name: str, job_id_str: str, **kwargs: Any) -> object:
        state.enqueued_tasks.append((task_name, UUID(job_id_str)))
        # ARQ returns a Job on success and None when the id is already queued.
        return object()

    mock_redis.enqueue_job = AsyncMock(side_effect=mock_enqueue_job)

    app = create_app()
    app.state.db_pool = pool
    app.state.redis_pool = mock_redis

    token = _make_jwt(user_id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    worker_config = WorkerConfig(
        environment="local",
        storage_bucket="media",
        webhook_signing_secret=get_settings().webhook_signing_secret,
        public_api_url="http://127.0.0.1:8000",
        redis_url="redis://127.0.0.1:6379/0",
        provider_concurrency_fake=10,
    )
    worker_ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": worker_config}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ── Step 1: Upload input image asset ──────────────────────────────────────────
        upload_resp = await client.post(
            f"/v1/projects/{project_id}/assets/uploads",
            headers=auth_headers,
            json={"filename": "first_frame.png", "mime_type": "image/png", "size_bytes": 1024},
        )
        assert upload_resp.status_code == 201, upload_resp.text
        input_asset_id = UUID(upload_resp.json()["asset_id"])

        # Complete the upload
        complete_resp = await client.post(
            f"/v1/assets/{input_asset_id}/complete",
            headers=auth_headers,
        )
        assert complete_resp.status_code == 200, complete_resp.text
        assert complete_resp.json()["metadata"]["status"] == "ready"

        # ── Step 2: Submit generation (image_to_video) ────────────────────────────────
        idempotency_key = str(uuid4())
        submit_resp = await client.post(
            f"/v1/projects/{project_id}/generations",
            headers={**auth_headers, "Idempotency-Key": idempotency_key},
            json={
                "model": "fake-i2v-v1",
                "task_type": "image_to_video",
                "prompt": "a dramatic drone shot over mountains",
                "inputs": [{"asset_id": str(input_asset_id), "role": "first_frame"}],
                "params": {"duration_s": 5},
            },
        )
        assert submit_resp.status_code == 202, submit_resp.text
        job_data = submit_resp.json()
        job_id = UUID(job_data["id"])
        assert job_data["status"] == "queued"

        # Verify task was enqueued
        assert (TASK_RUN_GENERATION, job_id) in state.enqueued_tasks

        # ── Step 3: Worker runs run_generation ────────────────────────────────────────
        await run_generation(worker_ctx, job_id)

        job_after_submit = state.jobs[job_id]
        assert job_after_submit["status"] == "running"
        provider_job_id = job_after_submit["provider_job_id"]
        assert provider_job_id is not None

        # ── Step 4: Provider webhook delivery ─────────────────────────────────────────
        webhook_token = _compute_job_token(job_id)
        webhook_payload = {
            "id": provider_job_id,
            "status": "succeeded",
            "outputs": [
                {
                    "url": "https://mock.storage.local/video.mp4",
                    "mime_type": "video/mp4",
                    "kind": "video",
                }
            ],
        }
        wh_resp = await client.post(
            f"/internal/webhooks/fake/{job_id}?token={webhook_token}",
            headers={"X-Fake-Signature": "valid_secret", "Content-Type": "application/json"},
            content=json.dumps(webhook_payload),
        )
        assert wh_resp.status_code == 200, wh_resp.text
        assert (TASK_FINALIZE_GENERATION, job_id) in state.enqueued_tasks

        # ── Step 5: Worker runs finalize_generation ───────────────────────────────────
        video_bytes = b"sample_video_mp4_bytes"
        mock_vmeta = VideoMetadata(
            width=1920,
            height=1080,
            duration_ms=5000,
            fps=Decimal("30.0"),
            mime_type="video/mp4",
        )

        def mock_make_poster(src: Any, dst: Any) -> None:
            Image.new("RGB", (320, 180), color=(0, 0, 0)).save(dst, format="JPEG")

        provider_status = ProviderStatus(
            state=ProviderJobState.SUCCEEDED,
            outputs=[
                ProviderOutput(
                    url="https://mock.storage.local/video.mp4",
                    mime_type="video/mp4",
                    kind=AssetKind.VIDEO,
                )
            ],
        )

        with (
            patch(
                "studio_providers.fake.FakeProvider.get_status",
                AsyncMock(return_value=provider_status),
            ),
            patch(
                "worker.tasks.finalize_generation.StorageClient.download_file",
                AsyncMock(return_value=video_bytes),
            ),
            patch(
                "worker.tasks.finalize_generation.StorageClient.upload_file",
                AsyncMock(return_value="path"),
            ),
            patch("worker.tasks.finalize_generation.probe_video", return_value=mock_vmeta),
            patch(
                "worker.tasks.finalize_generation.make_poster_frame", side_effect=mock_make_poster
            ),
        ):
            await finalize_generation(worker_ctx, job_id)

        job_after_finalize = state.jobs[job_id]
        assert job_after_finalize["status"] == "succeeded"

        # ── Step 6: Client queries generation from API ────────────────────────────────
        get_job_resp = await client.get(
            f"/v1/generations/{job_id}",
            headers=auth_headers,
        )
        assert get_job_resp.status_code == 200, get_job_resp.text
        job_result = get_job_resp.json()
        assert job_result["status"] == "succeeded"
        assert len(job_result["outputs"]) == 1

        output_asset = job_result["outputs"][0]
        output_asset_id = UUID(str(output_asset["asset_id"]))
        assert output_asset["kind"] == "video"
        assert output_asset["signed_url"] is not None

        # Query asset directly
        get_asset_resp = await client.get(
            f"/v1/assets/{output_asset_id}",
            headers=auth_headers,
        )
        assert get_asset_resp.status_code == 200, get_asset_resp.text
        asset_data = get_asset_resp.json()
        assert asset_data["id"] == str(output_asset_id)
        assert asset_data["source_job_id"] == str(job_id)
        assert asset_data["width"] == 1920
        assert asset_data["height"] == 1080


@pytest.mark.asyncio
async def test_e2e_backend_pipeline_failure() -> None:
    """End-to-end failure path:

    1. Client submits job with prompt containing FAIL
    2. Worker runs run_generation -> FakeProvider rejects permanently
    3. Job status becomes failed and credits are refunded
    4. Client queries generation -> status is failed with error details
    """
    from api.main import create_app

    user_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()

    state = E2EState(user_id, workspace_id, project_id)
    mock_conn = state.make_conn()
    pool = _make_pool(mock_conn)

    mock_redis = MagicMock()
    mock_redis.eval = AsyncMock(return_value=1)
    mock_redis.enqueue_job = AsyncMock()

    app = create_app()
    app.state.db_pool = pool
    app.state.redis_pool = mock_redis

    token = _make_jwt(user_id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    worker_config = WorkerConfig(
        environment="local",
        storage_bucket="media",
        webhook_signing_secret=get_settings().webhook_signing_secret,
        public_api_url="http://127.0.0.1:8000",
        redis_url="redis://127.0.0.1:6379/0",
    )
    worker_ctx = {"db_pool": pool, "redis_pool": mock_redis, "config": worker_config}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed input asset directly
        input_asset_id = uuid4()
        state.assets[input_asset_id] = {
            "id": input_asset_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "kind": "image",
            "origin": "upload",
            "storage_bucket": "media",
            "storage_path": "path",
            "thumbnail_path": None,
            "mime_type": "image/png",
            "size_bytes": 100,
            "width": 100,
            "height": 100,
            "duration_ms": None,
            "fps": None,
            "source_job_id": None,
            "parent_asset_id": None,
            "metadata": {"status": "ready"},
            "created_by": user_id,
            "created_at": datetime.now(UTC),
            "deleted_at": None,
        }

        # Submit generation with prompt FAIL
        submit_resp = await client.post(
            f"/v1/projects/{project_id}/generations",
            headers={**auth_headers, "Idempotency-Key": str(uuid4())},
            json={
                "model": "fake-i2v-v1",
                "task_type": "image_to_video",
                "prompt": "generate FAIL scene",
                "inputs": [{"asset_id": str(input_asset_id), "role": "first_frame"}],
                "params": {"duration_s": 5},
            },
        )
        assert submit_resp.status_code == 202
        job_id = UUID(submit_resp.json()["id"])

        # Worker runs run_generation
        await run_generation(worker_ctx, job_id)

        # Job must be failed
        assert state.jobs[job_id]["status"] == "failed"

        # Verify refund entry exists in credit_ledger
        refunds = [
            e for e in state.ledger if e.get("job_id") == job_id and e.get("reason") == "refund"
        ]
        assert len(refunds) == 1

        # Query API for job status
        get_resp = await client.get(
            f"/v1/generations/{job_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "failed"
        assert get_resp.json()["error_code"] is not None
