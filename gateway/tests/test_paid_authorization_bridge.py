import base64
from dataclasses import replace
from decimal import Decimal
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpu_control.execution import ApprovedExecutionPlan
from gpu_gateway.contracts import CandidateBinding, CostEvidence, PlanV2, plan_fingerprint
from gpu_gateway.config import Settings
from gpu_gateway.paid_authorization_bridge import (
    PaidAuthorizationBridgeError,
    verify_paid_authorization,
)


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


@pytest.fixture
def bridge_case():
    now = 1_800_000_000
    run_id = "a" * 32
    key_id = "paid:org-authority:key-v1"
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    plan = PlanV2(
        schema_version=2, repository="Unjuno/orbitune", source_sha="b" * 40,
        workload="gpu-train", workload_manifest_digest="c" * 64,
        image_digest="sha256:" + "d" * 64, parameters={}, provider="runpod",
        device_requirement={"gpu_profile": "a10g", "gpu_count": 1},
        runtime_seconds=3600, max_cost_usd=Decimal("0.50"),
        cost_evidence=CostEvidence(
            classification="PAID", additional_cost_usd=Decimal("0.50"),
            reference="runpod-price-snapshot:abc", observed_at=now - 10,
            expires_at=now + 60),
        authorization_policy_version="browser-approval-required-v1",
        selection_binding=CandidateBinding(
            workload_fingerprint="sha256:" + "e" * 64, provider="runpod",
            resource_id="NVIDIA A10G", evidence_fingerprint="sha256:" + "f" * 64),
    )
    core_plan = ApprovedExecutionPlan(
        provider="runpod", provider_resource_id="NVIDIA A10G",
        target_repo=plan.repository, target_sha=plan.source_sha,
        dockerfile_path="workloads/gpu/Dockerfile", image_digest=plan.image_digest,
        container_verification_reference="container-attestation:abc",
        gpu_profile="a10g", gpu_count=1, max_runtime_minutes=60,
        max_cost_usd=Decimal("0.50"), verified_hourly_price_usd=Decimal("0.50"),
        pricing_verification_reference="pricing-snapshot:abc",
        pricing_verified_at_utc="2027-01-15T07:59:00Z",
        pricing_valid_until_utc="2027-01-15T08:01:00Z",
        worst_case_cost_usd=Decimal("0.50"),
        authorization_reference="decision:abc",
    )
    core_plan.validate_shape()
    body = {
        "schema_version": 1, "issuer": "org-authority", "key_id": key_id,
        "audience": "gpu-control:runpod-paid-execution",
        "authorization_id": "authz-abc", "revocation_id": "revoke-abc",
        "run_id": run_id, "owner": "owner-subject", "actor": "taka",
        "decision_record_id": "decision-record-abc", "control_plane_sha": "1" * 40,
        "gateway_plan_fingerprint": plan_fingerprint(plan),
        "core_plan_fingerprint": core_plan.fingerprint().removeprefix("sha256:"),
        "provider": "runpod", "resource_id": "NVIDIA A10G",
        "image_digest": plan.image_digest, "runtime_seconds": 3600,
        "max_cost_usd": "0.50", "authorization_reference": "decision:abc",
        "policy_version": "paid-authority-v1", "issued_at": now - 30,
        "expires_at": now + 300,
    }
    envelope = body | {"signature": base64.urlsafe_b64encode(
        private.sign(_canonical(body))).rstrip(b"=").decode("ascii")}
    args = dict(
        trusted_keys={key_id: public}, expected_issuer="org-authority",
        now=now,
        expected_policy_version="paid-authority-v1",
        owner="owner-subject", actor="taka", decision_record_id="decision-record-abc",
        control_plane_sha="1" * 40, run_id=run_id, gateway_plan=plan,
        core_plan=core_plan, is_revoked=lambda _issuer, _id: False,
    )
    def resign(value):
        body = {key: item for key, item in value.items() if key != "signature"}
        return body | {"signature": base64.urlsafe_b64encode(
            private.sign(_canonical(body))).rstrip(b"=").decode("ascii")}

    return envelope, args, resign


