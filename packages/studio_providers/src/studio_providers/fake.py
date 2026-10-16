"""Deterministic FakeProvider for testing and local development without cloud costs."""

import asyncio
import json
import uuid
from collections.abc import Mapping
from typing import Any

from studio_core.models import AssetKind, TaskType
from studio_providers.base import (
    GenerationProvider,
    PermanentProviderError,
    ProviderJobRef,
    ProviderJobState,
    ProviderOutput,
    ProviderRequest,
    ProviderStatus,
    TransientProviderError,
    WebhookEvent,
)

# 1x1 transparent PNG data URI or sample mock URL
SAMPLE_PNG_URL = "https://mock.storage.local/media/fixtures/sample.png"
SAMPLE_MP4_URL = "https://mock.storage.local/media/fixtures/sample.mp4"


class FakeProvider(GenerationProvider):
    """Configurable in-memory FakeProvider satisfying the GenerationProvider protocol."""

    id: str = "fake"

    def __init__(
        self,
        latency_seconds: float = 0.0,
        fail_rate: float = 0.0,
        fail_on_prompt_contains: str = "FAIL",
        transient_fail_on_prompt_contains: str = "TRANSIENT_FAIL",
    ) -> None:
        self.latency_seconds = latency_seconds
        self.fail_rate = fail_rate
        self.fail_on_prompt_contains = fail_on_prompt_contains
        self.transient_fail_on_prompt_contains = transient_fail_on_prompt_contains
        self._jobs: dict[str, dict[str, Any]] = {}

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit request and record job state."""
        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        prompt = req.prompt or ""
        if (
            self.transient_fail_on_prompt_contains
            and self.transient_fail_on_prompt_contains in prompt
        ):
            raise TransientProviderError(f"Simulated transient failure for prompt: {prompt}")

        if self.fail_on_prompt_contains and self.fail_on_prompt_contains in prompt:
            raise PermanentProviderError(f"Simulated permanent failure for prompt: {prompt}")

        prediction_id = f"fake_pred_{uuid.uuid4().hex[:12]}"
        is_video = req.task_type in (TaskType.TEXT_TO_VIDEO, TaskType.IMAGE_TO_VIDEO)

        output = ProviderOutput(
            url=SAMPLE_MP4_URL if is_video else SAMPLE_PNG_URL,
            mime_type="video/mp4" if is_video else "image/png",
            kind=AssetKind.VIDEO if is_video else AssetKind.IMAGE,
        )

        self._jobs[prediction_id] = {
            "req": req,
            "status": ProviderJobState.SUCCEEDED,
            "outputs": [output],
            "canceled": False,
        }

        return ProviderJobRef(provider_id=self.id, provider_job_id=prediction_id)

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current status."""
        if ref.provider_job_id not in self._jobs:
            return ProviderStatus(
                state=ProviderJobState.FAILED,
                error_code="JOB_NOT_FOUND",
                error_message="Prediction does not exist in fake provider",
            )

        job_info = self._jobs[ref.provider_job_id]
        if job_info["canceled"]:
            return ProviderStatus(state=ProviderJobState.CANCELED)

        return ProviderStatus(
            state=job_info["status"],
            outputs=job_info["outputs"],
        )

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel prediction."""
        if ref.provider_job_id in self._jobs:
            self._jobs[ref.provider_job_id]["canceled"] = True
            self._jobs[ref.provider_job_id]["status"] = ProviderJobState.CANCELED

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify fake webhook signature and parse body."""
        signature = headers.get("x-fake-signature") or headers.get("X-Fake-Signature")
        if signature != "valid_secret":
            raise PermanentProviderError("Invalid webhook signature for fake provider")

        payload = json.loads(body.decode("utf-8"))
        prediction_id = payload.get("id", "unknown")
        status_str = payload.get("status", "succeeded")
        state = ProviderJobState(status_str)

        outputs: list[ProviderOutput] = []
        for out in payload.get("outputs", []):
            outputs.append(
                ProviderOutput(
                    url=out.get("url", SAMPLE_PNG_URL),
                    mime_type=out.get("mime_type", "image/png"),
                    kind=AssetKind(out.get("kind", "image")),
                )
            )

        return WebhookEvent(
            provider_id=self.id,
            provider_job_id=prediction_id,
            state=state,
            outputs=outputs,
            raw_payload=payload,
        )

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize raw dictionary payload."""
        outputs = []
        raw_outputs = raw.get("outputs") or [raw.get("output")]
        for item in raw_outputs:
            if not item:
                continue
            if isinstance(item, str):
                is_video = item.endswith(".mp4")
                outputs.append(
                    ProviderOutput(
                        url=item,
                        mime_type="video/mp4" if is_video else "image/png",
                        kind=AssetKind.VIDEO if is_video else AssetKind.IMAGE,
                    )
                )
            elif isinstance(item, dict):
                outputs.append(ProviderOutput.model_validate(item))
        return outputs

    def trigger_webhook_payload(self, ref: ProviderJobRef) -> tuple[dict[str, str], bytes]:
        """Helper to generate a valid webhook header and body for a submitted job."""
        job_info = self._jobs.get(ref.provider_job_id, {})
        outputs = [out.model_dump() for out in job_info.get("outputs", [])]
        payload = {
            "id": ref.provider_job_id,
            "status": "succeeded",
            "outputs": outputs,
        }
        headers = {"x-fake-signature": "valid_secret"}
        return headers, json.dumps(payload).encode("utf-8")
