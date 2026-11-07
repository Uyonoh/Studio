"""Tests for the GoogleProvider adapter with respx recorded fixtures."""

import base64
import json

import httpx
import pytest
import respx

from studio_core.models import AssetKind, TaskType
from studio_providers.base import (
    GenerationProvider,
    PermanentProviderError,
    ProviderInput,
    ProviderJobRef,
    ProviderJobState,
    ProviderRequest,
    RateLimitedError,
    TransientProviderError,
)
from studio_providers.contract import ProviderContractSuite
from studio_providers.google import GoogleProvider

GOOGLE_BASE = "https://generativelanguage.googleapis.com"
API_KEY = "test-gemini-key-123"
MODEL = "imagen-3.0-generate-002"

# 1x1 transparent PNG in base64
SAMPLE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

IMAGEN_PREDICT_RESPONSE = {
    "predictions": [
        {
            "bytesBase64Encoded": SAMPLE_PNG_B64,
            "mimeType": "image/png",
        }
    ]
}

GEMINI_GENERATE_CONTENT_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "inlineData": {
                            "data": SAMPLE_PNG_B64,
                            "mimeType": "image/png",
                        }
                    }
                ]
            }
        }
    ]
}


def _make_provider() -> GoogleProvider:
    return GoogleProvider(api_key=API_KEY, base_url=GOOGLE_BASE)


def _text_to_image_req(**kwargs: object) -> ProviderRequest:
    defaults: dict[str, object] = {
        "task_type": TaskType.TEXT_TO_IMAGE,
        "model": MODEL,
        "prompt": "A cozy cabin in the snowy woods",
    }
    defaults.update(kwargs)
    return ProviderRequest(**defaults)  # type: ignore[arg-type]


# ── Contract suite ───────────────────────────────────────────────────────


class TestGoogleContract(ProviderContractSuite):
    """Verify GoogleProvider satisfies the reusable contract suite."""

    @pytest.fixture
    def provider(self, respx_mock: respx.MockRouter) -> GenerationProvider:
        p = _make_provider()

        # Mock predict POST for default contract model and Google Imagen model
        respx_mock.post(
            url__regex=rf"^{GOOGLE_BASE}/v1beta/models/[^:]+:predict\?key={API_KEY}$"
        ).mock(return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE))

        return p


# ── Unit tests ───────────────────────────────────────────────────────────


