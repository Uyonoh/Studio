/** Helpers for reading RFC 7807 problem+json payloads returned by the API. */

export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: unknown;
  error_code?: string;
}

interface ValidationIssue {
  loc?: Array<string | number>;
  msg?: string;
}

/** Coerce an unknown error body into a problem-details shape. */
export function asProblem(error: unknown): ProblemDetails {
  if (error && typeof error === "object") {
    return error as ProblemDetails;
  }
  return {};
}

/** Extract a human-readable message from a problem payload. */
export function problemMessage(error: unknown, fallback: string): string {
  const problem = asProblem(error);

  if (typeof problem.detail === "string" && problem.detail.trim()) {
    return problem.detail;
  }
  if (Array.isArray(problem.detail) && problem.detail.length > 0) {
    const first = problem.detail[0] as ValidationIssue;
    if (first?.msg) return first.msg;
  }
  if (typeof problem.title === "string" && problem.title.trim()) {
    return problem.title;
  }
  return fallback;
}

/** Extract a stable error code, defaulting to the HTTP-derived value. */
export function problemCode(error: unknown, fallback = "UNKNOWN_ERROR"): string {
  const problem = asProblem(error);
  return problem.error_code || fallback;
}
