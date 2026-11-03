import * as Sentry from "@sentry/nextjs";

let initialized = false;

/**
 * Initialize the browser Sentry SDK when a DSN is configured.
 *
 * Sentry is optional in local development and tests: with no
 * `NEXT_PUBLIC_SENTRY_DSN` every helper below is a no-op, so the app never
 * makes network calls or requires a Sentry account.
 */
export function initSentry(): boolean {
  if (initialized) {
    return true;
  }

  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) {
    return false;
  }

  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE,
    tracesSampleRate: Number(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
    ),
  });
  initialized = true;
  return true;
}

/** Report an exception with optional structured context. */
export function captureException(
  error: unknown,
  context?: Record<string, unknown>,
): void {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
    return;
  }
  initSentry();
  Sentry.captureException(error, context ? { extra: context } : undefined);
}
