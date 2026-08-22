from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> None:
    values = list(range(10_000))
    total = sum(value * value for value in values)
    digest = hashlib.sha256(str(total).encode("utf-8")).hexdigest()

    result = {
        "schema_version": 1,
        "status": "ok",
        "workload_id": "gpu-control-reference",
        "calculation": {
            "sum_of_squares_0_to_9999": total,
            "sha256": digest,
        },
    }

    output_dir = Path("/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
