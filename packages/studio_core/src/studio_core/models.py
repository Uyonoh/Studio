"""Domain models and enums mirroring the PostgreSQL database schema."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class TaskType(StrEnum):
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_IMAGE = "image_to_image"
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"


class AssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class AssetOrigin(StrEnum):
    UPLOAD = "upload"
    GENERATED = "generated"
    DERIVED = "derived"


class JobStatus(StrEnum):
    QUEUED = "queued"
    SUBMITTING = "submitting"
    RUNNING = "running"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class InputRole(StrEnum):
    INIT_IMAGE = "init_image"
    REFERENCE_IMAGE = "reference_image"
    FIRST_FRAME = "first_frame"
    LAST_FRAME = "last_frame"
    MASK = "mask"
    AUDIO = "audio"
    VIDEO = "video"


class BaseDomainModel(BaseModel):
    """Base domain model enabling attribute access from ORM/asyncpg records."""

    model_config = ConfigDict(from_attributes=True)


class Profile(BaseDomainModel):
    id: UUID
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class Workspace(BaseDomainModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime


class WorkspaceMember(BaseDomainModel):
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    created_at: datetime


class Project(BaseDomainModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    cover_asset_id: UUID | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class Provider(BaseDomainModel):
    id: str
    name: str
    enabled: bool = True


class Model(BaseDomainModel):
    id: UUID
    provider_id: str
    provider_model: str
    slug: str
    display_name: str
    task_type: TaskType
    input_schema: dict[str, Any]
    default_params: dict[str, Any] = Field(default_factory=dict)
    cost_credits: Decimal = Decimal("1.00")
    enabled: bool = True


class Asset(BaseDomainModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    kind: AssetKind
    origin: AssetOrigin
    storage_bucket: str = "media"
    storage_path: str
    thumbnail_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    fps: Decimal | None = None
    source_job_id: UUID | None = None
    parent_asset_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: UUID | None = None
    created_at: datetime
    deleted_at: datetime | None = None


class GenerationJob(BaseDomainModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    created_by: UUID
    model_id: UUID
    task_type: TaskType
    status: JobStatus = JobStatus.QUEUED
    prompt: str | None = None
    negative_prompt: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    provider_job_id: str | None = None
    attempt: int = 0
    max_attempts: int = 3
    error_code: str | None = None
    error_message: str | None = None
    cost_credits: Decimal = Decimal("0.00")
    parent_job_id: UUID | None = None
    workflow_run_id: UUID | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    heartbeat_at: datetime | None = None


class JobInput(BaseDomainModel):
    job_id: UUID
    asset_id: UUID
    role: InputRole
    position: int = 0


class JobEvent(BaseDomainModel):
    id: int
    job_id: UUID
    type: str
    from_status: JobStatus | None = None
    to_status: JobStatus | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class CreditLedger(BaseDomainModel):
    id: int
    workspace_id: UUID
    job_id: UUID | None = None
    delta: Decimal
    reason: str
    created_at: datetime


class CreditTransaction(CreditLedger):
    """A ledger entry enriched with the running balance and job context."""

    balance_after: Decimal
    model_name: str | None = None
    job_status: str | None = None
    prompt: str | None = None