def test_verifies_independent_authorization_and_exact_plan_binding(bridge_case):
    envelope, args, _ = bridge_case
    result = verify_paid_authorization(envelope, **args)
    assert result.authorization_id == "authz-abc"
    assert result.revocation_id == "revoke-abc"
    assert result.gateway_plan_fingerprint == plan_fingerprint(args["gateway_plan"])
    assert result.valid_until == envelope["expires_at"]


def test_rejects_core_worst_case_cost_above_gateway_quote(bridge_case):
    envelope, args, resign = bridge_case
    old_evidence = args["gateway_plan"].cost_evidence
    evidence = old_evidence.model_copy(update={
        "additional_cost_usd": Decimal("0.49"),
    })
    plan = args["gateway_plan"].model_copy(update={"cost_evidence": evidence})
    body = {key: value for key, value in envelope.items() if key != "signature"}
    body["gateway_plan_fingerprint"] = plan_fingerprint(plan)
    with pytest.raises(PaidAuthorizationBridgeError, match="exceeds the current Gateway cost evidence"):
        verify_paid_authorization(
            resign(body), **(args | {"gateway_plan": plan}))


@pytest.mark.parametrize("field,value", [
    ("run_id", "0" * 32), ("owner", "other-owner"), ("actor", "other-actor"),
    ("decision_record_id", "other-decision"), ("control_plane_sha", "2" * 40),
    ("resource_id", "other-gpu"), ("image_digest", "sha256:" + "0" * 64),
    ("runtime_seconds", 1800), ("max_cost_usd", "0.25"),
])
def test_signed_but_mismatched_claims_are_rejected(bridge_case, field, value):
    envelope, args, resign = bridge_case
    changed = dict(envelope)
    changed[field] = value
    with pytest.raises(PaidAuthorizationBridgeError):
        verify_paid_authorization(resign(changed), **args)


def test_tampered_signature_is_rejected(bridge_case):
    envelope, args, _ = bridge_case
    changed = dict(envelope, actor="attacker")
    with pytest.raises(PaidAuthorizationBridgeError, match="signature"):
        verify_paid_authorization(changed, **args)


@pytest.mark.parametrize("now", [1_800_000_000 + 300, 1_800_000_000 - 31])
def test_expired_or_future_issued_authorization_is_rejected(bridge_case, now):
    envelope, args, resign = bridge_case
    old_cost = args["gateway_plan"].cost_evidence
    cost_evidence = old_cost.model_copy(update={
        "observed_at": min(old_cost.observed_at, now - 1),
        "expires_at": max(old_cost.expires_at, now + 1),
    })
    plan = args["gateway_plan"].model_copy(update={"cost_evidence": cost_evidence})
    body = {key: value for key, value in envelope.items() if key != "signature"}
    body["gateway_plan_fingerprint"] = plan_fingerprint(plan)
    changed = resign(body)
    with pytest.raises(PaidAuthorizationBridgeError, match="expired"):
        verify_paid_authorization(changed, **(args | {"now": now, "gateway_plan": plan}))


def test_revoked_authorization_is_rejected(bridge_case):
    envelope, args, _ = bridge_case
    with pytest.raises(PaidAuthorizationBridgeError, match="revoked"):
        verify_paid_authorization(envelope, **(args | {"is_revoked": lambda _issuer, _id: True}))


def test_unavailable_revocation_lookup_fails_closed(bridge_case):
    envelope, args, _ = bridge_case

    def unavailable(_issuer, _id):
        raise OSError("offline")

    with pytest.raises(PaidAuthorizationBridgeError, match="unavailable"):
        verify_paid_authorization(envelope, **(args | {"is_revoked": unavailable}))


