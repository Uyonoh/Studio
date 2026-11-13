import type { ModelInputCapability, StudioModel } from "@/hooks/use-models";

/**
 * Per-task defaults used when the API does not advertise capabilities.
 * Keeping these in sync with studio_core.capabilities means older responses
 * and test fixtures continue to work.
 */
const DEFAULT_CAPABILITIES: Record<string, ModelInputCapability[]> = {
  text_to_image: [],
  image_to_image: [
    {
      role: "init_image",
      kind: "image",
      required: true,
      max_count: 1,
      label: "Source image",
    },
  ],
  text_to_video: [],
  image_to_video: [
    {
      role: "first_frame",
      kind: "image",
      required: true,
      max_count: 1,
      label: "First frame",
    },
  ],
};

/** Return the media slots a model accepts, with API-provided data preferred. */
export function getInputCapabilities(model: StudioModel | null | undefined): ModelInputCapability[] {
  if (!model) return [];
  // An explicit list always wins, including an empty one (model takes no media).
  if (model.input_capabilities) return model.input_capabilities;
  return DEFAULT_CAPABILITIES[model.task_type] ?? [];
}

/** Media capabilities of a particular kind, in display order. */
export function capabilitiesOfKind(
  model: StudioModel | null | undefined,
  kind: string
): ModelInputCapability[] {
  return getInputCapabilities(model).filter((capability) => capability.kind === kind);
}
