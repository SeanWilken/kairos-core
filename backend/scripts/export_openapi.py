from __future__ import annotations

import json
from pathlib import Path
import sys

def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.main import app  # local import avoids E402

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
