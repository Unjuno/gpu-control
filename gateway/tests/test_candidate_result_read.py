import base64
import json
from dataclasses import replace
from decimal import Decimal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import update

from gpu_gateway.candidate_receipts import candidate_result_digest
from gpu_gateway.contracts import CandidateBinding, PlanV2, ResultV2, plan_fingerprint
from gpu_gateway.service import Prepare
from gpu_gateway.store import runs


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _seed_candidate_result(system):
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="candidate-result-read-0001"))
    run_id = created["id"]
    now = int(system.clock())
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    settings = replace(system.settings, candidate_receipt_public_keys_json=json.dumps({
        "provider:demo:test-v1": public.decode("ascii"),
    }))
    system.settings = settings
    system.service.settings = settings
    plan = PlanV2(
        schema_version=2, repository="Unjuno/gpu-control", source_sha="a" * 40,
        workload="gpu-smoke", workload_manifest_digest="b" * 64,
        image_digest="sha256:" + "c" * 64, parameters={}, provider="demo",
        device_requirement={"requires_gpu": True}, runtime_seconds=120,
        max_cost_usd=Decimal("1"), cost_evidence={
            "classification": "FREE", "additional_cost_usd": Decimal("0"),
            "reference": "test", "observed_at": now - 10, "expires_at": now + 100,
        }, authorization_policy_version="test-v1",
        selection_binding=CandidateBinding(
            workload_fingerprint="sha256:" + "d" * 64, provider="demo",
            resource_id="gpu-test-1", evidence_fingerprint="sha256:" + "e" * 64),
    )
    fingerprint = plan_fingerprint(plan)
    result = ResultV2(
        schema_version=2, run_id=run_id, source_sha=plan.source_sha,
        plan_fingerprint=fingerprint, provider="demo", image_digest=plan.image_digest,
        simulation=False, gpu_used=True, device="NVIDIA A10", exit_code=0,
        started_at=now - 2, finished_at=now - 1, runtime_seconds=1.0,
        metrics={"iterations": 10}, checks=["candidate_resource_verified", "device_identity_verified"],
        checksum="f" * 64, artifacts=[], known_cost_usd=Decimal("0"),
        cost_classification="FREE", cleanup_state="complete",
    )
    payload = {
        "run_id": run_id, "plan_fingerprint": fingerprint,
        "source_sha": plan.source_sha, "image_digest": plan.image_digest,
        "resource_id": plan.selection_binding.resource_id,
        "provider_execution_id": "demo-execution-1", "device_id": "GPU-uuid-test",
        "device_model": result.device, "gpu_used": True, "exit_code": 0,
        "result_sha256": candidate_result_digest(result.model_dump(mode="json")),
        "evidence_source": "demo.fake.receipt", "provider_object_sha256": "9" * 64,
    }
    unsigned = {"schema_version": 1, "signer": "provider",
                "key_id": "provider:demo:test-v1", "provider": "demo",
                "issued_at": now - 2, "expires_at": now + 60, "payload": payload}
    receipt = unsigned | {"signature": base64.urlsafe_b64encode(
        private.sign(_canonical(unsigned))).rstrip(b"=").decode("ascii")}
    stored_result = result.model_dump(mode="json") | {"candidate_receipt": receipt}
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == run_id).values(
            state="succeeded", plan=plan.model_dump(mode="json"),
            fingerprint=fingerprint, result=stored_result,
        ))
    return run_id


def test_candidate_receipt_is_verified_on_read_even_after_short_ttl(system):
    run_id = _seed_candidate_result(system)
    system.clock.advance(301)
    fetched = system.service.get(system.owner, run_id)
    assert fetched["state"] == "succeeded"
    assert fetched["result"]["candidate_receipt"]["signer"] == "provider"


def test_tampered_persisted_candidate_result_is_not_reported_as_success(system):
    run_id = _seed_candidate_result(system)
    row = system.store.read(run_id)
    result = dict(row["result"])
    result["metrics"] = {"iterations": 999}
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == run_id).values(result=result))

    fetched = system.service.get(system.owner, run_id)
    assert fetched["state"] == "failed"
    assert fetched["error"] == "result_integrity_failed"
    assert fetched["result"] == {"failure_code": "result_integrity_failed"}
    listed = system.service.list(system.owner)
    assert next(item for item in listed["experiments"] if item["id"] == run_id)["state"] == "failed"

    result["metrics"] = row["result"]["metrics"]
    result["cleanup_state"] = "unknown"
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == run_id).values(result=result))
    cleanup_tampered = system.service.get(system.owner, run_id)
    assert cleanup_tampered["state"] == "failed"
    assert cleanup_tampered["error"] == "result_integrity_failed"

    result["metrics"] = row["result"]["metrics"]
    result["cleanup_state"] = "unknown"
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == run_id).values(result=result))
    cleanup_tampered = system.service.get(system.owner, run_id)
    assert cleanup_tampered["state"] == "failed"
    assert cleanup_tampered["error"] == "result_integrity_failed"
