"""T3.7 — OpenAPI export and generated client tests.

Tests: schema can be exported deterministically, and the API module imports work.
"""

from __future__ import annotations

import json


def test_openapi_schema_is_exportable() -> None:
    """The FastAPI app can produce an OpenAPI schema without errors."""
    from api.main import create_app

    app = create_app()
    schema = app.openapi()
    assert schema["info"]["title"] == "AI Content Studio API"
    assert "paths" in schema
    # Key endpoints must be present
    paths = schema["paths"]
    assert "/v1/workspaces" in paths
    assert any("/v1/workspaces/{workspace_id}/projects" in p for p in paths)
    assert any("/v1/generations/{job_id}" in p for p in paths)
    assert "/internal/webhooks/{provider}/{job_id}" in paths


def test_openapi_schema_is_deterministic() -> None:
    """Two calls to openapi() produce the same JSON (keys identical)."""
    from api.main import create_app

    app1 = create_app()
    app2 = create_app()
    s1 = json.dumps(app1.openapi(), sort_keys=True)
    s2 = json.dumps(app2.openapi(), sort_keys=True)
    assert s1 == s2


def test_api_package_importable() -> None:
    """The api package itself can be imported without error."""
    import api

    assert api.__version__ == "0.1.0"


def test_main_module_importable() -> None:
    """api.main can be imported and create_app is callable."""
    from api.main import create_app

    app = create_app()
    assert app is not None
