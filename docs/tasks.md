# tasks.md — AI Content Studio MVP

> Execution plan for an AI coding agent (Antigravity). Work **one task at a time, in order**, respecting `Depends`.
> Source of truth for architecture, schema and API: `docs/design.md` (the Technical Design Document). **Save the TDD there before starting T0.1.** If this file and the TDD disagree, stop and ask.

---

## 0. How to use this file (agent instructions)

1. Pick the first task whose `Depends` are all `[x]`. Mark it `[~]` while working, `[x]` when its **DoD** is fully met.
2. Do only what the task says. No extra features, no drive-by refactors. Note out-of-scope ideas in `docs/BACKLOG.md`.
3. Write tests **with** the code, not after. A task is not done until its `Verify` commands pass.
4. Commit per task: `feat(T3.5): generations endpoints` (Conventional Commits). Keep commits small and buildable.
5. If blocked or a requirement is ambiguous, write the question in `docs/QUESTIONS.md`, make the safest minimal assumption, record it, and continue.
6. Never commit secrets. Never use the Supabase service-role key in browser code.
7. Before finishing a task, re-read its DoD line by line and confirm each item.

### Global conventions

| Area | Rule |
|---|---|
| Python | 3.12, `uv` for deps, `ruff` (lint+format), `mypy --strict`, `pytest` + `pytest-asyncio`. Async everywhere in API/worker. Pydantic v2. |
| TypeScript | Node 20, `pnpm`, Next.js App Router, strict TS, ESLint, Vitest, Playwright. |
| DB | Supabase CLI migrations only (`supabase/migrations/*.sql`), never hand-edit the live DB. Every table has RLS enabled. |
| IDs / time | UUID v4 primary keys; all timestamps `timestamptz` in UTC. |
| Errors | API errors use RFC 7807 problem+json with stable `error_code`. |
| Logging | Structured JSON; always include `request_id` and, where relevant, `job_id`. |
| Layering | `apps/api` and `apps/worker` depend on `packages/studio_core`; **neither imports the other**. Routers are thin; logic lives in `studio_core` services. |
| Config | All config via env vars parsed by one `Settings` class (`pydantic-settings`). Provide `.env.example`. |

### Global Definition of Done (applies to every task)

- [ ] Code compiles/type-checks: `ruff check`, `ruff format --check`, `mypy --strict` (Python) and `tsc --noEmit`, `eslint` (TS) pass for touched packages.
- [ ] New logic has unit tests; new endpoints have integration tests; coverage for touched modules ≥ 85%.
- [ ] No secrets, TODOs without ticket reference, or commented-out code.
- [ ] Public functions/classes have docstrings; non-obvious decisions get a short comment or ADR.
- [ ] `README`/docs updated if setup, env vars, or behavior changed.
- [ ] CI is green on the branch.

### Target repo layout

```text
apps/
  web/            Next.js
  api/            FastAPI (routers, deps, middleware)
  worker/         ARQ worker entrypoints
packages/
  studio_core/    settings, db, models, services, state machine, repositories
  studio_providers/ adapters + registry + FakeProvider
  studio_media/   thumbnails/metadata/ffmpeg helpers
  api-client/     generated TS client
supabase/         config.toml, migrations/, seed.sql, tests/ (pgTAP)
infra/            render.yaml, docker-compose.yml
docs/             design.md, adr/, runbooks/, BACKLOG.md, QUESTIONS.md
.github/workflows/
```

### Environment variables (reference)

```text
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
DATABASE_URL                # direct Postgres URL (worker/API)
REDIS_URL
STORAGE_BUCKET=media
PUBLIC_API_URL              # used to build webhook URLs
WEBHOOK_SIGNING_SECRET      # per-job token derivation
REPLICATE_API_TOKEN, REPLICATE_WEBHOOK_SECRET
FAL_KEY
SENTRY_DSN (optional), LOG_LEVEL
ENVIRONMENT=local|staging|production
```

---

## PHASE 0 — Foundation

### [x] T0.1 Monorepo scaffold
**Depends:** none
**Goal:** Empty-but-buildable monorepo with tooling for Python and TypeScript.
**Steps**
1. Init git repo, `.gitignore`, `.editorconfig`, `LICENSE` (placeholder), `README.md` (project overview + link to `docs/design.md`).
2. Create the folders in "Target repo layout". Python: root `pyproject.toml` as a `uv` workspace with members `apps/api`, `apps/worker`, `packages/studio_core`, `packages/studio_providers`, `packages/studio_media`. Each member has its own `pyproject.toml` and `src/<pkg>/__init__.py`.
3. TS: `pnpm-workspace.yaml` with `apps/web`, `packages/api-client`. (Next.js app is created in T6.1; leave placeholder `package.json`.)
4. Configure `ruff` (line length 100, isort rules), `mypy` strict, `pytest` (asyncio mode auto) at the root.
5. Add `Makefile` with targets: `setup`, `lint`, `typecheck`, `test`, `dev-api`, `dev-worker`, `dev-web`, `db-reset`.
6. Add `pre-commit` config (ruff, ruff-format, gitleaks).
**DoD**
- [x] `make setup && make lint && make typecheck && make test` succeed on a clean clone (tests may be a single smoke test per package).
- [x] `import studio_core, studio_providers, studio_media` works from `apps/api` and `apps/worker` environments.
- [x] `docs/design.md` exists and is the TDD.
**Verify:** `make lint typecheck test`

