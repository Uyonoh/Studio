"""Contract test suite for generation providers and FakeProvider test implementation."""

import pytest

from studio_core.models import TaskType
from studio_providers.base import (
    GenerationProvider,
    PermanentProviderError,
    ProviderJobState,
    ProviderRequest,
    TransientProviderError,
)
from studio_providers.contract import ProviderContractSuite
from studio_providers.fake import FakeProvider


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
