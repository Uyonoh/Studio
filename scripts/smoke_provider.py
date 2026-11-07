#!/usr/bin/env python3
"""Manual smoke test for real provider adapters.

Usage:
    python scripts/smoke_provider.py replicate
    python scripts/smoke_provider.py fal

Requires credentials in environment variables (REPLICATE_API_TOKEN or FAL_KEY).
NOT run in CI — manual verification only.
"""

import asyncio
import os
import sys
import time


async def smoke_replicate() -> None:
    """Smoke test: submit a text→image prediction on Replicate."""
    from studio_core.models import TaskType
    from studio_providers.base import ProviderRequest
    from studio_providers.replicate import ReplicateProvider

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("ERROR: REPLICATE_API_TOKEN not set")
        sys.exit(1)

    provider = ReplicateProvider(api_token=token)
    req = ProviderRequest(
        task_type=TaskType.TEXT_TO_IMAGE,
        model="black-forest-labs/flux-schnell",
        prompt="A serene Japanese garden with a koi pond, soft morning light, photorealistic",
        params={"num_outputs": 1},
    )

    print("[replicate] Submitting text→image prediction...")
    ref = await provider.submit(req)
    print(f"[replicate] Prediction ID: {ref.provider_job_id}")

    # Poll until terminal
    for i in range(60):
        status = await provider.get_status(ref)
        print(f"[replicate] Status: {status.state} (poll {i + 1})")
        if status.state in ("succeeded", "failed", "canceled"):
            if status.outputs:
                for j, out in enumerate(status.outputs):
                    print(f"[replicate] Output {j}: {out.url} ({out.kind})")
            if status.error_message:
                print(f"[replicate] Error: {status.error_message}")
            break
        await asyncio.sleep(2)
    else:
        print("[replicate] Timed out after 120s")


async def smoke_fal() -> None:
    """Smoke test: submit a text→image request on Fal."""
    from studio_core.models import TaskType
    from studio_providers.base import ProviderRequest
    from studio_providers.fal import FalProvider

    key = os.environ.get("FAL_KEY")
    if not key:
        print("ERROR: FAL_KEY not set")
        sys.exit(1)

    provider = FalProvider(api_key=key)
    req = ProviderRequest(
        task_type=TaskType.TEXT_TO_IMAGE,
        model="fal-ai/flux/schnell",
        prompt="A serene Japanese garden with a koi pond, soft morning light, photorealistic",
        params={"image_size": "landscape_16_9", "num_images": 1},
    )

    print("[fal] Submitting text→image request...")
    ref = await provider.submit(req)
    print(f"[fal] Request ID: {ref.provider_job_id}")

    # Poll until terminal
    for i in range(60):
        status = await provider.get_status(ref)
        print(f"[fal] Status: {status.state} (poll {i + 1})")
        if status.state in ("succeeded", "failed", "canceled"):
            if status.outputs:
                for j, out in enumerate(status.outputs):
                    print(f"[fal] Output {j}: {out.url} ({out.kind})")
            if status.error_message:
                print(f"[fal] Error: {status.error_message}")
            break
        await asyncio.sleep(2)
    else:
        print("[fal] Timed out after 120s")


async def smoke_google() -> None:
    """Smoke test: submit a prediction to Google AI (Imagen 3 or Veo 2)."""
    from studio_core.models import TaskType
    from studio_providers.base import ProviderRequest
    from studio_providers.google import GoogleProvider

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("ERROR: GEMINI_API_KEY or GOOGLE_API_KEY not set")
        sys.exit(1)

    provider = GoogleProvider(api_key=key)

    mode = "image"
    if len(sys.argv) >= 3 and sys.argv[2] in ("video", "image"):
        mode = sys.argv[2]

    if mode == "video":
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_VIDEO,
            model="veo-2.0-generate-001",
            prompt="A tranquil drone shot sweeping over autumn trees and a gentle river at sunset",
            params={"aspect_ratio": "16:9", "duration": 5, "resolution": "720p"},
        )
        print("[google] Submitting text→video prediction to Veo 2 (predictLongRunning)...")
    else:
        req = ProviderRequest(
            task_type=TaskType.TEXT_TO_IMAGE,
            model="imagen-3.0-generate-002",
            prompt="A serene Japanese garden with a koi pond, soft morning light, photorealistic",
            params={"aspect_ratio": "16:9", "num_images": 1},
        )
        print("[google] Submitting text→image prediction to Imagen 3...")

    ref = await provider.submit(req)
    print(f"[google] Prediction / Operation ID: {ref.provider_job_id}")

    # Poll status (synchronous for Imagen, async operation polling for Veo)
    for i in range(120):
        status = await provider.get_status(ref)
        print(f"[google] Status: {status.state} (poll {i + 1})")
        if status.state in ("succeeded", "failed", "canceled"):
            if status.outputs:
                for j, out in enumerate(status.outputs):
                    url_preview = out.url[:70] + "..." if len(out.url) > 70 else out.url
                    print(f"[google] Output {j}: {url_preview} ({out.kind})")
            if status.error_message:
                print(f"[google] Error: {status.error_message}")
            break
        await asyncio.sleep(5)
    else:
        print("[google] Timed out after polling")


PROVIDERS = {
    "replicate": smoke_replicate,
    "fal": smoke_fal,
    "google": smoke_google,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROVIDERS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(PROVIDERS.keys())}>")
        sys.exit(1)

    provider_name = sys.argv[1]
    print(f"Running smoke test for {provider_name}...")
    start = time.time()
    asyncio.run(PROVIDERS[provider_name]())
    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s")
