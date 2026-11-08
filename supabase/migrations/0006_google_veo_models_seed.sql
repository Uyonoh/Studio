-- Migration 0006: Seed Google Veo video generation models.
-- Idempotent: uses ON CONFLICT ... DO UPDATE.

-- 1. Ensure Google Provider is registered and enabled -----------------------
INSERT INTO public.providers (id, name, enabled)
VALUES ('google', 'Google AI (Imagen, Gemini & Veo)', true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  enabled = EXCLUDED.enabled;

-- 2. Models: Veo 2 (Text to Video) ------------------------------------------
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'google',
  'veo-2.0-generate-001',
  'google-veo-2',
  'Google Veo 2 (Text to Video)',
  'text_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "aspect_ratio": {
        "type": "string",
        "enum": ["16:9", "9:16", "1:1"],
        "default": "16:9"
      },
      "duration": {
        "type": "string",
        "enum": ["5", "8"],
        "default": "5"
      },
      "resolution": {
        "type": "string",
        "enum": ["720p", "1080p"],
        "default": "720p"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "16:9", "duration": "5", "resolution": "720p"}'::jsonb,
  25.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- 3. Models: Veo 2 (Image to Video) -----------------------------------------
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'google',
  'veo-2.0-generate-001',
  'google-veo-2-i2v',
  'Google Veo 2 (Image to Video)',
  'image_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "aspect_ratio": {
        "type": "string",
        "enum": ["16:9", "9:16", "1:1"],
        "default": "16:9"
      },
      "duration": {
        "type": "string",
        "enum": ["5", "8"],
        "default": "5"
      },
      "resolution": {
        "type": "string",
        "enum": ["720p", "1080p"],
        "default": "720p"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "16:9", "duration": "5", "resolution": "720p"}'::jsonb,
  25.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;
