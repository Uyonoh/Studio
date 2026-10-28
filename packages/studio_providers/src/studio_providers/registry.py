"""Registry mapping provider identifiers to GenerationProvider adapter instances."""

import logging

from studio_core.settings import Settings, get_settings
from studio_providers.base import GenerationProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry holding initialized provider instances."""

    def __init__(self) -> None:
        self._providers: dict[str, GenerationProvider] = {}

    def register(self, provider: GenerationProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.id] = provider

    def get(self, provider_id: str) -> GenerationProvider:
        """Look up provider by ID."""
        if provider_id not in self._providers:
            raise KeyError(f"Provider '{provider_id}' is not registered or enabled")
        return self._providers[provider_id]

    def has(self, provider_id: str) -> bool:
        return provider_id in self._providers


_registry: ProviderRegistry | None = None


def get_provider_registry(settings: Settings | None = None) -> ProviderRegistry:
    """Get or initialize the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        s = settings or get_settings()

        # Always register FakeProvider in non-production environments
        if s.environment != "production":
            from studio_providers.fake import FakeProvider

            _registry.register(FakeProvider())
            logger.info("Registered FakeProvider (environment=%s)", s.environment)

        # Register ReplicateProvider if credentials are configured
        if s.replicate_api_token:
            from studio_providers.replicate import ReplicateProvider

            _registry.register(
                ReplicateProvider(
                    api_token=s.replicate_api_token,
                    webhook_secret=s.replicate_webhook_secret,
                )
            )
            logger.info("Registered ReplicateProvider")

        # Register FalProvider if credentials are configured
        if s.fal_key:
            from studio_providers.fal import FalProvider

            _registry.register(FalProvider(api_key=s.fal_key))
            logger.info("Registered FalProvider")

    return _registry


def get_provider(provider_id: str) -> GenerationProvider:
    """Helper to fetch a provider from the global registry."""
    return get_provider_registry().get(provider_id)
