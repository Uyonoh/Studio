"""Google AI (Imagen / Veo) provider adapter implementing GenerationProvider."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from typing import Any, ClassVar

import httpx

from studio_core.models import AssetKind, TaskType
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
    """Generation provider adapter for Google AI (Imagen 3, Gemini, and Veo models)."""

    id: str = "google"

    # Shared process-level store for completed predictions: job_id -> ProviderStatus dict
    _shared_jobs: ClassVar[dict[str, dict[str, Any]]] = {}

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
        # Instance store fallback (also synchronizes with shared class store)
        self._jobs = self._shared_jobs

    @classmethod
    def is_gemini_model(cls, model: str) -> bool:
        """Check if model uses :generateContent instead of Imagen :predict / Veo."""
        lower = model.lower()
        return any(
            token in lower
            for token in ("gemini", "banana", "omni", "gemma", "flash-image", "pro-image")
        )

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a generation request to Google AI (Gemini, Imagen 3, or Veo)."""
        model = req.model.removeprefix("models/")

        if self.is_gemini_model(model):
            return await self._submit_gemini(req, model)

        is_video = (
            req.task_type in (TaskType.TEXT_TO_VIDEO, TaskType.IMAGE_TO_VIDEO)
            or "veo" in model.lower()
        )

        if is_video:
            return await self._submit_video(req, model)
        return await self._submit_image(req, model)

    async def _format_gemini_part(self, url: str) -> dict[str, Any]:
        """Format an input image/video URL for Gemini generateContent contents part."""
        if url.startswith("data:"):
            parts = url.split(",", 1)
            header = parts[0].removeprefix("data:")
            mime = header.split(";")[0] if ";" in header else "image/png"
            b64_data = parts[1] if len(parts) > 1 else ""
            return {
                "inlineData": {
                    "mimeType": mime or "image/png",
                    "data": b64_data,
                }
            }

        # If already a Google File API URI, pass as fileData
        if "generativelanguage.googleapis.com" in url:
            return {"fileData": {"fileUri": url, "mimeType": "image/png"}}

        # If HTTP/HTTPS URL, download and convert to inlineData base64
        if url.startswith(("http://", "https://")):
            try:
                r = await self._client.get(url, timeout=15.0)
                if r.is_success:
                    import base64

                    b64_data = base64.b64encode(r.content).decode("ascii")
                    mime = r.headers.get("content-type", "image/png").split(";")[0]
                    return {
                        "inlineData": {
                            "mimeType": mime or "image/png",
                            "data": b64_data,
                        }
                    }
            except Exception as exc:
                logger.warning("Failed to fetch image input from %s for Gemini: %s", url, exc)

        return {"fileData": {"fileUri": url, "mimeType": "image/png"}}

    async def _submit_gemini(self, req: ProviderRequest, model: str) -> ProviderJobRef:
        """Submit generation request to Gemini :generateContent endpoint."""
        job_id = f"goog_{uuid.uuid4().hex[:16]}"

        parts: list[dict[str, Any]] = []
        if req.prompt:
            parts.append({"text": req.prompt})

        for inp in req.inputs:
            if inp.role in ("init_image", "reference_image", "first_frame"):
                part = await self._format_gemini_part(inp.url)
                if part:
                    parts.append(part)

        is_video = (
            req.task_type in (TaskType.TEXT_TO_VIDEO, TaskType.IMAGE_TO_VIDEO)
            or "video" in model.lower()
        )
        modality = "VIDEO" if is_video else "IMAGE"
        generation_config: dict[str, Any] = {
            "responseModalities": [modality],
        }

        aspect_ratio = req.params.get("aspect_ratio") or req.params.get("aspectRatio")
        if aspect_ratio and not is_video:
            generation_config["imageConfig"] = {"aspectRatio": aspect_ratio}

        sample_count = int(
            req.params.get("num_images")
            or req.params.get("sample_count")
            or req.params.get("sampleCount")
            or 1
        )
        if sample_count > 1:
            generation_config["candidateCount"] = sample_count

        if "seed" in req.params:
            try:
                generation_config["seed"] = int(req.params["seed"])
            except (ValueError, TypeError):
                pass

        if "temperature" in req.params:
            try:
                generation_config["temperature"] = float(req.params["temperature"])
            except (ValueError, TypeError):
                pass

        payload: dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": generation_config,
        }

        if req.negative_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": f"Negative prompt / avoid: {req.negative_prompt}"}]
            }

        endpoint = f"/v1beta/models/{model}:generateContent?key={self._api_key}"
        headers = {"x-goog-api-key": self._api_key}
        resp = await self._client.post(endpoint, json=payload, headers=headers)
        self._check_response(resp)

        data = resp.json()
        outputs = self.normalize_output(data)
        if not outputs:
            raise PermanentProviderError("Google AI returned no outputs")

        self._jobs[job_id] = {
            "status": ProviderJobState.SUCCEEDED,
            "outputs": outputs,
            "canceled": False,
        }

        return ProviderJobRef(provider_id=self.id, provider_job_id=job_id)

    async def _submit_image(self, req: ProviderRequest, model: str) -> ProviderJobRef:
        """Submit image generation request to Imagen :predict endpoint."""
        job_id = f"goog_{uuid.uuid4().hex[:16]}"

        instance: dict[str, Any] = {"prompt": req.prompt or ""}
        if req.negative_prompt:
            instance["negativePrompt"] = req.negative_prompt

        for inp in req.inputs:
            if inp.role in ("init_image", "reference_image"):
                instance["image"] = self._format_input_image(inp.url)

        sample_count = int(
            req.params.get("num_images")
            or req.params.get("sample_count")
            or req.params.get("sampleCount")
            or 1
        )
        aspect_ratio = req.params.get("aspect_ratio") or req.params.get("aspectRatio") or "1:1"
        output_mime = (
            req.params.get("output_format")
            or req.params.get("output_mime_type")
            or req.params.get("outputMimeType")
            or "image/png"
        )
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
                    if k
                    not in (
                        "num_images",
                        "sample_count",
                        "sampleCount",
                        "aspect_ratio",
                        "aspectRatio",
                        "output_format",
                        "output_mime_type",
                        "outputMimeType",
                    )
                },
            },
        }

        endpoint = f"/v1beta/models/{model}:predict?key={self._api_key}"
        headers = {"x-goog-api-key": self._api_key}
        resp = await self._client.post(endpoint, json=payload, headers=headers)
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

    async def _submit_video(self, req: ProviderRequest, model: str) -> ProviderJobRef:
        """Submit video generation request to Veo :predictLongRunning endpoint."""
        instance: dict[str, Any] = {"prompt": req.prompt or ""}
        if req.negative_prompt:
            instance["negativePrompt"] = req.negative_prompt

        for inp in req.inputs:
            if inp.role in ("init_image", "first_frame", "reference_image"):
                instance["image"] = self._format_input_image(inp.url)

        aspect_ratio = req.params.get("aspect_ratio") or req.params.get("aspectRatio") or "16:9"
        duration_val = (
            req.params.get("duration")
            or req.params.get("duration_seconds")
            or req.params.get("durationSeconds")
            or 5
        )
        try:
            duration_seconds = int(duration_val)
        except (ValueError, TypeError):
            duration_seconds = 5

        sample_count = int(
            req.params.get("num_videos")
            or req.params.get("sample_count")
            or req.params.get("sampleCount")
            or 1
        )
        resolution = req.params.get("resolution", "720p")

        parameters: dict[str, Any] = {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration_seconds,
            "sampleCount": sample_count,
            "resolution": resolution,
        }
        for k, v in req.params.items():
            if k not in (
                "aspect_ratio",
                "aspectRatio",
                "duration",
                "duration_seconds",
                "durationSeconds",
                "num_videos",
                "sample_count",
                "sampleCount",
                "resolution",
            ):
                parameters[k] = v

        payload = {
            "instances": [instance],
            "parameters": parameters,
        }

        endpoint = f"/v1beta/models/{model}:predictLongRunning?key={self._api_key}"
        headers = {"x-goog-api-key": self._api_key}
        resp = await self._client.post(endpoint, json=payload, headers=headers)
        self._check_response(resp)

        data = resp.json()
        op_name = data.get("name")
        if not op_name:
            raise PermanentProviderError(f"Google AI returned no operation name: {data}")

        return ProviderJobRef(provider_id=self.id, provider_job_id=op_name)

    def _format_input_image(self, url: str) -> dict[str, Any]:
        """Format input image URL into Google API image payload."""
        if url.startswith("data:"):
            parts = url.split(",", 1)
            header = parts[0].removeprefix("data:")
            mime = header.split(";")[0] if ";" in header else "image/png"
            b64_data = parts[1] if len(parts) > 1 else ""
            return {
                "bytesBase64Encoded": b64_data,
                "mimeType": mime or "image/png",
            }
        return {"imageUri": url}

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current status and outputs from Google AI."""
        # 1. Long-Running Operation (Veo video generation)
        if ref.provider_job_id.startswith("operations/") or "/operations/" in ref.provider_job_id:
            op_path = ref.provider_job_id.lstrip("/")
            endpoint = f"/v1beta/{op_path}?key={self._api_key}"
            headers = {"x-goog-api-key": self._api_key}
            resp = await self._client.get(endpoint, headers=headers)
            self._check_response(resp)

            data = resp.json()
            if not data.get("done", False):
                return ProviderStatus(state=ProviderJobState.RUNNING)

            if "error" in data:
                err = data["error"]
                return ProviderStatus(
                    state=ProviderJobState.FAILED,
                    error_code=str(err.get("code") or "OPERATION_ERROR"),
                    error_message=err.get("message", "Video generation operation failed"),
                )

            outputs = self.normalize_output(data)
            if not outputs:
                return ProviderStatus(
                    state=ProviderJobState.FAILED,
                    error_code="NO_OUTPUTS",
                    error_message="Operation completed with no video outputs",
                )

            return ProviderStatus(
                state=ProviderJobState.SUCCEEDED,
                outputs=outputs,
            )

        # 2. In-memory / synchronous prediction job (Imagen)
        job = self._jobs.get(ref.provider_job_id)
        if job is None:
            return ProviderStatus(
                state=ProviderJobState.FAILED,
                error_code="JOB_NOT_FOUND",
                error_message=f"Google job {ref.provider_job_id} not found",
            )

        if job.get("canceled", False):
            return ProviderStatus(state=ProviderJobState.CANCELED)

        return ProviderStatus(
            state=job["status"],
            outputs=job.get("outputs", []),
        )

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a job (best effort)."""
        if ref.provider_job_id.startswith("operations/") or "/operations/" in ref.provider_job_id:
            op_path = ref.provider_job_id.lstrip("/")
            endpoint = f"/v1beta/{op_path}:cancel?key={self._api_key}"
            headers = {"x-goog-api-key": self._api_key}
            try:
                await self._client.post(endpoint, headers=headers)
            except Exception as exc:
                logger.warning("Failed to cancel Google operation %s: %s", ref.provider_job_id, exc)

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
        """Normalize Google AI predictions, operations, or inlineData into ProviderOutput items."""
        outputs: list[ProviderOutput] = []

        resp_val = raw.get("response")
        response_obj: dict[str, Any] = resp_val if isinstance(resp_val, dict) else raw

        # 1. Veo generateVideoResponse -> generatedSamples format
        gen_video_resp = response_obj.get("generateVideoResponse", {})
        samples = gen_video_resp.get("generatedSamples") or []
        for sample in samples:
            if isinstance(sample, dict):
                video_obj = sample.get("video", {})
                self._extract_video_item(video_obj, outputs)

        # 2. generatedVideos format
        gen_vids = response_obj.get("generatedVideos") or []
        for gv in gen_vids:
            if isinstance(gv, dict):
                video_obj = gv.get("video", gv)
                self._extract_video_item(video_obj, outputs)

        # 3. Imagen / Gemini predictions format
        for pred in response_obj.get("predictions", raw.get("predictions", [])):
            if isinstance(pred, dict):
                if "video" in pred:
                    self._extract_video_item(pred["video"], outputs)
                else:
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

        # 4. Gemini generateContent inlineData / fileData format
        for candidate in response_obj.get("candidates", raw.get("candidates", [])):
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
                file_data = part.get("fileData", {})
                file_uri = file_data.get("fileUri")
                mime_f = file_data.get("mimeType", "image/png")
                if file_uri:
                    if (
                        "generativelanguage.googleapis.com" in file_uri
                        and "key=" not in file_uri
                        and self._api_key
                    ):
                        sep = "&" if "?" in file_uri else "?"
                        file_uri = f"{file_uri}{sep}key={self._api_key}"
                    outputs.append(
                        ProviderOutput(
                            url=file_uri,
                            mime_type=mime_f,
                            kind=_guess_kind(mime_f, file_uri),
                        )
                    )

        # 5. Direct output list/dict fallback
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

    def _extract_video_item(self, video_obj: Any, outputs: list[ProviderOutput]) -> None:
        if not isinstance(video_obj, dict):
            return
        uri = video_obj.get("uri")
        b64 = video_obj.get("bytesBase64Encoded")
        mime = video_obj.get("mimeType", "video/mp4")
        if uri:
            # If Google API temporary URI, append API key so downloader has access
            if "generativelanguage.googleapis.com" in uri and "key=" not in uri and self._api_key:
                sep = "&" if "?" in uri else "?"
                uri = f"{uri}{sep}key={self._api_key}"
            outputs.append(
                ProviderOutput(
                    url=uri,
                    mime_type=mime,
                    kind=AssetKind.VIDEO,
                )
            )
        elif b64:
            data_uri = f"data:{mime};base64,{b64}"
            outputs.append(
                ProviderOutput(
                    url=data_uri,
                    mime_type=mime,
                    kind=AssetKind.VIDEO,
                )
            )

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
