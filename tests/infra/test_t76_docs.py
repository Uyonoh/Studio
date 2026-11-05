"""Static checks for T7.6: Documentation, ADRs, and Runbooks.

Ensures all architectural decisions, operational runbooks, developer onboarding,
and OpenAPI contract references are present, complete, and properly structured.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
ADR_DIR = DOCS_DIR / "adr"
RUNBOOKS_DIR = DOCS_DIR / "runbooks"
README_PATH = REPO_ROOT / "README.md"
OPENAPI_PATH = DOCS_DIR / "openapi.json"


def test_required_adrs_exist_and_follow_template() -> None:
    expected_adrs = [
        "001-postgres-job-source-of-truth.md",
        "002-arq-vs-celery.md",
        "003-initial-models.md",
    ]
    for adr_name in expected_adrs:
        path = ADR_DIR / adr_name
        assert path.is_file(), f"Missing ADR: {adr_name}"
        content = path.read_text(encoding="utf-8")
        assert "**Status:** Accepted" in content, f"{adr_name} missing status"
        assert "## Context" in content, f"{adr_name} missing Context"
        assert "## Decision" in content, f"{adr_name} missing Decision"
        assert "## Consequences" in content, f"{adr_name} missing Consequences"


def test_required_runbooks_exist_and_contain_core_sections() -> None:
    expected_runbooks = {
        "stuck-jobs.md": [
            "reconcile_jobs",
            "generation_jobs",
            "credit_ledger",
            "failed",
        ],
        "provider-outage.md": [
            "providers",
            "models",
            "enabled = false",
            "replicate",
            "fal",
        ],
        "webhook-replay.md": [
            "WEBHOOK_SIGNING_SECRET",
            "verify_webhook",
            "finalize_generation",
            "idempotent",
        ],
        "credit-correction.md": [
            "credit_ledger",
            "workspace_credit_balance",
            "reserve",
            "refund",
        ],
        "rotate-secrets.md": [
            "REPLICATE_API_TOKEN",
            "FAL_KEY",
            "WEBHOOK_SIGNING_SECRET",
            "DATABASE_URL",
        ],
        "restore-from-backup.md": [
            "Point-in-Time Recovery",
            "pg_dump",
            "media",
            "reconcile_jobs",
        ],
        "observability.md": [
            "Sentry",
            "/v1/admin/stats",
        ],
        "deployment.md": [
            "render.yaml",
            "Supabase",
        ],
        "cloudflare.md": [
            "WAF",
            "rate",
        ],
    }

    for runbook_name, markers in expected_runbooks.items():
        path = RUNBOOKS_DIR / runbook_name
        assert path.is_file(), f"Missing runbook: {runbook_name}"
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content, f"{runbook_name} missing expected marker: {marker}"


def test_readme_contains_developer_onboarding_and_service_commands() -> None:
    assert README_PATH.is_file()
    readme = README_PATH.read_text(encoding="utf-8")

    # Prerequisites & tools
    assert "uv" in readme
    assert "pnpm" in readme
    assert "Python 3.12+" in readme

    # Fast onboarding & local dev
    assert "make setup" in readme
    assert "dev-up" in readme
    assert "seed_dev_user.py" in readme
    assert "make dev-api" in readme
    assert "make dev-worker" in readme
    assert "make dev-web" in readme

    # Interactive API docs & schema references
    assert "http://localhost:8000/docs" in readme
    assert "http://localhost:8000/redoc" in readme
    assert "docs/openapi.json" in readme

    # Runbooks & ADR index
    assert "docs/adr/001-postgres-job-source-of-truth.md" in readme
    assert "docs/runbooks/stuck-jobs.md" in readme
    assert "docs/runbooks/provider-outage.md" in readme


def test_openapi_schema_is_valid_json_and_contains_core_paths() -> None:
    assert OPENAPI_PATH.is_file()
    schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert "openapi" in schema
    assert "paths" in schema

    paths = schema["paths"]
    # Check key endpoints are in the schema
    assert "/v1/projects/{project_id}/generations" in paths
    assert "/v1/generations/{job_id}" in paths
    assert "/v1/generations/{job_id}/cancel" in paths
    assert "/v1/generations/{job_id}/retry" in paths
    assert "/v1/models" in paths
    assert "/v1/admin/stats" in paths
    assert "/readyz" in paths
