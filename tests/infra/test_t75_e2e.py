"""Static checks for the T7.5 browser E2E suite.

The suite itself runs with Playwright. These tests guard the configuration that
makes failures debuggable in CI and the flow coverage promised by the task.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "apps" / "web" / "e2e"


def _playwright_config() -> str:
    return (REPO_ROOT / "apps" / "web" / "playwright.config.ts").read_text(encoding="utf-8")


def _ci_workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    assert isinstance(loaded, dict)
    return loaded


def test_playwright_retains_failure_artifacts() -> None:
    config = _playwright_config()
    assert 'trace: "retain-on-failure"' in config
    assert 'video: "retain-on-failure"' in config
    assert 'screenshot: "only-on-failure"' in config
    assert "webServer" in config


def test_ci_builds_then_runs_e2e_and_uploads_artifacts() -> None:
    workflow = _ci_workflow()
    job = workflow["jobs"]["e2e"]
    assert job["timeout-minutes"] <= 15
    steps = "\n".join(str(step) for step in job["steps"])
    assert "pnpm --filter @studio/api-client build" in steps
    assert "pnpm --filter @studio/web build" in steps
    assert "playwright install --with-deps chromium" in steps
    assert "pnpm --filter @studio/web e2e" in steps
    assert "actions/upload-artifact@v4" in steps
    assert "apps/web/test-results" in steps
    assert "apps/web/playwright-report" in steps
    # The production server avoids multi-minute on-demand dev compilation.
    assert job["env"]["E2E_USE_PROD"] == "1"


def test_e2e_server_can_run_the_production_build() -> None:
    server = (E2E_DIR / "dev-server.mjs").read_text(encoding="utf-8")
    assert 'process.env.E2E_USE_PROD === "1"' in server
    assert 'useProductionBuild ? "start" : "dev"' in server


def test_specs_cover_the_launch_flow_checklist() -> None:
    specs = "\n".join(path.read_text(encoding="utf-8") for path in E2E_DIR.glob("*.spec.ts"))
    for marker in (
        "requests a magic link",
        "creates a project",
        "uploads an image asset",
        "submits a prompt",
        "image-to-video generation",
        "cancels a running generation",
        "retries a failed generation",
        "insufficient-credits",
        "FAIL",
        "NO_CREDITS",
    ):
        assert marker in specs, marker
