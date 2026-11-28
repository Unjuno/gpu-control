"""Canonical JSON encoding and fingerprints for persisted control-plane data."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return the stable JSON representation used for Python fingerprints."""
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_fingerprint(value: Any) -> str:
    """Return a namespaced SHA-256 fingerprint of canonical JSON data."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