### [x] T0.2 Local dev environment
**Depends:** T0.1
**Goal:** One command brings up Postgres/Auth/Storage (Supabase local) and Redis.
**Steps**
1. `supabase init`; commit `supabase/config.toml`. Enable Realtime and Storage in config.
2. `infra/docker-compose.yml` with `redis:7` (port 6379, healthcheck). Supabase runs through `supabase start`.
3. `.env.example` with all variables from the reference list; `scripts/dev-up.sh` runs `supabase start` + `docker compose up -d redis` and prints local URLs/keys.
4. Document in `README.md`: prerequisites (Docker, Supabase CLI, uv, pnpm), first-run steps.
**DoD**
- [x] `scripts/dev-up.sh` works from a clean machine following the README only.
- [x] `redis-cli -u $REDIS_URL ping` returns `PONG`; Supabase Studio reachable locally.
**Verify:** run the script; curl `http://127.0.0.1:54321/rest/v1/` with anon key returns 200.

### [x] T0.3 CI skeleton
**Depends:** T0.1
**Goal:** GitHub Actions runs lint/type/test on every PR.
**Steps**
1. `.github/workflows/ci.yml` with jobs: `python` (uv sync, ruff, mypy, pytest with Redis service container), `web` (pnpm install, lint, tsc, vitest — skip if web not yet created), `secrets-scan` (gitleaks).
2. Cache `uv` and `pnpm` stores. Cancel superseded runs (`concurrency`).
3. Add PR template (checklist = Global DoD) and CODEOWNERS.
**DoD**
- [x] A PR with a deliberate lint error fails CI; fixing it turns CI green.
- [x] Run time under 6 minutes on a cold cache.
**Verify:** open a draft PR.

---

## PHASE 1 — Database

> Copy DDL from TDD §3.2/§3.3 into migrations. Split into the migrations below; do not rewrite the design without recording an ADR.

### [x] T1.1 Migration: identity, tenancy, projects
**Depends:** T0.2
**Goal:** `profiles`, `workspaces`, `workspace_members`, `projects`, `workspace_role` enum, auto-provisioning.
**Steps**
1. Migration `0001_identity.sql` with the tables from TDD §3.2 (identity & tenancy block).
2. Add trigger on `auth.users` insert: create `profiles` row, a default workspace named "<display_name>'s Workspace", and an `owner` membership.
3. Add `updated_at` trigger function and attach to `projects`.
4. Add `is_member(ws, min_role)` function (security definer, `set search_path = public`). **Check the enum ordering comparison actually yields the intended semantics** and write a test proving `viewer` cannot satisfy `editor`.
5. Enable RLS + policies for `profiles` (self read/update), `workspaces`, `workspace_members`, `projects` per TDD §3.3.
**DoD**
- [x] `supabase db reset` applies cleanly.
- [x] Creating a user via Supabase Auth yields profile + workspace + owner membership automatically.
- [x] Policies verified in T1.4 tests (stub tests may be added here).
**Verify:** `supabase db reset && supabase test db`

### [x] T1.2 Migration: models, assets, jobs, ledger
**Depends:** T1.1
**Goal:** All MVP generation tables.
**Steps**
1. `0002_generation.sql`: `providers`, `models`, `asset_kind`/`asset_origin` enums, `assets`, `job_status` enum, `generation_jobs`, `input_role` enum, `job_inputs`, `job_events`, `credit_ledger`, plus all indexes and FKs from TDD §3.2 (including the deferred FKs `projects.cover_asset_id` and `assets.source_job_id`).
2. RLS: members can `select` on `assets`, `generation_jobs`, `job_inputs`, `job_events` (events: admin+ only), `credit_ledger` (admin+). No client insert/update on jobs, events, ledger. Editors may insert/update/soft-delete `assets` where `origin='upload'`.
3. Add a SQL view `workspace_credit_balance` = `sum(delta)` per workspace.
4. Add DB-level guard: `check` that `generation_jobs.attempt <= max_attempts`.
5. Enable Realtime publication for `generation_jobs` only.
**DoD**
- [x] Reset applies cleanly; all indexes present (`\d+` check in a test).
- [x] Unique `(workspace_id, idempotency_key)` and unique `provider_job_id` enforced (test inserts a duplicate and expects failure).
- [x] `generation_jobs` is in the `supabase_realtime` publication.
**Verify:** `supabase db reset && supabase test db`

### [x] T1.3 Storage bucket, policies, seed data
**Depends:** T1.2
**Goal:** Private `media` bucket scoped by workspace path; seed providers/models.
**Steps**
1. Migration `0003_storage.sql`: create private bucket `media` (file size limit 500 MB, allowed MIME `image/*`, `video/*`). Storage policies: select/insert allowed when `is_member(first_path_segment::uuid, 'editor')` (select allowed for viewer+).
2. `supabase/seed.sql`: providers (`replicate`, `fal`, `fake`), and models for the `fake` provider covering all four task types, with realistic `input_schema` JSON Schemas (prompt, aspect_ratio enum, seed int, duration_s for video) and `cost_credits`.
3. Seed a dev user via a script (`scripts/seed_dev_user.py`) that signs up `dev@example.com` through the Auth admin API and grants 1000 credits via `credit_ledger`.
**DoD**
- [x] A member can upload/download only under their workspace prefix; non-members get denied (tested).
- [x] `select * from models` shows fake models for all four task types.
**Verify:** `supabase db reset && python scripts/seed_dev_user.py && supabase test db`

