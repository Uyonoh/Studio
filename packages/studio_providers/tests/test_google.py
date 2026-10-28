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
