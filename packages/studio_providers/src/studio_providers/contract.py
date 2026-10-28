"""Reusable contract test suite that any adapter (Fake, Replicate, Fal) must pass."""

import pytest

from studio_core.models import AssetKind, TaskType
from studio_providers.base import (
    GenerationProvider,
    ProviderJobState,
    ProviderRequest,
)


class ProviderContractSuite:
    """Base test suite that any adapter must pass."""

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
