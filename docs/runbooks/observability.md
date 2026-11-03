# Observability runbook

This runbook covers Sentry error reporting, structured job-transition logs,
the admin stats endpoint, dashboards, and alert rules. Everything is optional
in local development: when `SENTRY_DSN` is empty the API and worker skip
initialisation, and when `NEXT_PUBLIC_SENTRY_DSN` is empty the web app does the
same. No code path requires a Sentry account.

## 1. Services and environment variables

| Service | SDK | Required variables | Optional |
| --- | --- | --- | --- |
| API (`apps/api`) | `sentry-sdk[fastapi]` | `SENTRY_DSN` | `SENTRY_RELEASE`, `SENTRY_TRACES_SAMPLE_RATE` |
| Worker (`apps/worker`) | `sentry-sdk` | `SENTRY_DSN` | `SENTRY_RELEASE`, `SENTRY_TRACES_SAMPLE_RATE` |
| Web (`apps/web`) | `@sentry/nextjs` | `NEXT_PUBLIC_SENTRY_DSN` | `NEXT_PUBLIC_SENTRY_ENVIRONMENT`, `NEXT_PUBLIC_SENTRY_RELEASE`, `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` |

Shared variables:

- `ENVIRONMENT` — `local`, `staging`, or `production`. Used as the Sentry
  environment for the API and worker.
- `SENTRY_RELEASE` — explicit release tag. When unset, the API/worker fall back
  to `GIT_SHA`, `RENDER_GIT_COMMIT`, then `VERCEL_GIT_COMMIT_SHA`.
- `ADMIN_USER_IDS` — comma-separated Supabase user IDs allowed to call
  `GET /v1/admin/stats`. Empty denies everyone.

Use **separate Sentry projects** for `studio-api`, `studio-worker`, and
`studio-web` so quotas, alerts, and ownership are independent. Give each
project a DSN and store it as a secret in the deployment platform. Never put
the API/worker DSN in browser code; the web app uses the `NEXT_PUBLIC_`
variable, which is intentionally public.

### Source maps

Source-map upload is **not** configured yet. `next.config.mjs` does not wrap the
config in `withSentryConfig`, so web stack traces are minified until CI adds an
upload step (tracked for T7.4). Do not enable `hideSourceMaps` before uploads
work. Python services ship readable tracebacks without source maps.

## 2. What is captured

### API

- `create_app()` calls `init_sentry(service="api", ...)` once at import.
- A middleware assigns `X-Request-ID` (or honours an incoming one), stores it on
  `request.state.request_id`, and tags the Sentry scope with the request path
  and method.
- After JWT verification, `auth.py` sets `request.state.user_id` and the Sentry
  user context.
- The 500 handler reports the exception with request ID, path, method, and user
  ID. 4xx responses are expected client errors and are not reported.
- FastAPI request traces are sampled at `SENTRY_TRACES_SAMPLE_RATE` (default
  `0.1`).

### Worker

- `startup()` calls `init_sentry(service="worker", ...)`.
- `run_generation` and `finalize_generation` set a contextvar with `job_id`,
  `provider`, `model`, and `status`. Every `JobStateMachine.transition` emits a
  structured `job_transition` log line using that context, and provider/asset
  failures are sent to Sentry with the same tags.
- The contextvar is per async task, so concurrent ARQ jobs do not leak context
  into each other.

### Structured log line

Every state transition logs one line:

```
job_transition queued -> submitting
  event=job_transition
  job_id=<uuid>
  provider=<provider id>
  model=<model slug>
  status=<new status>
  from_status=<previous status>
  duration_ms=<ms since queued_at>
  error_code=<code or null>
```

Log-based metrics can count transitions by `status`, compute time-in-state from
`duration_ms`, and group failures by `provider` / `model`.

### Web

- `SentryInit` runs at client-bundle load and calls `initSentry()`; it renders
  nothing.
- `ErrorBoundary.componentDidCatch` reports the error with the React component
  stack. Without a DSN the helper returns immediately.

## 3. Admin stats endpoint

```
GET /v1/admin/stats
Authorization: Bearer <supabase access token>
```

The caller's `sub` must appear in `ADMIN_USER_IDS`; everyone else gets `403`
problem+json. The response contains:

```json
{
  "generated_at": "2026-11-03T20:00:00+00:00",
  "queue": { "depth": 3, "oldest_age_seconds": 42.1 },
  "failures": {
    "window_minutes": 15,
    "failed": 2,
    "completed": 40,
    "failure_rate": 0.05
  },
  "time_in_state": [
    { "status": "queued", "avg_seconds": 4.2, "samples": 120 }
  ],
  "durations": {
    "window_hours": 24,
    "completed_jobs": 300,
    "avg_total_seconds": 41.7,
    "avg_queue_seconds": 3.1,
    "avg_run_seconds": 35.9
  },
  "providers": [
    {
      "provider_id": "replicate",
      "jobs": 120,
      "failed": 3,
      "error_rate": 0.025,
      "avg_latency_seconds": 28.4,
      "cost_credits": 120.0
    }
  ]
}
```

`time_in_state` and `durations` use a 24-hour window. `failures` uses the last
15 minutes of `completed_at`. `providers.cost_credits` sums reserved credits for
succeeded jobs. The endpoint reads directly from Postgres and is safe to poll
once per minute.

## 4. Verifying reporting (forced errors)

