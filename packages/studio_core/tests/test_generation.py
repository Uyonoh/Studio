"""Tests for generation service: validations, task matching, credit reservation, idempotency."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from studio_core.generation import (
    ConcurrencyLimitError,
    GenerationService,
    GenerationSubmitRequest,
    IdempotencyConflictError,
    InputItem,
    InvalidParamsError,
    MissingInputError,
    ModelTaskMismatchError,
    PermissionDeniedError,
)
from studio_core.models import (
    Asset,
    AssetKind,
    AssetOrigin,
    InputRole,
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


def _image_asset(project: Project) -> Asset:
    return Asset(
        id=uuid4(),
        workspace_id=project.workspace_id,
        project_id=project.id,
        kind=AssetKind.IMAGE,
        origin=AssetOrigin.UPLOAD,
        storage_path=f"uploads/{uuid4()}.png",
        created_at=datetime.now(UTC),
    )


def _configure_service(
    service: GenerationService,
    project: Project,
    model: Model,
    assets: list[Asset],
) -> MagicMock:
    job = MagicMock()
    job.id = uuid4()
    service.project_repo.get_by_id = AsyncMock(return_value=project)  # type: ignore[method-assign]
    service.project_repo.get_member_role = AsyncMock(return_value=WorkspaceRole.EDITOR)  # type: ignore[method-assign]
    service.job_repo.get_by_idempotency_key = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.model_repo.get_by_slug = AsyncMock(return_value=model)  # type: ignore[method-assign]
    service.asset_repo.get_many = AsyncMock(return_value=assets)  # type: ignore[method-assign]
    service.job_repo.count_active_jobs_for_workspace = AsyncMock(return_value=0)  # type: ignore[method-assign]
    service.job_repo.create = AsyncMock(return_value=job)  # type: ignore[method-assign]
    service.job_repo.add_inputs = AsyncMock()  # type: ignore[method-assign]
    service.credit_service.reserve = AsyncMock()  # type: ignore[method-assign]
    return job


def _model(slug: str, task_type: TaskType) -> Model:
    return Model(
        id=uuid4(),
        provider_id="fake",
        provider_model=slug,
        slug=slug,
        display_name=slug,
        task_type=task_type,
        input_schema={"type": "object"},
        default_params={},
        cost_credits=Decimal("1.00"),
        enabled=True,
    )


@pytest.mark.asyncio
async def test_multi_image_capability_accepts_several_inputs(
    mock_conn: AsyncMock, test_project: Project
) -> None:
    model = _model("replicate-flux-2-pro-edit", TaskType.IMAGE_TO_IMAGE)
    assets = [_image_asset(test_project), _image_asset(test_project)]
    service = GenerationService(mock_conn)
    job = _configure_service(service, test_project, model, assets)

    req = GenerationSubmitRequest(
        model=model.slug,
        task_type=TaskType.IMAGE_TO_IMAGE,
        inputs=[
            InputItem(asset_id=assets[0].id, role=InputRole.INIT_IMAGE),
            InputItem(asset_id=assets[1].id, role=InputRole.INIT_IMAGE),
        ],
    )
    result = await service.create_job(uuid4(), test_project.id, req, "idem-multi")

    assert result is job
    service.job_repo.add_inputs.assert_awaited_once()  # type: ignore[attr-defined]
    records = service.job_repo.add_inputs.await_args.args[1]  # type: ignore[attr-defined]
    assert records == [
        (assets[0].id, "init_image", 0),
        (assets[1].id, "init_image", 1),
    ]


@pytest.mark.asyncio
async def test_multi_image_capability_rejects_too_many_inputs(
    mock_conn: AsyncMock, test_project: Project
) -> None:
    model = _model("replicate-codeformer", TaskType.IMAGE_TO_IMAGE)
    assets = [_image_asset(test_project), _image_asset(test_project)]
    service = GenerationService(mock_conn)
    _configure_service(service, test_project, model, assets)

    req = GenerationSubmitRequest(
        model=model.slug,
        task_type=TaskType.IMAGE_TO_IMAGE,
        inputs=[
            InputItem(asset_id=assets[0].id, role=InputRole.INIT_IMAGE),
            InputItem(asset_id=assets[1].id, role=InputRole.INIT_IMAGE),
        ],
    )
    with pytest.raises(InvalidParamsError, match="at most 1"):
        await service.create_job(uuid4(), test_project.id, req, "idem-too-many")


@pytest.mark.asyncio
async def test_first_last_frame_capability_accepts_both_frames(
    mock_conn: AsyncMock, test_project: Project
) -> None:
    model = _model("fal-kling-i2v", TaskType.IMAGE_TO_VIDEO)
    assets = [_image_asset(test_project), _image_asset(test_project)]
    service = GenerationService(mock_conn)
    _configure_service(service, test_project, model, assets)

    req = GenerationSubmitRequest(
        model=model.slug,
        task_type=TaskType.IMAGE_TO_VIDEO,
        inputs=[
            InputItem(asset_id=assets[0].id, role=InputRole.FIRST_FRAME),
            InputItem(asset_id=assets[1].id, role=InputRole.LAST_FRAME),
        ],
    )
    await service.create_job(uuid4(), test_project.id, req, "idem-frames")

    records = service.job_repo.add_inputs.await_args.args[1]  # type: ignore[attr-defined]
    assert records == [
        (assets[0].id, "first_frame", 0),
        (assets[1].id, "last_frame", 1),
    ]


@pytest.mark.asyncio
async def test_last_frame_rejected_when_model_does_not_support_it(
    mock_conn: AsyncMock, test_project: Project
) -> None:
    model = _model("fake-image-to-video", TaskType.IMAGE_TO_VIDEO)
    assets = [_image_asset(test_project), _image_asset(test_project)]
    service = GenerationService(mock_conn)
    _configure_service(service, test_project, model, assets)

    req = GenerationSubmitRequest(
        model=model.slug,
        task_type=TaskType.IMAGE_TO_VIDEO,
        inputs=[
            InputItem(asset_id=assets[0].id, role=InputRole.FIRST_FRAME),
            InputItem(asset_id=assets[1].id, role=InputRole.LAST_FRAME),
        ],
    )
    with pytest.raises(InvalidParamsError, match="last_frame"):
        await service.create_job(uuid4(), test_project.id, req, "idem-no-last")


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