### [x] T1.4 RLS and constraint tests (pgTAP)
**Depends:** T1.3
**Goal:** Automated proof of tenant isolation.
**Steps**
1. `supabase/tests/rls_*.sql` using pgTAP. Fixtures: two workspaces A and B; users: A-owner, A-editor, A-viewer, B-owner.
2. Cases: B-owner cannot read A's projects/assets/jobs; viewer cannot insert project; editor can; nobody can write `generation_jobs`/`credit_ledger` with the anon/authenticated role; storage path isolation.
**DoD**
- [x] ≥ 20 assertions, all passing; run in CI (add job `db-tests`).
**Verify:** `supabase test db`

---

## PHASE 2 — Core domain (`studio_core`, `studio_providers`)

### [x] T2.1 Settings, DB access, repositories
**Depends:** T1.3
**Goal:** Typed config and async data access.
**Steps**
1. `Settings` (pydantic-settings) with all env vars; fail fast with clear messages.
2. Async DB layer using `asyncpg` pool (`create_pool` helper, transaction context manager). Use plain SQL in repository classes (`JobRepository`, `AssetRepository`, `ProjectRepository`, `ModelRepository`, `LedgerRepository`, `EventRepository`) returning Pydantic models.
3. Pydantic domain models mirroring tables; enums for `JobStatus`, `TaskType`, `InputRole`, `AssetKind`.
4. Test fixtures: `db` fixture that connects to local Supabase Postgres and wraps each test in a rolled-back transaction.
**DoD**
- [x] CRUD for each repository covered by tests against the local DB.
- [x] No SQL string interpolation (parameterized only); a test greps for f-strings in repository SQL.
**Verify:** `uv run pytest packages/studio_core -q`

### [x] T2.2 Job state machine
**Depends:** T2.1
**Goal:** A single place that governs legal state transitions.
**Steps**
1. `studio_core/state_machine.py` defining the allowed transitions from TDD §5.2 as a dict; `can_transition(from, to)`.
2. `JobService.transition(job_id, expected, new, **fields)` performing a guarded update (`UPDATE ... WHERE id=$1 AND status=$2 RETURNING *`), setting `started_at`/`completed_at` appropriately, and appending a `job_events` row **in the same transaction**. Returns `None` if the guard failed (caller decides what to do).
3. Terminal states are immutable.
**DoD**
- [x] Property-based test (`hypothesis`) shows no illegal transition is ever accepted and terminal states never change.
- [x] Concurrency test: two simultaneous `transition(running→finalizing)` calls — exactly one succeeds.
**Verify:** `uv run pytest packages/studio_core -k state -q`

### [x] T2.3 Provider interface, registry, FakeProvider
**Depends:** T2.1
**Goal:** Provider abstraction and a deterministic fake for all tests/dev.
**Steps**
1. `studio_providers/base.py`: `ProviderRequest`, `ProviderJobRef`, `ProviderStatus` (enum: pending/running/succeeded/failed/canceled + `outputs`, `error`), `WebhookEvent`, `ProviderOutput` (url, mime, kind), and the `GenerationProvider` Protocol from TDD §5.4.
2. `registry.py`: `get_provider(provider_id) -> GenerationProvider`; register via entry in a dict built from Settings (only enable providers whose credentials exist).
3. `fake.py`: `FakeProvider` with configurable latency, failure injection (`fail_rate`, `fail_on_prompt_contains="FAIL"`), webhook simulation (an in-process `trigger_webhook(job)` helper), and outputs served from `packages/studio_providers/fixtures/` (tiny PNG and MP4) via a local HTTP file server fixture.
4. Error taxonomy: `TransientProviderError`, `PermanentProviderError`, `RateLimitedError(retry_after)`.
**DoD**
- [x] A reusable contract test suite (`tests/contract.py`) any adapter can inherit: submit → status → outputs, cancel, bad-input → `PermanentProviderError`, webhook verification (valid/invalid signature).
- [x] `FakeProvider` passes the contract suite.
**Verify:** `uv run pytest packages/studio_providers -q`

### [x] T2.4 Credits service
**Depends:** T2.1
**Goal:** Reserve/refund credits atomically.
**Steps**
1. `CreditService.reserve(workspace_id, job_id, amount)` — inside one transaction lock the workspace's balance (`SELECT ... FOR UPDATE` on `workspaces` row), check balance ≥ amount else raise `InsufficientCredits`, insert negative ledger row (`reason='reserve'`).
2. `refund(job_id)` — idempotent: refund once per job (check existing refund row).
3. `balance(workspace_id)`.
**DoD**
- [x] Concurrency test: 20 parallel reserves against a balance for 10 → exactly 10 succeed, balance never negative.
- [x] Double refund test results in one refund row.
**Verify:** `uv run pytest packages/studio_core -k credit -q`

