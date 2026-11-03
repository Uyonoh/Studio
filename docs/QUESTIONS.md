# Questions & Assumptions Log

This document records ambiguous requirements, environment differences, questions, and minimal safe assumptions made during execution.

---

### T0.2 — Local Dev Environment Tooling Note
- **Finding:** Neither `docker` nor a global `supabase` binary were detected on the Windows PATH of the host environment.
- **Action / Assumption:**
  1. Local Supabase CLI configuration was generated via `npx supabase init` with Realtime and Storage enabled.
  2. `infra/docker-compose.yml` was configured with `redis:7-alpine` container and health checks.
  3. Created both POSIX `scripts/dev-up.sh` and Windows PowerShell `scripts/dev-up.ps1` to launch Redis and local Supabase via `supabase` or `npx supabase`.
  4. Created `.env.example` with full configuration reference and updated `README.md` with prerequisites and first-run steps.
  5. When Docker Desktop / Docker daemon is installed and started on this machine, `scripts/dev-up.ps1` (or `scripts/dev-up.sh`) brings up the full local stack as specified.

### T6.3 - Asset library notes and assumptions
- **Backend lineage extension:** The drawer needs the source job's prompt/model/params and the job inputs, but GET /v1/assets/{id} only returned IDs plus asset metadata. Added an additive lineage block to AssetResponse (source job summary, input asset refs with signed URLs, parent asset). List responses leave lineage null to keep payloads small. OpenAPI spec and packages/api-client were regenerated.
- **Signed URL expiry:** Supabase signed URLs are refreshed by refetching the asset/list once when media fires an error event (there is no HTTP 403 observable from an <img>/<video> load), guarded per asset so a permanently broken file cannot loop.
- **Playwright harness:** The upload E2E runs against a self-contained mock backend (pps/web/e2e/mock-backend.mjs) that also impersonates the Supabase auth /auth/v1/user endpoint, so no Supabase/Redis/API stack is required. Session state is injected as a sb-<ref>-auth-token cookie matching @supabase/ssr's base64url encoding.
- **Design references:** The Stitch screens are light-mode "Luminous Canvas"; the app already ships a dark theme from T6.1/T6.2, so layout/interaction patterns were borrowed (drawer sections, prompt block, lineage tiles) while keeping the existing dark palette.

### T6.4 — Generation composer notes and assumptions
- **Flow mapping:** The five product flows collapse onto four API task types. Image+Text→Video is `image_to_video` with an optional prompt, so the composer exposes Mode (Image/Video) + Starting point (Text only / Text + image) and derives the task type from those two toggles.
- **Custom schema renderer:** Implemented a small renderer (`components/composer/schema-params-form.tsx`) instead of `react-jsonschema-form`, supporting enum, integer, number, boolean, and string plus `minimum`/`maximum`/`minLength`/`maxLength`. Unsupported shapes fall back to a text input and pass through unchanged.
- **Native validation disabled:** The form uses `noValidate` so the browser's constraint UI (e.g. the `max` bubble on number inputs) cannot pre-empt submission; `lib/generation-params.ts` validates and maps messages to the offending field instead.
- **Numeric inputs:** Number fields hold raw strings while typing and are coerced at submit time, so partial values like `-` or `0.` don't get swallowed. Blank values are omitted so server defaults apply.
- **Idempotency key ownership:** The composer generates one key per distinct payload signature (`JSON.stringify` of the submit body), reuses it when retrying an unchanged submission, and clears it after success. Changing any field produces a new key.
- **Error surfacing:** `402` shows a credits message, `429` includes `Retry-After`, `MISSING_INPUT` attaches to the image picker, FastAPI `422` issue lists map to matching schema fields when possible, and everything else falls back to the problem `detail`.

### T6.5 — Job status/history notes and assumptions
- **Realtime + fallback:** `hooks/use-job-realtime.ts` subscribes to `postgres_changes` on `generation_jobs` filtered by project. If the channel is not `SUBSCRIBED` within 5s, errors, or closes, the UI switches to polling. The timeout is overridable (`realtimeTimeoutMs`) so tests don't wait 5 seconds.
- **Polling scope:** Detail polling (`useLiveJob`) runs only for active jobs and only while the Realtime state is `disconnected`; with a live channel it stays disabled so the cache patch is the single source of truth. Backoff is 2s × 1.5ⁿ capped at 10s. A terminal polled status invalidates the list so outputs are fetched once.
- **Cache patching:** Realtime UPDATE payloads only carry row fields, not outputs, so updates patch every cached list under `["generations", projectId]` plus `["generation", id]`, then invalidate on terminal status to pick up outputs and derived fields.
- **"Use as input" adapter:** Outputs are not full asset records. `outputToAsset` builds a lightweight `Asset` from the output (`asset_id`, kind, mime, signed URL, source job) with empty workspace/project/storage fields, which is enough for the composer's image picker and submit payload. It is only offered for image outputs.
- **Composer remount:** The project page stores the chosen asset as `seedAsset` and remounts the composer with `key={seedAsset?.id ?? "composer"}` so the initial asset is applied without adding effect-driven state syncing.
- **E2E without Realtime:** The Playwright mock backend has no Realtime server, so `e2e/generation.spec.ts` deliberately exercises the polling fallback by advancing job state in `GET /v1/generations/{id}` (queued → running → succeeded) and asserting the card reaches `succeeded` and shows the output without a reload.

