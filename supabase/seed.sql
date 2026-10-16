-- supabase/seed.sql: Seed providers and models

-- 1. Providers ------------------------------------------------------------
insert into public.providers (id, name, enabled)
values
  ('fake', 'Deterministic Test Provider', true),
  ('replicate', 'Replicate', true),
  ('fal', 'Fal.ai', true)
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
