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
from studio_core.models import TaskType
from studio_core.repositories import ModelRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])

# Required input roles for each task type (drives UI and client validation)
REQUIRED_INPUT_ROLES: dict[str, list[str]] = {
    TaskType.TEXT_TO_IMAGE: [],
    TaskType.IMAGE_TO_IMAGE: ["init_image"],
    TaskType.TEXT_TO_VIDEO: [],
    TaskType.IMAGE_TO_VIDEO: ["first_frame"],
}


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
    required_input_roles: list[str]


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

    return [
        ModelResponse(
            id=m.id,
            slug=m.slug,
            display_name=m.display_name,
            task_type=m.task_type.value,
            provider_id=m.provider_id,
            input_schema=m.input_schema,
            default_params=m.default_params,
            cost_credits=str(m.cost_credits),
            required_input_roles=REQUIRED_INPUT_ROLES.get(m.task_type, []),
        )
        for m in models
    ]
