# ADR-003: Initial Model Selection

**Status:** Accepted  
**Date:** 2026-10-28  
**Decision makers:** Engineering team  

## Context

The MVP needs one or two real models per task type (text→image, image→image, text→video, image→video) from our supported providers (Replicate and Fal.ai). We need models that are:

1. **Stable** — actively maintained, unlikely to be deprecated soon.
2. **Cost-effective** — reasonable cost for an MVP where users get a credit budget.
3. **High quality** — state-of-the-art or near-SOTA results for their task type.
4. **Webhook-capable** — support asynchronous completion notifications.

## Decision

### Text → Image

| Model | Provider | Slug | Rationale |
|-------|----------|------|-----------|
| FLUX Schnell (BFL) | Replicate | `replicate-flux-schnell` | Very fast (~2s), high quality, widely used, cost-effective (~$0.003/image). Excellent text rendering and prompt adherence. |
| FLUX.1 [schnell] | Fal.ai | `fal-flux-schnell` | Same underlying model via Fal's infrastructure. Provides provider redundancy. |

### Image → Image

| Model | Provider | Slug | Rationale |
|-------|----------|------|-----------|
| FLUX Depth/Canny (BFL) | Replicate | `replicate-flux-depth` | ControlNet-style image-to-image with structural guidance. Good balance of fidelity and editability. |

### Text → Video

| Model | Provider | Slug | Rationale |
|-------|----------|------|-----------|
| MiniMax Video-01 (Hailuo) | Replicate | `replicate-minimax-video` | High-quality cinematic video from text. Strong motion coherence and physical realism. Supports 5s and 10s durations. |
| Kling v2 Standard | Fal.ai | `fal-kling-t2v` | Reliable text-to-video with good prompt adherence. Competitive quality at lower cost. |

### Image → Video

| Model | Provider | Slug | Rationale |
|-------|----------|------|-----------|
| MiniMax Video-01 I2V | Replicate | `replicate-minimax-i2v` | Excellent first-frame conditioning, smooth motion. |
| Kling v2 Standard I2V | Fal.ai | `fal-kling-i2v` | Robust image-to-video with `start_image_url` conditioning. Supports 5s and 10s. |

### Credit pricing formula

Credits are a unitless internal currency. We set 1 credit ≈ \$0.01 USD in provider cost:

| Task type | Typical provider cost | Credits |
|-----------|----------------------|---------|
| text_to_image | \$0.003–\$0.05 | 1–5 |
| image_to_image | \$0.005–\$0.05 | 2–5 |
| text_to_video (5s) | \$0.05–\$0.50 | 10–50 |
| image_to_video (5s) | \$0.05–\$0.50 | 10–50 |

We round up to simple integers for UX clarity and margin.

## Consequences

- FakeProvider models remain enabled only when `ENVIRONMENT != 'production'` (enforced in seed migration).
- New models can be added via a database migration (idempotent upsert) without code changes — only a mapper entry is needed if the model's input schema differs from the default mapping.
- Provider redundancy (same task type across Replicate and Fal) lets us disable one provider during outages.
