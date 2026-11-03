"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  ImageUp,
  Loader2,
  RotateCcw,
  XCircle,
} from "lucide-react";
import {
  isActiveJobStatus,
  TERMINAL_JOB_STATUSES,
  useCancelGeneration,
  useLiveJob,
  useRetryGeneration,
  type GenerationJob,
  type GenerationOutput,
} from "@/hooks/use-generations";
import type { Asset } from "@/hooks/use-assets";

const STATUS_STYLES: Record<string, string> = {
  queued: "border-[#3A3F4D] bg-[#1B1E26] text-[#9AA1B2]",
  submitting: "border-[#4A6CF7]/40 bg-[#4A6CF7]/10 text-[#8FA4FF]",
  running: "border-[#4A6CF7]/40 bg-[#4A6CF7]/10 text-[#8FA4FF]",
  finalizing: "border-[#7C5CFF]/40 bg-[#7C5CFF]/10 text-[#A995FF]",
  succeeded: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  failed: "border-red-500/40 bg-red-500/10 text-red-300",
  canceled: "border-[#3A3F4D] bg-[#1B1E26] text-[#9AA1B2]",
};

function statusIcon(status: string) {
  if (status === "succeeded") return <CheckCircle2 className="w-3.5 h-3.5" />;
  if (status === "failed") return <AlertTriangle className="w-3.5 h-3.5" />;
  if (status === "canceled") return <XCircle className="w-3.5 h-3.5" />;
  if (isActiveJobStatus(status)) return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
  return <Clock className="w-3.5 h-3.5" />;
}

function formatElapsed(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** Adapt a generated output into the asset shape the composer accepts. */
export function outputToAsset(jobId: string, output: GenerationOutput): Asset {
  const extension = output.mime_type?.split("/")[1] ?? "png";
  return {
    id: output.asset_id,
    workspace_id: "",
    project_id: "",
    kind: output.kind || "image",
    origin: "generated",
    mime_type: output.mime_type,
    size_bytes: null,
    width: null,
    height: null,
    duration_ms: null,
    fps: null,
    storage_path: "",
    thumbnail_path: null,
    thumbnail_url: output.thumbnail_url,
    signed_url: output.signed_url,
    source_job_id: jobId,
    parent_asset_id: null,
    metadata: {
      filename: `generated-${output.asset_id.slice(0, 8)}.${extension}`,
    },
    created_at: new Date().toISOString(),
  };
}

interface JobCardProps {
  job: GenerationJob;
  projectId: string;
  /** True when Realtime is unavailable and the card should poll. */
  poll: boolean;
  onUseAsInput?: (asset: Asset) => void;
}

/** One generation job with live status, outputs, and actions. */
export function JobCard({ job, projectId, poll, onUseAsInput }: JobCardProps) {
  const queryClient = useQueryClient();
  const active = isActiveJobStatus(job.status);
  const liveQuery = useLiveJob(job.id, poll && active);
  const current = poll && liveQuery.data ? liveQuery.data : job;

  const cancelMutation = useCancelGeneration(projectId);
  const retryMutation = useRetryGeneration(projectId);

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!isActiveJobStatus(current.status)) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [current.status]);

  // A polled terminal status means outputs are ready; refresh the list to load them.
  const liveStatus = liveQuery.data?.status;
  useEffect(() => {
    if (liveStatus && TERMINAL_JOB_STATUSES.has(liveStatus)) {
      queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
    }
  }, [liveStatus, projectId, queryClient]);

  const startedAt = current.started_at ? new Date(current.started_at).getTime() : null;
  const elapsed =
    isActiveJobStatus(current.status) && startedAt ? formatElapsed(now - startedAt) : null;

  const imageOutput = current.outputs.find((output) => output.kind === "image");
  const taskLabel = current.task_type.replace(/_/g, " ");

  return (
    <article
      aria-label={`Generation ${current.id}`}
      className="rounded-2xl border border-[#262A35] bg-[#14161C] p-4 space-y-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold capitalize ${
                STATUS_STYLES[current.status] ?? STATUS_STYLES.queued
              }`}
            >
              {statusIcon(current.status)}
              {current.status}
            </span>
            <span className="text-[11px] text-[#6B7280] capitalize">{taskLabel}</span>
            {elapsed && <span className="text-[11px] font-mono text-[#9AA1B2]">{elapsed}</span>}
          </div>
          <p className="text-sm text-[#E8EAF0] line-clamp-2">
            {current.prompt || "No prompt provided"}
          </p>
        </div>
      </div>

      {current.outputs.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {current.outputs.map((output) => (
            <div
              key={output.asset_id}
              className="overflow-hidden rounded-xl border border-[#262A35] bg-[#0F1117]"
            >
              {output.kind === "video" ? (
                <video
                  controls
                  loop
                  muted
                  playsInline
                  poster={output.thumbnail_url ?? undefined}
                  src={output.signed_url ?? undefined}
                  className="w-full max-h-56 bg-black"
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={output.thumbnail_url || output.signed_url || ""}
                  alt={current.prompt || "Generated output"}
                  className="w-full max-h-56 object-contain bg-black"
                />
              )}
            </div>
          ))}
        </div>
      )}

      {current.error_message && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {current.error_code ? `${current.error_code}: ` : ""}
          {current.error_message}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {isActiveJobStatus(current.status) && (
          <button
            type="button"
            onClick={() => cancelMutation.mutate(current.id)}
            disabled={cancelMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#262A35] bg-[#1B1E26] px-2.5 py-1.5 text-[11px] font-medium text-[#E8EAF0] hover:border-red-500/50 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            <XCircle className="w-3.5 h-3.5" />
            Cancel
          </button>
        )}

        {(current.status === "failed" || current.status === "canceled") && (
          <button
            type="button"
            onClick={() => retryMutation.mutate(current.id)}
            disabled={retryMutation.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#262A35] bg-[#1B1E26] px-2.5 py-1.5 text-[11px] font-medium text-[#E8EAF0] hover:border-[#7C5CFF]/50 disabled:opacity-50 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-[#7C5CFF]" />
            Retry
          </button>
        )}

        {current.status === "succeeded" && imageOutput && onUseAsInput && (
          <button
            type="button"
            onClick={() => onUseAsInput(outputToAsset(current.id, imageOutput))}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#262A35] bg-[#1B1E26] px-2.5 py-1.5 text-[11px] font-medium text-[#E8EAF0] hover:border-[#7C5CFF]/50 transition-colors"
          >
            <ImageUp className="w-3.5 h-3.5 text-[#7C5CFF]" />
            Use as input
          </button>
        )}

        {current.outputs[0]?.signed_url && (
          <a
            href={current.outputs[0].signed_url}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] text-[#9AA1B2] underline-offset-2 hover:text-[#E8EAF0] hover:underline"
          >
            Open media
          </a>
        )}
      </div>
    </article>
  );
}
