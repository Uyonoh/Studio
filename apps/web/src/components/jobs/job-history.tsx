"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, History, Loader2, RefreshCw } from "lucide-react";
import {
  TERMINAL_JOB_STATUSES,
  useProjectJobs,
  type GenerationJob,
  type JobListPage,
} from "@/hooks/use-generations";
import {
  useJobRealtime,
  type GenerationJobRow,
  type RealtimeConnectionState,
} from "@/hooks/use-job-realtime";
import type { Asset } from "@/hooks/use-assets";
import { JobCard } from "./job-card";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
  { value: "canceled", label: "Canceled" },
];

function connectionLabel(state: RealtimeConnectionState): { text: string; className: string } {
  if (state === "subscribed") {
    return { text: "Live", className: "bg-emerald-400" };
  }
  if (state === "connecting") {
    return { text: "Connecting", className: "bg-[#F5C451]" };
  }
  return { text: "Polling", className: "bg-[#F5C451]" };
}

interface JobHistoryProps {
  projectId: string;
  onUseAsInput?: (asset: Asset) => void;
  /** Realtime subscribe timeout override (used by tests for a fast fallback). */
  realtimeTimeoutMs?: number;
}

/** Live job history for a project, with Realtime updates and polling fallback. */
export function JobHistory({ projectId, onUseAsInput, realtimeTimeoutMs }: JobHistoryProps) {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading, isError, error, refetch, isFetching } = useProjectJobs(
    projectId,
    statusFilter || null
  );

  const handleJobChange = useCallback(
    (row: GenerationJobRow) => {
      const patch = <T extends GenerationJob>(job: T): T => ({
        ...job,
        status: row.status,
        error_code: row.error_code,
        error_message: row.error_message,
        started_at: row.started_at ?? job.started_at,
        completed_at: row.completed_at ?? job.completed_at,
      });

      // Patch every cached list (filters use separate query keys) immediately.
      queryClient.setQueriesData<JobListPage>({ queryKey: ["generations", projectId] }, (previous) => {
        if (!previous) return previous;
        return {
          ...previous,
          items: previous.items.map((job) => (job.id === row.id ? patch(job) : job)),
        };
      });

      queryClient.setQueryData<GenerationJob>(["generation", row.id], (previous) =>
        previous ? patch(previous) : previous
      );

      // Outputs only exist after a terminal transition; refetch to collect them.
      if (TERMINAL_JOB_STATUSES.has(row.status)) {
        queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
        queryClient.invalidateQueries({ queryKey: ["generation", row.id] });
      }
    },
    [projectId, queryClient]
  );

  const realtimeState = useJobRealtime(projectId, handleJobChange, realtimeTimeoutMs);
  const poll = realtimeState === "disconnected";
  const connection = connectionLabel(realtimeState);
  const jobs = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-[#A995FF]" />
          <h2 className="text-sm font-semibold text-[#E8EAF0]">Job history</h2>
          <span
            className="inline-flex items-center gap-1.5 rounded-full border border-[#262A35] bg-[#14161C] px-2 py-0.5 text-[10px] text-[#9AA1B2]"
            aria-live="polite"
          >
            <span className={`h-1.5 w-1.5 rounded-full ${connection.className}`} />
            {connection.text}
          </span>
          {isFetching && !isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-[#9AA1B2]" />}
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="job-status-filter" className="text-xs text-[#9AA1B2]">
            Status
          </label>
          <select
            id="job-status-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="px-2.5 py-1.5 rounded-lg bg-[#14161C] border border-[#262A35] text-xs text-[#E8EAF0] focus:outline-none focus:ring-2 focus:ring-[#7C5CFF]"
          >
            {STATUS_FILTERS.map((filter) => (
              <option key={filter.value || "all"} value={filter.value}>
                {filter.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => refetch()}
            aria-label="Refresh job history"
            className="p-1.5 rounded-lg bg-[#14161C] border border-[#262A35] text-[#9AA1B2] hover:text-[#E8EAF0] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-[#262A35] bg-[#14161C] p-12 text-sm text-[#9AA1B2]">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading jobs…
        </div>
      )}

      {isError && (
        <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-center space-y-2">
          <AlertCircle className="w-6 h-6 text-red-400 mx-auto" />
          <p className="text-sm text-red-300">
            {error instanceof Error ? error.message : "Failed to load job history"}
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="text-xs font-medium text-[#E8EAF0] underline underline-offset-2"
          >
            Try again
          </button>
        </div>
      )}

      {!isLoading && !isError && jobs.length === 0 && (
        <div className="rounded-2xl border border-dashed border-[#262A35] bg-[#14161C] p-12 text-center space-y-1">
          <p className="text-sm font-medium text-[#E8EAF0]">No generation jobs yet</p>
          <p className="text-xs text-[#9AA1B2]">
            Use the Generation Composer to create your first image or video.
          </p>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="grid gap-3 xl:grid-cols-2">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              projectId={projectId}
              poll={poll}
              onUseAsInput={onUseAsInput}
            />
          ))}
        </div>
      )}
    </div>
  );
}
