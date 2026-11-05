"""Static checks for the T7.4 deployment workflow.

The real DoD (a merge reaching staging, a gated production deploy, and a
rehearsed rollback) requires GitHub/Render/Vercel/Supabase credentials. These
tests keep the committed pipeline structure honest in the meantime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "deploy.yml"


def _workflow() -> dict[Any, Any]:
    loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML resolves the unquoted YAML 1.1 key `on` to boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _steps(job: dict[str, Any]) -> str:
    return "\n".join(json.dumps(step) for step in job["steps"])


def test_triggers_cover_pr_main_and_manual_dispatch() -> None:
    triggers = _triggers(_workflow())
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["pull_request"]["branches"] == ["main"]

    dispatch = triggers["workflow_dispatch"]
    target = dispatch["inputs"]["target"]
    assert target["required"] is True
    assert target["default"] == "staging"
    assert set(target["options"]) == {"staging", "production"}


def test_preview_handles_optional_supabase_branch_and_vercel_cli() -> None:
    preview = _workflow()["jobs"]["preview"]
    assert preview["environment"] == "preview"
    steps = _steps(preview)
    assert "SUPABASE_BRANCHING_ENABLED" in steps
    assert "supabase branches create" in steps
    assert "supabase db push" in steps
    assert "VERCEL_PREVIEWS_VIA_CLI" in steps
    assert "vercel@latest deploy --prebuilt" in steps


def test_staging_is_automatic_and_ordered() -> None:
    staging = _workflow()["jobs"]["staging"]
    assert staging["environment"] == "staging"
    assert "github.event_name == 'push'" in staging["if"]

    names = [step.get("name", "") for step in staging["steps"]]
    migrate = next(i for i, name in enumerate(names) if "migrations" in name.lower())
    render = next(i for i, name in enumerate(names) if "Render" in name)
    vercel = next(i for i, name in enumerate(names) if "Vercel" in name)
    readiness = next(i for i, name in enumerate(names) if "readiness" in name.lower())
    smoke = next(i for i, name in enumerate(names) if "Smoke" in name)
    assert migrate < render < vercel < readiness < smoke

    steps = _steps(staging)
    assert "supabase db push --include-all" in steps
    assert "RENDER_STAGING_API_DEPLOY_HOOK" in steps
    assert "RENDER_STAGING_WORKER_DEPLOY_HOOK" in steps
    assert "VERCEL_STAGING_DEPLOY_HOOK" in steps
    assert "/readyz" in steps
    assert "scripts/smoke_staging.sh" in steps
    assert "grant_type=password" in steps
    assert "SMOKE_MODEL" in steps


def test_production_requires_manual_dispatch_and_protected_environment() -> None:
    production = _workflow()["jobs"]["production"]
    assert production["environment"] == "production"
    assert "github.event_name == 'workflow_dispatch'" in production["if"]
    assert "inputs.target == 'production'" in production["if"]

    steps = _steps(production)
    assert "RENDER_PRODUCTION_API_DEPLOY_HOOK" in steps
    assert "RENDER_PRODUCTION_WORKER_DEPLOY_HOOK" in steps
    assert "VERCEL_PRODUCTION_DEPLOY_HOOK" in steps
    assert "scripts/smoke_staging.sh" in steps


def test_workflow_uses_secrets_and_vars_not_hardcoded_values() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "${{ secrets." in text
    assert "${{ vars." in text
    for marker in (
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_STAGING_DB_URL=",
        "postgresql://",
        "https://studio-api",
    ):
        assert marker not in text


def test_migration_policy_is_documented() -> None:
    runbook = (REPO_ROOT / "docs" / "runbooks" / "deployment.md").read_text(encoding="utf-8")
    assert "expand" in runbook.lower()
    assert "contract" in runbook.lower()
    assert "backward-compatible" in runbook.lower()
