from types import SimpleNamespace

import pytest

from gpu_gateway.client_ip import resolve_login_source
from gpu_gateway.config import Settings
from gpu_gateway.service import GatewayError


def request(peer, headers=None):
    return SimpleNamespace(scope={"client": (peer, 12345)}, headers=headers or {})


def test_direct_mode_ignores_forwarded_headers_and_normalizes_addresses():
    settings = Settings()
    public_peer = resolve_login_source(request(
        "198.51.100.9", {"x-forwarded-for": "203.0.113.10"}), settings)
    assert public_peer == resolve_login_source(request("198.51.100.9"), settings)
    assert resolve_login_source(request("::ffff:192.0.2.5"), settings) == \
        resolve_login_source(request("192.0.2.5"), settings)
    assert resolve_login_source(request("2001:db8:1234:5678::1"), settings) == \
        resolve_login_source(request("2001:db8:1234:5678::abcd"), settings)


def test_source_bucket_uses_secret_keyed_hmac():
    address = request("198.51.100.88")
    first = resolve_login_source(address, Settings(client_ip_hash_key="a" * 32))
    assert first == resolve_login_source(address, Settings(client_ip_hash_key="a" * 32))
    assert first != resolve_login_source(address, Settings(client_ip_hash_key="b" * 32))


def test_trusted_proxy_chain_uses_first_untrusted_hop_from_right():
    settings = Settings(client_ip_mode="trusted_proxy",
                        trusted_proxy_cidrs=("127.0.0.1/32", "10.0.0.0/8"))
    result = resolve_login_source(request(
        "127.0.0.1", {"x-forwarded-for": "198.51.100.10, 10.1.1.2"}), settings)
    assert result == resolve_login_source(request("198.51.100.10"), Settings())


def test_untrusted_peer_cannot_choose_bucket_with_forwarded_header():
    settings = Settings(client_ip_mode="trusted_proxy", trusted_proxy_cidrs=("127.0.0.1/32",))
    forwarded = resolve_login_source(request(
        "198.51.100.1", {"x-forwarded-for": "203.0.113.8"}), settings)
    assert forwarded == resolve_login_source(request("198.51.100.1"), Settings())


@pytest.mark.parametrize("value", ["", "not-an-ip", "198.51.100.1,", "198.51.100.1," * 9])
def test_trusted_proxy_rejects_missing_malformed_or_oversized_forwarded_chain(value):
    settings = Settings(client_ip_mode="trusted_proxy", trusted_proxy_cidrs=("127.0.0.1/32",))
    with pytest.raises(GatewayError) as error:
        resolve_login_source(request("127.0.0.1", {"x-forwarded-for": value}), settings)
    assert error.value.code == "login_source_unavailable"


def test_vercel_mode_requires_platform_runtime_and_platform_client_ip_header():
    settings = Settings(client_ip_mode="vercel", vercel_runtime=True)
    assert resolve_login_source(request(
        "10.0.0.2", {"x-vercel-forwarded-for": "198.51.100.21"}), settings) == \
        resolve_login_source(request("198.51.100.21"), Settings())
    with pytest.raises(GatewayError):
        resolve_login_source(request(
            "10.0.0.2", {"x-vercel-forwarded-for": "198.51.100.21, 203.0.113.7"}), settings)
    # Repeated identical values can occur after a proxy chain; conflicting
    # values must fail closed instead of letting header order choose a bucket.
    assert resolve_login_source(request(
        "10.0.0.2", {"x-vercel-forwarded-for": "198.51.100.21, 198.51.100.21"}), settings) == \
        resolve_login_source(request("198.51.100.21"), Settings())
    with pytest.raises(GatewayError):
        resolve_login_source(request(
            "10.0.0.2", {"x-vercel-forwarded-for": "198.51.100.21, 203.0.113.7"}), settings)
    with pytest.raises(GatewayError):
        resolve_login_source(request("10.0.0.2", {"x-vercel-forwarded-for": "198.51.100.21"}),
                             Settings(client_ip_mode="vercel", vercel_runtime=False))


def test_proxy_configuration_rejects_open_trust_networks():
    with pytest.raises(ValueError, match="entire address family"):
        Settings(client_ip_mode="trusted_proxy", trusted_proxy_cidrs=("0.0.0.0/0",)).validate()