Run these against a staging deployment after setting the DSNs. Delete the test
events from Sentry afterwards.

### API

1. `SENTRY_DSN` and `ENVIRONMENT=staging` are set; the API logs
   `Sentry enabled for API` at startup.
2. Add a temporary route that raises:

   ```python
   @app.get("/v1/_debug/sentry")
   async def _debug_sentry() -> None:
       raise RuntimeError("T7.2 forced API error")
   ```

3. `curl -i https://api.staging.example.com/v1/_debug/sentry` returns `500`
   problem+json with an `X-Request-ID` header.
4. Sentry shows one event tagged `service=api` with the same `request_id`, the
   request path, and the release. Remove the route.

Alternatively, call any endpoint with a deliberately broken DB pool in a
non-production environment and confirm the 500 handler reports it.

### Worker

1. Set `SENTRY_DSN` for the worker dyno and confirm
   `Sentry enabled for worker` in startup logs.
2. Enqueue a job for a model whose provider adapter raises on submit, or
   temporarily add `raise RuntimeError("T7.2 forced worker error")` at the top
   of `run_generation`.
3. The job transitions to `failed`; Sentry shows one event tagged
   `service=worker`, `job_id`, `provider`, and `model`. Revert the change.

### Web

1. Set `NEXT_PUBLIC_SENTRY_DSN` and rebuild the web app (public env vars are
   inlined at build time).
2. Add a temporary client component that throws during render inside the
   `ErrorBoundary`, or use the browser console:
   `Sentry.captureException(new Error("T7.2 forced web error"))` if the SDK is
   exposed in staging.
3. Sentry shows one event tagged `service=web` with the release. Remove the
   component.

## 5. Dashboard

Create one Sentry/Postgres dashboard with these panels:

| Panel | Source | Notes |
| --- | --- | --- |
| Queue depth | `admin/stats` → `queue.depth` | Current queued jobs. |
| Oldest queued age | `admin/stats` → `queue.oldest_age_seconds` | Leading indicator of a stuck worker. |
| Failure rate (15 min) | `admin/stats` → `failures.failure_rate` | Alert above 20%. |
| Avg time in state | `admin/stats` → `time_in_state` | Per-status, 24 h. |
| End-to-end duration | `admin/stats` → `durations` | Queue vs run time split. |
| Provider error rate | `admin/stats` → `providers[].error_rate` | Per provider, 24 h. |
| Provider latency | `admin/stats` → `providers[].avg_latency_seconds` | Compare against provider SLA. |
| Cost per job | `admin/stats` → `providers[].cost_credits / jobs` | Credits, not currency. |
| Error events | Sentry issues | Group by service and release. |

Poll `admin/stats` from the dashboard service with an admin token stored as a
secret. Do not expose the token to the browser.

## 6. Alert rules

Configure these in Sentry (error alerts) and in the metrics backend (threshold
alerts). Route them to the on-call channel.

| Alert | Condition | Severity | Action |
| --- | --- | --- | --- |
| Stuck jobs | `queue.oldest_age_seconds > 600` for 5 min | High | Check worker health, Redis connectivity, and reconciler logs. |
| Failure rate spike | `failures.failure_rate > 0.20` over 15 min with `completed >= 20` | High | Inspect Sentry provider tags and provider status pages. |
| Queue growing | `queue.depth` increasing for 15 min and `> 50` | Medium | Scale workers; check provider concurrency limits. |
| Provider errors | `providers[].error_rate > 0.25` over 1 h | Medium | Fail over or disable the model; notify the provider. |
| API 5xx | Sentry issue rate for `service=api` above baseline | High | Check release, DB pool, and recent deploys. |
| Worker crash loop | Sentry `service=worker` events with the same fingerprint > 5 in 10 min | High | Roll back the worker release; inspect job IDs. |
| Web error spike | Sentry `service=web` events above baseline after a deploy | Medium | Roll back or disable the affected route. |

Alert noise control:

- Ignore expected 4xx responses; only 5xx and unhandled exceptions page.
- Group worker alerts by `job_id` so one poisoned job does not page repeatedly.
- Use a 10-minute resolve window for transient provider outages.
- Add a maintenance mute during planned provider migrations.

## 7. Release tagging and rollback

- CI must export `GIT_SHA` (or set `SENTRY_RELEASE`) for API and worker builds.
  Vercel sets `VERCEL_GIT_COMMIT_SHA` for the web build; pass it through as
  `NEXT_PUBLIC_SENTRY_RELEASE`.
- Every event and trace carries the release, so "regression in release X" is a
  one-click filter in Sentry.
- On rollback, redeploy the previous image/commit; Sentry continues to accept
  events with the older release. Do not delete releases — they are needed to
  compare regressions.
- The admin stats endpoint has no release dimension; correlate spikes with the
  deploy timeline in Sentry.

## 8. Incident checklist

1. Open `GET /v1/admin/stats`; record queue depth, oldest age, failure rate,
   and per-provider error rates.
2. Open Sentry and filter by `service`, `release`, and `environment`.
3. For stuck jobs: check worker logs for `job_transition` lines and the
   reconciler; confirm Redis and Postgres health via `/readyz`.
4. For provider failures: check the provider status page, then disable the
   model in `public.models` or lower its concurrency.
5. For a bad deploy: roll back and confirm the failure rate returns to baseline.
6. After the incident: add the root cause and any new alert to this runbook,
   and record limit changes in `docs/QUESTIONS.md`.
