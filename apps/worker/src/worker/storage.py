"""Storage client and helpers for workers.

Handles downloading provider outputs and uploading objects to Supabase Storage.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from studio_core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def make_storage_path(workspace_id: Any, project_id: Any, asset_id: Any, filename: str) -> str:
    """Build standardized storage path: {workspace_id}/{project_id}/{asset_id}/{filename}"""
    return f"{workspace_id}/{project_id}/{asset_id}/{filename}"


def get_signed_download_url(storage_path: str, settings: Settings | None = None) -> str:
    """Generate signed download URL for an internal storage path."""
    s = settings or get_settings()
    return f"{s.supabase_url}/storage/v1/object/sign/{s.storage_bucket}/{storage_path}"


class StorageClient:
    """Client for uploading and downloading objects from Supabase Storage."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket = self.settings.storage_bucket
        self.base_url = f"{self.settings.supabase_url}/storage/v1"
        self.headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
        }

    async def upload_file(
        self,
        storage_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file directly to Supabase storage using the service role key."""
        url = f"{self.base_url}/object/{self.bucket}/{storage_path}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, content=data, headers=headers)
            if resp.status_code not in (200, 201):
                logger.error(
                    "Storage upload failed: status=%s body=%s",
                    resp.status_code,
                    resp.text,
                )
                resp.raise_for_status()
        return storage_path

    async def download_file(self, url: str, max_size_bytes: int = 500 * 1024 * 1024) -> bytes:
        """Download content with size limit and timeout."""
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_size_bytes:
                        raise ValueError(
                            f"Download exceeded maximum size of {max_size_bytes} bytes"
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
