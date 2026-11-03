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

