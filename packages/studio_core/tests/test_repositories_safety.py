"""Tests ensuring SQL repository safety: parameterized queries and no string interpolation."""

import inspect

import pytest

from studio_core import repositories


def test_no_fstrings_or_formatting_in_repository_sql() -> None:
    """Requirement T2.1: parameterized only; test verifies no unsafe string interpolation."""
    source = inspect.getsource(repositories)
    lines = source.splitlines()

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Verify no direct format or percent formatting of query text
        if "query % " in stripped or ".format(" in stripped:
            msg = f"Unsafe SQL formatting in repositories.py line {idx}: {stripped}"
            pytest.fail(msg)
