"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Coins,
  Image as ImageIcon,
  Loader2,
  Sparkles,
  Type,
  Video,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { ComposerImagePicker } from "./composer-image-picker";
import { ModelPicker } from "./model-picker";
import { SchemaParamsForm } from "./schema-params-form";
import {
  useModels,
  type ModelInputCapability,
  type StudioModel,
  type TaskType,
} from "@/hooks/use-models";
import {
  GenerationSubmitError,
  newIdempotencyKey,
  useSubmitGeneration,
  type GenerationJob,
  type SubmitGenerationPayload,
} from "@/hooks/use-generations";
import type { Asset } from "@/hooks/use-assets";
import { capabilitiesOfKind, getInputCapabilities } from "@/lib/model-inputs";
import {
  defaultParamValues,
  normalizeParamValues,
  validateParamValues,
  type ParamValue,
  type ParamValues,
} from "@/lib/generation-params";

export type ComposerMode = "image" | "video";

/** Map the composer's mode + input choice onto an API task type. */
export function deriveTaskType(mode: ComposerMode, withImage: boolean): TaskType {
  if (mode === "image") {
    return withImage ? "image_to_image" : "text_to_image";
  }
  return withImage ? "image_to_video" : "text_to_video";
}

interface GenerationComposerProps {
  projectId: string;
  /** Pre-selected source image, e.g. from a generated result's "Use as input". */
  initialAsset?: Asset | null;
  /** Called after a job is accepted so job history can update immediately. */
  onSubmitted?: (job: GenerationJob) => void;
}

const sectionClasses = "rounded-2xl border border-[#262A35] bg-[#14161C] p-5 space-y-4";

const segmentButton = (active: boolean) =>
  `flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
    active ? "bg-[#6C4CE8] text-white" : "text-[#9AA1B2] hover:text-[#E8EAF0]"
  }`;

