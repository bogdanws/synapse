"""Dump the FastAPI OpenAPI spec to ``openapi.json``.

Used by the frontend codegen pipeline:

    uv run python -m app.scripts.dump_openapi
    cd ../frontend && npm run codegen

Keeps frontend types in lockstep with backend Pydantic models.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.main import app


def main(out: Path | None = None) -> None:
    target = out or (Path(__file__).resolve().parents[2] / "openapi.json")
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
