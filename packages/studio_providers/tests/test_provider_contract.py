"""Contract test suite for generation providers and FakeProvider test implementation."""

import pytest

from studio_core.models import AssetKind, TaskType
from studio_providers.base import (
    GenerationProvider,
    PermanentProviderError,
    ProviderJobState,
    ProviderRequest,
    TransientProviderError,
)
from studio_providers.fake import FakeProvider


class ProviderContractSuite:
    """Base test suite that any adapter (Fake, Replicate, Fal) must pass."""

    @pytest.fixture
    def provider(self) -> GenerationProvider:
        raise NotImplementedError

    @pytest.mark.asyncio
    async def test_submit_returns_valid_job_ref(self, provider: GenerationProvider) -> None:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="test-model",
            prompt="A cozy cabin in the snowy woods",
        )
        ref = await provider.submit(req)
        assert ref.provider_id == provider.id
        assert len(ref.provider_job_id) > 0

    @pytest.mark.asyncio
    async def test_get_status_succeeded_with_outputs(self, provider: GenerationProvider) -> None:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="test-model",
            prompt="Futuristic city skyline at sunset",
        )
        ref = await provider.submit(req)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.SUCCEEDED
        assert len(status.outputs) > 0
        assert status.outputs[0].kind == AssetKind.IMAGE
        assert status.outputs[0].url.startswith("http")

    @pytest.mark.asyncio
    async def test_cancel_job(self, provider: GenerationProvider) -> None:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="test-model",
            prompt="Abstract geometric patterns",
        )
        ref = await provider.submit(req)
        await provider.cancel(ref)
        status = await provider.get_status(ref)
        assert status.state == ProviderJobState.CANCELED


class TestFakeProviderContract(ProviderContractSuite):
    """Verifies that FakeProvider satisfies the reusable contract suite."""

    @pytest.fixture
    def provider(self) -> GenerationProvider:
        return FakeProvider()

    @pytest.mark.asyncio
    async def test_permanent_failure_injection(self, provider: FakeProvider) -> None:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="test-model",
            prompt="This prompt will FAIL intentionally",
        )
        with pytest.raises(PermanentProviderError):
            await provider.submit(req)

    @pytest.mark.asyncio
    async def test_transient_failure_injection(self, provider: FakeProvider) -> None:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="test-model",
            prompt="Simulate TRANSIENT_FAIL now",
        )
        with pytest.raises(TransientProviderError):
            await provider.submit(req)

    def test_webhook_verification_valid_and_invalid(self, provider: FakeProvider) -> None:
        # Invalid signature
        with pytest.raises(PermanentProviderError):
            provider.verify_webhook({"x-fake-signature": "wrong"}, b"{}")

        # Valid signature
        body = (
            b'{"id": "pred_123", "status": "succeeded", "outputs": '
            b'[{"url": "http://img.png", "kind": "image"}]}'
        )
        event = provider.verify_webhook({"x-fake-signature": "valid_secret"}, body)
        assert event.provider_job_id == "pred_123"
        assert event.state == ProviderJobState.SUCCEEDED
        assert len(event.outputs) == 1
