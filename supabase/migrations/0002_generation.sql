-- 0002_generation.sql: Models, Assets, Jobs, Events, and Credit Ledger

-- 1. Provider & Model Registry --------------------------------------------
create table if not exists public.providers (
  id       text primary key,              -- 'replicate', 'fal', 'fake', etc.
  name     text not null,
  enabled  boolean not null default true
);

insert into public.providers (id, name, enabled)
values
  ('fake', 'Deterministic Test Provider', true),
  ('replicate', 'Replicate', true),
  ('fal', 'Fal.ai', true),
  ('google', 'Google AI (Imagen / Veo)', true)
on conflict (id) do update set
  name = excluded.name,
  enabled = excluded.enabled;

create table if not exists public.models (
  id               uuid primary key default gen_random_uuid(),
  provider_id      text not null references public.providers(id),
  provider_model   text not null,         -- provider's model slug/version
  slug             text unique not null,  -- internal stable name: 'img-fast-v1'
  display_name     text not null,
  task_type        text not null check (task_type in ('text_to_image', 'image_to_image', 'text_to_video', 'image_to_video')),
  input_schema     jsonb not null,        -- JSON Schema of accepted params
  default_params   jsonb not null default '{}'::jsonb,
  cost_credits     numeric(10,2) not null default 1,
  enabled          boolean not null default true,
  unique (provider_id, provider_model, task_type)
);

-- 2. Media Assets ---------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'asset_kind') then
    create type asset_kind as enum ('image', 'video', 'audio', 'other');
  end if;
  if not exists (select 1 from pg_type where typname = 'asset_origin') then
    create type asset_origin as enum ('upload', 'generated', 'derived');
  end if;
end
$$;

create table if not exists public.assets (
  id              uuid primary key default gen_random_uuid(),
  workspace_id    uuid not null references public.workspaces(id) on delete cascade,
  project_id      uuid not null references public.projects(id) on delete cascade,
  kind            asset_kind not null,
  origin          asset_origin not null,
  storage_bucket  text not null default 'media',
  storage_path    text not null,            -- {workspace}/{project}/{asset}/original.ext
  thumbnail_path  text,
  mime_type       text,
  size_bytes      bigint,
  width           int,
  height          int,
  duration_ms     int,
  fps             numeric(6,3),
  source_job_id   uuid,                     -- fk added after generation_jobs
  parent_asset_id uuid references public.assets(id), -- derived/edited-from
  metadata        jsonb not null default '{}'::jsonb,
  created_by      uuid references public.profiles(id),
  created_at      timestamptz not null default now(),
  deleted_at      timestamptz
);

create index if not exists idx_assets_project_created
  on public.assets (project_id, created_at desc)
  where deleted_at is null;

-- Add deferred foreign key from projects to assets for cover_asset_id
alter table public.projects drop constraint if exists projects_cover_fk;
alter table public.projects add constraint projects_cover_fk
  foreign key (cover_asset_id) references public.assets(id) on delete set null;

-- 3. Generation Jobs ------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'job_status') then
    create type job_status as enum (
      'queued', 'submitting', 'running', 'finalizing', 'succeeded', 'failed', 'canceled'
    );
  end if;
end
$$;

create table if not exists public.generation_jobs (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces(id) on delete cascade,
  project_id       uuid not null references public.projects(id) on delete cascade,
  created_by       uuid not null references public.profiles(id),
  model_id         uuid not null references public.models(id),
  task_type        text not null,
  status           job_status not null default 'queued',
  prompt           text,
  negative_prompt  text,
  params           jsonb not null default '{}'::jsonb,    -- validated, resolved params
  idempotency_key  text,
  provider_job_id  text,                                  -- provider's prediction id
  attempt          int not null default 0,
  max_attempts     int not null default 3,
  error_code       text,
  error_message    text,
  cost_credits     numeric(10,2) not null default 0,
  parent_job_id    uuid references public.generation_jobs(id), -- re-runs / variations
  workflow_run_id  uuid,                                  -- future: step in a workflow
  queued_at        timestamptz not null default now(),
  started_at       timestamptz,
  completed_at     timestamptz,
  heartbeat_at     timestamptz,
  constraint check_attempts check (attempt <= max_attempts),
  unique (workspace_id, idempotency_key)
);

create index if not exists idx_generation_jobs_project_queued
  on public.generation_jobs (project_id, queued_at desc);

create index if not exists idx_generation_jobs_active_heartbeat
  on public.generation_jobs (status, heartbeat_at)
  where status in ('submitting', 'running', 'finalizing');

create unique index if not exists idx_generation_jobs_provider_job_id
  on public.generation_jobs (provider_job_id)
  where provider_job_id is not null;

