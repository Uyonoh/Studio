"""Worker configuration and settings."""

from __future__ import annotations

from arq.connections import RedisSettings
from pydantic import Field

from studio_core.settings import Settings


class WorkerConfig(Settings):
    """Worker-specific configuration extending studio core Settings."""

    worker_max_jobs: int = Field(default=10, validation_alias="WORKER_MAX_JOBS")
    worker_job_timeout: int = Field(default=1800, validation_alias="WORKER_JOB_TIMEOUT")  # 30 mins
    provider_concurrency_fake: int = Field(default=10, validation_alias="PROVIDER_CONCURRENCY_FAKE")
    provider_concurrency_replicate: int = Field(
        default=5, validation_alias="PROVIDER_CONCURRENCY_REPLICATE"
    )
    provider_concurrency_fal: int = Field(default=5, validation_alias="PROVIDER_CONCURRENCY_FAL")

    # Timeouts for reconciler
    max_runtime_image_seconds: int = Field(
        default=600, validation_alias="MAX_RUNTIME_IMAGE_SECONDS"
    )  # 10 mins
    max_runtime_video_seconds: int = Field(
        default=1800, validation_alias="MAX_RUNTIME_VIDEO_SECONDS"
    )  # 30 mins
    reconcile_cron_interval_seconds: int = Field(
        default=60, validation_alias="RECONCILE_CRON_INTERVAL_SECONDS"
    )

    def get_redis_settings(self) -> RedisSettings:
        url = self.redis_url or "redis://127.0.0.1:6379/0"
        return RedisSettings.from_dsn(url)


_worker_config: WorkerConfig | None = None


def get_worker_config() -> WorkerConfig:
    global _worker_config
    if _worker_config is None:
        _worker_config = WorkerConfig()
    return _worker_config
