import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@sentry/nextjs", () => ({
  init: vi.fn(),
  captureException: vi.fn(),
}));

import * as Sentry from "@sentry/nextjs";
import { captureException } from "@/lib/sentry";

describe("Sentry client helper", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("is a no-op when no DSN is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "");

    captureException(new Error("boom"));

    expect(Sentry.init).not.toHaveBeenCalled();
    expect(Sentry.captureException).not.toHaveBeenCalled();
  });

  it("initializes and reports the exception with context when a DSN is set", () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://key@sentry.example/1");
    vi.stubEnv("NEXT_PUBLIC_SENTRY_ENVIRONMENT", "test");
    vi.stubEnv("NEXT_PUBLIC_SENTRY_RELEASE", "abc123");

    captureException(new Error("boom"), { jobId: "job-1" });

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://key@sentry.example/1",
        environment: "test",
        release: "abc123",
      }),
    );
    expect(Sentry.captureException).toHaveBeenCalledWith(expect.any(Error), {
      extra: { jobId: "job-1" },
    });
  });
});
