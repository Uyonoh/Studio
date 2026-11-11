import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getApiClient } from "@/lib/api";
import { asProblem, problemCode, problemMessage, type ProblemDetails } from "@/lib/problem";

export interface GenerationOutput {
  asset_id: string;
  kind: string;
  mime_type: string | null;
  signed_url: string | null;
  thumbnail_url: string | null;
}

export interface GenerationJob {
  id: string;
  project_id: string;
  workspace_id: string;
  status: string;
  task_type: string;
  prompt: string | null;
  params: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
  outputs: GenerationOutput[];
  links: Record<string, string>;
}

export interface GenerationInput {
  asset_id: string;
  role: string;
  [key: string]: unknown;
}

export interface SubmitGenerationPayload {
  model: string;
  task_type: string;
  prompt?: string | null;
  negative_prompt?: string | null;
  inputs: GenerationInput[];
  params: Record<string, unknown>;
}

/** Error carrying the parsed problem body, status, and Retry-After value. */
export class GenerationSubmitError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryAfterSeconds: number | null;
  readonly problem: ProblemDetails;

  constructor(
    message: string,
    status: number,
    code: string,
    retryAfterSeconds: number | null,
    problem: ProblemDetails
  ) {
    super(message);
    this.name = "GenerationSubmitError";
    this.status = status;
    this.code = code;
    this.retryAfterSeconds = retryAfterSeconds;
    this.problem = problem;
  }
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null;
}

/**
 * Submit a generation job with a caller-supplied idempotency key.
 *
 * The key is owned by the composer so retrying the same submission reuses it
 * and the backend deduplicates instead of charging twice.
 */
export function useSubmitGeneration(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      payload,
      idempotencyKey,
    }: {
      payload: SubmitGenerationPayload;
      idempotencyKey: string;
    }): Promise<GenerationJob> => {
      const client = getApiClient();
      const res = await client.POST("/v1/projects/{project_id}/generations", {
        params: {
          path: { project_id: projectId },
          header: { "Idempotency-Key": idempotencyKey },
        },
        body: payload,
      });

      if (res.error || !res.data) {
        const problem = asProblem(res.error);
        throw new GenerationSubmitError(
          problemMessage(res.error, "Failed to submit generation"),
          res.response.status,
          problemCode(res.error, `HTTP_${res.response.status}`),
          parseRetryAfter(res.response.headers.get("Retry-After")),
          problem
        );
      }

      return res.data as unknown as GenerationJob;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    },
  });
}

/** Generate an idempotency key, using the platform UUID generator when available. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface JobListPage {
  items: GenerationJob[];
  next_cursor: string | null;
}

export const ACTIVE_JOB_STATUSES = new Set(["queued", "submitting", "running", "finalizing"]);
export const TERMINAL_JOB_STATUSES = new Set(["succeeded", "failed", "canceled"]);

export function isActiveJobStatus(status: string): boolean {
  return ACTIVE_JOB_STATUSES.has(status);
}

/** List generation jobs for a project, optionally filtered by status. */
export function useProjectJobs(projectId?: string | null, status?: string | null) {
  return useQuery({
    queryKey: ["generations", projectId, status ?? "all"],
    queryFn: async (): Promise<JobListPage> => {
      const client = getApiClient();
      const res = await client.GET("/v1/projects/{project_id}/generations", {
        params: {
          path: { project_id: projectId as string },
          query: { status: status || undefined, limit: 50 },
        },
      });

      if (res.error) {
        throw new Error(problemMessage(res.error, "Failed to load generation jobs"));
      }

      return res.data as unknown as JobListPage;
    },
    enabled: !!projectId,
  });
}

/**
 * Fetch a single job, polling with 2s → 10s backoff while enabled.
 *
 * Used as the Realtime fallback: the worker/webhook still update Postgres, so
 * polling recovers the same state without a live channel.
 */
export function useLiveJob(jobId?: string | null, poll = false) {
  return useQuery({
    queryKey: ["generation", jobId],
    queryFn: async (): Promise<GenerationJob> => {
      const client = getApiClient();
      const res = await client.GET("/v1/generations/{job_id}", {
        params: { path: { job_id: jobId as string } },
      });

      if (res.error) {
        throw new Error(problemMessage(res.error, "Failed to load generation job"));
      }

      return res.data as unknown as GenerationJob;
    },
    enabled: !!jobId && poll,
    refetchInterval: poll
      ? (query) => Math.min(2000 * Math.pow(1.5, query.state.dataUpdateCount), 10_000)
      : false,
  });
}

function invalidateJobQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
  jobId?: string
) {
  queryClient.invalidateQueries({ queryKey: ["generations", projectId] });
  queryClient.invalidateQueries({ queryKey: ["credits"] });
  if (jobId) {
    queryClient.invalidateQueries({ queryKey: ["generation", jobId] });
  }
}

/** Cancel a queued or running job. */
export function useCancelGeneration(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (jobId: string) => {
      const client = getApiClient();
      const res = await client.POST("/v1/generations/{job_id}/cancel", {
        params: { path: { job_id: jobId } },
      });
      if (res.error) {
        throw new GenerationSubmitError(
          problemMessage(res.error, "Failed to cancel generation"),
          res.response.status,
          problemCode(res.error, `HTTP_${res.response.status}`),
          null,
          asProblem(res.error)
        );
      }
      return res.data as unknown as GenerationJob;
    },
    onSuccess: (job, jobId) => {
      toast.success("Generation canceled");
      invalidateJobQueries(queryClient, projectId, jobId);
      if (job?.id) {
        queryClient.setQueryData(["generation", job.id], job);
      }
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to cancel generation");
    },
  });
}

/** Re-run a failed or canceled job with the same inputs. */
export function useRetryGeneration(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (jobId: string) => {
      const client = getApiClient();
      const res = await client.POST("/v1/generations/{job_id}/retry", {
        params: { path: { job_id: jobId } },
      });
      if (res.error) {
        throw new GenerationSubmitError(
          problemMessage(res.error, "Failed to retry generation"),
          res.response.status,
          problemCode(res.error, `HTTP_${res.response.status}`),
          null,
          asProblem(res.error)
        );
      }
      return res.data as unknown as GenerationJob;
    },
    onSuccess: (job, originalJobId) => {
      toast.success("Retry queued");
      invalidateJobQueries(queryClient, projectId, originalJobId);
      if (job?.id) {
        queryClient.setQueryData(["generation", job.id], job);
      }
    },
    onError: (error: Error) => {
      toast.error(error.message || "Failed to retry generation");
    },
  });
}
