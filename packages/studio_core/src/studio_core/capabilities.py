"""Per-model media input capabilities.

The composer needs to know which media slots a model accepts and how many
files each slot allows. This module is the single source of truth used by the
models endpoint (to advertise capabilities to the browser) and by
:class:`studio_core.generation.GenerationService` (to enforce them).

Capabilities fall back to sensible per-task defaults, so catalog models keep
working without any extra data. Only models with unusual inputs (multiple
source images, first/last frames) need an explicit override below.
"""

from pydantic import BaseModel

from studio_core.models import AssetKind, InputRole, Model, TaskType


class InputCapability(BaseModel):
    """One media slot accepted by a model."""

    role: InputRole
    kind: AssetKind = AssetKind.IMAGE
    required: bool = False
    max_count: int = 1
    label: str


# Safe defaults for every task type. These preserve the original behaviour:
# image-to-image needs one init image and image-to-video needs one first frame.
DEFAULT_CAPABILITIES: dict[TaskType, tuple[InputCapability, ...]] = {
    TaskType.TEXT_TO_IMAGE: (),
    TaskType.IMAGE_TO_IMAGE: (
        InputCapability(
            role=InputRole.INIT_IMAGE,
            required=True,
            max_count=1,
            label="Source image",
        ),
    ),
    TaskType.TEXT_TO_VIDEO: (),
    TaskType.IMAGE_TO_VIDEO: (
        InputCapability(
            role=InputRole.FIRST_FRAME,
            required=True,
            max_count=1,
            label="First frame",
        ),
    ),
}


# Models whose provider accepts more than the task default.
# Keyed by the catalog's stable model slug.
MODEL_CAPABILITY_OVERRIDES: dict[str, tuple[InputCapability, ...]] = {
    # Replicate passes image inputs as a list for these models.
    "replicate-flux-2-pro-edit": (
        InputCapability(
            role=InputRole.INIT_IMAGE,
            required=True,
            max_count=4,
            label="Source images",
        ),
    ),
    "replicate-nano-banana-edit": (
        InputCapability(
            role=InputRole.INIT_IMAGE,
            required=True,
            max_count=4,
            label="Source images",
        ),
    ),
    # Kling image-to-video models accept a tail/last-frame image.
    "fal-kling-i2v": (
        InputCapability(
            role=InputRole.FIRST_FRAME,
            required=True,
            max_count=1,
            label="First frame",
        ),
        InputCapability(
            role=InputRole.LAST_FRAME,
            required=False,
            max_count=1,
            label="Last frame",
        ),
    ),
    "fal-kling-2-5-turbo-i2v": (
        InputCapability(
            role=InputRole.FIRST_FRAME,
            required=True,
            max_count=1,
            label="First frame",
        ),
        InputCapability(
            role=InputRole.LAST_FRAME,
            required=False,
            max_count=1,
            label="Last frame",
        ),
    ),
}


def get_input_capabilities(model: Model) -> list[InputCapability]:
    """Return the media slots accepted by ``model``.

    A model-specific override wins; otherwise the task default applies. The
    returned objects are copies so callers cannot mutate the registry.
    """
    capabilities = MODEL_CAPABILITY_OVERRIDES.get(
        model.slug,
        DEFAULT_CAPABILITIES.get(model.task_type, ()),
    )
    return [capability.model_copy() for capability in capabilities]
