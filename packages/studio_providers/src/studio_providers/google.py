"""Google AI (Gemini / Imagen) provider adapter implementing the GenerationProvider protocol."""

import json
import logging
import uuid
from collections.abc import Mapping
from typing import Any

import httpx

from studio_core.models import AssetKind
from studio_providers.base import (
    GenerationProvider,
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

logger = logging.getLogger(__name__)


def _guess_kind(mime_type: str | None, url: str) -> AssetKind:
    if mime_type and "video" in mime_type:
        return AssetKind.VIDEO
    lower = url.lower().split("?")[0]
    if lower.endswith((".mp4", ".webm", ".mov")):
        return AssetKind.VIDEO
    return AssetKind.IMAGE


class GoogleProvider(GenerationProvider):
    """Generation provider adapter for Google AI (Imagen 3 and Gemini models)."""

    id: str = "google"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com",
        request_timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=request_timeout,
        )
        # In-memory store for completed predictions: job_id -> ProviderStatus
        self._jobs: dict[str, dict[str, Any]] = {}

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a generation request to Google AI."""
        job_id = f"goog_{uuid.uuid4().hex[:16]}"
        model = req.model.removeprefix("models/")

        # Build payload for Imagen predict API
        instance: dict[str, Any] = {"prompt": req.prompt or ""}
        for inp in req.inputs:
            if inp.role in ("init_image", "reference_image"):
                instance["image"] = {"imageUri": inp.url}

        sample_count = int(req.params.get("num_images") or req.params.get("sample_count") or 1)
        aspect_ratio = req.params.get("aspect_ratio", "1:1")
        output_mime = req.params.get("output_format", "image/png")
        if not output_mime.startswith("image/"):
            output_mime = f"image/{output_mime}"

        payload = {
            "instances": [instance],
            "parameters": {
                "sampleCount": sample_count,
                "aspectRatio": aspect_ratio,
                "outputOptions": {"mimeType": output_mime},
                **{
                    k: v
                    for k, v in req.params.items()
                    if k not in ("num_images", "sample_count", "aspect_ratio", "output_format")
                },
            },
        }

        endpoint = f"/v1beta/models/{model}:predict?key={self._api_key}"
        resp = await self._client.post(endpoint, json=payload)
        self._check_response(resp)

        data = resp.json()
        outputs = self.normalize_output(data)
        if not outputs:
            raise PermanentProviderError("Google AI returned no image outputs")

        self._jobs[job_id] = {
            "status": ProviderJobState.SUCCEEDED,
            "outputs": outputs,
            "canceled": False,
        }

        return ProviderJobRef(provider_id=self.id, provider_job_id=job_id)

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current status and outputs."""
        job = self._jobs.get(ref.provider_job_id)
        if job is None:
            return ProviderStatus(
                state=ProviderJobState.FAILED,
                error_code="JOB_NOT_FOUND",
                error_message=f"Google job {ref.provider_job_id} not found",
            )

        if job["canceled"]:
            return ProviderStatus(state=ProviderJobState.CANCELED)

        return ProviderStatus(
            state=job["status"],
            outputs=job["outputs"],
        )

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a job (best effort)."""
        if ref.provider_job_id in self._jobs:
            self._jobs[ref.provider_job_id]["canceled"] = True
            self._jobs[ref.provider_job_id]["status"] = ProviderJobState.CANCELED

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify webhook delivery."""
        h = {k.lower(): v for k, v in headers.items()}
        signature = h.get("x-goog-signature") or h.get("x-google-signature")
        if not signature:
            raise PermanentProviderError("Missing Google webhook signature header")

        payload = json.loads(body.decode("utf-8"))
        job_id = payload.get("id", payload.get("name", "unknown"))
        state_str = payload.get("status", "SUCCEEDED").upper()
        state = (
            ProviderJobState.SUCCEEDED
            if state_str in ("SUCCEEDED", "OK")
            else ProviderJobState.FAILED
        )

        outputs = self.normalize_output(payload) if state == ProviderJobState.SUCCEEDED else []

        return WebhookEvent(
            provider_id=self.id,
            provider_job_id=job_id,
            state=state,
            outputs=outputs,
            raw_payload=payload,
        )

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize Google AI predictions or inlineData into ProviderOutput items."""
        outputs: list[ProviderOutput] = []

        # 1. Imagen predict format:
        # {"predictions": [{"bytesBase64Encoded": "...", "mimeType": "..."}]}
        for pred in raw.get("predictions", []):
            if isinstance(pred, dict):
                b64 = pred.get("bytesBase64Encoded")
                mime = pred.get("mimeType", "image/png")
                if b64:
                    data_uri = f"data:{mime};base64,{b64}"
                    outputs.append(
                        ProviderOutput(
                            url=data_uri,
                            mime_type=mime,
                            kind=_guess_kind(mime, data_uri),
                        )
                    )
                elif "url" in pred:
                    outputs.append(
                        ProviderOutput(
                            url=pred["url"],
                            mime_type=mime,
                            kind=_guess_kind(mime, pred["url"]),
                        )
                    )

        # 2. Gemini generateContent inlineData format
        for candidate in raw.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                inline = part.get("inlineData", {})
                b64 = inline.get("data")
                mime = inline.get("mimeType", "image/png")
                if b64:
                    data_uri = f"data:{mime};base64,{b64}"
                    outputs.append(
                        ProviderOutput(
                            url=data_uri,
                            mime_type=mime,
                            kind=_guess_kind(mime, data_uri),
                        )
                    )

        # 3. Direct output list/dict fallback
        if not outputs:
            raw_out = raw.get("outputs") or raw.get("output")
            if isinstance(raw_out, list):
                for item in raw_out:
                    if isinstance(item, str):
                        outputs.append(
                            ProviderOutput(
                                url=item,
                                kind=_guess_kind(None, item),
                            )
                        )
                    elif isinstance(item, dict) and "url" in item:
                        mime = item.get("mime_type")
                        outputs.append(
                            ProviderOutput(
                                url=item["url"],
                                mime_type=mime,
                                kind=_guess_kind(mime, item["url"]),
                            )
                        )
            elif isinstance(raw_out, str):
                outputs.append(
                    ProviderOutput(
                        url=raw_out,
                        kind=_guess_kind(None, raw_out),
                    )
                )

        return outputs

    def _check_response(self, resp: httpx.Response) -> None:
        """Map HTTP error codes to provider error types."""
        if resp.is_success:
            return

        status = resp.status_code
        body_text = resp.text

        if status == 429:
            retry_after = float(resp.headers.get("retry-after", "5"))
            raise RateLimitedError(
                f"Google rate limited: {body_text}",
                retry_after=retry_after,
            )

        if status in (400, 401, 403, 404, 422):
            raise PermanentProviderError(f"Google validation error ({status}): {body_text}")

        if status >= 500:
            raise TransientProviderError(f"Google server error ({status}): {body_text}")

        raise ProviderError(f"Google unexpected status ({status}): {body_text}")
