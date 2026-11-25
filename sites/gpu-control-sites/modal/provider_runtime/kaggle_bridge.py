"""Narrow Sites/Modal bridge over the official Kaggle Python client.

The Kaggle CLI does not offer JSON output for ``kernels status`` and its list
formatter omits the current version.  This module exposes only the two
read-only queries the trusted worker needs; it is not a generic provider API.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from enum import Enum
import json
import re
import sys
from typing import Any


_KERNEL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}/[a-z0-9][a-z0-9-]{0,49}$"
)
_VERSIONED_KERNEL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}/[a-z0-9][a-z0-9-]{0,49}/[1-9][0-9]*$"
)


def _status_payload(response: Any, *, version: int) -> dict[str, object]:
    status = getattr(response, "status", None)
    if isinstance(status, Enum):
        status = status.name.lower()
    elif isinstance(status, str):
        status = status.lower()
    if not isinstance(status, str) or not status:
        raise RuntimeError("Kaggle status response is invalid")
    message = getattr(response, "failure_message", None)
    return {
        "versionNumber": version,
        "status": status,
        "failureMessage": message if isinstance(message, str) and message else None,
    }


def latest_snapshot(api: Any, kernel: str) -> dict[str, object]:
    if _KERNEL_RE.fullmatch(kernel) is None:
        raise ValueError("Kaggle kernel identity is invalid")
    owner, slug = kernel.split("/", 1)
    kernels = api.kernels_list(mine=True, user=owner, search=slug, page_size=100) or []
    exact = [item for item in kernels if getattr(item, "ref", None) == kernel]
    if not exact:
        return {"versionNumber": 0, "status": "missing", "failureMessage": None}
    if len(exact) != 1:
        raise RuntimeError("Kaggle kernel identity is ambiguous")
    version = getattr(exact[0], "current_version_number", None)
    if type(version) is not int or version < 1:
        raise RuntimeError("Kaggle current version is invalid")
    return _status_payload(api.kernels_status(f"{kernel}/{version}"), version=version)


def exact_status(api: Any, kernel: str) -> dict[str, object]:
    if _VERSIONED_KERNEL_RE.fullmatch(kernel) is None:
        raise ValueError("versioned Kaggle kernel identity is invalid")
    version = int(kernel.rsplit("/", 1)[1])
    return _status_payload(api.kernels_status(kernel), version=version)


def main() -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("operation", choices=("latest", "status"))
    parser.add_argument("kernel")
    args = parser.parse_args()

    # Keep all third-party output away from stdout so the worker receives one
    # deterministic JSON object. Authentication still comes only from the
    # subprocess's restricted KAGGLE_API_TOKEN environment.
    with redirect_stdout(sys.stderr):
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()
        payload = (latest_snapshot(api, args.kernel) if args.operation == "latest"
                   else exact_status(api, args.kernel))
    print(json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
