from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / "shared-contracts" / "openapi" / "v1"
    target.mkdir(parents=True, exist_ok=True)
    output_file = target / "openapi.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, indent=2)
        f.write("\n")

    print(f"Wrote OpenAPI spec to {output_file}")


if __name__ == "__main__":
    main()
