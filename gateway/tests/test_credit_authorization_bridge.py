import base64
from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpu_control.capabilities import (
    Availability, CapabilityEvidence, CostBreakdown, CostClassification,
    OverageBehavior, QuotaEvidence,
)
from gpu_control.workloads import AcceleratorKind, NetworkRequirement, ResultTransport
from gpu_gateway.contracts import CandidateBinding, CostEvidence, PlanV2, plan_fingerprint
from gpu_gateway.credit_authorization_bridge import (
    CREDIT_AUTHORIZATION_AUDIENCE, CreditAuthorizationError,
    verify_credit_authorization,
)


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


@pytest.fixture
def credit_case():
    now = 1_800_000_000
    observed = datetime.fromtimestamp(now - 10, timezone.utc).isoformat().replace("+00:00", "Z")
    expires = datetime.fromtimestamp(now + 300, timezone.utc).isoformat().replace("+00:00", "Z")
    quota = QuotaEvidence(
        remaining_usage_usd=Decimal("2.00"), remaining_credits_usd=Decimal("1.00"),
        covered_components=("accelerator_usd", "cpu_usd", "memory_usd", "storage_usd", "egress_usd", "other_usd"),
        evidence_reference="account-quota:fixture", observed_at_utc=observed, valid_until_utc=expires,
    )
    evidence = CapabilityEvidence(
        provider="modal", resource_id="modal-gpu-t4", availability=Availability.AVAILABLE,
        cost_classification=CostClassification.CREDIT_BACKED,
        costs=CostBreakdown(accelerator_usd=Decimal("0.10"), cpu_usd=Decimal("0.01"),
                            memory_usd=Decimal("0.01"), storage_usd=Decimal("0"),
                            egress_usd=Decimal("0"), other_usd=Decimal("0")),
        hard_spend_cap_enforced=True, overage_behavior=OverageBehavior.STOPS,
        evidence_reference="modal-snapshot:fixture", evidence_source="modal-owner-read-fixture",
        observed_at_utc=observed, valid_until_utc=expires,
        supported_operating_systems=("linux",), supported_architectures=("x86_64",),
        accelerator_kind=AcceleratorKind.GPU, gpu_profiles=("t4",), max_gpu_count=1,
        max_vram_mib=16384, max_cpu_cores=Decimal("2"), max_memory_mib=8192,
        max_runtime_seconds=600, max_result_bytes=1048576,
        network_modes_supported=(NetworkRequirement.DISABLED,),
        result_transports=(ResultTransport.STDOUT,), cancellation_supported=True,
        cleanup_proof_supported=True, quota_evidence=quota,
        supported_runtime_requirements=("python:3.12",), estimated_queue_wait_seconds=0,
    )
    plan = PlanV2(
        schema_version=2, repository="Unjuno/orbitune", source_sha="b" * 40,
        workload="gpu-smoke", workload_manifest_digest="c" * 64,
        image_digest="sha256:" + "d" * 64, parameters={}, provider="modal",
        device_requirement={"accelerator_kind": "gpu", "gpu_profile": "t4", "gpu_count": 1},
        runtime_seconds=60, max_cost_usd=Decimal("0.12"),
        cost_evidence=CostEvidence(classification="CREDIT_BACKED", additional_cost_usd=Decimal("0.12"),
                                   reference=evidence.evidence_reference, observed_at=now - 10, expires_at=now + 300),
        authorization_policy_version="browser-approval-required-v1",
        selection_binding=CandidateBinding(workload_fingerprint="sha256:" + "e" * 64,
                                           provider="modal", resource_id=evidence.resource_id,
                                           evidence_fingerprint=evidence.fingerprint()),
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = "credit:org-authority:key-v1"
    body = {
        "schema_version": 1, "issuer": "org-authority", "key_id": key_id,
        "audience": CREDIT_AUTHORIZATION_AUDIENCE, "authorization_id": "credit-authz-1",
        "revocation_id": "credit-revoke-1", "run_id": "a" * 32,
        "owner": "owner-subject", "actor": "taka", "decision_record_id": "decision-1",
        "control_plane_sha": "1" * 40, "gateway_plan_fingerprint": plan_fingerprint(plan),
        "provider": "modal", "resource_id": evidence.resource_id,
        "image_digest": plan.image_digest, "runtime_seconds": plan.runtime_seconds,
        "max_gross_credit_debit_usd": "0.12", "max_out_of_pocket_usd": "0",
        "quota_evidence_fingerprint": evidence.fingerprint(),
        "authorization_reference": "owner-decision:fixture", "policy_version": "credit-v1",
        "issued_at": now - 5, "expires_at": now + 120,
    }
    def resign(changed):
        unsigned = {k: v for k, v in changed.items() if k != "signature"}
        return unsigned | {"signature": base64.urlsafe_b64encode(
            private.sign(_canonical(unsigned))).rstrip(b"=").decode("ascii")}
    envelope = resign(body)
    args = dict(
        trusted_keys={key_id: public}, expected_issuer="org-authority",
        expected_policy_version="credit-v1", now=now, owner="owner-subject",
        actor="taka", decision_record_id="decision-1", control_plane_sha="1" * 40,
        run_id="a" * 32, gateway_plan=plan, capability_evidence=evidence,
        is_revoked=lambda _issuer, _revocation_id: False,
    )
    return envelope, args, resign


def test_verifies_signed_exact_plan_credit_decision(credit_case):
    envelope, args, _ = credit_case
    verified = verify_credit_authorization(envelope, **args)
    assert verified.authorization_id == "credit-authz-1"
    assert verified.max_gross_credit_debit_usd == Decimal("0.12")
    assert verified.quota_evidence_fingerprint == args["capability_evidence"].fingerprint()


@pytest.mark.parametrize("field,value", [
    ("run_id", "0" * 32), ("owner", "other"), ("actor", "other"),
    ("decision_record_id", "other"), ("resource_id", "other-resource"),
    ("max_out_of_pocket_usd", "0.01"), ("quota_evidence_fingerprint", "f" * 64),
    ("max_gross_credit_debit_usd", "0.13"),
])
def test_rejects_signed_claim_mismatch(credit_case, field, value):
    _, args, resign = credit_case
    # The signed envelope is copied and resigned with the test-only private key.
    envelope = credit_case[0]
    changed = dict(envelope)
    changed[field] = value
    with pytest.raises(CreditAuthorizationError):
        verify_credit_authorization(resign(changed), **args)


def test_rejects_expired_stale_or_revoked_credit_authority(credit_case):
    envelope, args, resign = credit_case
    expired = dict(envelope, expires_at=args["now"])
    with pytest.raises(CreditAuthorizationError, match="expired"):
        verify_credit_authorization(resign(expired), **args)
    with pytest.raises(CreditAuthorizationError, match="revoked"):
        verify_credit_authorization(envelope, **(args | {"is_revoked": lambda *_: True}))


def test_rejects_missing_hard_stop_or_quota_coverage(credit_case):
    envelope, args, _ = credit_case
    evidence = args["capability_evidence"]
    with pytest.raises(CreditAuthorizationError, match="quota and hard-stop"):
        verify_credit_authorization(envelope, **(args | {
            "capability_evidence": evidence.__class__(**{
                **evidence.__dict__, "overage_behavior": OverageBehavior.CHARGED,
            })
        }))


def test_rejects_credit_component_omission_even_when_omitted_cost_is_zero(credit_case):
    envelope, args, _ = credit_case
    evidence = args["capability_evidence"]
    quota = evidence.quota_evidence
    reduced_quota = QuotaEvidence(
        remaining_usage_usd=quota.remaining_usage_usd,
        remaining_credits_usd=quota.remaining_credits_usd,
        covered_components=quota.covered_components[:-1],
        evidence_reference=quota.evidence_reference,
        observed_at_utc=quota.observed_at_utc,
        valid_until_utc=quota.valid_until_utc,
    )
    changed_evidence = evidence.__class__(**{**evidence.__dict__, "quota_evidence": reduced_quota})
    with pytest.raises(CreditAuthorizationError, match="quota evidence"):
        verify_credit_authorization(envelope, **(args | {"capability_evidence": changed_evidence}))


def test_rejects_plan_cost_ceiling_below_gross_credit_debit(credit_case):
    envelope, args, _ = credit_case
    low_ceiling = args["gateway_plan"].model_copy(update={"max_cost_usd": Decimal("0.11")})
    with pytest.raises(CreditAuthorizationError, match="quota evidence"):
        verify_credit_authorization(envelope, **(args | {"gateway_plan": low_ceiling}))


def test_credit_trust_settings_are_namespaced_and_require_matching_policy(credit_case, monkeypatch):
    envelope, args, _ = credit_case
    key_pem = args["trusted_keys"][envelope["key_id"]].decode("ascii")
    settings = __import__("gpu_gateway.config", fromlist=["Settings"]).Settings(
        credit_authorization_issuer="org-authority",
        credit_authorization_policy_version="credit-v1",
        credit_authorization_public_keys_json=json.dumps({envelope["key_id"]: key_pem}),
    )
    settings.validate()
    assert settings.credit_authorization_trusted_keys == args["trusted_keys"]

    broken = settings.__class__(
        credit_authorization_issuer="other-authority",
        credit_authorization_policy_version="credit-v1",
        credit_authorization_public_keys_json=json.dumps({envelope["key_id"]: key_pem}),
    )
    with pytest.raises(ValueError, match="matching trusted keys"):
        broken.validate()