class TestGoogleSubmit:
    """Tests for GoogleProvider.submit()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_returns_valid_job_ref(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE)
        )

        ref = await provider.submit(_text_to_image_req())

        assert ref.provider_id == "google"
        assert ref.provider_job_id.startswith("goog_")

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_includes_prompt_and_params(self) -> None:
        provider = _make_provider()
        route = respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE)
        )

        req = _text_to_image_req(
            prompt="cyberpunk cityscape",
            params={"num_images": 2, "aspect_ratio": "16:9", "output_format": "image/jpeg"},
        )
        await provider.submit(req)

        sent = json.loads(route.calls[0].request.content)
        instance = sent["instances"][0]
        params = sent["parameters"]
        assert instance["prompt"] == "cyberpunk cityscape"
        assert params["sampleCount"] == 2
        assert params["aspectRatio"] == "16:9"
        assert params["outputOptions"]["mimeType"] == "image/jpeg"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_maps_input_images(self) -> None:
        provider = _make_provider()
        route = respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE)
        )

        req = _text_to_image_req(
            inputs=[
                ProviderInput(role="init_image", url="https://example.com/source.png"),
            ]
        )
        await provider.submit(req)

        sent = json.loads(route.calls[0].request.content)
        instance = sent["instances"][0]
        assert instance["image"]["imageUri"] == "https://example.com/source.png"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_empty_predictions_raises_permanent(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json={"predictions": []})
        )

        with pytest.raises(PermanentProviderError, match="no image outputs"):
            await provider.submit(_text_to_image_req())

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_video_returns_operation_ref(self) -> None:
        provider = _make_provider()
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/veo-2.0-generate-001:predictLongRunning?key={API_KEY}"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"name": "operations/test-operation-12345"},
            )
        )

        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_VIDEO,
            model="veo-2.0-generate-001",
            prompt="A majestic eagle flying over mountains",
            params={"aspect_ratio": "16:9", "duration": 5, "resolution": "720p"},
        )
        ref = await provider.submit(req)

        assert ref.provider_id == "google"
        assert ref.provider_job_id == "operations/test-operation-12345"

        sent = json.loads(route.calls[0].request.content)
        assert sent["instances"][0]["prompt"] == "A majestic eagle flying over mountains"
        assert sent["parameters"]["aspectRatio"] == "16:9"
        assert sent["parameters"]["durationSeconds"] == 5
        assert sent["parameters"]["resolution"] == "720p"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_video_image_to_video_data_uri(self) -> None:
        provider = _make_provider()
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/veo-2.0-generate-001:predictLongRunning?key={API_KEY}"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"name": "operations/test-operation-i2v"},
            )
        )

        req = ProviderRequest(
            task_type=TaskType.IMAGE_TO_VIDEO,
            model="veo-2.0-generate-001",
            prompt="Camera slowly zooms in",
            inputs=[
                ProviderInput(role="first_frame", url=f"data:image/png;base64,{SAMPLE_PNG_B64}"),
            ],
            params={"aspect_ratio": "16:9"},
        )
        ref = await provider.submit(req)
        assert ref.provider_job_id == "operations/test-operation-i2v"

        sent = json.loads(route.calls[0].request.content)
        img_payload = sent["instances"][0]["image"]
        assert img_payload["bytesBase64Encoded"] == SAMPLE_PNG_B64
        assert img_payload["mimeType"] == "image/png"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_gemini_text_to_image(self) -> None:
        provider = _make_provider()
        model_name = "gemini-nano-banana-2.1"
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        ).mock(return_value=httpx.Response(200, json=GEMINI_GENERATE_CONTENT_RESPONSE))

        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model=model_name,
            prompt="futuristic hovercar",
            params={"aspect_ratio": "16:9", "num_images": 1},
        )
        ref = await provider.submit(req)

        assert ref.provider_id == "google"
        assert ref.provider_job_id.startswith("goog_")

        sent = json.loads(route.calls[0].request.content)
        assert sent["contents"][0]["parts"][0]["text"] == "futuristic hovercar"
        assert sent["generationConfig"]["responseModalities"] == ["IMAGE"]
        assert sent["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"

        # Check job store
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.SUCCEEDED
        assert len(status.outputs) == 1
        assert status.outputs[0].kind == AssetKind.IMAGE

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_gemini_image_to_image_data_uri(self) -> None:
        provider = _make_provider()
        model_name = "gemini-nano-banana-2.1"
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        ).mock(return_value=httpx.Response(200, json=GEMINI_GENERATE_CONTENT_RESPONSE))

        req = ProviderRequest(
            task_type=TaskType.IMAGE_TO_IMAGE,
            model=model_name,
            prompt="cyberpunk variant",
            inputs=[
                ProviderInput(role="init_image", url=f"data:image/png;base64,{SAMPLE_PNG_B64}"),
            ],
        )
        ref = await provider.submit(req)
        assert ref.provider_job_id.startswith("goog_")

        sent = json.loads(route.calls[0].request.content)
        parts = sent["contents"][0]["parts"]
        assert parts[0]["text"] == "cyberpunk variant"
        assert parts[1]["inlineData"]["data"] == SAMPLE_PNG_B64
        assert parts[1]["inlineData"]["mimeType"] == "image/png"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_gemini_external_image_url(self) -> None:
        provider = _make_provider()
        model_name = "gemini-3.1-flash-lite-image"
        # Mock external image download
        respx.get("https://storage.example.com/asset.png").mock(
            return_value=httpx.Response(
                200,
                content=b"\x89PNG\r\n\x1a\nfake_bytes",
                headers={"content-type": "image/png"},
            )
        )
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        ).mock(return_value=httpx.Response(200, json=GEMINI_GENERATE_CONTENT_RESPONSE))

        req = ProviderRequest(
            task_type=TaskType.IMAGE_TO_IMAGE,
            model=model_name,
            prompt="watercolor effect",
            inputs=[
                ProviderInput(role="init_image", url="https://storage.example.com/asset.png"),
            ],
        )
        ref = await provider.submit(req)
        assert ref.provider_job_id.startswith("goog_")

        sent = json.loads(route.calls[0].request.content)
        parts = sent["contents"][0]["parts"]
        assert "inlineData" in parts[1]
        assert parts[1]["inlineData"]["mimeType"] == "image/png"

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_gemini_video_modality(self) -> None:
        provider = _make_provider()
        model_name = "gemini-omni-1.2-flash"
        route = respx.post(
            f"{GOOGLE_BASE}/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        ).mock(return_value=httpx.Response(200, json=GEMINI_GENERATE_CONTENT_RESPONSE))

        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_VIDEO,
            model=model_name,
            prompt="A rolling ocean wave",
        )
        await provider.submit(req)

        sent = json.loads(route.calls[0].request.content)
        assert sent["generationConfig"]["responseModalities"] == ["VIDEO"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_submit_gemini_empty_response_raises_permanent(self) -> None:
        provider = _make_provider()
        model_name = "gemini-nano-banana-2.1"
        respx.post(
            f"{GOOGLE_BASE}/v1beta/models/{model_name}:generateContent?key={API_KEY}"
        ).mock(return_value=httpx.Response(200, json={"candidates": []}))

        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model=model_name,
            prompt="test",
        )
        with pytest.raises(PermanentProviderError, match="no outputs"):
            await provider.submit(req)


class TestGoogleGetStatus:
    """Tests for GoogleProvider.get_status()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_succeeded_with_data_uri_outputs(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE)
        )

        ref = await provider.submit(_text_to_image_req())
        status = await provider.get_status(ref)

        assert status.state == ProviderJobState.SUCCEEDED
        assert len(status.outputs) == 1
        assert status.outputs[0].url.startswith("data:image/png;base64,")
        assert status.outputs[0].kind == AssetKind.IMAGE

    @pytest.mark.asyncio
    async def test_get_status_unknown_job_returns_failed(self) -> None:
        provider = _make_provider()
        ref = ProviderJobRef(provider_id="google", provider_job_id="nonexistent")

        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.FAILED
        assert status.error_code == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_video_operation_running(self) -> None:
        provider = _make_provider()
        op_id = "operations/op-running-123"
        respx.get(f"{GOOGLE_BASE}/v1beta/{op_id}?key={API_KEY}").mock(
            return_value=httpx.Response(200, json={"name": op_id, "done": False})
        )

        ref = ProviderJobRef(provider_id="google", provider_job_id=op_id)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.RUNNING

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_video_operation_succeeded(self) -> None:
        provider = _make_provider()
        op_id = "operations/op-done-123"
        video_url = "https://generativelanguage.googleapis.com/v1beta/files/generated_video_789"
        respx.get(f"{GOOGLE_BASE}/v1beta/{op_id}?key={API_KEY}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": op_id,
                    "done": True,
                    "response": {
                        "generateVideoResponse": {
                            "generatedSamples": [
                                {
                                    "video": {
                                        "uri": video_url,
                                    }
                                }
                            ]
                        }
                    },
                },
            )
        )

        ref = ProviderJobRef(provider_id="google", provider_job_id=op_id)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.SUCCEEDED
        assert len(status.outputs) == 1
        assert status.outputs[0].kind == AssetKind.VIDEO
        assert status.outputs[0].url == f"{video_url}?key={API_KEY}"
        assert status.outputs[0].mime_type == "video/mp4"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_video_operation_failed(self) -> None:
        provider = _make_provider()
        op_id = "operations/op-failed-123"
        respx.get(f"{GOOGLE_BASE}/v1beta/{op_id}?key={API_KEY}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "name": op_id,
                    "done": True,
                    "error": {
                        "code": 400,
                        "message": "Content moderation policy triggered",
                    },
                },
            )
        )

        ref = ProviderJobRef(provider_id="google", provider_job_id=op_id)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.FAILED
        assert status.error_code == "400"
        assert status.error_message is not None
        assert "Content moderation" in status.error_message


