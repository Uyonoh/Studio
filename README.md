# AI Content Studio (MVP)

A modular AI content studio for text/image/video generation, media asset management, lineage tracking, and creative workflows.

---

## 1. Documentation Index

- **Architecture & Specifications:**
  - [Technical Design Document (TDD)](docs/design.md)
  - [Task Execution Plan](docs/tasks.md)
  - [OpenAPI Specification](docs/openapi.json)
- **Architecture Decision Records (ADRs):**
  - [ADR-001: PostgreSQL as Job Source of Truth](docs/adr/001-postgres-job-source-of-truth.md)
  - [ADR-002: Background Worker Runtime: ARQ over Celery](docs/adr/002-arq-vs-celery.md)
  - [ADR-003: Initial Model Selection & Pricing](docs/adr/003-initial-models.md)
- **Operations & Runbooks:**
  - [Runbook: Stuck Jobs Resolution](docs/runbooks/stuck-jobs.md)
  - [Runbook: Provider Outage & Model Disablement](docs/runbooks/provider-outage.md)
  - [Runbook: Webhook Replay & Idempotency](docs/runbooks/webhook-replay.md)
  - [Runbook: Credit Ledger & Balance Corrections](docs/runbooks/credit-correction.md)
  - [Runbook: Secrets Rotation Procedure](docs/runbooks/rotate-secrets.md)
  - [Runbook: Disaster Recovery & Database Restore](docs/runbooks/restore-from-backup.md)
  - [Runbook: Observability & Alerting](docs/runbooks/observability.md)
  - [Runbook: Deployment & Infrastructure](docs/runbooks/deployment.md)
  - [Runbook: Cloudflare WAF & Edge Rules](docs/runbooks/cloudflare.md)

---

## 2. Architecture & Monorepo Layout

```
Studio/
├── apps/
│   ├── api/             # FastAPI REST API service (Python 3.12, asyncpg, Pydantic v2)
│   ├── worker/          # Background worker (ARQ, Redis, reconciler cron)
│   └── web/             # Web frontend (Next.js 14 App Router, Tailwind CSS, shadcn/ui)
├── packages/
│   ├── api-client/      # Generated TypeScript API client (@studio/api-client)
│   ├── studio_core/     # Database models, repositories, state machine, queue abstractions
│   ├── studio_providers/# Provider adapters (FakeProvider, Replicate, Fal.ai)
│   └── studio_media/    # FFmpeg media inspection, poster generation, Supabase storage
├── infra/               # Render Blueprint (render.yaml), Docker Compose
├── scripts/             # Developer automation, OpenAPI export, smoke tests, seeding
└── supabase/            # PostgreSQL migrations (0001–0005), RLS policies, seed data
```

---

## 3. Developer Onboarding (< 30 Minutes Setup)

Follow these steps to set up a fully working local environment from scratch.

### 3.1 Prerequisites
Ensure the following tools are installed on your host machine:
- **Python 3.12+** and [**`uv`**](https://github.com/astral-sh/uv) (fast Python package manager)
- **Node.js 20+** and [**`pnpm`**](https://pnpm.io/) (v9+)
- **Docker & Docker Compose** (required for local Redis and Supabase)
- **Supabase CLI** (or run with `npx supabase`)
- **FFmpeg** (optional for local media processing tests: `ffmpeg -version`)

### 3.2 Environment Configuration
Copy the sample environment file to the repository root:
```bash
cp .env.example .env
```
The defaults in `.env.example` work out-of-the-box for local testing with the in-process `FakeProvider` and local Supabase/Redis.

### 3.3 Install Dependencies
Install Python virtual environment and Node packages across all workspaces:
```bash
make setup
```
*(Equivalent to `uv sync --all-packages` and `pnpm install`).*

### 3.4 Start Backing Services (Database, Redis, Storage)
Launch Redis and local Supabase:
- **macOS / Linux:**
  ```bash
  chmod +x scripts/dev-up.sh
  ./scripts/dev-up.sh
  ```
- **Windows (PowerShell):**
  ```powershell
  .\scripts\dev-up.ps1
  ```

This starts:
- **Redis:** `redis://127.0.0.1:6379/0`
- **Supabase PostgreSQL:** `postgresql://postgres:postgres@127.0.0.1:54322/postgres`
- **Supabase API & Auth:** `http://127.0.0.1:54321`
- **Supabase Studio UI:** `http://127.0.0.1:54323`

### 3.5 Seed Development User & Initial Models
Apply migrations and create a local test user:
```bash
# Seed a local development user and initial workspace
uv run python scripts/seed_dev_user.py
```

### 3.6 Start the Application Services
Open separate terminal windows or tabs to run the services:

1. **API Service:**
   ```bash
   make dev-api
   ```
   Runs FastAPI with auto-reload at `http://localhost:8000`.
   - **Interactive API Documentation:** Visit [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) or [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc).
   - **Health Check:** `http://localhost:8000/readyz`

2. **Background Worker:**
   ```bash
   make dev-worker
   ```
   Starts the ARQ worker process, listening for `run_generation`, `finalize_generation`, `cancel_generation`, and running the 60s `reconcile_jobs` cron.

3. **Web Application:**
   ```bash
   make dev-web
   ```
   Launches the Next.js frontend at [http://localhost:3000](http://localhost:3000).

---

## 4. API Schema & Client Generation

The TypeScript client in `packages/api-client` is generated directly from the FastAPI OpenAPI schema.

When modifying API routes, models, or query parameters:
1. Export the OpenAPI JSON schema:
   ```bash
   uv run python scripts/export_openapi.py
   ```
2. Re-generate types and build the client:
   ```bash
   pnpm --filter @studio/api-client build
   ```
3. Verify that `git diff docs/openapi.json` accurately reflects your intended API changes.

---

## 5. Development Workflow & Verification

### Code Formatting and Linting
```bash
make lint
```
Runs:
- `uv run ruff check .`
- `uv run ruff format --check .`
- `pnpm -r --if-present lint`

### Static Type Checking
```bash
make typecheck
```
Runs `mypy` across all Python apps/packages and `tsc` across frontend workspaces.

### Automated Test Suites
```bash
# Run all Python and Vitest unit/integration tests
make test

# Python tests specifically
uv run pytest

# Backend end-to-end integration test (FakeProvider pipeline)
uv run pytest tests/e2e_backend -q

# Frontend Vitest component tests (MSW mocked)
pnpm --filter web test

# Frontend Playwright browser E2E test suite (mocked backend, isolated)
pnpm --filter web e2e

# Run single E2E spec
pnpm --filter web e2e -g upload
```

### Manual Smoke Verification
Test inference generation locally against the `FakeProvider` or upstream providers:
```bash
# Smoke test FakeProvider
uv run python scripts/smoke_provider.py fake

# Smoke test Replicate or Fal (requires valid API keys in .env)
uv run python scripts/smoke_provider.py replicate
uv run python scripts/smoke_provider.py fal
```

---

## 6. Common Troubleshooting FAQs

- **Port 8000 / 54321 / 6379 already in use:**
  Check for stale Docker containers or existing Python processes:
  ```bash
  docker ps
  # Stop containers if needed
  docker compose -f infra/docker-compose.yml down
  ```
- **Database schema out-of-sync:**
  Reset local Supabase and re-apply all migrations:
  ```bash
  make db-reset
  uv run python scripts/seed_dev_user.py
  ```
- **Changes to OpenAPI schema not reflecting in Web app:**
  Run `uv run python scripts/export_openapi.py` followed by `pnpm --filter @studio/api-client build`.
