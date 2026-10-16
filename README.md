# AI Content Studio (MVP)

A modular AI content studio for text/image/video generation, asset lineage, and project management.

Refer to the technical documentation:
- [Technical Design Document (TDD)](docs/design.md)
- [Task Execution Plan](docs/tasks.md)

## Architecture Overview

- **Frontend**: Next.js (App Router, Tailwind CSS, TypeScript)
- **API**: FastAPI (Python 3.12, asyncpg, Pydantic v2)
- **Worker**: Python background worker (ARQ + Redis)
- **Database & Auth**: Supabase (PostgreSQL with RLS, Auth, Storage, Realtime)
- **Providers**: Adapter pattern supporting Replicate, Fal.ai, and an in-process FakeProvider for deterministic testing.

## Quickstart

### Prerequisites
- Python 3.12+ and [`uv`](https://github.com/astral-sh/uv)
- Node.js 20+ and [`pnpm`](https://pnpm.io/)
- Docker & Docker Compose
- Supabase CLI (or `npx supabase`)

### First-Run & Local Dev Setup
1. Copy the example environment variables:
   ```bash
   cp .env.example .env
   ```
2. Install workspace dependencies:
   ```bash
   make setup
   ```
3. Start the local database, storage, realtime, and Redis stack:
   - Linux/macOS:
     ```bash
     chmod +x scripts/dev-up.sh
     ./scripts/dev-up.sh
     ```
   - Windows (PowerShell):
     ```powershell
     .\scripts\dev-up.ps1
     ```
   This spins up:
   - Redis at `redis://127.0.0.1:6379`
   - Supabase local API at `http://127.0.0.1:54321`
   - Supabase Studio at `http://127.0.0.1:54323`
   - Supabase PostgreSQL at `postgresql://postgres:postgres@127.0.0.1:54322/postgres`

4. Run code quality and test suites:
   ```bash
   make lint
   make typecheck
   make test
   ```
