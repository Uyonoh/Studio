"""Moderation hook for generation prompts and inputs.

The default implementation is a no-op so local development and tests do not
depend on an external moderation provider. Deployments can replace it through
FastAPI dependency overrides (or by injecting a subclass into
``GenerationService``) without changing the generation flow.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel


class ModerationDecision(BaseModel):
    """Outcome of a moderation check."""

    allowed: bool = True
    code: str | None = None
    reason: str | None = None


class ModerationService:
    """No-op moderation service; always allows content."""

    async def check(
        self,
        prompt: str | None,
        inputs: Sequence[UUID] = (),
    ) -> ModerationDecision:
        """Return an allow decision for any prompt and input set."""
        return ModerationDecision(allowed=True)


class ModerationRejected(Exception):
    """Raised by provider-backed implementations to reject content."""

    def __init__(self, reason: str, code: str = "CONTENT_REJECTED") -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class StaticModerationService(ModerationService):
    """Test/development helper that rejects prompts containing blocked terms."""

    def __init__(self, blocked_terms: Sequence[str] = ()) -> None:
        self.blocked_terms = tuple(term.lower() for term in blocked_terms)

    async def check(
        self,
        prompt: str | None,
        inputs: Sequence[UUID] = (),
    ) -> ModerationDecision:
        text = (prompt or "").lower()
        for term in self.blocked_terms:
            if term and term in text:
                return ModerationDecision(
                    allowed=False,
                    code="CONTENT_REJECTED",
                    reason="Prompt contains disallowed content",
                )
        return ModerationDecision(allowed=True, reason=None, code=None)
