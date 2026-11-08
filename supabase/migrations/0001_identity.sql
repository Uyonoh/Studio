-- 0001_identity.sql: Identity, Tenancy, and Projects

create extension if not exists pgcrypto;

-- 1. Identity & tenancy ---------------------------------------------------
create table if not exists public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  avatar_url    text,
  created_at    timestamptz not null default now()
);

create table if not exists public.workspaces (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  owner_id    uuid not null references public.profiles(id),
  created_at  timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_type where typname = 'workspace_role') then
    create type workspace_role as enum ('owner', 'admin', 'editor', 'viewer');
  end if;
end
$$;

create table if not exists public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id      uuid not null references public.profiles(id) on delete cascade,
  role         workspace_role not null default 'editor',
  created_at   timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

create table if not exists public.projects (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references public.workspaces(id) on delete cascade,
  name           text not null,
  description    text,
  cover_asset_id uuid, -- fk added after assets table is created in 0002
  created_by     uuid not null references public.profiles(id),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  archived_at    timestamptz
);

create index if not exists idx_projects_workspace_created
  on public.projects (workspace_id, created_at desc)
  where archived_at is null;

-- 2. Triggers & Functions -------------------------------------------------

-- Updated_at trigger function
create or replace function public.handle_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_projects_updated_at on public.projects;
create trigger set_projects_updated_at
  before update on public.projects
  for each row
  execute function public.handle_updated_at();

-- Membership hierarchy helper:
-- workspace_role enum order: owner < admin < editor < viewer
-- A user with role 'admin' has 'admin' <= 'editor' (true), satisfying the minimum requirement.
-- A user with role 'viewer' has 'viewer' <= 'editor' (false), failing the check.
create or replace function public.is_member(ws uuid, min_role workspace_role default 'viewer')
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.workspace_members m
    where m.workspace_id = ws
      and m.user_id = auth.uid()
      and m.role <= min_role
  );
$$;

-- Auto-provisioning trigger on auth.users
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_display_name text;
  v_workspace_id uuid;
begin
  v_display_name := coalesce(
    new.raw_user_meta_data->>'display_name',
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'name',
    split_part(new.email, '@', 1),
    'User'
  );

  insert into public.profiles (id, display_name, avatar_url, created_at)
  values (
    new.id,
    v_display_name,
    new.raw_user_meta_data->>'avatar_url',
    now()
  )
  on conflict (id) do update set
    display_name = excluded.display_name,
    avatar_url = excluded.avatar_url;

  insert into public.workspaces (name, owner_id, created_at)
  values (
    v_display_name || '''s Workspace',
    new.id,
    now()
  )
  returning id into v_workspace_id;

  insert into public.workspace_members (workspace_id, user_id, role, created_at)
  values (
    v_workspace_id,
    new.id,
    'owner',
    now()
  );

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();

-- 3. Row-Level Security (RLS) ---------------------------------------------

alter table public.profiles enable row level security;
alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.projects enable row level security;

-- Profiles policies
drop policy if exists profile_read on public.profiles;
create policy profile_read on public.profiles
  for select
  using (true);

drop policy if exists profile_update on public.profiles;
create policy profile_update on public.profiles
  for update
  using (id = auth.uid())
  with check (id = auth.uid());

-- Workspaces policies
drop policy if exists workspace_read on public.workspaces;
create policy workspace_read on public.workspaces
  for select
  using (is_member(id));

drop policy if exists workspace_update on public.workspaces;
create policy workspace_update on public.workspaces
  for update
  using (is_member(id, 'admin'))
  with check (is_member(id, 'admin'));

-- Workspace members policies
drop policy if exists member_read on public.workspace_members;
create policy member_read on public.workspace_members
  for select
  using (is_member(workspace_id));

drop policy if exists member_admin on public.workspace_members;
create policy member_admin on public.workspace_members
  for all
  using (is_member(workspace_id, 'admin'))
  with check (is_member(workspace_id, 'admin'));

-- Projects policies
drop policy if exists proj_read on public.projects;
create policy proj_read on public.projects
  for select
  using (is_member(workspace_id));

drop policy if exists proj_write on public.projects;
create policy proj_write on public.projects
  for all
  using (is_member(workspace_id, 'editor'))
  with check (is_member(workspace_id, 'editor'));