class TestGoogleCancel:
    """Tests for GoogleProvider.cancel()."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_cancel_job(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(200, json=IMAGEN_PREDICT_RESPONSE)
        )

        ref = await provider.submit(_text_to_image_req())
        await provider.cancel(ref)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_unknown_job_does_not_raise(self) -> None:
        provider = _make_provider()
        ref = ProviderJobRef(provider_id="google", provider_job_id="nonexistent")
        await provider.cancel(ref)

    @pytest.mark.asyncio
    @respx.mock
    async def test_cancel_video_operation(self) -> None:
        provider = _make_provider()
        op_id = "operations/op-cancel-123"
        route = respx.post(f"{GOOGLE_BASE}/v1beta/{op_id}:cancel?key={API_KEY}").mock(
            return_value=httpx.Response(200, json={})
        )

        ref = ProviderJobRef(provider_id="google", provider_job_id=op_id)
        await provider.cancel(ref)
        assert route.called


class TestGoogleErrorMapping:
    """Tests for HTTP error code mapping."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_429_raises_rate_limited(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(
                429,
                text="Resource exhausted",
                headers={"retry-after": "12"},
            )
        )

        with pytest.raises(RateLimitedError) as exc_info:
            await provider.submit(_text_to_image_req())
        assert exc_info.value.retry_after == 12.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_500_raises_transient(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(500, text="Internal error")
        )

        with pytest.raises(TransientProviderError):
            await provider.submit(_text_to_image_req())

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_400_raises_permanent(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(400, text="Invalid argument")
        )

        with pytest.raises(PermanentProviderError):
            await provider.submit(_text_to_image_req())

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_403_raises_permanent(self) -> None:
        provider = _make_provider()
        respx.post(f"{GOOGLE_BASE}/v1beta/models/{MODEL}:predict?key={API_KEY}").mock(
            return_value=httpx.Response(403, text="Permission denied: API key invalid")
        )

        with pytest.raises(PermanentProviderError):
            await provider.submit(_text_to_image_req())


