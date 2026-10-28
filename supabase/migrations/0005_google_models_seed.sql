-- Migration 0005: Seed Google AI provider and Imagen 3 models.
-- Idempotent: uses ON CONFLICT ... DO UPDATE.

-- 1. Register Google Provider -----------------------------------------------
INSERT INTO public.providers (id, name, enabled)
VALUES ('google', 'Google AI (Imagen & Gemini)', true)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  enabled = EXCLUDED.enabled;

-- 2. Models: Imagen 3 (Text to Image) ----------------------------------------
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'google',
  'imagen-3.0-generate-002',
  'google-imagen-3',
  'Google Imagen 3 (High Quality)',
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
      "num_images": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 1
      },
      "output_format": {
        "type": "string",
        "enum": ["image/png", "image/jpeg", "image/webp"],
        "default": "image/png"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "1:1", "num_images": 1, "output_format": "image/png"}'::jsonb,
  3.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- 3. Models: Imagen 3 (Image to Image / Edit) -------------------------------
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'google',
  'imagen-3.0-generate-002',
  'google-imagen-3-remix',
  'Google Imagen 3 (Image Remix)',
  'image_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "aspect_ratio": {
        "type": "string",
        "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "default": "1:1"
      },
      "num_images": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 1
      },
      "output_format": {
        "type": "string",
        "enum": ["image/png", "image/jpeg", "image/webp"],
        "default": "image/png"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "1:1", "num_images": 1, "output_format": "image/png"}'::jsonb,
  4.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;
