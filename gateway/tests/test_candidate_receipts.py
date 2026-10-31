import base64
import hashlib
import json
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpu_gateway import candidate_receipts
from gpu_gateway.candidate_receipts import (
    CandidateReceiptError,
    candidate_result_digest,
    verify_candidate_receipt,
)
from gpu_gateway.config import Settings
from gpu_gateway.contracts import CandidateBinding, PlanV2, plan_fingerprint


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _fixture():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    plan = PlanV2(
        schema_version=2, repository="Unjuno/gpu-control", source_sha="a" * 40,
        workload="gpu-smoke", workload_manifest_digest="b" * 64,
        image_digest="sha256:" + "c" * 64, parameters={}, provider="runpod",
        device_requirement={"requires_gpu": True}, runtime_seconds=120,
        max_cost_usd=Decimal("1"), cost_evidence={
            "classification": "FREE", "additional_cost_usd": Decimal("0"),
            "reference": "test", "observed_at": 1000, "expires_at": 1100,
        }, authorization_policy_version="test-v1",
        selection_binding=CandidateBinding(
            workload_fingerprint="sha256:" + "d" * 64, provider="runpod",
            resource_id="gpu-type-123", evidence_fingerprint="sha256:" + "e" * 64),
    )
    fingerprint = plan_fingerprint(plan)
    result = {"device": "NVIDIA A10", "gpu_used": True, "exit_code": 0,
              "metrics": {"iterations": 4}, "checksum": "f" * 64}
    payload = {
        "run_id": "1" * 32, "plan_fingerprint": fingerprint,
        "source_sha": plan.source_sha, "image_digest": plan.image_digest,
        "resource_id": plan.selection_binding.resource_id,
        "provider_execution_id": "pod-abc123", "device_id": "GPU-uuid-123",
        "device_model": result["device"], "gpu_used": True, "exit_code": 0,
        "result_sha256": candidate_result_digest(result),
        "evidence_source": "runpod.graphql.pod",
        "provider_object_sha256": "9" * 64,
    }
    unsigned = {"schema_version": 1, "signer": "provider",
                "key_id": "provider:runpod:receipt-v1",
                "provider": "runpod", "issued_at": 1050, "expires_at": 1150,
                "payload": payload}
    signature = base64.urlsafe_b64encode(private.sign(_canonical(unsigned))).rstrip(b"=").decode()
    return plan, fingerprint, result, {**unsigned, "signature": signature}, {
        "provider:runpod:receipt-v1": public,
    }


def _verify(values, *, now=1060):
    plan, fingerprint, result, receipt, keys = values
    return verify_candidate_receipt(receipt, keys, now=now, plan=plan,
                                    fingerprint=fingerprint, run_id="1" * 32,
                                    result=result)


def test_provider_signed_candidate_receipt_binds_plan_resource_and_result():
    values = _fixture()
    assert _verify(values)["payload"]["provider_execution_id"] == "pod-abc123"


@pytest.mark.parametrize("mutation", ["resource", "fingerprint", "result", "signature", "untrusted_key"])
def test_candidate_receipt_rejects_tampering_or_identity_mismatch(mutation):
    plan, fingerprint, result, receipt, keys = _fixture()
    if mutation == "resource":
        receipt["payload"]["resource_id"] = "other-resource"
    elif mutation == "fingerprint":
        fingerprint = "0" * 64
    elif mutation == "result":
        result["metrics"]["iterations"] = 5
    elif mutation == "signature":
        receipt["signature"] = "A" * 86
    else:
        keys = {}
    with pytest.raises(CandidateReceiptError):
        verify_candidate_receipt(receipt, keys, now=1060, plan=plan,
                                 fingerprint=fingerprint, run_id="1" * 32,
                                 result=result)


def test_candidate_receipt_expiry_is_fail_closed():
    values = _fixture()
    with pytest.raises(CandidateReceiptError, match="stale"):
        _verify(values, now=1150)


def test_adapter_attestation_uses_distinct_signer_scope():
    plan, fingerprint, result, receipt, _provider_keys = _fixture()
    adapter_private = Ed25519PrivateKey.generate()
    adapter_public = adapter_private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    unsigned = dict(receipt)
    unsigned.update(signer="gateway_adapter", key_id="adapter:runpod:gateway-v1")
    unsigned["payload"] = dict(unsigned["payload"],
                               evidence_source="runpod.graphql.pod")
    signature = base64.urlsafe_b64encode(adapter_private.sign(_canonical(
        {key: value for key, value in unsigned.items() if key != "signature"}
    ))).rstrip(b"=").decode()
    unsigned["signature"] = signature
    valid = verify_candidate_receipt(unsigned, {"adapter:runpod:gateway-v1": adapter_public},
                                      now=1060, plan=plan, fingerprint=fingerprint,
                                      run_id="1" * 32, result=result)
    assert valid["signer"] == "gateway_adapter"

    with pytest.raises(CandidateReceiptError, match="not trusted"):
        verify_candidate_receipt(unsigned, {"provider:runpod:gateway-v1": adapter_public},
                                 now=1060, plan=plan, fingerprint=fingerprint,
                                 run_id="1" * 32, result=result)