-- Add deferred foreign key from assets to generation_jobs
create index if not exists idx_assets_source_job_id on public.assets (source_job_id);

alter table public.assets drop constraint if exists assets_source_job_fk;
alter table public.assets add constraint assets_source_job_fk
  foreign key (source_job_id) references public.generation_jobs(id) on delete set null;

-- 4. Job Inputs -----------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'input_role') then
    create type input_role as enum (
      'init_image', 'reference_image', 'first_frame', 'last_frame', 'mask', 'audio', 'video'
    );
  end if;
end
$$;

create table if not exists public.job_inputs (
  job_id    uuid not null references public.generation_jobs(id) on delete cascade,
  asset_id  uuid not null references public.assets(id),
  role      input_role not null,
  position  int not null default 0,
  primary key (job_id, asset_id, role)
);

-- 5. Append-Only Job Events -----------------------------------------------
create table if not exists public.job_events (
  id          bigint generated always as identity primary key,
  job_id      uuid not null references public.generation_jobs(id) on delete cascade,
  type        text not null,          -- 'state_change', 'webhook', 'retry', 'error', 'poll'
  from_status job_status,
  to_status   job_status,
  payload     jsonb,
  created_at  timestamptz not null default now()
);

create index if not exists idx_job_events_job_id on public.job_events (job_id, id);

-- 6. Credit Ledger & Balance View -----------------------------------------
create table if not exists public.credit_ledger (
  id           bigint generated always as identity primary key,
  workspace_id uuid not null references public.workspaces(id),
  job_id       uuid references public.generation_jobs(id),
  delta        numeric(10,2) not null,          -- negative = reserve/spend, positive = refund/grant
  reason       text not null,                   -- 'reserve', 'refund', 'purchase', 'grant'
  created_at   timestamptz not null default now()
);

create index if not exists idx_credit_ledger_workspace on public.credit_ledger (workspace_id);

create or replace view public.workspace_credit_balance as
select
  workspace_id,
  coalesce(sum(delta), 0)::numeric(10,2) as balance
from public.credit_ledger
group by workspace_id;

-- 7. Realtime Publication -------------------------------------------------
-- Ensure table is published in supabase_realtime
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = 'generation_jobs'
    ) then
      alter publication supabase_realtime add table public.generation_jobs;
    end if;
  end if;
end
$$;

-- 8. Row-Level Security ---------------------------------------------------
alter table public.providers enable row level security;
alter table public.models enable row level security;
alter table public.assets enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.job_inputs enable row level security;
alter table public.job_events enable row level security;
alter table public.credit_ledger enable row level security;

-- Providers & Models: readable by authenticated and anon users
drop policy if exists providers_read on public.providers;
create policy providers_read on public.providers
  for select
  using (true);

drop policy if exists models_read on public.models;
create policy models_read on public.models
  for select
  using (true);

-- Assets: read by workspace members; uploads insertable/editable by editors
drop policy if exists asset_read on public.assets;
create policy asset_read on public.assets
  for select
  using (is_member(workspace_id));

drop policy if exists asset_insert on public.assets;
create policy asset_insert on public.assets
  for insert
  with check (
    is_member(workspace_id, 'editor')
    and origin = 'upload'
  );

drop policy if exists asset_update on public.assets;
create policy asset_update on public.assets
  for update
  using (
    is_member(workspace_id, 'editor')
    and origin = 'upload'
  )
  with check (
    is_member(workspace_id, 'editor')
  );

drop policy if exists asset_delete on public.assets;
create policy asset_delete on public.assets
  for delete
  using (
    is_member(workspace_id, 'editor')
    and origin = 'upload'
  );

-- Generation jobs: read-only for workspace members; writes done via backend service-role
drop policy if exists job_read on public.generation_jobs;
create policy job_read on public.generation_jobs
  for select
  using (is_member(workspace_id));

-- Job inputs: read-only for workspace members
drop policy if exists job_inputs_read on public.job_inputs;
create policy job_inputs_read on public.job_inputs
  for select
  using (
    exists (
      select 1 from public.generation_jobs j
      where j.id = job_inputs.job_id
        and is_member(j.workspace_id)
    )
  );

-- Job events: read-only for workspace admin+
drop policy if exists job_events_read on public.job_events;
create policy job_events_read on public.job_events
  for select
  using (
    exists (
      select 1 from public.generation_jobs j
      where j.id = job_events.job_id
        and is_member(j.workspace_id, 'admin')
    )
  );

-- Credit ledger: read-only for workspace admin+
drop policy if exists ledger_read on public.credit_ledger;
create policy ledger_read on public.credit_ledger
  for select
  using (is_member(workspace_id, 'admin'));
