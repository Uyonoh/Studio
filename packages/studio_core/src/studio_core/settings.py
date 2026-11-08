"""Application settings for Studio Core, loaded from environment variables."""

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Studio settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase / Auth
    supabase_url: str = Field(
        default="http://127.0.0.1:54321",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    supabase_anon_key: str = Field(
        default="anon-key",
        validation_alias=AliasChoices(
            "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY"
        ),
    )
    supabase_service_role_key: str = Field(
        default="service-role-key",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"),
    )
    supabase_jwt_secret: str = Field(
        default="super-secret-jwt-token-with-at-least-32-characters-long",
        validation_alias="SUPABASE_JWT_SECRET",
    )

    # Database & Storage
    database_url: str = Field(
        default="postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", validation_alias="REDIS_URL")
    storage_bucket: str = Field(default="media", validation_alias="STORAGE_BUCKET")

    # API / Webhooks
    public_api_url: str = Field(default="http://127.0.0.1:8000", validation_alias="PUBLIC_API_URL")
    webhook_signing_secret: str = Field(
        default="local_webhook_secret_key_32_bytes_min",
        validation_alias="WEBHOOK_SIGNING_SECRET",
    )

    # Provider Credentials
    replicate_api_token: str | None = Field(default=None, validation_alias="REPLICATE_API_TOKEN")
    replicate_webhook_secret: str | None = Field(
        default=None, validation_alias="REPLICATE_WEBHOOK_SECRET"
    )
    fal_key: str | None = Field(default=None, validation_alias="FAL_KEY")
    gemini_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )

    # Limits & Orchestration
    max_active_jobs_per_workspace: int = Field(
        default=5, validation_alias="MAX_ACTIVE_JOBS_PER_WORKSPACE"
    )
    max_prompt_chars: int = Field(default=4000, validation_alias="MAX_PROMPT_CHARS")
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_submit_per_minute: int = Field(
        default=20, validation_alias="RATE_LIMIT_SUBMIT_PER_MINUTE"
    )
    rate_limit_upload_per_minute: int = Field(
        default=30, validation_alias="RATE_LIMIT_UPLOAD_PER_MINUTE"
    )

    # Runtime & Observability
    environment: Literal["local", "staging", "production"] = Field(
        default="local", validation_alias="ENVIRONMENT"
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    sentry_dsn: str | None = Field(default=None, validation_alias="SENTRY_DSN")
    sentry_release: str | None = Field(default=None, validation_alias="SENTRY_RELEASE")
    sentry_traces_sample_rate: float = Field(
        default=0.1, validation_alias="SENTRY_TRACES_SAMPLE_RATE"
    )
    admin_user_ids: str = Field(default="", validation_alias="ADMIN_USER_IDS")


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the cached or initialized Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
