"""Unit tests verifying SQL migrations, syntax, ordering, and constraints."""

from pathlib import Path

# Repo root is 3 levels up from packages/studio_core/tests/test_migrations.py:
# parents[0] = tests, parents[1] = studio_core, parents[2] = packages, parents[3] = Studio root
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_migrations_exist_and_ordered() -> None:
    migrations_dir = REPO_ROOT / "supabase" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    filenames = [f.name for f in migration_files]

    assert "0001_identity.sql" in filenames
    assert "0002_generation.sql" in filenames
    assert "0003_storage.sql" in filenames
    assert "0004_models_seed.sql" in filenames
    assert "0005_google_models_seed.sql" in filenames


def test_identity_migration_contents() -> None:
    migration_file = REPO_ROOT / "supabase" / "migrations" / "0001_identity.sql"
    content = migration_file.read_text(encoding="utf-8")

    assert "create table if not exists public.profiles" in content
    assert "create table if not exists public.workspaces" in content
    assert "create table if not exists public.workspace_members" in content
    assert "create table if not exists public.projects" in content
    assert "create type workspace_role as enum ('owner', 'admin', 'editor', 'viewer');" in content
    assert "is_member(" in content
    assert "security definer" in content
    assert "set search_path = public" in content
    assert "alter table public.profiles enable row level security;" in content
    assert "alter table public.workspaces enable row level security;" in content
    assert "alter table public.workspace_members enable row level security;" in content
    assert "alter table public.projects enable row level security;" in content


def test_generation_migration_contents() -> None:
    migration_file = REPO_ROOT / "supabase" / "migrations" / "0002_generation.sql"
    content = migration_file.read_text(encoding="utf-8")

    assert "create table if not exists public.providers" in content
    assert "create table if not exists public.models" in content
    assert "create table if not exists public.assets" in content
    assert "create table if not exists public.generation_jobs" in content
    assert "create table if not exists public.job_inputs" in content
    assert "create table if not exists public.job_events" in content
    assert "create table if not exists public.credit_ledger" in content
    assert "create or replace view public.workspace_credit_balance" in content
    assert "check (attempt <= max_attempts)" in content
    assert "unique (workspace_id, idempotency_key)" in content
    assert "unique index if not exists idx_generation_jobs_provider_job_id" in content
    assert "alter publication supabase_realtime add table public.generation_jobs" in content


def test_storage_migration_contents() -> None:
    migration_file = REPO_ROOT / "supabase" / "migrations" / "0003_storage.sql"
    content = migration_file.read_text(encoding="utf-8")

    assert "storage.buckets" in content
    assert "'media'" in content
    assert "524288000" in content
    assert "public.is_member(" in content


def test_seed_contents() -> None:
    seed_file = REPO_ROOT / "supabase" / "seed.sql"
    content = seed_file.read_text(encoding="utf-8")

    assert "insert into public.providers" in content
    assert "'fake'" in content
    assert "'replicate'" in content
    assert "'fal'" in content
    assert "'text_to_image'" in content
    assert "'image_to_image'" in content
    assert "'text_to_video'" in content
    assert "'image_to_video'" in content


def test_models_seed_migration_contents() -> None:
    migration_file = REPO_ROOT / "supabase" / "migrations" / "0004_models_seed.sql"
    content = migration_file.read_text(encoding="utf-8")

    assert "replicate" in content
    assert "fal" in content
    assert "black-forest-labs/flux-schnell" in content
    assert "fal-ai/flux/schnell" in content
    assert "text_to_image" in content
    assert "image_to_image" in content
    assert "text_to_video" in content
    assert "image_to_video" in content
    assert "on conflict (provider_id, provider_model, task_type) do update" in content.lower()


def test_google_models_seed_migration_contents() -> None:
    migration_file = REPO_ROOT / "supabase" / "migrations" / "0005_google_models_seed.sql"
    content = migration_file.read_text(encoding="utf-8")

    assert "google" in content
    assert "imagen-3.0-generate-002" in content
    assert "text_to_image" in content
    assert "image_to_image" in content
    assert "on conflict (provider_id, provider_model, task_type) do update" in content.lower()
