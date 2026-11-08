"""Guards for the production runtime dependency set.

The API image installs only ``apps/api/requirements.txt``. Supabase issues ES256
tokens, and PyJWT can only verify those when its ``crypto`` extra (which pulls in
``cryptography``) is installed. Losing either half of that breaks every
authenticated request with ``401 INVALID_TOKEN``.
"""

from __future__ import annotations

from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[1]


def test_pyjwt_crypto_extra_is_declared() -> None:
    """PyJWT must request its crypto extra so ES256 verification is possible."""
    pyproject = (_API_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert "pyjwt[crypto]" in pyproject


def test_runtime_requirements_include_cryptography() -> None:
    """The Docker image installs this file, so it must ship the crypto backend."""
    requirements = (_API_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert "\ncryptography==" in requirements
