"""T3.3 / T3.4 — Asset endpoints and models endpoint tests."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from studio_media.media import VideoMetadata

from .conftest import make_jwt


def _make_app(mock_conn: AsyncMock) -> FastAPI:
    from api.main import create_app

    app = create_app()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool = mock_pool
    app.state.redis_pool = None
    return app


def _mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    return conn


def _asset_row(
    asset_id: UUID | None = None,
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    kind: str = "image",
    origin: str = "upload",
    mime_type: str = "image/png",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": asset_id or uuid.uuid4(),
        "workspace_id": workspace_id or uuid.uuid4(),
        "project_id": project_id or uuid.uuid4(),
        "kind": kind,
        "origin": origin,
        "storage_bucket": "media",
        "storage_path": "ws/proj/asset/file.png",
        "thumbnail_path": None,
        "mime_type": mime_type,
        "size_bytes": 12345,
        "width": 512,
        "height": 512,
        "duration_ms": None,
        "fps": None,
        "source_job_id": None,
        "parent_asset_id": None,
        "metadata": '{"status": "ready"}',
        "created_by": uuid.uuid4(),
        "created_at": now,
        "deleted_at": None,
    }


# ── Upload request ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_upload_returns_201_and_url() -> None:
    """POST /assets/uploads creates draft and returns signed URL."""
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id, project_id=proj_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "projects" in query and "archived_at IS NULL" in query:
            return {"workspace_id": ws_id}
        if "INSERT INTO public.assets" in query:
            return asset
        if "assets" in query and "storage_path" in query:
            return {"id": asset["id"]}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={"mime_type": "image/png", "size_bytes": 1024, "filename": "test.png"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "asset_id" in body
    assert "upload_url" in body


@pytest.mark.asyncio
async def test_request_upload_rejects_non_media_mime() -> None:
    """Non image/* or video/* MIME types get 415."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "projects" in query:
            return {"workspace_id": ws_id}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={"mime_type": "application/pdf", "size_bytes": 1024, "filename": "doc.pdf"},
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_request_upload_rejects_oversized() -> None:
    """Files exceeding 500 MB get 413."""
    uid = uuid.uuid4()
    proj_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "projects" in query:
            return {"workspace_id": ws_id}
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/projects/{proj_id}/assets/uploads",
            json={
                "mime_type": "image/png",
                "size_bytes": 600 * 1024 * 1024,  # 600 MB
                "filename": "huge.png",
            },
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 413


# ── Get asset ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_asset_happy_path() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.assets" in query:
            return asset
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="viewer")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/assets/{asset['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(asset["id"])
    assert body["mime_type"] == "image/png"
    assert body["lineage"] == {"source_job": None, "inputs": [], "parent": None}


@pytest.mark.asyncio
async def test_get_asset_returns_lineage_for_generated_asset() -> None:
    """Generated assets expose the source job, its params and its inputs."""
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    job_id = uuid.uuid4()
    input_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id, origin="generated")
    asset["source_job_id"] = job_id
    asset["parent_asset_id"] = parent_id

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "FROM public.generation_jobs" in query:
            return {
                "id": job_id,
                "task_type": "image_to_video",
                "status": "succeeded",
                "prompt": "slow dolly-in, golden hour",
                "negative_prompt": "blurry",
                "params": '{"duration_s": 5, "seed": 42}',
                "queued_at": datetime.now(UTC),
                "model_slug": "img-fast-v1",
                "model_display_name": "Fast Image v1",
            }
        if "SELECT id, kind, storage_path, thumbnail_path" in query:
            return {
                "id": parent_id,
                "kind": "image",
                "storage_path": "ws/proj/parent/frame.png",
                "thumbnail_path": None,
            }
        if "public.assets" in query:
            return asset
        return None

    async def fetch_side_effect(query: str, *args: Any) -> list[dict[str, Any]]:
        if "public.job_inputs" in query:
            return [
                {
                    "asset_id": input_id,
                    "kind": "image",
                    "storage_path": "ws/proj/input/frame.png",
                    "thumbnail_path": None,
                    "role": "first_frame",
                }
            ]
        return []

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetch = AsyncMock(side_effect=fetch_side_effect)
    conn.fetchval = AsyncMock(return_value="viewer")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/assets/{asset['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 200
    lineage = resp.json()["lineage"]
    assert lineage["source_job"]["id"] == str(job_id)
    assert lineage["source_job"]["prompt"] == "slow dolly-in, golden hour"
    assert lineage["source_job"]["params"] == {"duration_s": 5, "seed": 42}
    assert lineage["source_job"]["model_slug"] == "img-fast-v1"
    assert lineage["inputs"][0]["asset_id"] == str(input_id)
    assert lineage["inputs"][0]["kind"] == "image"
    assert lineage["inputs"][0]["role"] == "first_frame"
    assert (
        "/storage/v1/object/sign/media/ws/proj/input/frame.png"
        in lineage["inputs"][0]["signed_url"]
    )
    assert lineage["inputs"][0]["thumbnail_url"] is None
    assert lineage["parent"]["asset_id"] == str(parent_id)


@pytest.mark.asyncio
async def test_get_asset_404_if_not_found() -> None:
    uid = uuid.uuid4()
    asset_id = uuid.uuid4()
    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/assets/{asset_id}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 404


# ── Soft delete ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_asset_returns_204() -> None:
    uid = uuid.uuid4()
    ws_id = uuid.uuid4()
    asset = _asset_row(workspace_id=ws_id)

    conn = _mock_conn()

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "public.assets" in query:
            return asset
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"/v1/assets/{asset['id']}",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 204


# ── Models endpoint ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_models_returns_enabled_models() -> None:
    uid = uuid.uuid4()
    model_row = {
        "id": uuid.uuid4(),
        "provider_id": "fake",
        "provider_model": "fake-t2i",
        "slug": "fake-img-v1",
        "display_name": "Fake Image v1",
        "task_type": "text_to_image",
        "input_schema": '{"type": "object", "properties": {}}',
        "default_params": "{}",
        "cost_credits": "1.00",
        "enabled": True,
    }

    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[model_row])
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) == 1
    assert models[0]["slug"] == "fake-img-v1"
    assert models[0]["task_type"] == "text_to_image"
    assert "Cache-Control" in resp.headers


@pytest.mark.asyncio
async def test_list_models_filter_by_task_type() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[])  # filtered result
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models?task_type=text_to_image",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_models_rejects_invalid_task_type() -> None:
    uid = uuid.uuid4()
    conn = _mock_conn()
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/models?task_type=invalid_type",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )
    assert resp.status_code == 400


# ── Complete upload: real media processing ─────────────────────────────────────


def _png_bytes(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeStorage:
    """Stands in for the Supabase storage client in upload-processing tests."""

    def __init__(self, data: bytes = b"", error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.uploaded: list[tuple[str, bytes, str]] = []
        self.deleted: list[str] = []

    async def download_file(self, storage_path: str, max_size_bytes: int = 0) -> bytes:
        if self.error is not None:
            raise self.error
        return self.data

    async def upload_file(self, storage_path: str, data: bytes, content_type: str = "") -> str:
        self.uploaded.append((storage_path, data, content_type))
        return storage_path

    async def delete_file(self, storage_path: str) -> None:
        self.deleted.append(storage_path)


def _pending_asset_row(kind: str = "image", filename: str = "photo.png") -> dict[str, Any]:
    asset = _asset_row(kind=kind, mime_type="image/png" if kind == "image" else "video/mp4")
    asset["metadata"] = f'{{"status": "pending", "filename": "{filename}"}}'
    asset["width"] = None
    asset["height"] = None
    asset["duration_ms"] = None
    asset["fps"] = None
    asset["thumbnail_path"] = None
    return asset


def _conn_returning_pending_then_ready(pending: dict[str, Any], ready: dict[str, Any]) -> AsyncMock:
    conn = _mock_conn()
    reads = {"count": 0}

    async def fetchrow_side_effect(query: str, *args: Any) -> dict[str, Any] | None:
        if "FROM public.assets" in query:
            reads["count"] += 1
            return pending if reads["count"] == 1 else ready
        return None

    conn.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    conn.fetchval = AsyncMock(return_value="editor")
    return conn


@pytest.mark.asyncio
async def test_complete_upload_probes_image_and_generates_thumbnail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completing an image upload stores real dimensions and a thumbnail."""
    uid = uuid.uuid4()
    png = _png_bytes(4, 3)
    pending = _pending_asset_row(filename="photo.png")
    thumb_path = f"{pending['workspace_id']}/{pending['project_id']}/{pending['id']}/thumbnail.jpg"
    ready = {
        **pending,
        "width": 4,
        "height": 3,
        "size_bytes": len(png),
        "thumbnail_path": thumb_path,
        "metadata": '{"status": "ready", "filename": "photo.png"}',
    }

    conn = _conn_returning_pending_then_ready(pending, ready)
    fake_storage = _FakeStorage(data=png)
    monkeypatch.setattr("api.routers.assets.StorageClient", lambda: fake_storage)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/assets/{pending['id']}/complete",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["width"] == 4
    assert body["height"] == 3
    assert body["size_bytes"] == len(png)
    assert body["mime_type"] == "image/png"
    assert body["duration_ms"] is None
    assert body["thumbnail_path"] == thumb_path
    assert body["thumbnail_url"] is not None
    assert body["metadata"]["status"] == "ready"

    # The generated thumbnail was uploaded as JPEG.
    assert len(fake_storage.uploaded) == 1
    uploaded_path, uploaded_bytes, uploaded_type = fake_storage.uploaded[0]
    assert uploaded_path == thumb_path
    assert uploaded_type == "image/jpeg"
    assert uploaded_bytes.startswith(b"\xff\xd8")  # JPEG magic

    final_updates = [
        call for call in conn.execute.call_args_list if "SET mime_type = $2" in call.args[0]
    ]
    assert len(final_updates) == 1
    args = final_updates[0].args
    assert args[1] == pending["id"]
    assert args[2] == "image/png"
    assert args[3] == len(png)
    assert args[4] == 4
    assert args[5] == 3
    assert args[6] is None
    assert args[7] is None
    assert args[8] == thumb_path
    assert '"ready"' in args[9]


@pytest.mark.asyncio
async def test_complete_upload_probes_video_and_generates_poster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completing a video upload stores duration/fps and a poster frame."""
    uid = uuid.uuid4()
    pending = _pending_asset_row(kind="video", filename="clip.mp4")
    thumb_path = f"{pending['workspace_id']}/{pending['project_id']}/{pending['id']}/thumbnail.jpg"
    ready = {
        **pending,
        "width": 1920,
        "height": 1080,
        "duration_ms": 12345,
        "fps": Decimal("30.000"),
        "thumbnail_path": thumb_path,
        "metadata": '{"status": "ready", "filename": "clip.mp4"}',
    }

    def fake_probe_video(path: Any) -> VideoMetadata:
        return VideoMetadata(
            width=1920,
            height=1080,
            duration_ms=12345,
            fps=Decimal("30.000"),
            mime_type="video/mp4",
        )

    def fake_poster(src: Any, dst: Any, time_s: float = 0.0) -> None:
        with open(dst, "wb") as fh:
            fh.write(b"\xff\xd8fake-poster")

    monkeypatch.setattr("api.routers.assets.probe_video", fake_probe_video)
    monkeypatch.setattr("api.routers.assets.make_poster_frame", fake_poster)

    conn = _conn_returning_pending_then_ready(pending, ready)
    fake_storage = _FakeStorage(data=b"fake-video-bytes")
    monkeypatch.setattr("api.routers.assets.StorageClient", lambda: fake_storage)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/assets/{pending['id']}/complete",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["width"] == 1920
    assert body["height"] == 1080
    assert body["duration_ms"] == 12345
    assert float(body["fps"]) == 30.0
    assert body["thumbnail_path"] == thumb_path
    assert body["thumbnail_url"] is not None

    assert len(fake_storage.uploaded) == 1
    assert fake_storage.uploaded[0][2] == "image/jpeg"


@pytest.mark.asyncio
async def test_complete_upload_rejects_invalid_media(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupt uploads are rejected, deleted from storage, and marked failed."""
    uid = uuid.uuid4()
    pending = _pending_asset_row(filename="broken.png")
    conn = _conn_returning_pending_then_ready(pending, pending)
    fake_storage = _FakeStorage(data=b"this is definitely not an image")
    monkeypatch.setattr("api.routers.assets.StorageClient", lambda: fake_storage)
    app = _make_app(conn)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/assets/{pending['id']}/complete",
            headers={"Authorization": f"Bearer {make_jwt(uid)}"},
        )

    assert resp.status_code == 422
    assert "not valid media" in resp.json()["detail"]
    assert fake_storage.deleted == [pending["storage_path"]]

    failed_updates = [
        call
        for call in conn.execute.call_args_list
        if "metadata = metadata || $2::jsonb" in call.args[0] and '"failed"' in call.args[2]
    ]
    assert len(failed_updates) == 1
