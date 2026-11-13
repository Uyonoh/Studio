"""Fal.ai provider adapter implementing the GenerationProvider protocol."""

import json
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from studio_core.models import AssetKind
from studio_providers.base import (
    GenerationProvider,
    PermanentProviderError,
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

# Mapping from fal content_type to AssetKind
_CONTENT_TYPE_TO_KIND: dict[str, AssetKind] = {
    "image/png": AssetKind.IMAGE,
    "image/jpeg": AssetKind.IMAGE,
    "image/webp": AssetKind.IMAGE,
    "video/mp4": AssetKind.VIDEO,
    "audio/mpeg": AssetKind.AUDIO,
    "audio/wav": AssetKind.AUDIO,
}

# Mapping from ProviderInput role to fal input field name
_ROLE_TO_FAL_FIELD: dict[str, str] = {
    "mask": "mask_url",
    "audio": "audio_url",
    "video": "video_url",
}

# Some fal models use a dedicated field for the last frame instead of the
# generic ``image_url`` slot used by their first frame. Kling calls it
# ``tail_image_url``; other families may use a different key, so only the
# known overrides are listed here and the fallback stays generic.
_LAST_FRAME_INPUT_KEY: dict[str, str] = {
    "fal-ai/kling-video/v2/standard/image-to-video": "tail_image_url",
    "fal-ai/kling-video/v2.5-turbo/pro/image-to-video": "tail_image_url",
}
_DEFAULT_LAST_FRAME_KEY = "last_frame_url"


class FalProvider(GenerationProvider):
    """Fal.ai generation provider using the queue-based API."""

    id: str = "fal"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://queue.fal.run",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Key {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # Store job metadata: request_id → {model, response_url, status_url, cancel_url}
        self._jobs: dict[str, dict[str, str]] = {}

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a generation request to the fal queue API."""
        # Build input payload
        input_data: dict[str, Any] = {}
        if req.prompt is not None:
            input_data["prompt"] = req.prompt
        if req.negative_prompt is not None:
            input_data["negative_prompt"] = req.negative_prompt

        # Map input assets by role. Image inputs share a single slot when
        # there is one and become ``image_urls`` when a model accepts several.
        image_urls: list[str] = []
        for inp in req.inputs:
            if inp.role in ("init_image", "reference_image"):
                image_urls.append(inp.url)
            elif inp.role == "first_frame":
                input_data["image_url"] = inp.url
            elif inp.role == "last_frame":
                last_frame_key = _LAST_FRAME_INPUT_KEY.get(req.model, _DEFAULT_LAST_FRAME_KEY)
                input_data[last_frame_key] = inp.url
            else:
                field_name = _ROLE_TO_FAL_FIELD.get(inp.role, f"{inp.role}_url")
                input_data[field_name] = inp.url

        if len(image_urls) == 1:
            input_data["image_url"] = image_urls[0]
        elif image_urls:
            input_data["image_urls"] = image_urls

        # Merge extra params (allows overriding anything)
        input_data.update(req.params)

        # Build URL with optional webhook
        url = f"{self._base_url}/{req.model}"
        if req.webhook_url:
            url = f"{url}?fal_webhook={quote(req.webhook_url, safe='')}"

        response = await self._client.post(url, json=input_data)
        self._raise_for_status(response)

        data = response.json()
        request_id: str = data["request_id"]

        # Store URLs for later use
        self._jobs[request_id] = {
            "model": req.model,
            "response_url": data.get(
                "response_url",
                f"{self._base_url}/{req.model}/requests/{request_id}",
            ),
            "status_url": data.get(
                "status_url",
                f"{self._base_url}/{req.model}/requests/{request_id}/status",
            ),
            "cancel_url": data.get(
                "cancel_url",
                f"{self._base_url}/{req.model}/requests/{request_id}/cancel",
            ),
        }

        return ProviderJobRef(provider_id=self.id, provider_job_id=request_id)

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current status and outputs from fal."""
        job_meta = self._jobs.get(ref.provider_job_id)
        if job_meta is None:
            return ProviderStatus(
                state=ProviderJobState.FAILED,
                error_code="JOB_NOT_FOUND",
                error_message=(
                    f"No metadata stored for job {ref.provider_job_id}. "
                    "Job may have been submitted by a different instance."
                ),
            )

        # Check status
        status_url = job_meta["status_url"]
        status_resp = await self._client.get(status_url)
        self._raise_for_status(status_resp)

        status_data = status_resp.json()
        fal_status: str = status_data.get("status", "UNKNOWN")

        state = _map_fal_status(fal_status)

        if state == ProviderJobState.SUCCEEDED:
            # Fetch the full result
            response_url = job_meta["response_url"]
            result_resp = await self._client.get(response_url)
            self._raise_for_status(result_resp)

            result_data = result_resp.json()
            outputs = self.normalize_output(result_data)

            return ProviderStatus(state=state, outputs=outputs)

        if state == ProviderJobState.FAILED:
            return ProviderStatus(
                state=state,
                error_code="FAL_JOB_FAILED",
                error_message=status_data.get("error", "Job failed on fal"),
            )

        return ProviderStatus(state=state)

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a running job on fal. Swallows errors."""
        job_meta = self._jobs.get(ref.provider_job_id)
        if job_meta is None:
            logger.warning("Cannot cancel job %s: no metadata stored", ref.provider_job_id)
            return

        cancel_url = job_meta["cancel_url"]
        try:
            await self._client.put(cancel_url)
        except httpx.HTTPError:
            logger.warning("Failed to cancel job %s on fal", ref.provider_job_id, exc_info=True)

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify fal webhook signature and parse event payload.

        TODO: Implement full Ed25519 verification with JWKS keys from
        https://rest.fal.ai/.well-known/jwks.json for production use.
        Currently only checks that the signature header is present.
        """
        # Check for signature header (case-insensitive lookup)
        signature = _get_header_case_insensitive(headers, "X-Fal-Webhook-Signature")
        if not signature:
            raise PermanentProviderError("Missing X-Fal-Webhook-Signature header in fal webhook")

        payload: dict[str, Any] = json.loads(body.decode("utf-8"))

        request_id: str = payload.get("request_id", payload.get("gateway_request_id", "unknown"))
        fal_webhook_status: str = payload.get("status", "ERROR")

        if fal_webhook_status == "OK":
            state = ProviderJobState.SUCCEEDED
        else:
            state = ProviderJobState.FAILED

        raw_output = payload.get("payload", {})
        outputs = self.normalize_output(raw_output) if raw_output else []

        return WebhookEvent(
            provider_id=self.id,
            provider_job_id=request_id,
            state=state,
            outputs=outputs,
            raw_payload=payload,
        )

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize fal output formats into a list of ProviderOutput items.

        Handles fal's common output shapes:
        - ``{"images": [{"url": "...", "content_type": "image/jpeg", ...}]}``
        - ``{"video": {"url": "...", "content_type": "video/mp4"}}``
        """
        outputs: list[ProviderOutput] = []

        # Handle images list
        for img in raw.get("images", []):
            if isinstance(img, dict) and "url" in img:
                content_type = img.get("content_type", "image/png")
                outputs.append(
                    ProviderOutput(
                        url=img["url"],
                        mime_type=content_type,
                        kind=_CONTENT_TYPE_TO_KIND.get(content_type, AssetKind.IMAGE),
                    )
                )

        # Handle video dict
        video = raw.get("video")
        if isinstance(video, dict) and "url" in video:
            content_type = video.get("content_type", "video/mp4")
            outputs.append(
                ProviderOutput(
                    url=video["url"],
                    mime_type=content_type,
                    kind=_CONTENT_TYPE_TO_KIND.get(content_type, AssetKind.VIDEO),
                )
            )

        return outputs

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map HTTP error codes to provider error types."""
        if response.is_success:
            return

        status = response.status_code
        body_text = response.text

        if status == 429:
            retry_after = float(response.headers.get("retry-after", "5"))
            raise RateLimitedError(
                f"Fal rate limited: {body_text}",
                retry_after=retry_after,
            )

        if status >= 500:
            raise TransientProviderError(f"Fal server error ({status}): {body_text}")

        if status in (400, 422):
            raise PermanentProviderError(f"Fal validation error ({status}): {body_text}")

        # Other 4xx
        raise PermanentProviderError(f"Fal client error ({status}): {body_text}")


def _map_fal_status(fal_status: str) -> ProviderJobState:
    """Map fal queue status strings to ProviderJobState."""
    mapping: dict[str, ProviderJobState] = {
        "IN_QUEUE": ProviderJobState.PENDING,
        "IN_PROGRESS": ProviderJobState.RUNNING,
        "COMPLETED": ProviderJobState.SUCCEEDED,
    }
    return mapping.get(fal_status, ProviderJobState.FAILED)


def _get_header_case_insensitive(headers: Mapping[str, str], name: str) -> str | None:
    """Look up a header value case-insensitively."""
    lower_name = name.lower()
    for key, value in headers.items():
        if key.lower() == lower_name:
            return value
    return None
