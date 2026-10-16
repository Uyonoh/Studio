.PHONY: setup lint typecheck test dev-api dev-worker dev-web db-reset

setup:
	uv sync --all-packages
	pnpm install

lint:
	uv run ruff check .
	uv run ruff format --check .
	pnpm -r --if-present lint

typecheck:
	uv run mypy -p api -p worker -p studio_core -p studio_providers -p studio_media
	uv run mypy apps/api/tests apps/worker/tests packages/studio_core/tests packages/studio_providers/tests packages/studio_media/tests
	pnpm -r --if-present typecheck

test:
	uv run pytest
	pnpm -r --if-present test

dev-api:
	uv run uvicorn api.main:app --reload --port 8000

dev-worker:
	uv run python -m worker.main

dev-web:
	pnpm --filter @studio/web dev

db-reset:
	supabase db reset
