"""Resolve a login throttle key from an explicitly trusted client address."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress

from .service import GatewayError

MAX_FORWARDED_FOR_BYTES = 512
MAX_FORWARDED_HOPS = 8


def _address(value: str):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("invalid IP address")
    parsed = ipaddress.ip_address(value)
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        return parsed.ipv4_mapped
    return parsed


def _trusted(address, networks) -> bool:
    return any(address.version == network.version and address in network for network in networks)


def _canonical_bucket(address, key: str) -> str:
    if isinstance(address, ipaddress.IPv6Address):
        address = ipaddress.ip_network(f"{address}/64", strict=False).network_address
    canonical = str(address)
    message = ("gpu-control-login-source-v1\0" + canonical).encode()
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _single_forwarded_address(value: str):
    """Parse Vercel's client-IP header, allowing only identical proxy duplicates.

    Vercel documents x-vercel-forwarded-for as the client address, even when
    x-forwarded-for may be overwritten by an upstream proxy. If duplicates
    appear, do not select one of differing values based on attacker-controlled
    ordering.
    """
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_FORWARDED_FOR_BYTES:
        raise ValueError("invalid forwarded address")
    values = value.split(",")
    if len(values) > MAX_FORWARDED_HOPS:
        raise ValueError("too many forwarded addresses")
    try:
        addresses = [_address(item.strip()) for item in values]
    except ValueError:
        raise ValueError("invalid forwarded address") from None
    if any(address != addresses[0] for address in addresses[1:]):
        raise ValueError("conflicting forwarded addresses")
    return addresses[0]


def resolve_login_source(request, settings) -> str:
    """Return a pseudonymous source bucket; never trust caller headers by default."""
    peer = request.scope.get("client")
    if not isinstance(peer, (tuple, list)) or not peer or not isinstance(peer[0], str):
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)
    try:
        peer_address = _address(peer[0])
    except ValueError:
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503) from None

    mode = settings.client_ip_mode
    if mode == "direct":
        return _canonical_bucket(peer_address, settings.client_ip_hash_key)
    if mode == "vercel":
        if not settings.vercel_runtime:
            raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)
        value = request.headers.get("x-vercel-forwarded-for", "")
        try:
            address = _single_forwarded_address(value)
        except ValueError:
            raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503) from None
        return _canonical_bucket(address, settings.client_ip_hash_key)
    if mode != "trusted_proxy":
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)

    networks = tuple(ipaddress.ip_network(value, strict=False) for value in settings.trusted_proxy_cidrs)
    if not _trusted(peer_address, networks):
        # Forwarding headers from a direct, untrusted peer are ignored.
        return _canonical_bucket(peer_address, settings.client_ip_hash_key)

    value = request.headers.get("x-forwarded-for", "")
    if not value or len(value.encode("utf-8")) > MAX_FORWARDED_FOR_BYTES:
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)
    parts = value.split(",")
    if len(parts) > MAX_FORWARDED_HOPS:
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)
    try:
        forwarded = [_address(item.strip()) for item in parts]
    except ValueError:
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503) from None

    current = peer_address
    for candidate in reversed(forwarded):
        if not _trusted(current, networks):
            break
        current = candidate
    if _trusted(current, networks):
        raise GatewayError("login_source_unavailable", "Sign-in is temporarily unavailable", 503)
    return _canonical_bucket(current, settings.client_ip_hash_key)
