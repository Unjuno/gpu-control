import pytest

from gpu_gateway.provider_account_scope import derive_provider_account_scope


def test_scope_is_stable_across_credential_rotation_and_separates_accounts():
    key = b"k" * 32
    first = derive_provider_account_scope("runpod", "runpod-primary", key)

    # Provider API credentials are not part of this identity; rotations use
    # the same operator-managed scope ID and therefore the same lease row.
    old_credential = "provider-secret-A"
    new_credential = "provider-secret-B"
    assert old_credential != new_credential
    assert first == derive_provider_account_scope("runpod", "runpod-primary", key)
    assert first != derive_provider_account_scope("runpod", "runpod-secondary", key)
    assert first != derive_provider_account_scope("other", "runpod-primary", key)
    assert len(first) == 64
    assert "runpod-primary" not in first


@pytest.mark.parametrize("provider,account_id,key", [
    ("RunPod", "runpod-primary", b"k" * 32),
    ("runpod", "", b"k" * 32),
    ("runpod", "runpod primary", b"k" * 32),
    ("runpod", "a" * 257, b"k" * 32),
    ("runpod", "runpod-primary", b"short"),
])
def test_scope_rejects_invalid_inputs(provider, account_id, key):
    with pytest.raises(ValueError):
        derive_provider_account_scope(provider, account_id, key)


def test_provider_scope_hmac_key_loads_from_base64_environment(monkeypatch):
    import base64
    from gpu_gateway.config import Settings

    raw = b"stable-provider-scope-key-material-32bytes"
    monkeypatch.setenv("GATEWAY_PROVIDER_ACCOUNT_SCOPE_HMAC_KEY_B64", base64.b64encode(raw).decode("ascii"))
    monkeypatch.setenv("GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID", "runpod-primary")
    settings = Settings.from_env()

    assert settings.provider_account_scope_hmac_key == raw
    assert settings.runpod_account_scope_id == "runpod-primary"
    assert raw.decode("ascii") not in repr(settings)
    assert "runpod-primary" not in repr(settings)


@pytest.mark.parametrize("encoded", ["not base64!", "c2hvcnQ="])
def test_provider_scope_hmac_key_rejects_invalid_or_short_environment_value(monkeypatch, encoded):
    from gpu_gateway.config import Settings

    monkeypatch.setenv("GATEWAY_PROVIDER_ACCOUNT_SCOPE_HMAC_KEY_B64", encoded)
    with pytest.raises(ValueError, match="provider account scope HMAC key"):
        Settings.from_env()