### T6.6 — Accessibility, responsiveness, and polish notes
- **Axe tooling:** Added `@axe-core/playwright` and `e2e/a11y.spec.ts`, which scans `/login`, `/projects`, and the project workspace across the assets/composer/history tabs using the WCAG 2.0/2.1 A/AA rule sets.
- **Contrast tokens:** Axe flagged white text on the old primary violet (`#7C5CFF`, 4.35:1) and small violet-on-dark labels. Primary fills moved to `#6C4CE8` (hover `#5B3FD6`) and violet text on dark surfaces moved to `#A995FF`; muted text moved from `#6B7280` to `#9AA1B2`. The brand accent remains `#7C5CFF` for borders, rings, icons, and decorative fills.
- **Focus management:** A shared `useFocusTrap` hook now handles Tab/Shift+Tab wrapping, initial focus, Escape, and focus restoration for the create/rename/archive dialogs and the asset drawer. It captures the trigger during render so the dialog's own autofocus cannot overwrite the restore target.
- **Responsive navigation:** The sidebar is off-canvas below `lg` with a backdrop, a menu button in the top bar, and a close button; `AppShell` also adds a skip link and a single `main` landmark. Content padding no longer conflicts with the fixed top bar (`pt-16` lives on the shell wrapper).
- **Empty states:** Existing project/asset/job empty states were kept and re-checked under the new contrast values; no new placeholder screens were required.
- **Mock backend:** Added `GET /v1/workspaces/{id}/projects` so the projects page (and the axe scan for it) renders against the same self-contained mock as the other E2E flows.

### T7.1 - Rate limits, quotas, and abuse-control notes
- **Token bucket:** `api/rate_limit.py` runs a Lua script (`HMGET`/`HSET`/`EXPIRE`) so the read-refill-consume-write cycle is atomic across API workers. Each bucket stores `tokens` and the last refill timestamp in Redis; capacity equals the per-minute allowance, so the configured value is also the burst size. Keys expire after one full refill window plus 60 seconds.
- **Two scopes:** Submit and retry share `ratelimit:submit:{user|workspace}:<id>`; uploads use `ratelimit:upload:...`. Both the caller's personal bucket and the workspace bucket are consumed, so one member cannot spend the whole workspace budget and a shared workspace still caps aggregate throughput. Retries are charged to the submit budget.
- **Fail-open:** If `redis_pool` is `None`, Redis `eval` raises, or the reply is unexpected, the request is allowed and a warning is logged. This keeps local development and transient Redis outages working; Cloudflare edge rules are the backstop documented in `docs/runbooks/cloudflare.md`.
- **Dependency wiring:** The limiter runs as a FastAPI route dependency on `POST /projects/{id}/generations`, `POST /generations/{id}/retry`, and `POST /projects/{id}/assets/uploads`. It resolves the workspace from the project/job row before consuming the workspace bucket. A `429` uses the existing problem+json shape with `error_code=RATE_LIMITED` and a `Retry-After` header in whole seconds.
- **Prompt length:** `MAX_PROMPT_CHARS` (default 4000) applies to both `prompt` and `negative_prompt`. The check runs after the idempotency replay but before model lookup, so a replayed request still returns its original job and an oversized prompt never reaches a provider or the ledger. Violations raise `PromptTooLongError` (`PROMPT_TOO_LONG`, 422).
- **Moderation:** `ModerationService.check(prompt, input_asset_ids)` defaults to a no-op; `StaticModerationService` is provided for tests/dev. The API resolves an app-scoped implementation from `app.state.moderation_service`, and `GenerationService` calls it before model loading and credit reservation. A rejection raises `ContentRejectedError` (`CONTENT_REJECTED`, 422) and therefore never reserves or refunds credits.
- **Concurrency cap:** The existing `MAX_ACTIVE_JOBS_PER_WORKSPACE` check in `GenerationService` remains the per-workspace job cap; it is now documented alongside the new limits in `.env.example`.