### [x] T2.5 Generation request validation and job creation
**Depends:** T2.2, T2.3, T2.4
**Goal:** Everything the API does on submit, as a testable service.
**Steps**
1. `GenerationService.create_job(user, project_id, request, idempotency_key)`:
   - Load project → verify membership role ≥ editor.
   - Load model; ensure `enabled` and `task_type` matches.
   - Validate `params` against `model.input_schema` (`jsonschema`), merge `default_params`.
   - Enforce required input roles per task type (`image_to_image`: `init_image`; `image_to_video`: `first_frame`; text tasks: none). Verify all input assets exist, are in the same workspace/project's workspace, and correct `kind`.
   - Enforce per-workspace concurrent active jobs cap (setting, default 5).
   - In one transaction: insert job (`queued`), `job_inputs`, reserve credits. On unique violation of idempotency key return the existing job (same payload) or raise `IdempotencyConflict` if payload differs.
2. Return the job; **enqueueing is the caller's responsibility** (API) so this stays transport-agnostic.
**DoD**
- [x] Tests for each validation failure path with specific `error_code`s (`MODEL_TASK_MISMATCH`, `INVALID_PARAMS`, `MISSING_INPUT`, `INSUFFICIENT_CREDITS`, `CONCURRENCY_LIMIT`, `IDEMPOTENCY_CONFLICT`).
- [x] Replaying the same idempotency key + payload returns the same job without double-charging.
**Verify:** `uv run pytest packages/studio_core -k generation -q`

---

## PHASE 3 — API (`apps/api`)

### [x] T3.1 FastAPI skeleton, auth, errors, middleware
**Depends:** T2.1
**Goal:** App factory with auth and consistent errors.
**Steps**
1. `create_app()` with lifespan (open/close DB pool and Redis).
2. Auth dependency: verify Supabase JWT (HS256 with `SUPABASE_JWT_SECRET`, or JWKS if configured); expose `CurrentUser(id, email)`. Reject expired/invalid with 401 problem+json.
3. Middleware: request ID (`X-Request-ID` in/out), structured access logs, CORS (allow the web origin from env), body-size limit.
4. Exception handlers mapping domain errors → problem+json with `error_code`.
5. `GET /healthz` (liveness) and `GET /readyz` (checks DB + Redis).
**DoD**
- [x] Tests: valid/invalid/expired token; problem+json shape; request ID propagated to logs.
- [x] `uvicorn apps.api.main:app` starts and `/docs` renders.
**Verify:** `uv run pytest apps/api -q`