def test_unknown_envelope_fields_are_rejected(bridge_case):
    envelope, args, _ = bridge_case
    with pytest.raises(PaidAuthorizationBridgeError, match="fields"):
        verify_paid_authorization(envelope | {"extra": "ignored"}, **args)


@pytest.mark.parametrize("field,value", [
    ("policy_version", ["nested"]), ("authorization_id", "x" * 257),
    ("issued_at", 1 << 80),
])
def test_non_scalar_or_oversized_claims_are_rejected(bridge_case, field, value):
    envelope, args, _ = bridge_case
    with pytest.raises(PaidAuthorizationBridgeError):
        verify_paid_authorization(dict(envelope, **{field: value}), **args)


def test_untrusted_or_wrongly_scoped_key_is_rejected(bridge_case):
    envelope, args, _ = bridge_case
    with pytest.raises(PaidAuthorizationBridgeError, match="not trusted"):
        verify_paid_authorization(envelope, **(args | {"trusted_keys": {}}))


def test_core_plan_fingerprint_mismatch_is_rejected(bridge_case):
    envelope, args, _ = bridge_case
    wrong_core = replace(args["core_plan"], provider_resource_id="another-gpu")
    with pytest.raises(PaidAuthorizationBridgeError):
        verify_paid_authorization(envelope, **(args | {"core_plan": wrong_core}))


def test_zero_additional_cost_plan_cannot_consume_paid_authorization(bridge_case):
    envelope, args, resign = bridge_case
    plan = args["gateway_plan"].model_copy(update={
        "cost_evidence": CostEvidence(
            classification="FREE_QUOTA", additional_cost_usd=Decimal("0"),
            reference="free-quota", observed_at=1_800_000_000 - 10,
            expires_at=1_800_000_000 + 60),
    })
    body = {key: value for key, value in envelope.items() if key != "signature"}
    body["gateway_plan_fingerprint"] = plan_fingerprint(plan)
    changed = resign(body)
    with pytest.raises(PaidAuthorizationBridgeError, match="zero-additional-cost"):
        verify_paid_authorization(changed, **(args | {"gateway_plan": plan}))


def test_wrong_audience_with_valid_signature_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    changed = resign(dict(envelope, audience="other-service"))
    with pytest.raises(PaidAuthorizationBridgeError, match="audience"):
        verify_paid_authorization(changed, **args)


def test_overlong_ttl_with_valid_signature_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    changed = resign(dict(envelope, expires_at=envelope["issued_at"] + 901))
    with pytest.raises(PaidAuthorizationBridgeError, match="validity window"):
        verify_paid_authorization(changed, **args)


def test_negative_issue_time_with_valid_signature_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    changed = resign(dict(envelope, issued_at=-1))
    with pytest.raises(PaidAuthorizationBridgeError, match="validity window"):
        verify_paid_authorization(changed, **args)


def test_non_boolean_revocation_result_is_rejected(bridge_case):
    envelope, args, _ = bridge_case
    with pytest.raises(PaidAuthorizationBridgeError, match="status is invalid"):
        verify_paid_authorization(envelope, **(args | {"is_revoked": lambda _issuer, _id: 0}))


def test_noncanonical_cost_ceiling_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    changed = resign(dict(envelope, max_cost_usd="0.5"))
    with pytest.raises(PaidAuthorizationBridgeError, match="core plan mapping"):
        verify_paid_authorization(changed, **args)


def test_gateway_cost_evidence_above_ceiling_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    plan = args["gateway_plan"].model_copy(update={
        "cost_evidence": CostEvidence(
            classification="PAID", additional_cost_usd=Decimal("0.75"),
            reference="over-ceiling", observed_at=1_800_000_000 - 10,
            expires_at=1_800_000_000 + 60),
    })
    changed = resign(dict(
        envelope, gateway_plan_fingerprint=plan_fingerprint(plan)))
    with pytest.raises(PaidAuthorizationBridgeError, match="cost evidence"):
        verify_paid_authorization(changed, **(args | {"gateway_plan": plan}))


