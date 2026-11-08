"use client";

import { initSentry } from "@/lib/sentry";

// Initialize once when the client bundle loads. No-op without a DSN.
initSentry();

/** Invisible component that keeps Sentry initialization in the root layout. */
export function SentryInit(): null {
  return null;
}