### [x] T3.2 Workspaces and projects endpoints
**Depends:** T3.1, T1.4
**Goal:** CRUD per TDD §4.1.
**Steps**
1. Routers `workspaces.py`, `projects.py` with Pydantic request/response schemas (`response_model` everywhere).
2. Cursor pagination helper (opaque base64 of `(created_at, id)`), default limit 24, max 100.
3. Soft-archive on `DELETE /v1/projects/{id}`.
**DoD**
- [x] Integration tests: happy path, 403 for non-member, 404 for cross-workspace IDs (don't leak existence), pagination stable across inserts.
**Verify:** `uv run pytest apps/api -k projects -q`

### [x] T3.3 Asset endpoints and uploads
**Depends:** T3.2
**Goal:** Signed upload flow and asset reads.
**Steps**
1. `POST /v1/projects/{id}/assets/uploads` → validate declared MIME/size, create draft asset row (`deleted_at` null but `metadata.status='pending'`), return Supabase signed upload URL and `asset_id`.
2. `POST /v1/assets/{id}/complete` → verify object exists in storage, sniff real MIME with `python-magic`, extract dimensions/duration (`studio_media` — Pillow for images, `ffprobe` for video), generate thumbnail, update row, set `metadata.status='ready'`. Reject and delete mismatched files.
3. `GET /v1/assets/{id}` and list endpoint return signed download URLs (TTL 1 hour) and lineage (`source_job_id`, `parent_asset_id`, inputs of the source job).
4. `DELETE` → soft delete.
5. Implement `studio_media`: `probe_image`, `probe_video`, `make_thumbnail`, `make_poster_frame`. Install `ffmpeg` in the API/worker Docker images.
**DoD**
- [x] Tests with fixture image/video: metadata correct; spoofed extension rejected; oversize rejected.
- [x] Download URLs expire (test with short TTL setting).
**Verify:** `uv run pytest apps/api packages/studio_media -k asset -q`

### [x] T3.4 Models endpoint
**Depends:** T3.1
**Goal:** `GET /v1/models?task_type=` returning enabled models with `input_schema`, `default_params`, `cost_credits`, and which input roles each task needs.
**DoD**
- [x] Disabled models/providers never returned; response cached 60s (`Cache-Control`).
- [x] Test for filtering by `task_type`.
**Verify:** `uv run pytest apps/api -k models -q`

### [x] T3.5 Generation endpoints
**Depends:** T2.5, T3.2, T3.3, T4.0 (queue helper below)
**Goal:** Submit/get/list/cancel/retry per TDD §4.2.
**Steps**
1. Implement `enqueue(queue, task_name, job_id)` in `studio_core/queue.py` (ARQ `create_pool`, `enqueue_job(..., _job_id=str(job_id))` so duplicate enqueues dedupe). *(This is "T4.0": do it here first.)*
2. `POST /v1/projects/{id}/generations` — require `Idempotency-Key` header (400 if missing), call `GenerationService.create_job`, enqueue `run_generation`, return `202` with job + `Location` header. If enqueue fails, mark job `failed` with `ENQUEUE_FAILED` and refund (do not leave orphaned `queued` rows).
3. `GET /v1/generations/{id}` with outputs (assets with signed URLs) and error info. List endpoint with `status` filter and cursor pagination.
4. `POST .../cancel` — transition to `canceled` if not terminal, enqueue `cancel_generation` if `running`, refund.
5. `POST .../retry` — only for `failed`/`canceled`; creates a new job with `parent_job_id`, same inputs (new idempotency key derived server-side).
**DoD**
- [x] Integration tests with a stub queue: 202 shape, validation errors, idempotent replay, cancel/retry rules, cross-workspace denial.
- [x] Enqueue failure path leaves job `failed` and credits refunded (test).
**Verify:** `uv run pytest apps/api -k generations -q`

### [x] T3.6 Provider webhook receiver
**Depends:** T3.5, T2.3
**Goal:** Safe, idempotent webhook ingestion.
**Steps**
1. `POST /internal/webhooks/{provider}/{job_id}?token=...`: verify per-job token (HMAC of `job_id` with `WEBHOOK_SIGNING_SECRET`, constant-time compare) **and** provider signature via `provider.verify_webhook`.
2. Append `job_events(type='webhook', payload=<raw>)`. If the job is not terminal and status is `running`, enqueue `finalize_generation`. Always return `200` quickly for valid but redundant deliveries; `401` for bad signature/token.
3. Never trust provider payload for state; the finalize task re-fetches status via `get_status` when possible.
**DoD**
- [x] Tests: bad signature → 401; duplicate delivery → 200, only one finalize enqueued (dedupe via ARQ job id); unknown job → 404; terminal job → 200 no-op.
**Verify:** `uv run pytest apps/api -k webhook -q`

### [x] T3.7 OpenAPI export and generated client
**Depends:** T3.5
**Goal:** Typed client for the frontend and a breaking-change gate.
**Steps**
1. `scripts/export_openapi.py` writes `docs/openapi.json` deterministically.
2. `packages/api-client`: generate types/client with `openapi-typescript` + `openapi-fetch`; export `createClient(baseUrl, getToken)`.
3. CI: regenerate and fail if `docs/openapi.json` changed but was not committed; add `oasdiff breaking` check against `main`.
**DoD**
- [x] `pnpm --filter api-client build` passes; CI gate demonstrably fails on a deliberate breaking change.
**Verify:** `make openapi && git diff --exit-code docs/openapi.json`

---

## PHASE 4 — Worker (`apps/worker`)

### [x] T4.1 Worker bootstrap and `run_generation`
**Depends:** T3.5 (queue helper), T2.3
**Goal:** Claim a queued job and submit it to the provider.
**Steps**
1. ARQ `WorkerSettings`: functions `run_generation`, `finalize_generation`, `cancel_generation`; cron `reconcile_jobs`; `max_jobs` from env; `job_timeout`; startup/shutdown hooks opening DB pool and Redis; graceful shutdown on SIGTERM.
2. `run_generation(ctx, job_id)`:
   - Guarded transition `queued → submitting`; if guard fails, exit (already claimed/terminal).
   - If `provider_job_id` already set, skip submit and go to polling/waiting (idempotent retry).
   - Resolve inputs to signed URLs (TTL ≥ 1h); build `ProviderRequest`; call `provider.submit` passing webhook URL (`PUBLIC_API_URL/internal/webhooks/...?token=`).
   - Save `provider_job_id`, `started_at`, transition `submitting → running`, set `heartbeat_at`.
3. Error handling: `RateLimitedError` / `TransientProviderError` → `submitting → queued`, `attempt += 1`, re-enqueue with ARQ `defer` (exponential backoff with jitter, base 5s, cap 5m). `PermanentProviderError` or attempts exhausted → `failed` with `error_code`/`error_message`, refund credits.
4. Per-provider concurrency limiter (Redis semaphore) configured via Settings.
**DoD**
- [x] Integration test with FakeProvider: job goes `queued → running` and `provider_job_id` stored.
- [x] Tests: transient error retries then succeeds; permanent error fails + refunds; attempts exhausted fails; second delivery of the same task doesn't double-submit.
**Verify:** `uv run pytest apps/worker -k run_generation -q`

### [x] T4.2 `finalize_generation`
**Depends:** T4.1, T3.3 (studio_media)
**Goal:** Turn provider outputs into owned assets.
**Steps**
1. Guarded transition `running → finalizing` (skip if already finalizing/terminal).
2. `get_status` from provider; if still running (webhook early), revert to `running` and exit; if failed → `failed` + refund.
3. For each output: stream-download (size cap, timeout, content-type check) → upload to `media/{workspace}/{project}/{asset_id}/original.{ext}` → probe metadata → thumbnail (image) or poster frame (video) → insert `assets` (`origin='generated'`, `source_job_id`, `metadata` containing prompt/model/params/seed). Do it in a way that retried finalization doesn't create duplicates (deterministic asset key, e.g. UUIDv5 of `job_id + output_index`).
4. Transition `finalizing → succeeded`, set `completed_at`.
5. On failure: retry up to N times for transient errors, then `failed` + refund.
**DoD**
- [x] Test: image and video outputs end up in storage with correct metadata and thumbnails; assets reference the job.
- [x] Re-running finalize on a finished job is a no-op; re-running mid-failure produces no duplicate assets.
- [x] Oversized/non-media outputs are rejected with `OUTPUT_INVALID`.
**Verify:** `uv run pytest apps/worker -k finalize -q`

### [x] T4.3 Reconciler (safety net)
**Depends:** T4.2
**Goal:** Recover from lost webhooks/crashed workers.
**Steps**
1. Cron every 60s `reconcile_jobs`:
   - `queued` older than 2 min and not present in Redis → re-enqueue.
   - `submitting` with stale `heartbeat_at` (> 3 min) → back to `queued` (attempt+1) or fail if exhausted.
   - `running` older than `min_poll_age` → call `get_status`; if terminal, enqueue `finalize_generation`.
   - Jobs exceeding per-task max runtime (image 10 min, video 30 min, configurable) → `failed` with `TIMEOUT`, attempt provider `cancel`, refund.
   - `finalizing` stale > 5 min → re-enqueue finalize.
2. Use `SELECT ... FOR UPDATE SKIP LOCKED` so multiple reconciler instances don't collide. Limit batch size.
3. On startup, run one reconciliation pass (covers Redis loss).
**DoD**
- [x] Tests (with time travel via injectable clock): each stuck-state scenario above is recovered/failed as specified.
- [x] Two concurrent reconcilers don't process the same job twice.
**Verify:** `uv run pytest apps/worker -k reconcile -q`

### [x] T4.4 `cancel_generation`
**Depends:** T4.1
**Goal:** Best-effort provider cancel.
**Steps:** If job has `provider_job_id`, call `provider.cancel` (swallow "already finished"); record event; ensure credits refunded exactly once; if provider finished anyway, discard outputs (don't create assets).
**DoD**
- [x] Tests: cancel while `running` stops further processing; finalize after cancel is a no-op.
**Verify:** `uv run pytest apps/worker -k cancel -q`

### [x] T4.5 End-to-end backend test
**Depends:** T4.2, T3.6
**Goal:** Prove the whole pipeline without the UI.
**Steps:** Test that boots API (httpx ASGI), worker (in-process ARQ), Redis and local Supabase; creates user/project; uploads an image; submits `image_to_video` via the FakeProvider; triggers fake webhook; asserts job `succeeded`, asset exists, signed URL downloads. Include failure variant (prompt contains `FAIL`).
**DoD**
- [x] Test runs in CI in < 90s and is stable over 20 consecutive runs.
**Verify:** `uv run pytest tests/e2e_backend -q`

---

## PHASE 5 — Real providers

### [x] T5.1 Replicate adapter
**Depends:** T2.3, T4.1
**Goal:** `ReplicateProvider` implementing the Protocol.
**Steps**
1. Use `httpx` against Replicate's predictions API (or the official SDK in async mode). Map `ProviderRequest` → model-specific input via a small per-model mapper registry keyed by `models.provider_model`.
2. Submit with `webhook` URL and `webhook_events_filter=["completed"]`; store prediction ID.
3. `verify_webhook` per Replicate's signing scheme (secret from Settings); `get_status`, `cancel`, `normalize_output` (outputs may be a string or list).
4. Map HTTP 429/5xx → `RateLimitedError`/`TransientProviderError`; 4xx validation → `PermanentProviderError`.
5. Check the provider's current API docs before implementing; do not assume field names from memory.
**DoD**
- [x] Inherits the contract test suite using recorded fixtures (`respx`/`vcrpy`), no live calls in CI.
- [x] A manual smoke script `scripts/smoke_provider.py replicate` generates one real image (documented, not in CI).
**Verify:** `uv run pytest packages/studio_providers -k replicate -q`

### [x] T5.2 Fal.ai adapter
**Depends:** T5.1 (reuse patterns)
**Goal:** `FalProvider` using fal's queue API (submit → status → result, with webhook URL).
**Steps/DoD:** Same as T5.1 (mappers, signature verification per current docs, error mapping, contract suite, smoke script).
**Verify:** `uv run pytest packages/studio_providers -k fal -q`

### [x] T5.3 Real model catalog rows
**Depends:** T5.1, T5.2
**Goal:** Seed one or two models per task type.
**Steps**
1. Pick current, stable models per task type (text→image, image→image, text→video, image→video) from the providers' catalogs; record choice and reasoning in `docs/adr/003-initial-models.md`.
2. Write migration `0004_models_seed.sql` (idempotent upserts) with accurate `input_schema`, defaults, and `cost_credits` derived from provider pricing (document the formula).
3. Ensure `FakeProvider` models remain enabled only when `ENVIRONMENT != production`.
**DoD**
- [x] `GET /v1/models` returns real models in staging; smoke script generates one asset per task type successfully.
**Verify:** run smoke script for each task type on staging.

---

## PHASE 6 — Frontend (`apps/web`)

### [x] T6.1 Next.js scaffold and Supabase auth
**Depends:** T3.7
**Goal:** Authenticated shell.
**Steps**
1. `create-next-app` (App Router, TS, Tailwind), add `shadcn/ui`, `@supabase/ssr`, `@tanstack/react-query`, `zod`, `react-hook-form`.
2. Supabase auth with email magic link + one OAuth provider (Google). Middleware refreshes session; protect `(app)` routes.
3. `lib/api.ts`: instantiate `@studio/api-client` with the user's access token; React Query provider; global error boundary + toast.
4. Layout: sidebar (workspace switcher, projects), top bar (credits balance, user menu).
**DoD**
- [x] Sign in/out works locally; unauthenticated visit to `/projects` redirects to `/login`.
- [x] Vitest + RTL smoke tests for layout; Lighthouse accessibility ≥ 90 on login page.
**Verify:** `pnpm --filter web lint typecheck test && pnpm --filter web build`

### [x] T6.2 Projects pages
**Depends:** T6.1, T3.2
**Goal:** List/create/rename/archive projects.
**DoD**
- [x] Empty, loading, error states implemented; optimistic create; keyboard accessible dialogs.
- [x] Component tests with MSW covering list/create/error.
**Verify:** `pnpm --filter web test`

### [x] T6.3 Asset library and uploads
**Depends:** T6.2, T3.3
**Goal:** Grid of project assets with direct-to-storage upload.
**Steps**
1. Responsive grid (images/videos with thumbnail; hover play for video), filter by kind/origin, infinite scroll via cursor.
2. Upload: drag-drop and picker → request signed URL → `PUT` to storage with progress → call `complete` → refresh. Client-side type/size pre-check.
3. Asset detail drawer: preview (image / `<video controls>`), metadata, lineage (source job prompt/model/params, parent/inputs), download, delete.
**DoD**
- [x] Upload failure/retry handled; delete confirms; signed URL refresh handled when expired (refetch on 403).
- [x] Component tests + one Playwright test for upload.
**Verify:** `pnpm --filter web test && pnpm --filter web e2e -g upload`

### [ ] T6.4 Generation composer (schema-driven)
**Depends:** T6.3, T3.4, T3.5
**Goal:** One UI for all five flows.
**Steps**
1. Mode selector: Image / Video; input selector: Text only | Text + image (pick from library or upload).
2. Model picker populated from `GET /v1/models?task_type=` (derive task type from mode + attached image).
3. Parameter form generated from each model's JSON Schema (`react-jsonschema-form` or a small custom renderer for enum/int/number/boolean/string) with `default_params` prefilled; show credit cost live.
4. Submit with a client-generated `Idempotency-Key` (reuse on retry of the same submission). Handle `402`, `422` (inline field errors), `429`.
**DoD**
- [ ] All five flows submit correct payloads (unit tests assert request bodies).
- [ ] Double-click doesn't create two jobs.
- [ ] Form validation errors map to fields; cost shown matches model.
**Verify:** `pnpm --filter web test -k composer`

### [ ] T6.5 Job status and history (Realtime)
**Depends:** T6.4
**Goal:** Live job cards.
**Steps**
1. Subscribe to Supabase Realtime `postgres_changes` on `generation_jobs` filtered by `project_id`; on update, patch React Query cache; when `succeeded`, fetch outputs.
2. Fallback: if the channel isn't `SUBSCRIBED` within 5s or disconnects, poll `GET /v1/generations/{id}` with backoff 2s→10s.
3. Job card states: queued, running (elapsed timer), finalizing, succeeded (preview), failed (error + retry button), canceled; cancel button for active jobs; "use as input" action on results.
**DoD**
- [ ] With the FakeProvider, status transitions render live without a page refresh; killing Realtime falls back to polling (tested with a mocked channel).
- [ ] No duplicate subscriptions after navigation (cleanup verified).
**Verify:** `pnpm --filter web test -k jobs && pnpm --filter web e2e -g generation`

### [ ] T6.6 Polish: accessibility, responsiveness, empty states
**Depends:** T6.5
**DoD**
- [ ] Axe checks pass on main pages; usable at 375px width; focus management in dialogs/drawers; dark mode works.
**Verify:** `pnpm --filter web e2e -g a11y`

---

## PHASE 7 — Hardening, deployment, launch

### [ ] T7.1 Rate limits, quotas, abuse controls
**Depends:** T3.5
**Steps:** Redis token-bucket middleware (per user and per workspace) on submit/upload endpoints returning `429` with `Retry-After`; per-workspace concurrent job cap (already T2.5) configurable; prompt length limits; moderation hook interface `ModerationService.check(prompt, inputs)` (no-op default implementation, called in `create_job`; provider-backed implementation optional); Cloudflare WAF/rate rules documented in `docs/runbooks/cloudflare.md`.
**DoD**
- [ ] Tests: limit triggers and resets; moderation rejection returns `CONTENT_REJECTED` and refunds nothing (never reserved).
**Verify:** `uv run pytest apps/api -k limit -q`

### [ ] T7.2 Observability
**Depends:** T4.3
**Steps:** Sentry in API, worker, web (release tagging from git SHA); log `job_id`, `provider`, `model`, `status`, durations on every transition; metrics endpoint or log-based metrics: queue depth, time-in-state, provider latency/error rate, cost per job; admin-only `GET /v1/admin/stats`; alert rules documented (stuck jobs > 10 min, failure rate > 20% over 15 min, queue depth growing).
**DoD**
- [ ] Forced exception in each service appears in Sentry with request/job context; dashboard/alerts described in `docs/runbooks/observability.md`.
**Verify:** trigger test errors on staging.

### [ ] T7.3 Containers and `render.yaml`
**Depends:** T4.5
**Steps**
1. Multi-stage Dockerfiles for `api` and `worker` (uv, non-root user, ffmpeg installed, healthcheck).
2. `infra/render.yaml` blueprint: web service `api`, background worker `worker`, cron/worker for reconciler if not using ARQ cron, Key Value (Redis), env groups (`shared`, `api`, `worker`), health check path `/readyz`, autoscaling off for MVP.
3. Vercel project config for `apps/web` (env vars, root directory, build command).
4. Pooler note: use the Supabase connection pooler (transaction mode) for the API if connection counts grow; keep direct connection for migrations/worker—document settings.
**DoD**
- [ ] Blueprint deploys to a staging Render environment from scratch; API `/readyz` is green and the worker connects to Redis and DB.
**Verify:** deploy staging; run `scripts/smoke_staging.sh`.

### [ ] T7.4 CD pipelines and environments
**Depends:** T7.3, T0.3
**Steps:** GitHub Actions: on PR → preview (Vercel preview + Supabase branch DB if available); on merge to `main` → apply Supabase migrations to staging → deploy API/worker → deploy web → run `smoke_staging.sh` (includes a real-provider generation); production deploy via manual approval environment. Migration policy: backward-compatible (expand → migrate → contract). Secrets only in GitHub/Render/Vercel env stores.
**DoD**
- [ ] A merge to `main` reaches staging without manual steps; production requires approval; rollback procedure documented and rehearsed once.
**Verify:** perform a trivial change end-to-end.

### [ ] T7.5 Browser E2E suite
**Depends:** T6.5, T7.3
**Steps:** Playwright against preview/staging using FakeProvider: sign up → create project → upload → text→image → image→video → cancel → retry failure (`FAIL` prompt) → insufficient credits path.
**DoD**
- [ ] Suite passes in CI in < 8 min with < 2% flake over 20 runs; traces/videos uploaded on failure.
**Verify:** `pnpm --filter web e2e`

### [ ] T7.6 Documentation and runbooks
**Depends:** T7.2
**Steps:** ADRs (`001` Postgres as job source of truth, `002` ARQ vs Celery, `003` initial models); runbooks: stuck jobs, provider outage (disable model/provider via DB flag), webhook replay, credit correction, rotate secrets, restore from backup; developer onboarding in README (target: new dev productive in < 30 min); API docs published from `/docs` and `docs/openapi.json`.
**DoD**
- [ ] A teammate (or a fresh agent session) follows README + runbooks without outside help and succeeds.

### [ ] T7.7 Launch checklist
**Depends:** all above
**DoD**
- [ ] RLS tests green; no service-role key in web bundle (grep build output).
- [ ] Backups enabled on Supabase; retention policy for `job_events` documented (monthly partitions or scheduled purge).
- [ ] Provider spend limits/budgets set at the provider dashboards; credits seeded for test users only.
- [ ] Load test: 50 concurrent generations on staging with FakeProvider complete without stuck jobs; 10 real jobs per task type succeed.
- [ ] Failure drills done: kill worker mid-job, drop Redis, drop webhooks — all jobs recover or fail cleanly with refunds.
- [ ] Privacy/terms pages, content policy, and contact email in the web footer.
- [ ] Production env vars verified; DNS and Cloudflare proxy/WAF active; Sentry alerts routed.

---

## Appendix A — Suggested prompts for the agent

- **Start a task:** "Open `tasks.md`. Execute task `T2.2` only. Read `docs/design.md` §5.2 first. Write tests alongside code. When done, run the Verify command, tick the checkbox, and summarize what changed and any assumptions in `docs/QUESTIONS.md`."
- **Review pass:** "Review the diff for `T3.5` against its DoD and the Global DoD. List unmet items and risks (race conditions, missing RLS, secret leakage). Fix only unmet items."
- **Debug a stuck state:** "Reproduce with `FakeProvider`, add a failing test first, then fix. Don't change the state machine without updating `docs/design.md` §5.2 and an ADR."

## Appendix B — Milestones

| Milestone | Tasks | Outcome |
|---|---|---|
| M1 Backend walking skeleton | T0.x–T4.5 | Full pipeline works with FakeProvider, no UI |
| M2 Real generations | T5.x | Real images/videos from Replicate/Fal |
| M3 Usable app | T6.x | Create projects, upload, generate, view results live |
| M4 Production-ready | T7.x | Deployed, observable, tested, documented |

## Appendix C — Out of scope for MVP (do **not** build; keep seams only)

Video stitching/timeline editor, collaborative editing/presence/comments, workflow DAG engine, self-hosted GPU adapter, payments/billing integration, team invitations UI (roles exist in schema), outbound webhooks, R2/CDN migration.
