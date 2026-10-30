from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpu_gateway.provider_evidence import (
    ProviderEvidenceError,
    build_signed_observation,
    verify_signed_observation,
)
from gpu_gateway.config import Settings
from gpu_gateway.store import Store
from gpu_gateway.worker import Worker


def _keys():
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, {"worker-2026-01": public_pem}


def _observation(private_pem, *, version=1, payload=None):
    return build_signed_observation(
        provider="runpod",
        source="runpod-graphql",
        source_revision="51ca7f02ab5cb57c09ad917172af36c29a58790c",
        version=version,
        observed_at=10_000,
        expires_at=10_120,
        payload=payload or {"candidates": []},
        key_id="worker-2026-01",
        private_key_pem=private_pem,
    )


def test_signed_observation_verifies_fresh_envelope_and_version_high_water():
    private_pem, public_keys = _keys()
    envelope = _observation(private_pem)

    assert verify_signed_observation(envelope, public_keys, now=10_050) == envelope
    with pytest.raises(ProviderEvidenceError, match="stale or replayed"):
        verify_signed_observation(envelope, public_keys, now=10_050, minimum_version=1)


@pytest.mark.parametrize("mutation,now", [
    (lambda value: value["payload"].update(candidates=[{"price": "0.01"}]), 10_050),
    (lambda value: value.update(signature="A" * 86), 10_050),
    (lambda value: None, 10_120),
])
def test_signed_observation_rejects_tampered_or_expired_evidence(mutation, now):
    private_pem, public_keys = _keys()
    envelope = _observation(private_pem)
    mutation(envelope)

    with pytest.raises(ProviderEvidenceError):
        verify_signed_observation(envelope, public_keys, now=now)


def test_signed_observation_rejects_unknown_key_and_overlong_ttl():
    private_pem, public_keys = _keys()
    envelope = _observation(private_pem)
    with pytest.raises(ProviderEvidenceError, match="not trusted"):
        verify_signed_observation(envelope, {}, now=10_050)
    with pytest.raises(ProviderEvidenceError, match="validity window"):
        build_signed_observation(
            provider="runpod", source="runpod-graphql", source_revision="rev",
            version=1, observed_at=10_000, expires_at=10_301,
            payload={}, key_id="worker-2026-01", private_key_pem=private_pem,
        )


def test_store_replaces_only_with_higher_signed_observation_version(tmp_path):
    private_pem, public_keys = _keys()
    store = Store(f"sqlite:///{tmp_path / 'provider-observations.db'}")
    store.initialize()

    first = _observation(private_pem, version=1)
    second = _observation(private_pem, version=2, payload={"candidates": [{"gpu": "A100"}]})
    forged = _observation(private_pem, version=3)
    forged["payload"]["candidates"] = [{"gpu": "forged"}]
    assert store.write_provider_observation(first, public_keys, now=10_050) is True
    assert store.write_provider_observation(first, public_keys, now=10_050) is False
    assert store.write_provider_observation(second, public_keys, now=10_050) is True
    with pytest.raises(ProviderEvidenceError, match="digest mismatch"):
        store.write_provider_observation(forged, public_keys, now=10_050)

    saved = store.read_provider_observation("runpod")
    assert saved["version"] == 2
    assert saved["envelope"] == second
    assert saved["envelope_sha256"] == hashlib.sha256(
        json_canonical(second)
    ).hexdigest()
    assert verify_signed_observation(saved["envelope"], public_keys, now=10_050)["version"] == 2
    assert store.read_verified_provider_observation(
        "runpod", public_keys, now=10_050
    ) == second
    with pytest.raises(ProviderEvidenceError, match="not current"):
        store.read_verified_provider_observation("runpod", public_keys, now=10_120)


def test_worker_role_signs_and_persists_but_supervisor_cannot_publish(tmp_path):
    private_pem, public_keys = _keys()
    settings = Settings(
        provider_evidence_public_keys_json=json.dumps({
            key_id: pem.decode("ascii") for key_id, pem in public_keys.items()
        }),
        provider_evidence_signing_key_id="worker-2026-01",
        provider_evidence_signing_key_pem=private_pem,
    )
    settings.validate()
    store = Store(f"sqlite:///{tmp_path / 'worker-observation.db'}")
    store.initialize()
    worker = Worker(store, settings, {}, clock=lambda: 10_000, registry={})

    assert worker.persist_provider_observation(
        provider="runpod", source="runpod-graphql",
        source_revision="51ca7f02ab5cb57c09ad917172af36c29a58790c",
        version=1, expires_at=10_120, payload={"candidates": []},
    ) is True
    assert store.read_verified_provider_observation(
        "runpod", settings.provider_evidence_trusted_keys, now=10_050
    )["version"] == 1

    supervisor = Worker(store, settings, {}, clock=lambda: 10_000,
                        registry={}, role="supervisor")
    with pytest.raises(RuntimeError, match="only be published by the worker"):
        supervisor.persist_provider_observation(
            provider="runpod", source="runpod-graphql", source_revision="r",
            version=2, expires_at=10_120, payload={},
        )


def json_canonical(value):
    import json
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")
