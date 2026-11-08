"""Base protocols, models, and error taxonomy for generation providers."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from studio_core.models import AssetKind, TaskType


class ProviderError(Exception):
    """Base provider exception."""

    def __init__(self, message: str, code: str = "PROVIDER_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class TransientProviderError(ProviderError):
    """Transient failure (network blip, 500, timeout) safe to retry with backoff."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="TRANSIENT_PROVIDER_ERROR")


class PermanentProviderError(ProviderError):
    """Unrecoverable failure (bad parameters, safety violation, invalid asset)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PERMANENT_PROVIDER_ERROR")


class RateLimitedError(ProviderError):
    """Provider rate limited (429). Includes optional retry_after in seconds."""

    def __init__(self, message: str, retry_after: float = 5.0) -> None:
        super().__init__(message, code="RATE_LIMITED")
        self.retry_after = retry_after


class ProviderInput(BaseModel):
    """An input asset resolved to a short-lived download URL."""

    role: str
    url: str
    kind: AssetKind = AssetKind.IMAGE


class ProviderRequest(BaseModel):
    """Provider-neutral generation request."""

    task_type: TaskType
    model: str
    prompt: str | None = None
    negative_prompt: str | None = None
    inputs: list[ProviderInput] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = None


class ProviderJobRef(BaseModel):
    """Reference identifying a submitted job with a provider."""

    provider_id: str
    provider_job_id: str


class ProviderJobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class ProviderOutput(BaseModel):
    """A single output produced by the provider."""

    url: str
    mime_type: str | None = None
    kind: AssetKind = AssetKind.IMAGE


class ProviderStatus(BaseModel):
    """Current status of a provider prediction/job."""

    state: ProviderJobState
    outputs: list[ProviderOutput] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class WebhookEvent(BaseModel):
    """Normalized webhook payload received from a provider."""

    provider_id: str
    provider_job_id: str
    state: ProviderJobState
    outputs: list[ProviderOutput] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class GenerationProvider(Protocol):
    """Protocol that all generation providers must satisfy."""

    id: str

    async def submit(self, req: ProviderRequest) -> ProviderJobRef:
        """Submit a prediction/generation job to the provider."""
        ...

    async def get_status(self, ref: ProviderJobRef) -> ProviderStatus:
        """Fetch current status and outputs from the provider."""
        ...

    async def cancel(self, ref: ProviderJobRef) -> None:
        """Cancel a running prediction with the provider."""
        ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify webhook signature and parse event."""
        ...

    def normalize_output(self, raw: dict[str, Any]) -> list[ProviderOutput]:
        """Normalize raw provider payload into a list of ProviderOutput items."""
        ...
