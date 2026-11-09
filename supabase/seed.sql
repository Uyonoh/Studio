-- supabase/seed.sql: Seed providers, models, and the local dev user.

-- ============================================================================
-- OPTIONAL: reset the model catalog before reseeding
-- ============================================================================
-- Uncomment this block when you want a clean model slate (for example after
-- replacing the Google catalog). It removes model-referencing job/ledger rows
-- first, then deletes every model. Providers and dev-user credits are kept.
--
-- begin;
--   delete from public.credit_ledger where job_id is not null;
--   delete from public.generation_jobs;
--   delete from public.models;
-- commit;
--
-- To reset only the Google catalog, use:
-- delete from public.models where provider_id = 'google';

-- 1. Providers ------------------------------------------------------------
insert into public.providers (id, name, enabled)
values
  ('fake', 'Deterministic Test Provider', true),
  ('replicate', 'Replicate', true),
  ('fal', 'Fal.ai', true),
  ('google', 'Google AI (Gemini, Nano Banana & Omni)', true)
on conflict (id) do update set
  name = excluded.name,
  enabled = excluded.enabled;

-- 2. Models (FakeProvider models covering all 4 task types) ----------------
-- text_to_image
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values (
  'fake',
  'fake-text-to-image-v1',
  'fake-image-fast',
  'Fake Fast Image Generator',
  'text_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "aspect_ratio": {
        "type": "string",
        "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "default": "1:1"
      },
      "seed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 2147483647
      },
      "output_format": {
        "type": "string",
        "enum": ["png", "jpg", "webp"],
        "default": "png"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "1:1", "output_format": "png"}'::jsonb,
  1.00,
  true
)
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- image_to_image
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values (
  'fake',
  'fake-image-to-image-v1',
  'fake-image-remix',
  'Fake Image Remix & Variation',
  'image_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "strength": {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
        "default": 0.75
      },
      "seed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 2147483647
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"strength": 0.75}'::jsonb,
  1.50,
  true
)
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- text_to_video
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values (
  'fake',
  'fake-text-to-video-v1',
  'fake-video-fast',
  'Fake Text to Video Generator',
  'text_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "duration_s": {
        "type": "integer",
        "enum": [3, 5, 10],
        "default": 5
      },
      "aspect_ratio": {
        "type": "string",
        "enum": ["16:9", "9:16", "1:1"],
        "default": "16:9"
      },
      "seed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 2147483647
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"duration_s": 5, "aspect_ratio": "16:9"}'::jsonb,
  5.00,
  true
)
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- image_to_video
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values (
  'fake',
  'fake-image-to-video-v1',
  'fake-image-to-video',
  'Fake Image Animator',
  'image_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "duration_s": {
        "type": "integer",
        "enum": [3, 5, 10],
        "default": 5
      },
      "motion_bucket_id": {
        "type": "integer",
        "minimum": 1,
        "maximum": 255,
        "default": 127
      },
      "seed": {
        "type": "integer",
        "minimum": 0,
        "maximum": 2147483647
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"duration_s": 5, "motion_bucket_id": 127}'::jsonb,
  5.00,
  true
)
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- 3. Google AI Models -----------------------------------------------------
-- Retire the legacy Imagen 3 / Veo 2 rows inserted by migrations 0005 and
-- 0006. Unreferenced rows are removed; referenced rows are disabled so
-- historical jobs keep working.
delete from public.models m
where m.provider_id = 'google'
  and m.provider_model in ('imagen-3.0-generate-002', 'veo-2.0-generate-001')
  and not exists (
    select 1
    from public.generation_jobs j
    where j.model_id = m.id
  );

update public.models
set enabled = false
where provider_id = 'google'
  and provider_model in ('imagen-3.0-generate-002', 'veo-2.0-generate-001');

