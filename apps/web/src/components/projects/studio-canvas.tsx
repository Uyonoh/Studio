"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AtSign,
  Check,
  ChevronDown,
  Clock,
  Coins,
  Image as ImageIcon,
  Layers,
  Loader2,
  Maximize2,
  Plus,
  Ratio,
  SlidersHorizontal,
  Sparkles,
  UploadCloud,
  Video,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { AssetDetailDrawer } from "@/components/assets/asset-detail-drawer";
import { ModelPicker } from "@/components/composer/model-picker";
import { SchemaParamsForm } from "@/components/composer/schema-params-form";
import {
  uploadAssetWithProgress,
  useAssets,
  type Asset,
} from "@/hooks/use-assets";
import {
  GenerationSubmitError,
  newIdempotencyKey,
  TERMINAL_JOB_STATUSES,
  useProjectJobs,
  useSubmitGeneration,
  type GenerationJob,
  type SubmitGenerationPayload,
} from "@/hooks/use-generations";
import { useJobRealtime, type GenerationJobRow } from "@/hooks/use-job-realtime";
import { useModels, type StudioModel, type TaskType } from "@/hooks/use-models";
import {
  defaultParamValues,
  normalizeParamValues,
  paramLabel,
  validateParamValues,
  type ModelInputSchema,
  type ParamValue,
  type ParamValues,
} from "@/lib/generation-params";
import { capabilitiesOfKind } from "@/lib/model-inputs";

type ComposerMode = "image" | "video";

interface StudioCanvasProps {
  projectId: string;
}

interface CanvasPin {
  id: string;
  assetId: string | null;
  asset: Asset | null;
  kind: string;
  src: string | null;
  poster: string | null;
  label: string;
  origin: string;
  width: number | null;
  height: number | null;
  createdAt: string;
  status?: string;
}

/** Map the composer's mode + input choice onto an API task type. */
function taskTypeFor(mode: ComposerMode, hasInputs: boolean): TaskType {
  if (mode === "image") return hasInputs ? "image_to_image" : "text_to_image";
  return hasInputs ? "image_to_video" : "text_to_video";
}

function assetName(asset: Asset): string {
  const filename = asset.metadata?.filename;
  if (typeof filename === "string" && filename.trim()) return filename;
  const path = asset.storage_path ?? "";
  return path.split("/").pop() || `${asset.kind}-${asset.id.slice(0, 8)}`;
}

function assetToPin(asset: Asset): CanvasPin {
  const isVideo = asset.kind === "video" || asset.mime_type?.startsWith("video/");
  return {
    id: `asset:${asset.id}`,
    assetId: asset.id,
    asset,
    kind: isVideo ? "video" : "image",
    src: asset.signed_url || asset.thumbnail_url,
    poster: asset.thumbnail_url,
    label: assetName(asset),
    origin: asset.origin,
    width: asset.width,
    height: asset.height,
    createdAt: asset.created_at,
  };
}

function jobToPins(job: GenerationJob): CanvasPin[] {
  const isVideoJob = job.task_type.includes("video");
  const pins = job.outputs.map((output) => ({
    id: `output:${job.id}:${output.asset_id}`,
    assetId: output.asset_id,
    asset: null,
    kind: output.kind || (isVideoJob ? "video" : "image"),
    src: output.signed_url || output.thumbnail_url,
    poster: output.thumbnail_url,
    label: job.prompt || `${output.kind} ${output.asset_id.slice(0, 8)}`,
    origin: "generated",
    width: null,
    height: null,
    createdAt: job.completed_at || job.queued_at,
    status: job.status,
  })) satisfies CanvasPin[];

  if (pins.length > 0 || TERMINAL_JOB_STATUSES.has(job.status)) return pins;

  return [
    {
      id: `job:${job.id}`,
      assetId: null,
      asset: null,
      kind: isVideoJob ? "video" : "image",
      src: null,
      poster: null,
      label: job.prompt || "Generating…",
      origin: "generated",
      width: null,
      height: null,
      createdAt: job.queued_at,
      status: job.status,
    },
  ];
}

function findEnumKey(
  schema: ModelInputSchema,
  candidates: string[]
): string | null {
  for (const candidate of candidates) {
    const property = schema.properties?.[candidate];
    if (property?.enum && property.enum.length > 0) return candidate;
  }
  return null;
}

const chipClasses =
  "inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[#262A35] bg-[#101217] px-2.5 py-1.5 text-[11px] font-medium text-[#C7CBD6] transition-colors hover:border-[#3A3F4D] hover:text-[#E8EAF0] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF]";

