-- Migration 0008: Expand the Replicate catalog with models from the
-- "Try for Free" collection (https://replicate.com/collections/try-for-free).
--
-- Existing Replicate coverage (migration 0004):
--   * black-forest-labs/flux-schnell   text -> image (budget)
--   * xlabs-ai/flux-dev-controlnet     image -> image (structural)
--   * minimax/video-01                 text/image -> video
--
-- This migration adds the image generation, editing, upscaling, and
-- restoration models that are currently available from that collection.
-- The collection still links google/imagen-4, but that model has been
-- delisted from Replicate, so google/nano-banana is used as the Google
-- image option instead.
--
-- Video reframing/upscaling models in the collection (luma/reframe-video,
-- topazlabs/video-upscale) are intentionally omitted because the catalog
-- only supports text/image -> video, not video -> video.
--
-- Idempotent: ON CONFLICT ... DO UPDATE keeps re-runs safe.

-- ═══════════════════════════════════════════════════════════════════════════
-- TEXT → IMAGE
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES
  (
    'replicate',
    'black-forest-labs/flux-1.1-pro',
    'replicate-flux-1-1-pro',
    'FLUX 1.1 Pro (High Fidelity Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["custom", "1:1", "16:9", "3:2", "2:3", "4:5", "5:4", "9:16", "3:4", "4:3"],
          "default": "1:1"
        },
        "width": {
          "type": "integer",
          "minimum": 256,
          "maximum": 1440
        },
        "height": {
          "type": "integer",
          "minimum": 256,
          "maximum": 1440
        },
        "output_format": {
          "type": "string",
          "enum": ["webp", "jpg", "png"],
          "default": "webp"
        },
        "output_quality": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "default": 80
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 6,
          "default": 2
        },
        "prompt_upsampling": {
          "type": "boolean",
          "default": false
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1", "output_format": "webp", "output_quality": 80, "safety_tolerance": 2, "prompt_upsampling": false}'::jsonb,
    4.00,
    true
  ),
  (
    'replicate',
    'black-forest-labs/flux-dev',
    'replicate-flux-dev',
    'FLUX.1 Dev (Balanced Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:1", "16:9", "21:9", "3:2", "2:3", "4:5", "5:4", "3:4", "4:3", "9:16", "9:21"],
          "default": "1:1"
        },
        "num_outputs": {
          "type": "integer",
          "minimum": 1,
          "maximum": 4,
          "default": 1
        },
        "num_inference_steps": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50,
          "default": 28
        },
        "guidance": {
          "type": "number",
          "minimum": 0,
          "maximum": 10,
          "default": 3.5
        },
        "megapixels": {
          "type": "string",
          "enum": ["1", "0.25"],
          "default": "1"
        },
        "output_format": {
          "type": "string",
          "enum": ["webp", "jpg", "png"],
          "default": "webp"
        },
        "output_quality": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "default": 80
        },
        "go_fast": {
          "type": "boolean",
          "default": true
        },
        "disable_safety_checker": {
          "type": "boolean",
          "default": false
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1", "num_outputs": 1, "num_inference_steps": 28, "guidance": 3.5, "megapixels": "1", "output_format": "webp", "output_quality": 80, "go_fast": true, "disable_safety_checker": false}'::jsonb,
    3.00,
    true
  ),
  (
    'replicate',
    'black-forest-labs/flux-2-pro',
    'replicate-flux-2-pro',
    'FLUX.2 Pro (Premium Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["match_input_image", "custom", "1:1", "16:9", "3:2", "2:3", "4:5", "5:4", "9:16", "3:4", "4:3"],
          "default": "1:1"
        },
        "resolution": {
          "type": "string",
          "enum": ["match_input_image", "0.5 MP", "1 MP", "2 MP", "4 MP"],
          "default": "1 MP"
        },
        "width": {
          "type": "integer",
          "minimum": 256,
          "maximum": 2048
        },
        "height": {
          "type": "integer",
          "minimum": 256,
          "maximum": 2048
        },
        "output_format": {
          "type": "string",
          "enum": ["webp", "jpg", "png"],
          "default": "webp"
        },
        "output_quality": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "default": 80
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5,
          "default": 2
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1", "resolution": "1 MP", "output_format": "webp", "output_quality": 80, "safety_tolerance": 2}'::jsonb,
    5.00,
    true
  ),
  (
    'replicate',
    'ideogram-ai/ideogram-v3-turbo',
    'replicate-ideogram-v3-turbo',
    'Ideogram 3.0 Turbo (Text & Design)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["1:3", "3:1", "1:2", "2:1", "9:16", "16:9", "10:16", "16:10", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "1:1"],
          "default": "1:1"
        },
        "style_type": {
          "type": "string",
          "enum": ["None", "Auto", "General", "Realistic", "Design"],
          "default": "None"
        },
        "magic_prompt_option": {
          "type": "string",
          "enum": ["Auto", "On", "Off"],
          "default": "Auto"
        },
        "seed": {
          "type": "integer",
          "minimum": 0,
          "maximum": 2147483647
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "1:1", "style_type": "None", "magic_prompt_option": "Auto"}'::jsonb,
    3.00,
    true
  ),
  (
    'replicate',
    'google/nano-banana',
    'replicate-nano-banana',
    'Google Nano Banana (Fast Image)',
    'text_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["match_input_image", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "match_input_image"
        },
        "output_format": {
          "type": "string",
          "enum": ["jpg", "png"],
          "default": "jpg"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "match_input_image", "output_format": "jpg"}'::jsonb,
    4.00,
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
-- IMAGE → IMAGE
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO public.models (
  provider_id, provider_model, slug, display_name, task_type,
  input_schema, default_params, cost_credits, enabled
) VALUES
  (
    'replicate',
    'black-forest-labs/flux-kontext-pro',
    'replicate-flux-kontext-pro',
    'FLUX.1 Kontext Pro (Instruction Edit)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["match_input_image", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4", "21:9", "9:21", "2:1", "1:2"],
          "default": "match_input_image"
        },
        "output_format": {
          "type": "string",
          "enum": ["jpg", "png"],
          "default": "png"
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 0,
          "maximum": 6,
          "default": 2
        },
        "prompt_upsampling": {
          "type": "boolean",
          "default": false
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "match_input_image", "output_format": "png", "safety_tolerance": 2, "prompt_upsampling": false}'::jsonb,
    5.00,
    true
  ),
  (
    'replicate',
    'black-forest-labs/flux-2-pro',
    'replicate-flux-2-pro-edit',
    'FLUX.2 Pro Edit (Image to Image)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["match_input_image", "custom", "1:1", "16:9", "3:2", "2:3", "4:5", "5:4", "9:16", "3:4", "4:3"],
          "default": "match_input_image"
        },
        "resolution": {
          "type": "string",
          "enum": ["match_input_image", "0.5 MP", "1 MP", "2 MP", "4 MP"],
          "default": "match_input_image"
        },
        "width": {
          "type": "integer",
          "minimum": 256,
          "maximum": 2048
        },
        "height": {
          "type": "integer",
          "minimum": 256,
          "maximum": 2048
        },
        "output_format": {
          "type": "string",
          "enum": ["webp", "jpg", "png"],
          "default": "webp"
        },
        "output_quality": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100,
          "default": 80
        },
        "safety_tolerance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5,
          "default": 2
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "match_input_image", "resolution": "match_input_image", "output_format": "webp", "output_quality": 80, "safety_tolerance": 2}'::jsonb,
    5.00,
    true
  ),
  (
    'replicate',
    'google/nano-banana',
    'replicate-nano-banana-edit',
    'Google Nano Banana Edit (Image to Image)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "aspect_ratio": {
          "type": "string",
          "enum": ["match_input_image", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
          "default": "match_input_image"
        },
        "output_format": {
          "type": "string",
          "enum": ["jpg", "png"],
          "default": "jpg"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"aspect_ratio": "match_input_image", "output_format": "jpg"}'::jsonb,
    4.00,
    true
  ),
  (
    'replicate',
    'topazlabs/image-upscale',
    'replicate-image-upscale',
    'Topaz Image Upscale (Enhance)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "enhance_model": {
          "type": "string",
          "enum": ["Standard V2", "Low Resolution V2", "CGI", "High Fidelity V2", "Text Refine"],
          "default": "Standard V2"
        },
        "output_format": {
          "type": "string",
          "enum": ["jpg", "png"],
          "default": "jpg"
        },
        "upscale_factor": {
          "type": "string",
          "enum": ["None", "2x", "4x", "6x"],
          "default": "None"
        },
        "face_enhancement": {
          "type": "boolean",
          "default": false
        },
        "subject_detection": {
          "type": "string",
          "enum": ["None", "All", "Foreground", "Background"],
          "default": "None"
        },
        "face_enhancement_strength": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.8
        },
        "face_enhancement_creativity": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"enhance_model": "Standard V2", "output_format": "jpg", "upscale_factor": "None", "face_enhancement": false, "subject_detection": "None", "face_enhancement_strength": 0.8, "face_enhancement_creativity": 0}'::jsonb,
    2.00,
    true
  ),
  (
    'replicate',
    'sczhou/codeformer',
    'replicate-codeformer',
    'CodeFormer (Face Restoration)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "upscale": {
          "type": "integer",
          "minimum": 1,
          "maximum": 4,
          "default": 2
        },
        "face_upsample": {
          "type": "boolean",
          "default": true
        },
        "background_enhance": {
          "type": "boolean",
          "default": true
        },
        "codeformer_fidelity": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "default": 0.5
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"upscale": 2, "face_upsample": true, "background_enhance": true, "codeformer_fidelity": 0.5}'::jsonb,
    1.00,
    true
  ),
  (
    'replicate',
    'tencentarc/gfpgan',
    'replicate-gfpgan',
    'GFPGAN (Face Restoration)',
    'image_to_image',
    '{
      "$schema": "http://json-schema.org/draft-07/schema#",
      "type": "object",
      "properties": {
        "scale": {
          "type": "number",
          "minimum": 1,
          "maximum": 4,
          "default": 2
        },
        "version": {
          "type": "string",
          "enum": ["v1.2", "v1.3", "v1.4", "RestoreFormer"],
          "default": "v1.4"
        }
      },
      "additionalProperties": false
    }'::jsonb,
    '{"scale": 2, "version": "v1.4"}'::jsonb,
    1.00,
    true
  )
ON CONFLICT (provider_id, provider_model, task_type) DO UPDATE SET
  slug = EXCLUDED.slug,
  display_name = EXCLUDED.display_name,
  input_schema = EXCLUDED.input_schema,
  default_params = EXCLUDED.default_params,
  cost_credits = EXCLUDED.cost_credits,
  enabled = EXCLUDED.enabled;
