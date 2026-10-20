#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to docs/openapi.json.

Usage:
    uv run python scripts/export_openapi.py

The output is deterministic (keys sorted) so that CI can detect schema drift
with ``git diff --exit-code docs/openapi.json``.
"""

import json
import sys
from pathlib import Path

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api" / "src"))

from api.main import create_app  # noqa: E402


def main() -> None:
    app = create_app()
    schema = app.openapi()
    output_path = Path(__file__).parent.parent / "docs" / "openapi.json"
    output_path.write_text(
        json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {output_path}")


if __name__ == "__main__":
    main()
