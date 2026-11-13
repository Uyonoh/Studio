"""Models router — GET /v1/models?task_type=

Returns enabled models with their JSON Schemas, defaults, and cost.
Response is Cache-Control: max-age=60 to reduce DB load.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel

from api.auth import AuthUser
from api.deps import DBConn
from studio_core.capabilities import get_input_capabilities
from studio_core.models import TaskType
from studio_core.repositories import ModelRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])


class InputCapabilityResponse(BaseModel):
    """A media slot the model accepts, with its limits."""

    role: str
    kind: str
    required: bool
    max_count: int
    label: str


class ModelResponse(BaseModel):
    """Model descriptor returned to clients."""

    id: UUID
    slug: str
    display_name: str
    task_type: str
    provider_id: str
    input_schema: dict[str, Any]
    default_params: dict[str, Any]
    cost_credits: str  # serialized as string for precision
    # Kept for backwards compatibility; prefer input_capabilities.
    required_input_roles: list[str]
    input_capabilities: list[InputCapabilityResponse]


@router.get("/models", response_model=list[ModelResponse])
async def list_models(
    user: AuthUser,
    db: DBConn,
    response: Response,
    task_type: str | None = None,
) -> list[ModelResponse]:
    """Return all enabled models, optionally filtered by task_type.

    Response is cached for 60 seconds via Cache-Control.
    """
    response.headers["Cache-Control"] = "max-age=60, private"

    parsed_task: TaskType | None = None
    if task_type is not None:
        try:
            parsed_task = TaskType(task_type)
        except ValueError as exc:
            valid = ", ".join(t.value for t in TaskType)
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Invalid task_type '{task_type}'. Valid values: {valid}",
            ) from exc

    repo = ModelRepository(db)
    models = await repo.list_models(task_type=parsed_task, only_enabled=True)

    responses: list[ModelResponse] = []
    for model in models:
        capabilities = get_input_capabilities(model)
        responses.append(
            ModelResponse(
                id=model.id,
                slug=model.slug,
                display_name=model.display_name,
                task_type=model.task_type.value,
                provider_id=model.provider_id,
                input_schema=model.input_schema,
                default_params=model.default_params,
                cost_credits=str(model.cost_credits),
                required_input_roles=[
                    capability.role.value for capability in capabilities if capability.required
                ],
                input_capabilities=[
                    InputCapabilityResponse(
                        role=capability.role.value,
                        kind=capability.kind.value,
                        required=capability.required,
                        max_count=capability.max_count,
                        label=capability.label,
                    )
                    for capability in capabilities
                ],
            )
        )
    return responses
