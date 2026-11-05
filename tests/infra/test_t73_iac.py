"""Static checks for the T7.3 deployment artefacts.

These tests do not replace the real staging deploy (documented in
``docs/runbooks/deployment.md``). They exist so CI catches accidental drift in
the Render Blueprint, the Dockerfiles, the Vercel config, and the smoke script
without needing cloud credentials.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: str) -> dict[str, Any]:
    loaded = yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _render() -> dict[str, Any]:
    return _load_yaml("infra/render.yaml")


def _services(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {service["name"]: service for service in blueprint["services"]}


def _groups(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {group["name"]: group for group in blueprint["envVarGroups"]}


def _env(service: dict[str, Any], key: str) -> dict[str, Any]:
    return next(env_var for env_var in service["envVars"] if env_var.get("key") == key)


def test_render_blueprint_defines_api_worker_and_redis() -> None:
    blueprint = _render()
    services = _services(blueprint)
    assert set(services) == {"studio-api", "studio-worker", "studio-redis"}

    api = services["studio-api"]
    assert api["type"] == "web"
    assert api["runtime"] == "docker"
    assert api["dockerfilePath"] == "./apps/api/Dockerfile"
    assert api["dockerContext"] == "."
    assert api["healthCheckPath"] == "/readyz"
    assert api["autoDeployTrigger"] == "off"
    assert api["numInstances"] == 1

    worker = services["studio-worker"]
    assert worker["type"] == "worker"
    assert worker["runtime"] == "docker"
    assert worker["dockerfilePath"] == "./apps/worker/Dockerfile"
    assert worker["dockerContext"] == "."
    assert worker["autoDeployTrigger"] == "off"
    assert worker["numInstances"] == 1

    redis = services["studio-redis"]
    assert redis["type"] == "keyvalue"
    assert redis["maxmemoryPolicy"] == "noeviction"
    assert redis["ipAllowList"] == []


def test_render_blueprint_wires_env_groups_and_services() -> None:
    blueprint = _render()
    groups = _groups(blueprint)
    assert {"studio-shared", "studio-providers", "studio-api", "studio-worker"} <= set(groups)

    shared_keys = {env_var["key"] for env_var in groups["studio-shared"]["envVars"]}
    assert {
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SENTRY_DSN",
        "ADMIN_USER_IDS",
    } <= shared_keys

    services = _services(blueprint)
    for name, expected_groups in (
        ("studio-api", {"studio-shared", "studio-providers", "studio-api"}),
        ("studio-worker", {"studio-shared", "studio-providers", "studio-worker"}),
    ):
        service = services[name]
        assert {
            env_var["fromGroup"] for env_var in service["envVars"] if "fromGroup" in env_var
        } == expected_groups

        assert _env(service, "REDIS_URL")["fromService"] == {
            "type": "keyvalue",
            "name": "studio-redis",
            "property": "connectionString",
        }
        # Secrets are prompted for in the Render UI and never committed.
        assert _env(service, "DATABASE_URL")["sync"] is False


def test_render_blueprint_keeps_secrets_out_of_git() -> None:
    blueprint = _render()
    for group in blueprint["envVarGroups"]:
        for env_var in group["envVars"]:
            if env_var["key"].endswith(("_KEY", "_SECRET", "_TOKEN", "_DSN")):
                assert env_var.get("sync") is False, env_var["key"]
                assert "value" not in env_var, env_var["key"]


def test_dockerfiles_are_multistage_nonroot_and_healthchecked() -> None:
    expected_commands = {
        "api": 'CMD ["uvicorn", "api.main:app"',
        "worker": 'CMD ["arq", "worker.main.WorkerSettings"]',
    }
    for app, command in expected_commands.items():
        dockerfile = (REPO_ROOT / "apps" / app / "Dockerfile").read_text(encoding="utf-8")
        assert dockerfile.count("FROM ") >= 2, f"{app} Dockerfile must be multi-stage"
        assert "ghcr.io/astral-sh/uv" in dockerfile
        assert "uv pip install" in dockerfile
        assert "ffmpeg" in dockerfile
        assert re.search(r"^USER studio$", dockerfile, re.MULTILINE)
        assert "HEALTHCHECK" in dockerfile
        assert 'ENV PYTHONPATH="/app/src"' in dockerfile
        assert command in dockerfile


def test_dockerignore_keeps_the_build_context_small() -> None:
    patterns = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {".git", "**/node_modules", "apps/web", "docs", "tests"} <= patterns


def test_vercel_config_builds_the_web_workspace() -> None:
    config = json.loads((REPO_ROOT / "apps" / "web" / "vercel.json").read_text(encoding="utf-8"))
    assert config["framework"] == "nextjs"
    # api-client is consumed from its gitignored dist/, so a clean checkout must
    # compile it before Next.js builds.
    assert config["buildCommand"] == (
        "pnpm --filter @studio/api-client build && pnpm --filter @studio/web build"
    )


def test_smoke_script_checks_health_readiness_and_optional_generation() -> None:
    script = (REPO_ROOT / "scripts" / "smoke_staging.sh").read_text(encoding="utf-8")
    assert script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in script
    assert "/healthz" in script
    assert "/readyz" in script
    assert '"db":"ok"' in script
    assert '"redis":"ok"' in script
    assert "WEB_BASE_URL" in script
    assert "SMOKE_USER_TOKEN" in script
    assert "SMOKE_PROJECT_ID" in script
