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
- Supabase CLI

### Setup
```bash
make setup
make lint
make typecheck
make test
```
