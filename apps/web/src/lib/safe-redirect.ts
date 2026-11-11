export const DEFAULT_AUTH_DESTINATION = "/projects";

/**
 * Normalize a post-login destination so it can only ever point inside this app.
 *
 * Rejecting protocol-relative (`//evil.com`), absolute, and backslash-prefixed
 * values prevents the `redirectedFrom` / `next` query params from being used as
 * an open redirect.
 */
export function safeRedirectPath(
  value: string | null | undefined,
  fallback: string = DEFAULT_AUTH_DESTINATION
): string {
  if (!value) return fallback;
  if (!value.startsWith("/")) return fallback;
  if (value.startsWith("//") || value.startsWith("/\\")) return fallback;
  if (/[\r\n]/.test(value)) return fallback;
  // Avoid bouncing between auth pages after a successful sign in.
  if (value.startsWith("/login") || value.startsWith("/auth/")) return fallback;
  return value;
}
