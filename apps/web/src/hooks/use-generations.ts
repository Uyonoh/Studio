import { useMutation, useQueryClient } from "@tanstack/react-query";
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