-- Image models: Nano Banana family (Gemini :generateContent)
-- - Nano Banana 2.1  -> gemini-nano-banana-2.1
-- - Nano Banana 2    -> gemini-3.1-flash-image
-- - Nano Banana 2 Lite -> gemini-3.1-flash-lite-image
-- - Nano Banana Pro  -> gemini-3-pro-image
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values
  (
    'google',
    'gemini-nano-banana-2.1',
    'google-nano-banana-2-1',
    'Google Nano Banana 2.1 (Text to Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    3.00,
    true
  ),
  (
    'google',
    'gemini-nano-banana-2.1',
    'google-nano-banana-2-1-edit',
    'Google Nano Banana 2.1 (Image Edit)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    3.50,
    true
  ),
  (
    'google',
    'gemini-3.1-flash-image',
    'google-nano-banana-2',
    'Google Nano Banana 2 (Text to Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    2.00,
    true
  ),
  (
    'google',
    'gemini-3.1-flash-image',
    'google-nano-banana-2-edit',
    'Google Nano Banana 2 (Image Edit)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    2.50,
    true
  ),
  (
    'google',
    'gemini-3.1-flash-lite-image',
    'google-nano-banana-2-lite',
    'Google Nano Banana 2 Lite (Text to Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    1.00,
    true
  ),
  (
    'google',
    'gemini-3-pro-image',
    'google-nano-banana-pro',
    'Google Nano Banana Pro (Text to Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    6.00,
    true
  ),
  (
    'google',
    'gemini-3-pro-image',
    'google-nano-banana-pro-edit',
    'Google Nano Banana Pro (Image Edit)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "1:1"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        },
        "temperature": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 2.0,
          "default": 1.0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1"}'::jsonb,
    6.50,
    true
  )
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- Video models: Veo 3.1 (predictLongRunning) and Gemini Omni (generateContent)
-- - Veo 3.1       -> veo-3.1-generate-001
-- - Veo 3.1 Fast  -> veo-3.1-fast-generate-001
-- - Gemini Omni   -> gemini-omni-1.2-flash
insert into public.models (
  provider_id,
  provider_model,
  slug,
  display_name,
  task_type,
  input_schema,
  default_params,
  cost_credits,
  enabled
)
values
  (
    'google',
    'veo-3.1-generate-001',
    'google-veo-3-1',
    'Google Veo 3.1 (Text to Video)',
    'text_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["16:9", "9:16"],
          "default": "16:9"
        },
        "duration": {
          "type": "string",
          "enum": ["4", "6", "8"],
          "default": "8"
        },
        "resolution": {
          "type": "string",
          "enum": ["720p", "1080p", "4k"],
          "default": "720p"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "16:9", "duration": "8", "resolution": "720p"}'::jsonb,
    50.00,
    true
  ),
  (
    'google',
    'veo-3.1-generate-001',
    'google-veo-3-1-i2v',
    'Google Veo 3.1 (Image to Video)',
    'image_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["16:9", "9:16"],
          "default": "16:9"
        },
        "duration": {
          "type": "string",
          "enum": ["4", "6", "8"],
          "default": "8"
        },
        "resolution": {
          "type": "string",
          "enum": ["720p", "1080p", "4k"],
          "default": "720p"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "16:9", "duration": "8", "resolution": "720p"}'::jsonb,
    50.00,
    true
  ),
  (
    'google',
    'veo-3.1-fast-generate-001',
    'google-veo-3-1-fast',
    'Google Veo 3.1 Fast (Text to Video)',
    'text_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["16:9", "9:16"],
          "default": "16:9"
        },
        "duration": {
          "type": "string",
          "enum": ["4", "6", "8"],
          "default": "8"
        },
        "resolution": {
          "type": "string",
          "enum": ["720p", "1080p", "4k"],
          "default": "720p"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "16:9", "duration": "8", "resolution": "720p"}'::jsonb,
    25.00,
    true
  ),
  (
    'google',
    'veo-3.1-fast-generate-001',
    'google-veo-3-1-fast-i2v',
    'Google Veo 3.1 Fast (Image to Video)',
    'image_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["16:9", "9:16"],
          "default": "16:9"
        },
        "duration": {
          "type": "string",
          "enum": ["4", "6", "8"],
          "default": "8"
        },
        "resolution": {
          "type": "string",
          "enum": ["720p", "1080p", "4k"],
          "default": "720p"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "16:9", "duration": "8", "resolution": "720p"}'::jsonb,
    25.00,
    true
  ),
  (
    'google',
    'gemini-omni-1.2-flash',
    'google-omni-1-2-flash',
    'Google Gemini Omni 1.2 Flash (Text to Video)',
    'text_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {},
      "additionalProperties": false
    }'::jsonb,
    '{}'::jsonb,
    25.00,
    true
  ),
  (
    'google',
    'gemini-omni-1.2-flash',
    'google-omni-1-2-flash-i2v',
    'Google Gemini Omni 1.2 Flash (Image to Video)',
    'image_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {},
      "additionalProperties": false
    }'::jsonb,
    '{}'::jsonb,
    25.00,
    true
  )