function CompactSelect({
  icon,
  label,
  value,
  options,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  value: ParamValue;
  options: Array<string | number | boolean>;
  onChange: (value: string) => void;
}) {
  const current = value === undefined || value === null ? "" : String(value);
  return (
    <label className={`${chipClasses} relative cursor-pointer`} title={label}>
      <span className="text-[#9AA1B2]" aria-hidden="true">
        {icon}
      </span>
      <select
        aria-label={label}
        value={current}
        onChange={(event) => onChange(event.target.value)}
        className="max-w-[9rem] cursor-pointer appearance-none truncate bg-transparent pr-4 text-[11px] font-medium text-[#E8EAF0] focus:outline-none"
      >
        {current === "" && <option value="">{label}</option>}
        {options.map((option) => (
          <option key={String(option)} value={String(option)} className="bg-[#14161C]">
            {String(option)}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2 h-3 w-3 text-[#9AA1B2]"
        aria-hidden="true"
      />
    </label>
  );
}

function CanvasPinCard({
  pin,
  onOpen,
  onUseAsReference,
  onMediaError,
}: {
  pin: CanvasPin;
  onOpen: (pin: CanvasPin) => void;
  onUseAsReference: (pin: CanvasPin) => void;
  onMediaError: (pin: CanvasPin) => void;
}) {
  const isVideo = pin.kind === "video";
  const ratio =
    pin.width && pin.height
      ? Math.min(Math.max(pin.width / pin.height, 0.62), 1.9)
      : isVideo
        ? 16 / 9
        : 1;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(pin)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(pin);
        }
      }}
      aria-label={`Open ${pin.label}`}
      className="group relative mb-4 w-full break-inside-avoid overflow-hidden rounded-2xl border border-[#262A35] bg-[#14161C] text-left transition-all hover:border-[#7C5CFF]/60 hover:shadow-[0_8px_30px_rgba(124,92,255,0.15)] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF]"
      style={{ breakInside: "avoid" }}
    >
      <div
        className="relative w-full overflow-hidden bg-[#0E1015]"
        style={{ aspectRatio: String(ratio) }}
      >
        {pin.status && !pin.src ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-[linear-gradient(110deg,#12141A_8%,#191C24_18%,#12141A_33%)] bg-[length:200%_100%] animate-[shimmer_1.8s_linear_infinite] px-4 text-center">
            <Loader2 className="h-5 w-5 animate-spin text-[#A995FF]" />
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#9AA1B2]">
              {pin.status}
            </span>
            <span className="line-clamp-2 text-[11px] text-[#C7CBD6]">{pin.label}</span>
          </div>
        ) : isVideo ? (
          pin.poster ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={pin.poster}
              alt={pin.label}
              loading="lazy"
              onError={() => onMediaError(pin)}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : (
            <video
              src={pin.src ?? undefined}
              muted
              loop
              playsInline
              preload="metadata"
              onError={() => onMediaError(pin)}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          )
        ) : pin.src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={pin.src}
            alt={pin.label}
            loading="lazy"
            onError={() => onMediaError(pin)}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[#9AA1B2]">
            <ImageIcon className="h-6 w-6 text-[#A995FF]" />
          </div>
        )}

        <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-2 p-2.5">
          <span className="rounded-full border border-white/10 bg-black/55 px-2 py-0.5 text-[10px] font-mono capitalize text-[#E8EAF0] backdrop-blur-md">
            {pin.origin}
          </span>
          {isVideo && (
            <span className="flex items-center gap-1 rounded-full border border-white/10 bg-black/55 px-2 py-0.5 text-[10px] font-medium text-[#E8EAF0] backdrop-blur-md">
              <Video className="h-3 w-3 text-[#A995FF]" />
              Video
            </span>
          )}
        </div>

        <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/45 opacity-0 backdrop-blur-[2px] transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onOpen(pin);
            }}
            title="Open asset details"
            aria-label={`Open details for ${pin.label}`}
            className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-[#14161C]/90 px-3 py-1.5 text-[11px] font-medium text-[#E8EAF0] shadow-lg hover:bg-[#1B1E26]"
          >
            <Maximize2 className="h-3.5 w-3.5 text-[#A995FF]" />
            Details
          </button>
          {pin.asset && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onUseAsReference(pin);
              }}
              title="Use as a reference"
              aria-label={`Use ${pin.label} as a reference`}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-[#14161C]/90 px-3 py-1.5 text-[11px] font-medium text-[#E8EAF0] shadow-lg hover:bg-[#1B1E26]"
            >
              <Plus className="h-3.5 w-3.5 text-[#A995FF]" />
              Reference
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-[#262A35] px-3 py-2">
        <span className="truncate text-[11px] font-medium text-[#E8EAF0]">{pin.label}</span>
        <span className="shrink-0 font-mono text-[10px] text-[#9AA1B2]">
          {pin.width && pin.height ? `${pin.width}×${pin.height}` : pin.kind}
        </span>
      </div>
    </div>
  );
}

export function StudioCanvas({ projectId }: StudioCanvasProps) {
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<ComposerMode>("image");
  const [prompt, setPrompt] = useState("");
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [params, setParams] = useState<ParamValues>({});
  const [inputsByRole, setInputsByRole] = useState<Record<string, Asset[]>>({});
  const [activeRole, setActiveRole] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [imageError, setImageError] = useState<string | undefined>();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastJob, setLastJob] = useState<GenerationJob | null>(null);
  const [isReferenceOpen, setIsReferenceOpen] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const promptRef = useRef<HTMLTextAreaElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const referenceRef = useRef<HTMLDivElement>(null);
  const referenceMenuRef = useRef<HTMLDivElement>(null);
  const advancedRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  const idempotency = useRef<{ key: string; signature: string } | null>(null);
  const lastModelSlug = useRef<string | null>(null);
  const refreshedAssetIds = useRef<Set<string>>(new Set());

  const attachedAssets = useMemo(
    () => Object.values(inputsByRole).flat(),
    [inputsByRole]
  );
  const hasInputs = attachedAssets.length > 0;
  // If the user has attached inputs, use image-to-x models; otherwise fetch the full mode catalog or text-to-x models.
  const taskType = taskTypeFor(mode, hasInputs);
  const companionTaskType = taskTypeFor(mode, !hasInputs);

  const { data: models = [], isLoading: modelsLoading, isError: modelsError } = useModels(taskType);
  const { data: companionModels = [] } = useModels(companionTaskType);
  const selectedModel: StudioModel | null =
    models.find((model) => model.slug === selectedSlug) ?? models[0] ?? null;
  const imageCapabilities = useMemo(() => {
    const direct = capabilitiesOfKind(selectedModel, "image");
    if (direct.length > 0) return direct;
    // If the currently selected model is text_to_image / text_to_video, look up what
    // capabilities the mode's image models support so references can still be attached.
    const companion = companionModels.find((m) => capabilitiesOfKind(m, "image").length > 0);
    return capabilitiesOfKind(companion, "image");
  }, [selectedModel, companionModels]);
  const mutation = useSubmitGeneration(projectId);

  const {
    data: assetPages,
    refetch: refetchAssets,
  } = useAssets(projectId);
  const { data: jobPage } = useProjectJobs(projectId);
  const projectAssets = useMemo(
    () => assetPages?.pages.flatMap((page) => page.items) ?? [],
    [assetPages]
  );
  const jobs = useMemo(() => jobPage?.items ?? [], [jobPage]);

  const handleJobChange = useCallback(
    (row: GenerationJobRow) => {
      if (!TERMINAL_JOB_STATUSES.has(row.status)) return;
      void queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
    },
    [projectId, queryClient]
  );
  useJobRealtime(projectId, handleJobChange);

  // Keep a valid selection whenever the task type (and model list) changes.
  useEffect(() => {
    if (models.length === 0) return;
    if (!selectedSlug || !models.some((model) => model.slug === selectedSlug)) {
      setSelectedSlug(models[0].slug);
    }
  }, [models, selectedSlug]);

  // Reset parameters to the model defaults when a different model is picked.
  useEffect(() => {
    if (!selectedModel) return;
    if (lastModelSlug.current === selectedModel.slug) return;
    lastModelSlug.current = selectedModel.slug;
    setParams(
      defaultParamValues(
        selectedModel.input_schema,
        selectedModel.default_params
      ) as ParamValues
    );
    setFieldErrors({});
  }, [selectedModel]);

  // Drop references only if the model is an image-input model that cannot accept them.
  useEffect(() => {
    if (!selectedModel) return;
    const capabilities = capabilitiesOfKind(selectedModel, "image");
    if (capabilities.length === 0) return;
    setInputsByRole((previous) => {
      const next: Record<string, Asset[]> = {};
      let changed = false;
      for (const capability of capabilities) {
        const current = previous[capability.role] ?? [];
        const trimmed = current.slice(0, capability.max_count);
        if (trimmed.length > 0) next[capability.role] = trimmed;
        if (trimmed.length !== current.length) changed = true;
      }
      if (Object.keys(previous).some((role) => !(role in next))) changed = true;
      return changed ? next : previous;
    });
  }, [selectedModel]);

  useEffect(() => {
    if (!activeRole && imageCapabilities.length > 0) {
      setActiveRole(imageCapabilities[0].role);
    } else if (
      activeRole &&
      imageCapabilities.length > 0 &&
      !imageCapabilities.some((capability) => capability.role === activeRole)
    ) {
      setActiveRole(imageCapabilities[0].role);
    }
  }, [activeRole, imageCapabilities]);

  // Close popovers when clicking elsewhere.
  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (
        isReferenceOpen &&
        !referenceRef.current?.contains(target) &&
        !referenceMenuRef.current?.contains(target)
      ) {
        setIsReferenceOpen(false);
      }
      if (
        isAdvancedOpen &&
        !advancedRef.current?.contains(target) &&
        !(target instanceof Element && target.closest("[data-advanced-trigger]"))
      ) {
        setIsAdvancedOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [isReferenceOpen, isAdvancedOpen]);

  const handleMediaError = useCallback(
    (assetId: string) => {
      if (refreshedAssetIds.current.has(assetId)) return;
      refreshedAssetIds.current.add(assetId);
      void refetchAssets();
    },
    [refetchAssets]
  );

  function addReference(asset: Asset, role?: string) {
    const capabilities =
      imageCapabilities.length > 0
        ? imageCapabilities
        : capabilitiesOfKind(selectedModel, "image");
    if (capabilities.length === 0) {
      toast.error("This model does not accept image references.");
      return;
    }

    const target =
      (role && capabilities.find((capability) => capability.role === role)) ||
      capabilities.find(
        (capability) =>
          (inputsByRole[capability.role]?.length ?? 0) < capability.max_count
      ) ||
      capabilities[capabilities.length - 1];

    setInputsByRole((previous) => {
      const current = previous[target.role] ?? [];
      if (current.some((selected) => selected.id === asset.id)) return previous;
      if (current.length >= target.max_count) {
        toast.error(`${target.label} accepts up to ${target.max_count} reference${target.max_count === 1 ? "" : "s"}.`);
        return previous;
      }
      return {
        ...previous,
        [target.role]: [...current, asset].slice(0, target.max_count),
      };
    });
  }

  function toggleReference(asset: Asset) {
    if (!activeRole) {
      addReference(asset);
      return;
    }
    const capability = imageCapabilities.find((item) => item.role === activeRole);
    if (!capability) return;
    setInputsByRole((previous) => {
      const current = previous[activeRole] ?? [];
      if (current.some((selected) => selected.id === asset.id)) {
        return { ...previous, [activeRole]: current.filter((item) => item.id !== asset.id) };
      }
      if (current.length >= capability.max_count) {
        toast.error(`${capability.label} accepts up to ${capability.max_count} reference${capability.max_count === 1 ? "" : "s"}.`);
        return previous;
      }
      return { ...previous, [activeRole]: [...current, asset] };
    });
  }

  function removeReference(role: string, assetId: string) {
    setInputsByRole((previous) => ({
      ...previous,
      [role]: (previous[role] ?? []).filter((asset) => asset.id !== assetId),
    }));
  }

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        const asset = await uploadAssetWithProgress({ projectId, file });
        await queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
        if (asset.kind === "image") addReference(asset);
      }
      toast.success("Attachment uploaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  }

  function buildPayload(model: StudioModel): SubmitGenerationPayload {
    const inputs: SubmitGenerationPayload["inputs"] = [];
    for (const capability of capabilitiesOfKind(model, "image")) {
      for (const asset of inputsByRole[capability.role] ?? []) {
        inputs.push({ asset_id: asset.id, role: capability.role });
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
    const missingCapability = imageCapabilities.find(
      (capability) =>
        capability.required && (inputsByRole[capability.role]?.length ?? 0) === 0
    );
    const noImageSupport = hasInputs && imageCapabilities.length === 0;
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
      setPrompt("");
      toast.success("Generation queued");
      setIsReferenceOpen(false);
      setIsAdvancedOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
    } catch (error) {
      applySubmitError(error, selectedModel);
    } finally {
      inFlight.current = false;
    }
  }

  function openReferencePicker() {
    if (imageCapabilities.length === 0) {
      toast.error("This model does not accept image references.");
      return;
    }
    setIsAdvancedOpen(false);
    setIsReferenceOpen((open) => !open);
  }

  const ratios = useMemo(() => {
    if (!selectedModel) return null;
    const key = findEnumKey(selectedModel.input_schema, [
      "aspect_ratio",
      "aspectRatio",
      "ratio",
    ]);
    if (!key) return null;
    return {
      key,
      property: selectedModel.input_schema.properties![key],
      label: paramLabel(key, selectedModel.input_schema.properties![key]),
    };
  }, [selectedModel]);

  const resolutions = useMemo(() => {
    if (!selectedModel) return null;
    const key = findEnumKey(selectedModel.input_schema, [
      "resolution",
      "quality",
      "megapixels",
    ]);
    if (!key) return null;
    return {
      key,
      property: selectedModel.input_schema.properties![key],
      label: paramLabel(key, selectedModel.input_schema.properties![key]),
    };
  }, [selectedModel]);

  const durations = useMemo(() => {
    if (!selectedModel) return null;
    const key = findEnumKey(selectedModel.input_schema, [
      "duration_s",
      "duration",
      "duration_seconds",
      "length",
    ]);
    if (!key) return null;
    return {
      key,
      property: selectedModel.input_schema.properties![key],
      label: paramLabel(key, selectedModel.input_schema.properties![key]),
    };
  }, [selectedModel]);

  const featuredParamKeys = useMemo(
    () =>
      new Set(
        [ratios?.key, resolutions?.key, durations?.key].filter(
          (key): key is string => Boolean(key)
        )
      ),
    [ratios?.key, resolutions?.key, durations?.key]
  );

  const extraEnumParams = useMemo(() => {
    if (!selectedModel) return [];
    return Object.entries(selectedModel.input_schema.properties ?? {}).filter(
      ([key, property]) =>
        !featuredParamKeys.has(key) &&
        Array.isArray(property.enum) &&
        property.enum.length > 0
    );
  }, [selectedModel, featuredParamKeys]);

  const advancedParams = useMemo(
    () =>
      Object.entries(selectedModel?.input_schema.properties ?? {}).filter(
        ([, property]) => !Array.isArray(property.enum) || property.enum.length === 0
      ),
    [selectedModel]
  );

  const pins = useMemo(() => {
    const assetPins = projectAssets.map(assetToPin);
    const assetIds = new Set(projectAssets.map((asset) => asset.id));
    const outputPins = jobs
      .flatMap(jobToPins)
      .filter((pin) => !pin.assetId || !assetIds.has(pin.assetId));
    return [...outputPins, ...assetPins].sort((a, b) => {
      const timeA = new Date(a.createdAt).getTime();
      const timeB = new Date(b.createdAt).getTime();
      if (timeA !== timeB) return timeB - timeA;
      return b.id.localeCompare(a.id);
    });
  }, [projectAssets, jobs]);

  const credits = selectedModel?.cost_credits ?? "—";
  const referenceCount = attachedAssets.length;
  const canGenerate = Boolean(selectedModel) && !mutation.isPending;

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <div
        className="flex-1 overflow-y-auto px-4 pb-64 pt-2 sm:px-6 lg:px-8"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(154,161,178,0.14) 1px, transparent 0)",
          backgroundSize: "22px 22px",
        }}
      >
        {pins.length === 0 ? (
          <div className="flex h-full min-h-[12rem] items-center justify-center px-6 text-center">
            <div className="max-w-sm space-y-2">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-[#262A35] bg-[#14161C] text-[#A995FF]">
                <Layers className="h-6 w-6" />
              </div>
              <h2 className="text-sm font-semibold text-[#E8EAF0]">Your canvas is empty</h2>
              <p className="text-xs leading-relaxed text-[#9AA1B2]">
                Describe an idea below, or reference an existing asset. Generated media and
                references pin themselves here automatically.
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-[110rem] columns-2 gap-4 sm:columns-3 lg:columns-4 2xl:columns-5">
            {pins.map((pin) => (
              <CanvasPinCard
                key={pin.id}
                pin={pin}
                onOpen={(item) => {
                  if (item.assetId) {
                    setSelectedAssetId(item.assetId);
                  }
                }}
                onUseAsReference={(item) => {
                  if (!item.asset) return;
                  addReference(item.asset);
                  toast.success(`Added ${assetName(item.asset)} as a reference`);
                }}
                onMediaError={(item) => {
                  if (item.assetId) handleMediaError(item.assetId);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Prompt dock */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 bg-gradient-to-t from-[#0B0C10] via-[#0B0C10]/95 to-transparent px-3 pb-3 pt-10 sm:px-6 sm:pb-5">
        <div className="pointer-events-auto mx-auto w-full max-w-5xl">
          <form onSubmit={handleSubmit} noValidate>
            <div className="flex items-stretch gap-2 sm:gap-3">
              {/* Output type toggle */}
              <div
                role="group"
                aria-label="Output type"
                className="flex shrink-0 flex-col justify-center gap-1 rounded-2xl border border-[#262A35] bg-[#14161C] p-1 shadow-card"
              >
                <button
                  type="button"
                  aria-pressed={mode === "image"}
                  onClick={() => setMode("image")}
                  title="Generate an image"
                  className={`flex min-w-[3.25rem] flex-col items-center gap-0.5 rounded-xl px-2 py-2 text-[10px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
                    mode === "image"
                      ? "bg-[#6C4CE8] text-white"
                      : "text-[#9AA1B2] hover:bg-[#1B1E26] hover:text-[#E8EAF0]"
                  }`}
                >
                  <ImageIcon className="h-4 w-4" />
                  Image
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "video"}
                  onClick={() => setMode("video")}
                  title="Generate a video"
                  className={`flex min-w-[3.25rem] flex-col items-center gap-0.5 rounded-xl px-2 py-2 text-[10px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
                    mode === "video"
                      ? "bg-[#6C4CE8] text-white"
                      : "text-[#9AA1B2] hover:bg-[#1B1E26] hover:text-[#E8EAF0]"
                  }`}
                >
                  <Video className="h-4 w-4" />
                  Video
                </button>
              </div>

              {/* Main prompt card */}
              <div className="min-w-0 flex-1 rounded-2xl border border-[#262A35] bg-[#0F1117]/95 p-2.5 shadow-card backdrop-blur-xl sm:p-3">
                <div className="flex items-stretch gap-2 sm:gap-3">
                  <label htmlFor="studio-canvas-prompt" className="sr-only">
                    Prompt
                  </label>
                  <textarea
                    id="studio-canvas-prompt"
                    ref={promptRef}
                    value={prompt}
                    onChange={(event) => setPrompt(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                    rows={2}
                    placeholder={
                      mode === "image"
                        ? "Describe the image you want to create..."
                        : "Describe the video you want to create..."
                    }
                    className="min-h-[3.25rem] flex-1 resize-none bg-transparent px-1.5 py-1 text-sm leading-relaxed text-[#E8EAF0] placeholder:text-[#9AA1B2]/80 focus:outline-none"
                  />

                  <button
                    type="submit"
                    disabled={!canGenerate}
                    className="flex w-[5.5rem] shrink-0 flex-col items-center justify-center gap-0.5 rounded-xl bg-[#D4FF3F] px-3 text-[#0B0C10] transition-all hover:bg-[#E2FF73] focus:outline-none focus:ring-2 focus:ring-[#D4FF3F] focus:ring-offset-2 focus:ring-offset-[#0F1117] active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 sm:w-24"
                  >
                    {mutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                    <span className="text-[11px] font-bold uppercase tracking-wide">
                      {mutation.isPending ? "Wait" : "Generate"}
                    </span>
                    <span className="flex items-center gap-0.5 text-[10px] font-semibold opacity-70">
                      <Coins className="h-2.5 w-2.5" />
                      {credits}
                    </span>
                  </button>
                </div>

                {/* Compact horizontal controls */}
                <div className="relative mt-2">
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                  <input
                    ref={uploadInputRef}
                    type="file"
                    multiple
                    accept="image/*,video/*"
                    className="hidden"
                    onChange={(event) => void handleUpload(event.target.files)}
                  />

                  <button
                    type="button"
                    onClick={() => uploadInputRef.current?.click()}
                    disabled={isUploading}
                    title="Upload an attachment"
                    aria-label="Upload an attachment"
                    className={`${chipClasses} px-2`}
                  >
                    {isUploading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-[#A995FF]" />
                    ) : (
                      <Plus className="h-3.5 w-3.5 text-[#A995FF]" />
                    )}
                  </button>

                  <div ref={referenceRef} className="flex shrink-0 items-center gap-1.5">
                    <button
                      type="button"
                      onClick={openReferencePicker}
                      title="Reference a project asset"
                      aria-label="Reference a project asset"
                      aria-expanded={isReferenceOpen}
                      className={`${chipClasses} px-2`}
                    >
                      <AtSign className="h-3.5 w-3.5 text-[#A995FF]" />
                    </button>

                    <button
                      type="button"
                      onClick={openReferencePicker}
                      aria-expanded={isReferenceOpen}
                      title="Attached references"
                      className={chipClasses}
                    >
                      <Layers className="h-3.5 w-3.5 text-[#9AA1B2]" />
                      <span>References</span>
                      {referenceCount > 0 && (
                        <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[#6C4CE8] px-1 text-[10px] font-semibold text-white">
                          {referenceCount}
                        </span>
                      )}
                      <ChevronDown className="h-3 w-3 text-[#9AA1B2]" />
                    </button>

                  </div>

                  {modelsLoading ? (
                    <span className={`${chipClasses} text-[#9AA1B2]`}>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Models…
                    </span>
                  ) : modelsError ? (
                    <span className={`${chipClasses} text-red-400`}>Models unavailable</span>
                  ) : models.length > 0 && selectedModel ? (
                    <ModelPicker
                      models={models}
                      value={selectedModel.slug}
                      onChange={setSelectedSlug}
                      labelledBy="studio-canvas-model"
                      variant="compact"
                    />
                  ) : (
                    <span className={`${chipClasses} text-[#9AA1B2]`}>No models</span>
                  )}

                  {ratios && (
                    <CompactSelect
                      icon={<Ratio className="h-3.5 w-3.5" />}
                      label={ratios.label}
                      value={params[ratios.key]}
                      options={ratios.property.enum ?? []}
                      onChange={(value) =>
                        setParams((previous) => ({ ...previous, [ratios.key]: value }))
                      }
                    />
                  )}

                  {resolutions && (
                    <CompactSelect
                      icon={<Maximize2 className="h-3.5 w-3.5" />}
                      label={resolutions.label}
                      value={params[resolutions.key]}
                      options={resolutions.property.enum ?? []}
                      onChange={(value) =>
                        setParams((previous) => ({ ...previous, [resolutions.key]: value }))
                      }
                    />
                  )}

                  {durations && (
                    <CompactSelect
                      icon={<Clock className="h-3.5 w-3.5" />}
                      label={durations.label}
                      value={params[durations.key]}
                      options={durations.property.enum ?? []}
                      onChange={(value) =>
                        setParams((previous) => ({ ...previous, [durations.key]: value }))
                      }
                    />
                  )}

                  {extraEnumParams.map(([key, property]) => (
                    <CompactSelect
                      key={key}
                      icon={<SlidersHorizontal className="h-3.5 w-3.5" />}
                      label={paramLabel(key, property)}
                      value={params[key]}
                      options={property.enum ?? []}
                      onChange={(value) =>
                        setParams((previous) => ({ ...previous, [key]: value }))
                      }
                    />
                  ))}

                  {advancedParams.length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsReferenceOpen(false);
                        setIsAdvancedOpen((open) => !open);
                      }}
                      aria-expanded={isAdvancedOpen}
                      title="Advanced parameters"
                      data-advanced-trigger
                      className={`${chipClasses} px-2`}
                    >
                      <SlidersHorizontal className="h-3.5 w-3.5 text-[#A995FF]" />
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => promptRef.current?.focus()}
                    title="Focus prompt"
                    aria-label="Focus prompt"
                    className={`${chipClasses} ml-auto px-2`}
                  >
                    <ChevronDown className="h-3.5 w-3.5 rotate-[-90deg] text-[#9AA1B2]" />
                  </button>
                  </div>

                  {isReferenceOpen && (
                    <div
                      ref={referenceMenuRef}
                      className="absolute bottom-full left-0 z-40 mb-2 max-h-[26rem] w-[min(34rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-[#262A35] bg-[#0F1117] p-3 shadow-2xl shadow-black/60"
                    >
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-[#E8EAF0]">
                          <Layers className="h-3.5 w-3.5 text-[#A995FF]" />
                          References
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsReferenceOpen(false)}
                          aria-label="Close references"
                          className="rounded-md p-1 text-[#9AA1B2] hover:bg-[#1B1E26] hover:text-[#E8EAF0]"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {imageCapabilities.length > 1 && (
                        <div className="mb-2 flex flex-wrap gap-1.5">
                          {imageCapabilities.map((capability) => (
                            <button
                              key={capability.role}
                              type="button"
                              onClick={() => setActiveRole(capability.role)}
                              className={`rounded-lg border px-2 py-1 text-[10px] font-medium transition-colors ${
                                activeRole === capability.role
                                  ? "border-[#7C5CFF]/60 bg-[#6C4CE8]/20 text-[#E8EAF0]"
                                  : "border-[#262A35] text-[#9AA1B2] hover:text-[#E8EAF0]"
                              }`}
                            >
                              {capability.label}
                              <span className="ml-1 font-mono text-[9px] text-[#9AA1B2]">
                                {(inputsByRole[capability.role]?.length ?? 0)}/
                                {capability.max_count}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}

                      {imageCapabilities.length === 0 ? (
                        <p className="px-1 py-4 text-center text-xs text-[#9AA1B2]">
                          The selected model does not accept images. Pick another model or switch
                          output type.
                        </p>
                      ) : (
                        <ReferenceGrid
                          assets={projectAssets.filter((asset) => asset.kind === "image")}
                          activeRole={activeRole}
                          inputsByRole={inputsByRole}
                          onToggle={toggleReference}
                          onRemove={removeReference}
                        />
                      )}

                      <button
                        type="button"
                        onClick={() => uploadInputRef.current?.click()}
                        disabled={isUploading}
                        className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[#262A35] px-3 py-2 text-[11px] font-medium text-[#9AA1B2] hover:border-[#7C5CFF]/50 hover:text-[#E8EAF0] disabled:opacity-50"
                      >
                        {isUploading ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#A995FF]" />
                        ) : (
                          <UploadCloud className="h-3.5 w-3.5 text-[#A995FF]" />
                        )}
                        Upload a new reference
                      </button>
                    </div>
                  )}

                  {isAdvancedOpen && selectedModel && (
                    <div
                      ref={advancedRef}
                      className="absolute bottom-full right-0 z-40 mb-2 max-h-[24rem] w-[min(24rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-[#262A35] bg-[#0F1117] p-3 shadow-2xl shadow-black/60"
                    >
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-[#E8EAF0]">Parameters</span>
                        <button
                          type="button"
                          onClick={() => setIsAdvancedOpen(false)}
                          aria-label="Close parameters"
                          className="rounded-md p-1 text-[#9AA1B2] hover:bg-[#1B1E26] hover:text-[#E8EAF0]"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <SchemaParamsForm
                        schema={selectedModel.input_schema}
                        values={params}
                        errors={fieldErrors}
                        onChange={(name: string, value: ParamValue) =>
                          setParams((previous) => ({ ...previous, [name]: value }))
                        }
                        idPrefix="studio-canvas-param"
                      />
                    </div>
                  )}
                </div>

                {/* Attached reference chips */}
                {attachedAssets.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {Object.entries(inputsByRole).flatMap(([role, assets]) =>
                      assets.map((asset) => (
                        <span
                          key={`${role}:${asset.id}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-[#7C5CFF]/40 bg-[#6C4CE8]/10 px-2 py-1 text-[10px] text-[#E8EAF0]"
                        >
                          <Layers className="h-3 w-3 text-[#A995FF]" />
                          <span className="max-w-[10rem] truncate">{assetName(asset)}</span>
                          <button
                            type="button"
                            onClick={() => removeReference(role, asset.id)}
                            aria-label={`Remove ${assetName(asset)}`}
                            className="rounded-sm text-[#9AA1B2] hover:text-[#E8EAF0]"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </span>
                      ))
                    )}
                  </div>
                )}

                {(imageError || submitError || Object.keys(fieldErrors).length > 0) && (
                  <div role="alert" className="mt-2 space-y-1">
                    {imageError && (
                      <p className="flex items-start gap-1.5 text-[11px] text-red-400">
                        <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
                        {imageError}
                      </p>
                    )}
                    {submitError && (
                      <p className="flex items-start gap-1.5 text-[11px] text-red-400">
                        <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
                        {submitError}
                      </p>
                    )}
                    {Object.entries(fieldErrors).map(([name, message]) => (
                      <p key={name} className="text-[11px] text-red-400">
                        {name.replace(/_/g, " ")}: {message}
                      </p>
                    ))}
                  </div>
                )}

                {lastJob && (
                  <div
                    role="status"
                    className="mt-2 flex items-center gap-1.5 text-[10px] text-emerald-300"
                  >
                    <Check className="h-3 w-3" />
                    Queued <span className="font-mono">{lastJob.id}</span> ({lastJob.status})
                  </div>
                )}
              </div>
            </div>
          </form>
        </div>
      </div>

      <AssetDetailDrawer
        assetId={selectedAssetId}
        projectId={projectId}
        onClose={() => setSelectedAssetId(null)}
      />
    </div>
  );
}

function ReferenceGrid({
  assets,
  activeRole,
  inputsByRole,
  onToggle,
  onRemove,
}: {
  assets: Asset[];
  activeRole: string | null;
  inputsByRole: Record<string, Asset[]>;
  onToggle: (asset: Asset) => void;
  onRemove: (role: string, assetId: string) => void;
}) {
  const selected = activeRole ? inputsByRole[activeRole] ?? [] : [];

  if (assets.length === 0) {
    return (
      <p className="px-1 py-4 text-center text-xs text-[#9AA1B2]">
        No images in this project yet. Upload one to use it as a reference.
      </p>
    );
  }

  return (
    <>
      <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-5" role="group" aria-label="Reference assets">
        {assets.map((asset) => {
          const selectedIndex = selected.findIndex((item) => item.id === asset.id);
          const isSelected = selectedIndex >= 0;
          const src = asset.thumbnail_url || asset.signed_url || "";
          return (
            <button
              key={asset.id}
              type="button"
              onClick={() => onToggle(asset)}
              aria-pressed={isSelected}
              aria-label={`Use ${assetName(asset)}`}
              title={assetName(asset)}
              className={`relative aspect-square overflow-hidden rounded-lg border transition-all focus:outline-none focus:ring-2 focus:ring-[#7C5CFF] ${
                isSelected
                  ? "border-[#7C5CFF] ring-2 ring-[#7C5CFF]/40"
                  : "border-[#262A35] hover:border-[#7C5CFF]/60"
              }`}
            >
              {src ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={src} alt={assetName(asset)} className="h-full w-full object-cover" />
              ) : (
                <span className="flex h-full w-full items-center justify-center text-[#9AA1B2]">
                  <ImageIcon className="h-4 w-4" />
                </span>
              )}
              {isSelected && (
                <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#6C4CE8] px-1 text-[10px] font-semibold text-white">
                  {selected.length > 1 ? selectedIndex + 1 : <Check className="h-3 w-3" />}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {selected.length > 0 && activeRole && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selected.map((asset) => (
            <span
              key={asset.id}
              className="inline-flex items-center gap-1 rounded-lg border border-[#262A35] bg-[#14161C] px-2 py-1 text-[10px] text-[#C7CBD6]"
            >
              <span className="max-w-[9rem] truncate">{assetName(asset)}</span>
              <button
                type="button"
                onClick={() => onRemove(activeRole, asset.id)}
                aria-label={`Remove ${assetName(asset)}`}
                className="text-[#9AA1B2] hover:text-[#E8EAF0]"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </>
  );
}
