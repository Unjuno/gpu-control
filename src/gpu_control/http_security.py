"""Credential-safe HTTP defaults shared by source and provider readers.

Callers still own the fixed endpoint, operation, and authorization policy. Injected
openers are trusted test/integration dependencies, not an untrusted public option.
"""
from __future__ import annotations

import json
import math
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_JSON_RESPONSE_BYTES = 1_048_576
MAX_JSON_DEPTH = 64


class ResponseBoundaryError(ValueError):
    """An HTTP response exceeded the bounded structured-data contract."""


class NoRedirects(HTTPRedirectHandler):
    """Never forward credential-bearing requests, even to a same-origin redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise HTTPError(req.full_url, code, "HTTP redirects are forbidden", headers, None)


def validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResponseBoundaryError("HTTP timeout must be finite and positive")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ResponseBoundaryError("HTTP timeout must be finite and positive") from exc
    if not math.isfinite(result) or result <= 0:
        raise ResponseBoundaryError("HTTP timeout must be finite and positive")
    return result


def urlopen_no_redirects(request: Request, *, timeout: float) -> Any:
    parsed = urlsplit(request.full_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ResponseBoundaryError("HTTP requests require an HTTPS origin without URL credentials")
    # Do not install a process-global opener. In particular, never mutate urllib's
    # behavior for unrelated code or allow an external redirect to inherit auth.
    return build_opener(NoRedirects()).open(request, timeout=validate_timeout(timeout))


def read_bounded_body(response: Any, *, max_bytes: int = MAX_JSON_RESPONSE_BYTES) -> bytes:
    if type(max_bytes) is not int or max_bytes < 1:
        raise ResponseBoundaryError("HTTP byte limit must be a positive integer")
    headers = getattr(response, "headers", None)
    length = headers.get("Content-Length") if headers is not None else None
    if length is not None:
        try:
            count = int(length)
        except (ValueError, TypeError) as exc:
            raise ResponseBoundaryError("HTTP Content-Length is invalid") from exc
        if count < 0 or count > max_bytes:
            raise ResponseBoundaryError("HTTP response exceeds the byte limit")
    raw = response.read(max_bytes + 1)
    if not isinstance(raw, bytes):
        raise ResponseBoundaryError("HTTP response body must be bytes")
    if len(raw) > max_bytes:
        raise ResponseBoundaryError("HTTP response exceeds the byte limit")
    return raw


def decode_json_body(raw: bytes) -> Any:
    if not isinstance(raw, bytes) or len(raw) > MAX_JSON_RESPONSE_BYTES:
        raise ResponseBoundaryError("JSON response exceeds the byte limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ResponseBoundaryError("JSON response contains duplicate object keys")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ResponseBoundaryError("JSON response contains a non-finite number")

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        # Never echo untrusted response text, which may include credentials.
        raise ResponseBoundaryError("HTTP response contains invalid or excessive JSON") from exc
    pending = [(payload, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise ResponseBoundaryError("JSON response exceeds the nesting limit")
        if isinstance(value, dict):
            pending.extend((item, depth + 1) for item in value.values())
            pending.extend((key, depth + 1) for key in value)
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ResponseBoundaryError("JSON response contains a non-finite number")
        elif isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ResponseBoundaryError("JSON response contains invalid Unicode") from exc
    return payload
