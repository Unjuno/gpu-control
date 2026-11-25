from __future__ import annotations

from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so credentials and signed URLs remain at their origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def open_no_redirect(request: Request, *, timeout: float):
    return build_opener(NoRedirectHandler()).open(request, timeout=timeout)


def read_bounded(response: Any, *, max_bytes: int) -> bytes:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("response byte limit must be a positive integer")
    headers = getattr(response, "headers", None)
    if headers is not None:
        encoding = headers.get("Content-Encoding", "identity").lower()
        if encoding not in ("", "identity"):
            raise ValueError("compressed HTTP responses are not accepted")
        content_length = headers.get("Content-Length")
        if content_length is not None:
            try:
                length = int(content_length)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid HTTP Content-Length") from exc
            if length < 0 or length > max_bytes:
                raise ValueError("HTTP response exceeds the byte limit")
    raw = response.read(max_bytes + 1)
    if not isinstance(raw, bytes):
        raise ValueError("HTTP response body must be bytes")
    if len(raw) > max_bytes:
        raise ValueError("HTTP response exceeds the byte limit")
    return raw
