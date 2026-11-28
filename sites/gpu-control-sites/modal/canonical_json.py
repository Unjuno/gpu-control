"""Canonical UTF-8 JSON bytes shared by the Modal runtime modules."""

from __future__ import annotations

import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON data with the stable byte contract used by Sites Worker."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
