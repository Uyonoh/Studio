"""Replicate provider adapter using the Replicate HTTP predictions API."""

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from typing import Any

import httpx

from studio_core.models import AssetKind
from studio_providers.base import (
    PermanentProviderError,
    ProviderError,
    ProviderJobRef,
    ProviderJobState,
    ProviderOutput,
    ProviderRequest,
    ProviderStatus,
    RateLimitedError,
    TransientProviderError,
    WebhookEvent,
)

# Replicate status → internal state mapping
_STATUS_MAP: dict[str, ProviderJobState] = {
    "starting": ProviderJobState.PENDING,
    "processing": ProviderJobState.RUNNING,
    "succeeded": ProviderJobState.SUCCEEDED,
    "failed": ProviderJobState.FAILED,
    "canceled": ProviderJobState.CANCELED,
}

# Replay protection: reject webhook timestamps older than this (seconds)
_WEBHOOK_TOLERANCE_SECONDS = 300


def _guess_kind_from_url(url: str) -> AssetKind:
    """Infer asset kind from a URL's extension."""
    lower = url.lower().split("?")[0]
    if lower.endswith((".mp4", ".webm", ".mov", ".avi")):
        return AssetKind.VIDEO
    return AssetKind.IMAGE


class ReplicateProvider:
    """Generation provider adapter for Replicate's predictions API."""

    id: str = "replicate"

    def __init__(
        self,
        api_token: str,
        webhook_secret: str | None = None,
        base_url: str = "https://api.replicate.com",
        request_timeout: float = 30.0,
    ) -> None:
        self.api_token = api_token
        self.webhook_secret = webhook_secret
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=request_timeout,
        )

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a prediction to Replicate."""
        input_payload: dict[str, Any] = {}

        # Map prompt
        if req.prompt:
            input_payload["prompt"] = req.prompt
        if req.negative_prompt:
            input_payload["negative_prompt"] = req.negative_prompt

        # Map input assets by role
        for inp in req.inputs:
            if inp.role in ("init_image", "reference_image"):
                input_payload["image"] = inp.url
            elif inp.role == "first_frame":
                input_payload["first_frame"] = inp.url
            elif inp.role == "last_frame":
                input_payload["last_frame"] = inp.url
            elif inp.role == "mask":
                input_payload["mask"] = inp.url

        # Merge model-specific params
        input_payload.update(req.params)

        body: dict[str, Any] = {
            "version": req.model,
            "input": input_payload,
        }

        if req.webhook_url:
            body["webhook"] = req.webhook_url
            body["webhook_events_filter"] = ["completed"]

        resp = await self._client.post("/v1/predictions", json=body)
        self._check_response(resp)

        data = resp.json()
        return ProviderJobRef(
            provider_id=self.id,
            provider_job_id=data["id"],
        )

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current prediction status from Replicate."""
        resp = await self._client.get(f"/v1/predictions/{ref.provider_job_id}")
        self._check_response(resp)

        data = resp.json()
        raw_status = data.get("status", "failed")
        state = _STATUS_MAP.get(raw_status, ProviderJobState.FAILED)

        outputs: list[ProviderOutput] = []
        if state == ProviderJobState.SUCCEEDED:
            outputs = self.normalize_output(data)

        error_message = data.get("error")
        return ProviderStatus(
            state=state,
            outputs=outputs,
            error_code="PROVIDER_FAILURE" if error_message else None,
            error_message=error_message,
        )

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a running prediction. Swallow 'already finished' errors."""
        try:
            resp = await self._client.post(f"/v1/predictions/{ref.provider_job_id}/cancel")
            # 404 or 409 means already done — swallow
            if resp.status_code not in (200, 201, 404, 409):
                self._check_response(resp)
        except (httpx.HTTPError, ProviderError):
            pass  # Best-effort cancel

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify Replicate webhook using Svix/Standard Webhooks HMAC-SHA256 scheme."""
        # Normalize header access (case-insensitive)
        h = {k.lower(): v for k, v in headers.items()}

        msg_id = h.get("webhook-id") or h.get("svix-id")
        timestamp = h.get("webhook-timestamp") or h.get("svix-timestamp")
        signature_header = h.get("webhook-signature") or h.get("svix-signature")

        if not msg_id or not timestamp or not signature_header:
            raise PermanentProviderError("Missing required webhook signature headers")

        if not self.webhook_secret:
            raise PermanentProviderError("Webhook secret not configured for Replicate provider")

        # Replay protection
        try:
            ts_int = int(timestamp)
        except ValueError:
            raise PermanentProviderError("Invalid webhook timestamp") from None

        if abs(time.time() - ts_int) > _WEBHOOK_TOLERANCE_SECONDS:
            raise PermanentProviderError("Webhook timestamp outside tolerance window")

        # Compute expected signature
        signed_content = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

        # Secret: strip "whsec_" prefix and base64-decode
        secret_str = self.webhook_secret
        if secret_str.startswith("whsec_"):
            secret_str = secret_str[6:]
        secret_bytes = base64.b64decode(secret_str)

        expected = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")

        # Compare against any of the provided signatures (space-separated "v1,<sig>")
        signatures = signature_header.split(" ")
        matched = any(
            sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected) for sig in signatures
        )
        if not matched:
            raise PermanentProviderError("Invalid Replicate webhook signature")

        # Parse prediction payload
        payload = json.loads(body.decode("utf-8"))
        raw_status = payload.get("status", "failed")
        state = _STATUS_MAP.get(raw_status, ProviderJobState.FAILED)
        outputs = self.normalize_output(payload) if state == ProviderJobState.SUCCEEDED else []

        return WebhookEvent(
            provider_id=self.id,
            provider_job_id=payload.get("id", ""),
            state=state,
            outputs=outputs,
            raw_payload=payload,
        )

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize Replicate output (string, list of strings, or list of dicts)."""
        outputs: list[ProviderOutput] = []
        raw_output = raw.get("output")

        if raw_output is None:
            return outputs

        # Single string URL
        if isinstance(raw_output, str):
            kind = _guess_kind_from_url(raw_output)
            outputs.append(ProviderOutput(url=raw_output, kind=kind))
            return outputs

        # List of items
        if isinstance(raw_output, list):
            for item in raw_output:
                if isinstance(item, str):
                    kind = _guess_kind_from_url(item)
                    outputs.append(ProviderOutput(url=item, kind=kind))
                elif isinstance(item, dict):
                    url = item.get("url", "")
                    mime = item.get("mime_type") or item.get("content_type")
                    is_video = bool(mime and "video" in mime)
                    kind = AssetKind.VIDEO if is_video else _guess_kind_from_url(url)
                    outputs.append(ProviderOutput(url=url, mime_type=mime, kind=kind))

        return outputs

    def _check_response(self, resp: httpx.Response) -> None:
        """Map HTTP errors to typed provider exceptions."""
        if resp.is_success:
            return

        body_text = resp.text
        status = resp.status_code

        if status == 429:
            retry_after = float(resp.headers.get("retry-after", "5"))
            raise RateLimitedError(f"Replicate rate limited: {body_text}", retry_after=retry_after)

        if status in (400, 401, 403, 404, 409, 422):
            raise PermanentProviderError(f"Replicate error {status}: {body_text}")

        if status >= 500:
            raise TransientProviderError(f"Replicate server error {status}: {body_text}")

        raise TransientProviderError(f"Replicate unexpected status {status}: {body_text}")