class TestGoogleWebhook:
    """Tests for GoogleProvider.verify_webhook()."""

    def test_webhook_verification_valid(self) -> None:
        provider = _make_provider()
        payload = {
            "id": "goog_test123",
            "status": "SUCCEEDED",
            "predictions": IMAGEN_PREDICT_RESPONSE["predictions"],
        }
        headers = {"X-Goog-Signature": "valid_token"}

        event = provider.verify_webhook(headers, json.dumps(payload).encode())

        assert event.provider_id == "google"
        assert event.provider_job_id == "goog_test123"
        assert event.state == ProviderJobState.SUCCEEDED
        assert len(event.outputs) == 1
        assert event.outputs[0].kind == AssetKind.IMAGE

    def test_webhook_verification_missing_signature(self) -> None:
        provider = _make_provider()
        with pytest.raises(PermanentProviderError, match="Missing Google webhook signature"):
            provider.verify_webhook({}, b"{}")


class TestGoogleNormalizeOutput:
    """Tests for GoogleProvider.normalize_output()."""

    def test_normalize_output_predictions(self) -> None:
        provider = _make_provider()
        outputs = provider.normalize_output(IMAGEN_PREDICT_RESPONSE)

        assert len(outputs) == 1
        assert outputs[0].url.startswith("data:image/png;base64,")
        assert outputs[0].mime_type == "image/png"
        assert outputs[0].kind == AssetKind.IMAGE

    def test_normalize_output_inline_data(self) -> None:
        provider = _make_provider()
        raw = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": base64.b64encode(b"fake_jpeg").decode(),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        outputs = provider.normalize_output(raw)

        assert len(outputs) == 1
        assert outputs[0].mime_type == "image/jpeg"
        assert outputs[0].url.startswith("data:image/jpeg;base64,")
        assert outputs[0].kind == AssetKind.IMAGE

    def test_normalize_output_url_fallback(self) -> None:
        provider = _make_provider()
        raw = {"output": ["https://storage.googleapis.com/bucket/output.mp4"]}
        outputs = provider.normalize_output(raw)

        assert len(outputs) == 1
        assert outputs[0].url == "https://storage.googleapis.com/bucket/output.mp4"
        assert outputs[0].kind == AssetKind.VIDEO

    def test_normalize_output_veo_generate_video_response(self) -> None:
        provider = _make_provider()
        raw = {
            "response": {
                "generateVideoResponse": {
                    "generatedSamples": [
                        {
                            "video": {
                                "uri": "https://generativelanguage.googleapis.com/v1beta/files/vid123",
                            }
                        }
                    ]
                }
            }
        }
        outputs = provider.normalize_output(raw)
        assert len(outputs) == 1
        assert outputs[0].kind == AssetKind.VIDEO
        assert outputs[0].mime_type == "video/mp4"
        assert outputs[0].url == f"https://generativelanguage.googleapis.com/v1beta/files/vid123?key={API_KEY}"

    def test_normalize_output_veo_base64_video(self) -> None:
        provider = _make_provider()
        fake_b64 = "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDE="
        raw = {
            "response": {
                "predictions": [
                    {
                        "video": {
                            "bytesBase64Encoded": fake_b64,
                            "mimeType": "video/mp4",
                        }
                    }
                ]
            }
        }
        outputs = provider.normalize_output(raw)
        assert len(outputs) == 1
        assert outputs[0].kind == AssetKind.VIDEO
        assert outputs[0].url == f"data:video/mp4;base64,{fake_b64}"
