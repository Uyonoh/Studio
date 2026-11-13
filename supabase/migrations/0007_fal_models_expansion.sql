-- Migration 0007: Expand the Fal.ai catalog with cheap and mid/high tiers.
--
-- Existing Fal.ai coverage (migration 0004):
--   * fal-ai/flux/schnell          text -> image (cheap)
--   * fal-ai/kling-video/v2/...    text/image -> video (mid)
--
-- This migration adds two tiers per task type so the composer can offer a
-- budget option and a higher-fidelity option without leaving Fal.ai.
-- Idempotent: ON CONFLICT ... DO UPDATE keeps re-runs safe.

-- ═══════════════════════════════════════════════════════════════════════════
-- IMAGE MODELS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES
  (
    'fal',
    'fal-ai/flux/dev',
    'fal-flux-dev',
    'FLUX.1 Dev (Balanced Image)',
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
        "num_inference_steps": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50,
          "default": 28
        },
        "guidance_scale": {
          "type": "number",
          "minimum": 1.0,
          "maximum": 20.0,
          "default": 3.5
        },
        "num_images": {
          "type": "integer",
          "minimum": 1,
          "maximum": 4,
          "default": 1
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "output_format": {
          "type": "string",
          "enum": ["jpeg", "png"],
          "default": "jpeg"
        },
        "enable_safety_checker": {
          "type": "boolean",
          "default": true
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"image_size": "landscape_4_3", "num_inference_steps": 28, "guidance_scale": 3.5, "num_images": 1, "output_format": "jpeg", "enable_safety_checker": true}'::jsonb,
    3.00,
    true
  ),
  (
    'fal',
    'fal-ai/flux-pro/v1.1',
    'fal-flux-pro-1-1',
    'FLUX1.1 Pro (High Fidelity Image)',
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
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "output_format": {
          "type": "string",
          "enum": ["jpeg", "png"],
          "default": "jpeg"
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 6,
          "default": 2
        },
        "enhance_prompt": {
          "type": "boolean",
          "default": false
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"image_size": "landscape_4_3", "num_images": 1, "output_format": "jpeg", "safety_tolerance": 2, "enhance_prompt": false}'::jsonb,
    5.00,
    true
  ),
  (
    'fal',
    'fal-ai/flux/dev/image-to-image',
    'fal-flux-dev-i2i',
    'FLUX.1 Dev Remix (Image to Image)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "strength": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "default": 0.85
        },
        "num_inference_steps": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50,
          "default": 28
        },
        "guidance_scale": {
          "type": "number",
          "minimum": 1.0,
          "maximum": 20.0,
          "default": 3.5
        },
        "num_images": {
          "type": "integer",
          "minimum": 1,
          "maximum": 4,
          "default": 1
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "output_format": {
          "type": "string",
          "enum": ["jpeg", "png"],
          "default": "jpeg"
        },
        "enable_safety_checker": {
          "type": "boolean",
          "default": true
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"strength": 0.85, "num_inference_steps": 28, "guidance_scale": 3.5, "num_images": 1, "output_format": "jpeg", "enable_safety_checker": true}'::jsonb,
    3.00,
    true
  ),
  (
    'fal',
    'fal-ai/flux-pro/kontext',
    'fal-flux-kontext-pro',
    'FLUX.1 Kontext Pro (Instruction Edit)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16", "9:21"],
          "default": "1:1"
        },
        "num_images": {
          "type": "integer",
          "minimum": 1,
          "maximum": 4,
          "default": 1
        },
        "guidance_scale": {
          "type": "number",
          "minimum": 1.0,
          "maximum": 20.0,
          "default": 3.5
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "output_format": {
          "type": "string",
          "enum": ["jpeg", "png"],
          "default": "jpeg"
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 6,
          "default": 2
        },
        "enhance_prompt": {
          "type": "boolean",
          "default": false
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1", "num_images": 1, "guidance_scale": 3.5, "output_format": "jpeg", "safety_tolerance": 2, "enhance_prompt": false}'::jsonb,
    5.00,
    true
  )
ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;

-- ═══════════════════════════════════════════════════════════════════════════
-- VIDEO MODELS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES
  (
    'fal',
    'minimax/h3-max-turbo/text-to-video',
    'fal-h3-max-turbo-t2v',
    'H3 Max Turbo (Fast Text to Video)',
    'text_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "duration": {
          "type": "integer",
          "minimum": 5,
          "maximum": 15,
          "default": 5
        },
        "resolution": {
          "type": "string",
          "enum": ["480P", "768P", "1080P"],
          "default": "768P"
        },
        "aspect_ratio": {
          "type": "string",
          "enum": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
          "default": "16:9"
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
    '{"duration": 5, "resolution": "768P", "aspect_ratio": "16:9", "enable_safety_checker": true}'::jsonb,
    10.00,
    true
  ),
  (
    'fal',
    'minimax/h3-max-turbo/image-to-video',
    'fal-h3-max-turbo-i2v',
    'H3 Max Turbo (Fast Image to Video)',
    'image_to_video',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "duration": {
          "type": "integer",
          "minimum": 5,
          "maximum": 15,
          "default": 5
        },
        "resolution": {
          "type": "string",
          "enum": ["480P", "768P", "1080P"],
          "default": "768P"
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
    '{"duration": 5, "resolution": "768P", "enable_safety_checker": true}'::jsonb,
    10.00,
    true
  ),
  (
    'fal',
    'fal-ai/kling-video/v2.5-turbo/pro/text-to-video',
    'fal-kling-2-5-turbo-t2v',
    'Kling 2.5 Turbo Pro (Text to Video)',
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
        "negative_prompt": {
          "type": "string",
          "maxLength": 2500
        },
        "cfg_scale": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "default": 0.5
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"duration": "5", "aspect_ratio": "16:9", "cfg_scale": 0.5}'::jsonb,
    40.00,
    true
  ),
  (
    'fal',
    'fal-ai/kling-video/v2.5-turbo/pro/image-to-video',
    'fal-kling-2-5-turbo-i2v',
    'Kling 2.5 Turbo Pro (Image to Video)',
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
        "negative_prompt": {
          "type": "string",
          "maxLength": 2500
        },
        "cfg_scale": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "default": 0.5
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"duration": "5", "cfg_scale": 0.5}'::jsonb,
    40.00,
    true
  )
ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;
