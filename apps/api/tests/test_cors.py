"""Tests for CORS origin configuration, including REGEX_WEB_ORIGINS."""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.main import _parse_origin_regex, create_app
from studio_core.settings import Settings


def _cors_kwargs(app: FastAPI) -> dict[str, object]:
    middleware = [
        m
        for m in app.user_middleware
        if isinstance(m.cls, type) and issubclass(m.cls, CORSMiddleware)
    ]
    assert middleware, "CORSMiddleware is not registered"
    return middleware[-1].kwargs


def test_parse_origin_regex_combines_patterns() -> None:
    parsed = _parse_origin_regex(
        r"^https://studio-[a-z0-9-]+\.vercel\.app$, ^https://example\.com$"
    )
    assert parsed == (r"(?:^https://studio-[a-z0-9-]+\.vercel\.app$)|(?:^https://example\.com$)")


def test_parse_origin_regex_keeps_commas_inside_quantifiers() -> None:
    parsed = _parse_origin_regex(r"^https://api-[a-z]{1,3}\.example\.com$")
    assert parsed == r"^https://api-[a-z]{1,3}\.example\.com$"


def test_parse_origin_regex_empty_returns_none() -> None:
    assert _parse_origin_regex("") is None
    assert _parse_origin_regex("  ,  ") is None


def test_create_app_passes_regex_origins_to_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(regex_web_origins=r"^https://.*\.vercel\.app$")
    monkeypatch.setattr("api.main.get_settings", lambda: settings)

    app = create_app()

    kwargs = _cors_kwargs(app)
    assert kwargs["allow_origin_regex"] == r"^https://.*\.vercel\.app$"
    assert kwargs["allow_origins"] == ["http://localhost:3000"]
