"""Opaque, stable scope identifiers for provider account concurrency gates."""
from __future__ import annotations

import hashlib
import hmac
import re


def derive_provider_account_scope(provider: str, account_scope_id: str, hmac_key: bytes) -> str:
    """Return a non-reversible scope stable across provider credential rotation.

    ``account_scope_id`` is a non-secret, operator-managed identity that must
    remain the same for every credential belonging to one provider account.
    The HMAC key must also be shared by all Gateway processes and kept stable
    while allocations may still exist. Provider credentials are intentionally
    excluded so rotating one cannot create a second lease namespace.
    """
    if (not isinstance(provider, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", provider) is None or
            not isinstance(account_scope_id, str) or not account_scope_id or len(account_scope_id) > 256 or
            any(character.isspace() for character in account_scope_id) or
            not isinstance(hmac_key, bytes) or len(hmac_key) < 32 or len(hmac_key) > 4096):
        raise ValueError("provider account scope inputs are invalid")
    message = (b"gpu-control/provider-account-scope/v1\0" + provider.encode("ascii") +
               b"\0" + account_scope_id.encode("utf-8"))
    return hmac.new(hmac_key, message, hashlib.sha256).hexdigest()