on conflict (provider_id, provider_model, task_type) do update set
  slug = excluded.slug,
  display_name = excluded.display_name,
  input_schema = excluded.input_schema,
  default_params = excluded.default_params,
  cost_credits = excluded.cost_credits,
  enabled = excluded.enabled;

-- 4. Local dev user -------------------------------------------------------
-- Email:    dev@example.com
-- Password: DevPassword123!
-- Credits:  1000.00
create extension if not exists pgcrypto;

do $$
declare
  dev_user_id        uuid := '00000000-0000-0000-0000-000000000001';
  dev_workspace_id   uuid;
  current_balance    numeric(10,2);
begin
  -- 4.1 Create the auth user if it does not exist. The on_auth_user_created
  -- trigger (migration 0001) creates the profile, workspace, and owner
  -- membership automatically.
  if not exists (select 1 from auth.users where email = 'dev@example.com') then
    insert into auth.users (
      instance_id,
      id,
      aud,
      role,
      email,
      encrypted_password,
      email_confirmed_at,
      raw_app_meta_data,
      raw_user_meta_data,
      created_at,
      updated_at,
      confirmation_token,
      email_change,
      email_change_token_new,
      recovery_token
    ) values (
      '00000000-0000-0000-0000-000000000000',
      dev_user_id,
      'authenticated',
      'authenticated',
      'dev@example.com',
      crypt('DevPassword123!', gen_salt('bf')),
      now(),
      '{"provider":"email","providers":["email"]}'::jsonb,
      '{"full_name":"Dev User"}'::jsonb,
      now(),
      now(),
      '',
      '',
      '',
      ''
    );

  else
    select id into dev_user_id from auth.users where email = 'dev@example.com';
  end if;

  -- 4.2 Make email/password login work cleanly. This also repairs an existing
  -- dev user whose email identity is missing.
  if not exists (
    select 1
    from auth.identities
    where user_id = dev_user_id
      and provider = 'email'
  ) then
    insert into auth.identities (
      id,
      user_id,
      provider_id,
      identity_data,
      provider,
      last_sign_in_at,
      created_at,
      updated_at
    ) values (
      dev_user_id,
      dev_user_id,
      dev_user_id::text,
      format('{"sub":"%s","email":"dev@example.com"}', dev_user_id)::jsonb,
      'email',
      now(),
      now(),
      now()
    );
  end if;

  -- 4.3 Ensure the profile exists (the trigger normally handles this).
  insert into public.profiles (id, display_name)
  values (dev_user_id, 'Dev User')
  on conflict (id) do nothing;

  -- 4.4 Find the auto-provisioned workspace, or create one if the user
  -- already existed without a membership.
  select m.workspace_id
  into dev_workspace_id
  from public.workspace_members m
  where m.user_id = dev_user_id
  order by m.created_at
  limit 1;

  if dev_workspace_id is null then
    insert into public.workspaces (name, owner_id)
    values ('Dev User''s Workspace', dev_user_id)
    returning id into dev_workspace_id;

    insert into public.workspace_members (workspace_id, user_id, role)
    values (dev_workspace_id, dev_user_id, 'owner')
    on conflict (workspace_id, user_id) do nothing;
  end if;

  -- 4.5 Grant credits until the workspace balance is exactly 1000.
  select coalesce(sum(delta), 0)
  into current_balance
  from public.credit_ledger
  where workspace_id = dev_workspace_id;

  if current_balance < 1000 then
    insert into public.credit_ledger (workspace_id, delta, reason)
    values (dev_workspace_id, 1000 - current_balance, 'grant');
  end if;
end $$;
