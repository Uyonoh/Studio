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
