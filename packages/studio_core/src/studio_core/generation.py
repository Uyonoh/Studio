"""Generation submission service: validation, limits, deduplication, and atomic job creation."""

from typing import Any
from uuid import UUID

import asyncpg
import jsonschema
from pydantic import BaseModel, Field

from studio_core.credits import CreditService, InsufficientCredits
from studio_core.models import (
    AssetKind,
    GenerationJob,
    InputRole,
    TaskType,
    WorkspaceRole,
)
from studio_core.moderation import ModerationService
from studio_core.repositories import (
    AssetRepository,
    JobRepository,
    ModelRepository,
    ProjectRepository,
)
from studio_core.settings import get_settings


class GenerationServiceError(Exception):
    """Base error for generation service failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ModelTaskMismatchError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("MODEL_TASK_MISMATCH", message)


class InvalidParamsError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_PARAMS", message)


class MissingInputError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("MISSING_INPUT", message)


class InsufficientCreditsError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("INSUFFICIENT_CREDITS", message)


class ConcurrencyLimitError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("CONCURRENCY_LIMIT", message)


class IdempotencyConflictError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("IDEMPOTENCY_CONFLICT", message)


class PermissionDeniedError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("PERMISSION_DENIED", message)


class PromptTooLongError(GenerationServiceError):
    def __init__(self, limit: int, field: str = "Prompt") -> None:
        super().__init__(
            "PROMPT_TOO_LONG",
            f"{field} exceeds the maximum length of {limit} characters",
        )


class ContentRejectedError(GenerationServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("CONTENT_REJECTED", message)


class InputItem(BaseModel):
    asset_id: UUID
    role: InputRole


class GenerationSubmitRequest(BaseModel):
    model: str  # slug or UUID string
    task_type: TaskType
    prompt: str | None = None
    negative_prompt: str | None = None
    inputs: list[InputItem] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class GenerationService:
    """Orchestrates job validation, credit reservation, and creation."""

    def __init__(
        self,
        conn: asyncpg.Connection,
        moderation_service: ModerationService | None = None,
    ) -> None:
        self.conn = conn
        self.project_repo = ProjectRepository(conn)
        self.model_repo = ModelRepository(conn)
        self.asset_repo = AssetRepository(conn)
        self.job_repo = JobRepository(conn)
        self.credit_service = CreditService(conn)
        self.moderation_service = moderation_service or ModerationService()

    async def create_job(
        self,
        user_id: UUID,
        project_id: UUID,
        request: GenerationSubmitRequest,
        idempotency_key: str,
        parent_job_id: UUID | None = None,
    ) -> GenerationJob:
        """Validate input, reserve credits, and persist job in database."""
        # 1. Load project & check membership (minimum role: editor)
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise GenerationServiceError("PROJECT_NOT_FOUND", f"Project {project_id} not found")

        role = await self.project_repo.get_member_role(project.workspace_id, user_id)
        if not role or role == WorkspaceRole.VIEWER:
            raise PermissionDeniedError("User does not have editor permission in this workspace")

        # 2. Check Idempotency Key
        existing_job = await self.job_repo.get_by_idempotency_key(
            project.workspace_id, idempotency_key
        )
        if existing_job:
            # Check if payload matches
            prompt_match = existing_job.prompt == request.prompt
            task_match = existing_job.task_type == request.task_type
            if prompt_match and task_match:
                return existing_job
            raise IdempotencyConflictError(
                f"Idempotency key '{idempotency_key}' was used with a different request payload"
            )

        # 3. Enforce prompt length limits and moderation before any model load
        #    or credit reservation, so rejected content costs nothing.
        settings = get_settings()
        if request.prompt and len(request.prompt) > settings.max_prompt_chars:
            raise PromptTooLongError(settings.max_prompt_chars, "Prompt")
        if request.negative_prompt and len(request.negative_prompt) > settings.max_prompt_chars:
            raise PromptTooLongError(settings.max_prompt_chars, "Negative prompt")

        decision = await self.moderation_service.check(
            request.prompt,
            [inp.asset_id for inp in request.inputs],
        )
        if not decision.allowed:
            raise ContentRejectedError(
                decision.reason or "Prompt was rejected by the moderation service"
            )

        # 4. Load model & verify task_type
        # Can be slug or UUID
        model = None
        try:
            model_uuid = UUID(request.model)
            model = await self.model_repo.get_by_id(model_uuid)
        except ValueError:
            model = await self.model_repo.get_by_slug(request.model)

        if not model or not model.enabled:
            raise GenerationServiceError(
                "MODEL_NOT_FOUND", f"Model '{request.model}' is disabled or does not exist"
            )

        if model.task_type != request.task_type:
            raise ModelTaskMismatchError(
                f"Model '{model.slug}' supports task '{model.task_type.value}', "
                f"not '{request.task_type.value}'"
            )

        # 5. Validate parameters against model.input_schema & merge default_params
        merged_params = dict(model.default_params)
        merged_params.update(request.params)

        try:
            jsonschema.validate(instance=merged_params, schema=model.input_schema)
        except jsonschema.ValidationError as err:
            raise InvalidParamsError(f"Invalid generation parameters: {err.message}") from err

        # 6. Enforce required inputs per task type
        input_roles_present = {inp.role for inp in request.inputs}
        if request.task_type == TaskType.IMAGE_TO_IMAGE:
            if InputRole.INIT_IMAGE not in input_roles_present:
                raise MissingInputError("Task 'image_to_image' requires an 'init_image' input")
        elif request.task_type == TaskType.IMAGE_TO_VIDEO:
            if InputRole.FIRST_FRAME not in input_roles_present:
                raise MissingInputError("Task 'image_to_video' requires a 'first_frame' input")

        # Verify all input assets exist, are in the same workspace, and match kinds
        asset_ids = [inp.asset_id for inp in request.inputs]
        if asset_ids:
            assets = await self.asset_repo.get_many(asset_ids)
            asset_map = {a.id: a for a in assets}
            if len(asset_map) != len(asset_ids):
                raise MissingInputError("One or more input assets do not exist or were deleted")

            for inp in request.inputs:
                asset = asset_map[inp.asset_id]
                if asset.workspace_id != project.workspace_id:
                    raise PermissionDeniedError("Input asset belongs to a different workspace")
                image_roles = (
                    InputRole.INIT_IMAGE,
                    InputRole.FIRST_FRAME,
                    InputRole.REFERENCE_IMAGE,
                )
                if inp.role in image_roles and asset.kind != AssetKind.IMAGE:
                    err_msg = f"Input role '{inp.role.value}' must be an image asset"
                    raise InvalidParamsError(err_msg)

        # 7. Enforce per-workspace concurrent active jobs cap
        active_jobs = await self.job_repo.count_active_jobs_for_workspace(project.workspace_id)
        if active_jobs >= settings.max_active_jobs_per_workspace:
            cap = settings.max_active_jobs_per_workspace
            raise ConcurrencyLimitError(f"Workspace active generation limit of {cap} reached")

        # 8. Reserve credits & insert job
        cost_credits = model.cost_credits
        job = await self.job_repo.create(
            workspace_id=project.workspace_id,
            project_id=project.id,
            created_by=user_id,
            model_id=model.id,
            task_type=request.task_type,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            params=merged_params,
            cost_credits=cost_credits,
            idempotency_key=idempotency_key,
            parent_job_id=parent_job_id,
        )

        # Insert inputs
        if request.inputs:
            input_records = [
                (inp.asset_id, inp.role.value, idx) for idx, inp in enumerate(request.inputs)
            ]
            await self.job_repo.add_inputs(job.id, input_records)

        # Reserve credits
        try:
            await self.credit_service.reserve(
                workspace_id=project.workspace_id,
                job_id=job.id,
                amount=cost_credits,
            )
        except InsufficientCredits as err:
            raise InsufficientCreditsError(str(err)) from err

        return job