def test_receipt_trust_keys_are_separate_from_gateway_observation_signing_keys():
    _, _, _, _, keys = _fixture()
    settings = Settings(candidate_receipt_public_keys_json=json.dumps({
        "provider:runpod:receipt-v1": next(iter(keys.values())).decode("ascii")
    }))
    assert set(settings.candidate_receipt_trusted_keys) == {"provider:runpod:receipt-v1"}


def _sign_adapter_receipt(**kwargs):
    signer = getattr(candidate_receipts, "sign_adapter_candidate_receipt", None)
    assert callable(signer), "adapter receipt signer is not implemented"
    return signer(**kwargs)


def test_adapter_receipt_signer_binds_plan_result_and_authenticated_projection():
    plan, fingerprint, result, _, _ = _fixture()
    private = Ed25519PrivateKey.generate()
    projection = {"id": "pod-abc123", "status": "EXITED",
                  "gpu": {"id": "gpu-type-123", "count": 1}}
    receipt = _sign_adapter_receipt(
        private_key=private, key_id="adapter:runpod:gateway-v1",
        issued_at=1050, expires_at=1150, now=1060, plan=plan,
        fingerprint=fingerprint, run_id="1" * 32, result=result,
        provider_execution_id="pod-abc123", device_id="GPU-uuid-123",
        evidence_source="runpod.rest_v2.pod",
        provider_object_projection=projection,
    )
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    verified = verify_candidate_receipt(
        receipt, {"adapter:runpod:gateway-v1": public}, now=1060,
        plan=plan, fingerprint=fingerprint, run_id="1" * 32, result=result,
    )
    assert verified["signer"] == "gateway_adapter"
    assert verified["payload"]["resource_id"] == plan.selection_binding.resource_id
    assert verified["payload"]["provider_object_sha256"] == hashlib.sha256(
        _canonical(projection)).hexdigest()
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    signature = base64.urlsafe_b64decode(receipt["signature"] + "==")
    private.public_key().verify(signature, _canonical(unsigned))


@pytest.mark.parametrize(("change", "message"), [
    ({"expires_at": 1351}, "validity window"),
    ({"issued_at": 1070}, "validity window"),
    ({"fingerprint": "0" * 64}, "plan fingerprint"),
    ({"provider_object_projection": None}, "provider object projection"),
    ({"provider_object_projection": []}, "provider object projection"),
    ({"provider_object_projection": {1: "value"}}, "provider object projection"),
    ({"provider_object_projection": {"nested": (1, 2)}}, "provider object projection"),
    ({"evidence_source": "modal.sandbox.get"}, "receipt provider evidence source"),
    ({"result": {"device": "NVIDIA A10", "gpu_used": False, "exit_code": 0,
                 "metrics": {"iterations": 4}, "checksum": "f" * 64}},
     "receipt identity or result"),
])
def test_adapter_receipt_signer_rejects_invalid_provider_projection_or_result(change, message):
    plan, fingerprint, result, _, _ = _fixture()
    private = Ed25519PrivateKey.generate()
    values = {
        "private_key": private, "key_id": "adapter:runpod:gateway-v1",
        "issued_at": 1050, "expires_at": 1150, "now": 1060, "plan": plan,
        "fingerprint": fingerprint, "run_id": "1" * 32, "result": result,
        "provider_execution_id": "pod-abc123", "device_id": "GPU-uuid-123",
        "evidence_source": "runpod.rest_v2.pod",
        "provider_object_projection": {"id": "pod-abc123", "status": "EXITED"},
    }
    values.update(change)
    with pytest.raises(CandidateReceiptError, match=message):
        _sign_adapter_receipt(**values)


def test_adapter_receipt_signer_rejects_cyclic_provider_projection():
    plan, fingerprint, result, _, _ = _fixture()
    private = Ed25519PrivateKey.generate()
    projection = {}
    projection["self"] = projection
    with pytest.raises(CandidateReceiptError, match="cycles"):
        _sign_adapter_receipt(
            private_key=private, key_id="adapter:runpod:gateway-v1",
            issued_at=1050, expires_at=1150, now=1060, plan=plan,
            fingerprint=fingerprint, run_id="1" * 32, result=result,
            provider_execution_id="pod-abc123", device_id="GPU-uuid-123",
            evidence_source="runpod.rest_v2.pod",
            provider_object_projection=projection,
        )
