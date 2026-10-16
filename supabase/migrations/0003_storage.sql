-- 0003_storage.sql: Storage bucket and policies

-- 1. Create 'media' private bucket ----------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'media',
  'media',
  false,
  524288000, -- 500 MB
  array['image/*', 'video/*']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- 2. Storage Objects RLS Policies -----------------------------------------
-- Path pattern: {workspace_id}/{project_id}/{asset_id}/{filename}
-- The first path segment is workspace_id.

-- Allow workspace members (viewer+) to read objects
drop policy if exists "Media bucket select" on storage.objects;
create policy "Media bucket select" on storage.objects
  for select
  using (
    bucket_id = 'media'
    and public.is_member(
      (storage.foldername(name))[1]::uuid,
      'viewer'
    )
  );

-- Allow workspace editors+ to insert/upload objects
drop policy if exists "Media bucket insert" on storage.objects;
create policy "Media bucket insert" on storage.objects
  for insert
  with check (
    bucket_id = 'media'
    and public.is_member(
      (storage.foldername(name))[1]::uuid,
      'editor'
    )
  );

-- Allow workspace editors+ to update objects
drop policy if exists "Media bucket update" on storage.objects;
create policy "Media bucket update" on storage.objects
  for update
  using (
    bucket_id = 'media'
    and public.is_member(
      (storage.foldername(name))[1]::uuid,
      'editor'
    )
  )
  with check (
    bucket_id = 'media'
    and public.is_member(
      (storage.foldername(name))[1]::uuid,
      'editor'
    )
  );

-- Allow workspace editors+ to delete objects
drop policy if exists "Media bucket delete" on storage.objects;
create policy "Media bucket delete" on storage.objects
  for delete
  using (
    bucket_id = 'media'
    and public.is_member(
      (storage.foldername(name))[1]::uuid,
      'editor'
    )
  );