@pytest.mark.parametrize("cost_evidence", [
    CostEvidence(classification="UNKNOWN", additional_cost_usd=None,
                 reference="unknown", observed_at=1_800_000_000 - 10,
                 expires_at=1_800_000_000 + 60),
    CostEvidence(classification="PAID", additional_cost_usd=None,
                 reference="missing-total", observed_at=1_800_000_000 - 10,
                 expires_at=1_800_000_000 + 60),
    CostEvidence(classification="PAID", additional_cost_usd=Decimal("0"),
                 reference="zero-paid", observed_at=1_800_000_000 - 10,
                 expires_at=1_800_000_000 + 60),
    CostEvidence(classification="PAID", additional_cost_usd=Decimal("0.50"),
                 reference="expired", observed_at=1_800_000_000 - 100,
                 expires_at=1_800_000_000 - 1),
    CostEvidence(classification="PAID", additional_cost_usd=Decimal("0.50"),
                 reference="no-times", observed_at=None, expires_at=None),
])
def test_unknown_zero_or_stale_gateway_cost_evidence_is_rejected(bridge_case, cost_evidence):
    envelope, args, _ = bridge_case
    plan = args["gateway_plan"].model_copy(update={"cost_evidence": cost_evidence})
    with pytest.raises(PaidAuthorizationBridgeError, match="cost evidence"):
        verify_paid_authorization(envelope, **(args | {"gateway_plan": plan}))


def test_stale_policy_version_with_valid_signature_is_rejected(bridge_case):
    envelope, args, resign = bridge_case
    changed = resign(dict(envelope, policy_version="retired-policy"))
    with pytest.raises(PaidAuthorizationBridgeError, match="policy version"):
        verify_paid_authorization(changed, **args)


def test_paid_authorization_trust_keys_are_namespace_scoped_in_settings(bridge_case):
    envelope, args, _ = bridge_case
    key_pem = args["trusted_keys"][envelope["key_id"]].decode("ascii")
    settings = Settings(
        paid_authorization_issuer="org-authority",
        paid_authorization_policy_version="paid-authority-v1",
        paid_authorization_public_keys_json=json.dumps({envelope["key_id"]: key_pem}),
    )
    settings.validate()
    assert settings.paid_authorization_trusted_keys == args["trusted_keys"]


def test_paid_authorization_trust_settings_reject_mismatched_issuer(bridge_case):
    envelope, args, _ = bridge_case
    key_pem = args["trusted_keys"][envelope["key_id"]].decode("ascii")
    settings = Settings(
        paid_authorization_issuer="another-authority",
        paid_authorization_policy_version="paid-authority-v1",
        paid_authorization_public_keys_json=json.dumps({envelope["key_id"]: key_pem}),
    )
    with pytest.raises(ValueError, match="matching trusted keys"):
        settings.validate()


def test_paid_authorization_trust_settings_load_from_environment(bridge_case, monkeypatch):
    envelope, args, _ = bridge_case
    key_pem = args["trusted_keys"][envelope["key_id"]].decode("ascii")
    monkeypatch.setenv("GATEWAY_PAID_AUTHORIZATION_ISSUER", "org-authority")
    monkeypatch.setenv("GATEWAY_PAID_AUTHORIZATION_POLICY_VERSION", "paid-authority-v1")
    monkeypatch.setenv(
        "GATEWAY_PAID_AUTHORIZATION_PUBLIC_KEYS_JSON",
        json.dumps({envelope["key_id"]: key_pem}),
    )
    settings = Settings.from_env()
    assert settings.paid_authorization_issuer == "org-authority"
    assert settings.paid_authorization_policy_version == "paid-authority-v1"
    assert envelope["key_id"] in settings.paid_authorization_trusted_keys