/** Schema-driven composer for every text/image → image/video flow. */
export function GenerationComposer({
  projectId,
  initialAsset = null,
  onSubmitted,
}: GenerationComposerProps) {
  const [mode, setMode] = useState<ComposerMode>("image");
  const [withImage, setWithImage] = useState(Boolean(initialAsset));
  const [prompt, setPrompt] = useState("");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [params, setParams] = useState<ParamValues>({});
  const [inputsByRole, setInputsByRole] = useState<Record<string, Asset[]>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [imageError, setImageError] = useState<string | undefined>();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastJob, setLastJob] = useState<GenerationJob | null>(null);

  const inFlight = useRef(false);
  const idempotency = useRef<{ key: string; signature: string } | null>(null);
  const lastModelSlug = useRef<string | null>(null);

  const taskType = deriveTaskType(mode, withImage);
  const { data: models = [], isLoading: modelsLoading, isError: modelsError } = useModels(taskType);
  const selectedModel: StudioModel | null =
    models.find((model) => model.slug === selectedSlug) ?? models[0] ?? null;
  const imageCapabilities = capabilitiesOfKind(selectedModel, "image");

  const mutation = useSubmitGeneration(projectId);

  // Keep a valid selection when the task type (and therefore model list) changes.
  useEffect(() => {
    if (models.length === 0) return;
    if (!selectedSlug || !models.some((model) => model.slug === selectedSlug)) {
      setSelectedSlug(models[0].slug);
    }
  }, [models, selectedSlug]);

  // Reset parameters to the model defaults whenever a different model is picked.
  useEffect(() => {
    if (!selectedModel) return;
    if (lastModelSlug.current === selectedModel.slug) return;
    lastModelSlug.current = selectedModel.slug;
    setParams(
      defaultParamValues(selectedModel.input_schema, selectedModel.default_params) as ParamValues
    );
    setFieldErrors({});
  }, [selectedModel]);

  // Seed a caller-provided asset (e.g. "Use as input") into the first image slot.
  useEffect(() => {
    if (!initialAsset || !selectedModel) return;
    const capabilities = capabilitiesOfKind(selectedModel, "image");
    const target = capabilities.find((capability) => capability.required) ?? capabilities[0];
    if (!target) return;

    setInputsByRole((previous) => {
      const current = previous[target.role] ?? [];
      if (current.some((asset) => asset.id === initialAsset.id)) return previous;
      return {
        ...previous,
        [target.role]: [...current, initialAsset].slice(0, target.max_count),
      };
    });
  }, [initialAsset, selectedModel]);

  // Drop selections that the newly selected model cannot accept.
  useEffect(() => {
    if (!selectedModel) return;
    const capabilities = capabilitiesOfKind(selectedModel, "image");

    setInputsByRole((previous) => {
      const next: Record<string, Asset[]> = {};
      let changed = false;
      for (const capability of capabilities) {
        const current = previous[capability.role] ?? [];
        const trimmed = current.slice(0, capability.max_count);
        if (trimmed.length > 0) next[capability.role] = trimmed;
        if (trimmed.length !== current.length) changed = true;
      }
      const removedRole = Object.keys(previous).some((role) => !(role in next));
      if (removedRole) changed = true;
      return changed ? next : previous;
    });
  }, [selectedModel]);

  useEffect(() => {
    if (!withImage) setImageError(undefined);
  }, [withImage]);

  function buildPayload(model: StudioModel): SubmitGenerationPayload {
    const inputs: SubmitGenerationPayload["inputs"] = [];

    if (withImage) {
      for (const capability of capabilitiesOfKind(model, "image")) {
        for (const asset of inputsByRole[capability.role] ?? []) {
          inputs.push({ asset_id: asset.id, role: capability.role });
        }
      }
    }

    return {
      model: model.slug,
      task_type: taskType,
      prompt: prompt.trim() ? prompt.trim() : null,
      inputs,
      params: normalizeParamValues(model.input_schema, params),
    };
  }

  function applySubmitError(error: unknown, model: StudioModel) {
    if (error instanceof GenerationSubmitError) {
      if (error.code === "MISSING_INPUT") {
        setImageError(error.message);
        return;
      }
      if (error.status === 402) {
        setSubmitError(
          "Not enough credits for this generation. Top up your workspace or wait for an active job to be refunded."
        );
        return;
      }
      if (error.status === 429) {
        setSubmitError(
          error.retryAfterSeconds
            ? `Too many active generations. Retry in ${error.retryAfterSeconds}s.`
            : "Too many active generations. Try again shortly."
        );
        return;
      }

      // FastAPI validation errors carry a list of {loc, msg}; surface them inline.
      const detail = error.problem.detail;
      if (Array.isArray(detail)) {
        const mapped: Record<string, string> = {};
        let unmapped = false;

        for (const issue of detail as Array<{ loc?: Array<string | number>; msg?: string }>) {
          const field = issue.loc?.[issue.loc.length - 1];
          if (typeof field === "string" && model.input_schema.properties?.[field]) {
            mapped[field] = issue.msg ?? "Invalid value";
          } else {
            unmapped = true;
          }
        }

        if (Object.keys(mapped).length > 0) {
          setFieldErrors((previous) => ({ ...previous, ...mapped }));
          if (!unmapped) return;
        }
      }

      setSubmitError(error.message);
      return;
    }

    setSubmitError(error instanceof Error ? error.message : "Failed to submit generation");
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || mutation.isPending || !selectedModel) return;

    const errors = validateParamValues(selectedModel.input_schema, params);
    const hasImageSlots = imageCapabilities.length > 0;
    const missingCapability = withImage
      ? imageCapabilities.find(
          (capability) =>
            capability.required && (inputsByRole[capability.role]?.length ?? 0) === 0
        )
      : undefined;
    const noImageSupport = withImage && !hasImageSlots;
    const inputError = noImageSupport
      ? "This model does not accept image inputs."
      : missingCapability
        ? `Choose a ${missingCapability.label.toLowerCase()} for this flow.`
        : undefined;

    setFieldErrors(errors);
    setImageError(inputError);
    setSubmitError(null);

    if (Object.keys(errors).length > 0 || inputError) return;

    const payload = buildPayload(selectedModel);
    const signature = JSON.stringify(payload);

    // Reuse the key while the payload is unchanged so a retry is deduplicated.
    if (!idempotency.current || idempotency.current.signature !== signature) {
      idempotency.current = { key: newIdempotencyKey(), signature };
    }

    inFlight.current = true;
    try {
      const job = await mutation.mutateAsync({
        payload,
        idempotencyKey: idempotency.current.key,
      });
      idempotency.current = null;
      setLastJob(job);
      toast.success("Generation queued");
      onSubmitted?.(job);
    } catch (error) {
      applySubmitError(error, selectedModel);
    } finally {
      inFlight.current = false;
    }
  }

  const credits = selectedModel?.cost_credits ?? "—";

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]"
    >
      <div className="space-y-6">
        {/* Output type */}
        <section className={sectionClasses} aria-labelledby="composer-output-heading">
          <div>
            <h2 id="composer-output-heading" className="text-sm font-semibold text-[#E8EAF0]">
              Output
            </h2>
            <p className="text-xs text-[#9AA1B2] mt-0.5">Choose what you want to generate.</p>
          </div>
          <div
            role="group"
            aria-label="Output type"
            className="inline-flex items-center bg-[#0F1117] border border-[#262A35] rounded-xl p-1"
          >
            <button
              type="button"
              aria-pressed={mode === "image"}
              onClick={() => setMode("image")}
              className={segmentButton(mode === "image")}
            >
              <ImageIcon className="w-4 h-4" />
              Image
            </button>
            <button
              type="button"
              aria-pressed={mode === "video"}
              onClick={() => setMode("video")}
              className={segmentButton(mode === "video")}
            >
              <Video className="w-4 h-4" />
              Video
            </button>
          </div>
        </section>

        {/* Starting point + source image */}
        <section className={sectionClasses} aria-labelledby="composer-input-heading">
          <div>
            <h2 id="composer-input-heading" className="text-sm font-semibold text-[#E8EAF0]">
              Starting point
            </h2>
            <p className="text-xs text-[#9AA1B2] mt-0.5">
              {imageCapabilities.length > 1
                ? "Set a first frame and an optional last frame to guide the result."
                : "Start from text, or add one or more images to guide the result."}
            </p>
          </div>
          <div
            role="group"
            aria-label="Starting point"
            className="inline-flex items-center bg-[#0F1117] border border-[#262A35] rounded-xl p-1"
          >
            <button
              type="button"
              aria-pressed={!withImage}
              onClick={() => setWithImage(false)}
              className={segmentButton(!withImage)}
            >
              <Type className="w-4 h-4" />
              Text only
            </button>
            <button
              type="button"
              aria-pressed={withImage}
              onClick={() => setWithImage(true)}
              className={segmentButton(withImage)}
            >
              <ImageIcon className="w-4 h-4" />
              Text + image
            </button>
          </div>

          {withImage && selectedModel && imageCapabilities.length === 0 && (
            <p role="alert" className="text-xs text-red-400">
              This model does not accept image inputs.
            </p>
          )}

          {withImage &&
            imageCapabilities.map((capability: ModelInputCapability, index: number) => (
              <ComposerImagePicker
                key={capability.role}
                projectId={projectId}
                kind={capability.kind}
                label={capability.label}
                max={capability.max_count}
                values={inputsByRole[capability.role] ?? []}
                error={index === 0 ? imageError : undefined}
                onChange={(assets) =>
                  setInputsByRole((previous) => ({
                    ...previous,
                    [capability.role]: assets,
                  }))
                }
              />
            ))}
        </section>

        {/* Prompt */}
        <section className={sectionClasses} aria-labelledby="composer-prompt-heading">
          <div>
            <h2 id="composer-prompt-heading" className="text-sm font-semibold text-[#E8EAF0]">
              Prompt
            </h2>
            <p className="text-xs text-[#9AA1B2] mt-0.5">
              Describe the subject, mood, camera movement, and style.
            </p>
          </div>
          <label htmlFor="composer-prompt" className="sr-only">
            Prompt
          </label>
          <textarea
            id="composer-prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={5}
            placeholder={
              mode === "image"
                ? "A cinematic still of a lighthouse at dusk, soft fog, 35mm"
                : "Slow dolly-in over a misty forest, golden hour, gentle camera shake"
            }
            className="w-full px-3 py-2 rounded-xl bg-[#0F1117] border border-[#262A35] text-sm text-[#E8EAF0] placeholder:text-[#9AA1B2] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] resize-y"
          />
        </section>

        {/* Parameters */}
        <section className={sectionClasses} aria-labelledby="composer-params-heading">
          <div>
            <h2 id="composer-params-heading" className="text-sm font-semibold text-[#E8EAF0]">
              Parameters
            </h2>
            <p className="text-xs text-[#9AA1B2] mt-0.5">
              Optional settings come from the selected model&apos;s schema.
            </p>
          </div>

          {selectedModel && (
            <SchemaParamsForm
              schema={selectedModel.input_schema}
              values={params}
              errors={fieldErrors}
              onChange={(name: string, value: ParamValue) =>
                setParams((previous) => ({ ...previous, [name]: value }))
              }
            />
          )}
        </section>
      </div>

      {/* Summary / submit */}
      <aside className="space-y-4 lg:sticky lg:top-6 self-start">
        <div className={sectionClasses}>
          <div className="flex items-center gap-2">
            <Wand2 className="w-4 h-4 text-[#A995FF]" />
            <h2 className="text-sm font-semibold text-[#E8EAF0]">Model</h2>
          </div>

          {modelsLoading && (
            <div className="flex items-center gap-2 text-xs text-[#9AA1B2]">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading models…
            </div>
          )}

          {modelsError && (
            <p className="text-xs text-red-400">Could not load models. Refresh and try again.</p>
          )}

          {!modelsLoading && !modelsError && models.length === 0 && (
            <p className="text-xs text-[#9AA1B2]">No models are available for this flow yet.</p>
          )}

          {models.length > 0 && (
            <div className="space-y-1.5">
              <span
                id="composer-model-label"
                className="block text-xs font-medium text-[#C7CBD6]"
              >
                Model
              </span>
              <ModelPicker
                models={models}
                value={selectedModel?.slug ?? null}
                onChange={setSelectedSlug}
                labelledBy="composer-model-label"
              />
            </div>
          )}

          <div className="flex items-center justify-between rounded-xl bg-[#0F1117] border border-[#262A35] px-3 py-2">
            <span className="flex items-center gap-1.5 text-xs text-[#9AA1B2]">
              <Coins className="w-3.5 h-3.5 text-[#F5C451]" />
              Estimated cost
            </span>
            <span className="text-sm font-semibold text-[#E8EAF0]">
              <span data-testid="generation-cost">{credits}</span> credits
            </span>
          </div>

          <button
            type="submit"
            disabled={mutation.isPending || !selectedModel}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#6C4CE8] text-white text-sm font-semibold hover:bg-[#6B4CF0] disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#14161C] focus:ring-[#7C5CFF]"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Submitting…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Generate
              </>
            )}
          </button>

          {submitError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          {lastJob && (
            <div
              role="status"
              className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300"
            >
              Queued <span className="font-mono">{lastJob.id}</span> ({lastJob.status})
            </div>
          )}
        </div>

        <p className="text-[11px] text-[#9AA1B2] px-1">
          Submissions are deduplicated: retrying an unchanged request will not start a second job.
        </p>
      </aside>
    </form>
  );
}
