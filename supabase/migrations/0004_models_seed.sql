-- Migration 0004: Seed real model catalog rows for Replicate and Fal.ai providers.
-- See docs/adr/003-initial-models.md for selection rationale and pricing formula.
-- Idempotent: uses ON CONFLICT ... DO UPDATE for safe re-runs.

-- ═══════════════════════════════════════════════════════════════════════════
-- TEXT → IMAGE
-- ═══════════════════════════════════════════════════════════════════════════

-- Replicate: FLUX Schnell (Black Forest Labs)
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'replicate',
  'black-forest-labs/flux-schnell',
  'replicate-flux-schnell',
  'FLUX Schnell (Fast Image)',
  'text_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "aspect_ratio": {
        "type": "string",
        "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21"],
        "default": "1:1"
      },
      "num_outputs": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 1
      },
      "output_format": {
        "type": "string",
        "enum": ["png", "jpg", "webp"],
        "default": "webp"
      },
      "output_quality": {
        "type": "integer",
        "minimum": 1,
        "maximum": 100,
        "default": 80
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      },
      "num_inference_steps": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 4
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"aspect_ratio": "1:1", "num_outputs": 1, "output_format": "webp", "output_quality": 80, "num_inference_steps": 4}'::jsonb,
  1.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- Fal.ai: FLUX Schnell
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'fal',
  'fal-ai/flux/schnell',
  'fal-flux-schnell',
  'FLUX Schnell (Fal)',
  'text_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "image_size": {
        "type": "string",
        "enum": ["square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"],
        "default": "landscape_4_3"
      },
      "num_images": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 1
      },
      "num_inference_steps": {
        "type": "integer",
        "minimum": 1,
        "maximum": 12,
        "default": 4
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      },
      "enable_safety_checker": {
        "type": "boolean",
        "default": true
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"image_size": "landscape_4_3", "num_images": 1, "num_inference_steps": 4, "enable_safety_checker": true}'::jsonb,
  1.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- ═══════════════════════════════════════════════════════════════════════════
-- IMAGE → IMAGE
-- ═══════════════════════════════════════════════════════════════════════════

-- Replicate: FLUX Depth (ControlNet-style)
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'replicate',
  'xlabs-ai/flux-dev-controlnet',
  'replicate-flux-depth',
  'FLUX ControlNet (Image Remix)',
  'image_to_image',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "num_outputs": {
        "type": "integer",
        "minimum": 1,
        "maximum": 4,
        "default": 1
      },
      "guidance_scale": {
        "type": "number",
        "minimum": 1.0,
        "maximum": 30.0,
        "default": 3.5
      },
      "num_inference_steps": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 28
      },
      "strength": {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
        "default": 0.85
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      },
      "output_format": {
        "type": "string",
        "enum": ["png", "jpg", "webp"],
        "default": "webp"
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"num_outputs": 1, "guidance_scale": 3.5, "num_inference_steps": 28, "strength": 0.85, "output_format": "webp"}'::jsonb,
  3.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- ═══════════════════════════════════════════════════════════════════════════
-- TEXT → VIDEO
-- ═══════════════════════════════════════════════════════════════════════════

-- Replicate: MiniMax Video-01 (Hailuo)
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'replicate',
  'minimax/video-01',
  'replicate-minimax-video',
  'MiniMax Video-01 (Cinematic)',
  'text_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "prompt_optimizer": {
        "type": "boolean",
        "default": true
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"prompt_optimizer": true}'::jsonb,
  25.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- Fal.ai: Kling v2 Standard (Text→Video)
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'fal',
  'fal-ai/kling-video/v2/standard/text-to-video',
  'fal-kling-t2v',
  'Kling v2 (Text to Video)',
  'text_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "duration": {
        "type": "string",
        "enum": ["5", "10"],
        "default": "5"
      },
      "aspect_ratio": {
        "type": "string",
        "enum": ["16:9", "9:16", "1:1"],
        "default": "16:9"
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"duration": "5", "aspect_ratio": "16:9"}'::jsonb,
  20.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- ═══════════════════════════════════════════════════════════════════════════
-- IMAGE → VIDEO
-- ═══════════════════════════════════════════════════════════════════════════

-- Replicate: MiniMax Video-01 I2V
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'replicate',
  'minimax/video-01',
  'replicate-minimax-i2v',
  'MiniMax Video-01 I2V (Animate Image)',
  'image_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "prompt_optimizer": {
        "type": "boolean",
        "default": true
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"prompt_optimizer": true}'::jsonb,
  25.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- Fal.ai: Kling v2 Standard (Image→Video)
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES (
  'fal',
  'fal-ai/kling-video/v2/standard/image-to-video',
  'fal-kling-i2v',
  'Kling v2 (Animate Image)',
  'image_to_video',
  '{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "duration": {
        "type": "string",
        "enum": ["5", "10"],
        "default": "5"
      },
      "seed": {
        "type": "integer",
        "minimum": 0
      }
    },
    "additionalProperties": false
  }'::jsonb,
  '{"duration": "5"}'::jsonb,
  20.00,
  true
) ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- ═══════════════════════════════════════════════════════════════════════════
-- Ensure FakeProvider models are disabled in production
-- ═══════════════════════════════════════════════════════════════════════════
-- NOTE: This is enforced by the application registry (FakeProvider only
-- registers when ENVIRONMENT != 'production'). The DB rows remain enabled
-- for local dev and staging. To disable them in production DB:
--
--   UPDATE public.models SET enabled = false WHERE provider_id = 'fake';
