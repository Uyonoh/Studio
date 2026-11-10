"""Supabase Storage helpers for the API.

The API uses the service-role key to read uploaded objects (to probe them) and
to write derived objects such as thumbnails. Signed URLs are still used for
client-facing downloads; these helpers are for server-side access only.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from studio_core.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _encode_path(path: str) -> str:
    """Percent-encode a storage path while keeping ``/`` separators."""
    return quote(path, safe="/")


class StorageClient:
    """Minimal service-role client for Supabase Storage."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bucket = self.settings.storage_bucket
        self.base_url = f"{self.settings.supabase_url}/storage/v1"
        self.headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
        }

    async def download_file(
        self, storage_path: str, max_size_bytes: int = 500 * 1024 * 1024
    ) -> bytes:
        """Download an object, enforcing a maximum size."""
        url = f"{self.base_url}/object/{self.bucket}/{_encode_path(storage_path)}"
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", url, headers=self.headers) as resp:
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

    async def upload_file(
        self,
        storage_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload (or overwrite) an object using the service-role key."""
        url = f"{self.base_url}/object/{self.bucket}/{_encode_path(storage_path)}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, content=data, headers=headers)
            if resp.status_code not in (200, 201):
                logger.error(
                    "Storage upload failed: status=%s body=%s", resp.status_code, resp.text
                )
                resp.raise_for_status()
        return storage_path

    async def delete_file(self, storage_path: str) -> None:
        """Delete an object. Best-effort: failures are logged, not raised."""
        url = f"{self.base_url}/object/{self.bucket}/{_encode_path(storage_path)}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(url, headers=self.headers)
            if resp.status_code not in (200, 204, 404):
                logger.warning(
                    "Storage delete failed: status=%s body=%s", resp.status_code, resp.text
                )
        except Exception:  # noqa: BLE001
            logger.warning("Storage delete raised for %s", storage_path, exc_info=True)
