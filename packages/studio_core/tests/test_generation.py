"""Tests for generation service: validations, task matching, credit reservation, idempotency."""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from studio_core.generation import (
    ConcurrencyLimitError,
    GenerationService,
    GenerationSubmitRequest,
    IdempotencyConflictError,
    InvalidParamsError,
    MissingInputError,
    ModelTaskMismatchError,
    PermissionDeniedError,
)
from studio_core.models import (
    Model,
    Project,
    TaskType,
    WorkspaceRole,
)


@pytest.fixture
def mock_conn() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def test_project() -> Project:
    now_dt = pytest.importorskip("datetime").datetime.now(
        pytest.importorskip("datetime").timezone.utc
    )
    return Project(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Test Project",
        created_by=uuid4(),
        created_at=now_dt,
        updated_at=now_dt,
    )


@pytest.fixture
def text_to_image_model() -> Model:
    return Model(
        id=uuid4(),
        provider_id="fake",
        provider_model="mock-txt2img",
        slug="txt-fast",
        display_name="Fast Image",
        task_type=TaskType.TEXT_TO_IMAGE,
        input_schema={
            "type": "object",
            "properties": {
                "aspect_ratio": {"type": "string", "enum": ["1:1", "16:9", "9:16"]},
                "seed": {"type": "integer"},
            },
            "required": ["aspect_ratio"],
        },
        default_params={"aspect_ratio": "1:1"},
        cost_credits=Decimal("1.00"),
        enabled=True,
    )


@pytest.mark.asyncio
async def test_permission_denied_for_viewer(mock_conn: AsyncMock, test_project: Project) -> None:
    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.VIEWER)  # type: ignore[method-assign]

    req = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A cute cat",
    )
    with pytest.raises(PermissionDeniedError):
        await service.create_job(uuid4(), test_project.id, req, "idem-1")


@pytest.mark.asyncio
async def test_model_task_mismatch(
    mock_conn: AsyncMock, test_project: Project, text_to_image_model: Model
) -> None:
    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.model_repo.get_by_slug = AsyncMock(return_value=text_to_image_model)  # type: ignore[method-assign]

    req = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.IMAGE_TO_VIDEO,  # mismatch!
        prompt="A cute cat walking",
    )
    with pytest.raises(ModelTaskMismatchError):
        await service.create_job(uuid4(), test_project.id, req, "idem-1")


@pytest.mark.asyncio
async def test_invalid_parameters_schema(
    mock_conn: AsyncMock, test_project: Project, text_to_image_model: Model
) -> None:
    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.model_repo.get_by_slug = AsyncMock(return_value=text_to_image_model)  # type: ignore[method-assign]

    req = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A cute cat",
        params={"aspect_ratio": "invalid-ratio"},  # not in enum!
    )
    with pytest.raises(InvalidParamsError):
        await service.create_job(uuid4(), test_project.id, req, "idem-1")


@pytest.mark.asyncio
async def test_missing_required_input_role(mock_conn: AsyncMock, test_project: Project) -> None:
    img2vid_model = Model(
        id=uuid4(),
        provider_id="fake",
        provider_model="mock-img2vid",
        slug="vid-fast",
        display_name="Fast Video",
        task_type=TaskType.IMAGE_TO_VIDEO,
        input_schema={"type": "object"},
        default_params={},
        cost_credits=Decimal("2.00"),
        enabled=True,
    )
    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.model_repo.get_by_slug = AsyncMock(return_value=img2vid_model)  # type: ignore[method-assign]

    # image_to_video requires first_frame, but inputs is empty
    req = GenerationSubmitRequest(
        model="vid-fast",
        task_type=TaskType.IMAGE_TO_VIDEO,
        prompt="Animate",
        inputs=[],
    )
    with pytest.raises(MissingInputError, match="first_frame"):
        await service.create_job(uuid4(), test_project.id, req, "idem-1")


@pytest.mark.asyncio
async def test_concurrency_limit_exceeded(
    mock_conn: AsyncMock, test_project: Project, text_to_image_model: Model
) -> None:
    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.model_repo.get_by_slug = AsyncMock(return_value=text_to_image_model)  # type: ignore[method-assign]
    service.job_repo.count_active_jobs_for_workspace = AsyncMock(return_value=10)  # type: ignore[method-assign]

    req = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A cute cat",
    )
    with pytest.raises(ConcurrencyLimitError):
        await service.create_job(uuid4(), test_project.id, req, "idem-1")


@pytest.mark.asyncio
async def test_idempotency_key_replay_same_and_different(
    mock_conn: AsyncMock, test_project: Project
) -> None:
    now_dt = pytest.importorskip("datetime").datetime.now(
        pytest.importorskip("datetime").timezone.utc
    )
    existing_job = pytest.importorskip("studio_core.models").GenerationJob(
        id=uuid4(),
        workspace_id=test_project.workspace_id,
        project_id=test_project.id,
        created_by=uuid4(),
        model_id=uuid4(),
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A cute cat",
        queued_at=now_dt,
    )

    service = GenerationService(mock_conn)
    service.project_repo.get_by_id = AsyncMock(return_value=test_project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=existing_job)  # type: ignore[method-assign]

    # Replay with same prompt and task -> returns existing job
    req_same = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A cute cat",
    )
    job = await service.create_job(uuid4(), test_project.id, req_same, "idem-1")
    assert job.id == existing_job.id

    # Replay with different payload -> raises conflict
    req_diff = GenerationSubmitRequest(
        model="txt-fast",
        task_type=TaskType.TEXT_TO_IMAGE,
        prompt="A different prompt",
    )
    with pytest.raises(IdempotencyConflictError):
        await service.create_job(uuid4(), test_project.id, req_diff, "idem-1")
