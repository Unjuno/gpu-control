from decimal import Decimal
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from gpu_gateway.admission import evaluate_admission, load_local_cpu_policy, plan_for_workload
from gpu_gateway.contracts import CostEvidence, PlanV2, plan_fingerprint
from gpu_gateway.config import Workload
from gpu_gateway.service import GatewayError, digest
from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.store import control, runs
from sqlalchemy import select, update
from gpu_gateway.registry import ProviderRegistration
from gpu_gateway.worker import Worker


def plan(**overrides):
    value = {
        "schema_version": 2,
        "repository": "Unjuno/gpu-control",
        "source_sha": "a" * 40,
        "workload": "cpu-smoke-v1",
        "workload_manifest_digest": "b" * 64,
        "image_digest": "sha256:" + "c" * 64,
        "parameters": {},
        "provider": "local_cpu",
        "device_requirement": {"kind": "cpu", "requires_gpu": False, "profile": "smoke"},
        "runtime_seconds": 20,
        "max_cost_usd": Decimal("0"),
        "cost_evidence": CostEvidence(
            classification="LOCAL", additional_cost_usd=Decimal("0"),
            reference="operator-confirmed-no-provider-charge", observed_at=100,
            expires_at=200,
        ),
        "authorization_policy_version": "local-cpu-v1",
    }
    value.update(overrides)
    return PlanV2.model_validate(value)


def policy(**overrides):
    value = {
        "version": "local-cpu-v1",
        "enabled": True,
        "valid_until": 180,
        "workloads": ["cpu-smoke-v1"],
        "max_runtime_seconds": 30,
        "max_cost_usd": "0.00",
        "allowed_profiles": ["smoke"],
    }
    value.update(overrides)
    return value


def test_zero_cap_local_cpu_only():
    decision = evaluate_admission(plan(), policy(), now=120)
    assert decision.allowed is True
    assert decision.approval_required is False
    assert decision.blocking_reason is None
    assert decision.valid_until == 180


def test_paid_provider_cannot_reuse_zero_cost_local_policy():
    paid = plan(provider="modal", cost_evidence=CostEvidence(
        classification="FREE", additional_cost_usd=Decimal("0"), reference="free",
        observed_at=100, expires_at=200))
    decision = evaluate_admission(paid, policy(), now=120)
    assert decision.allowed is False
    assert decision.blocking_reason == "PROVIDER_NOT_LOCAL_CPU"


def test_policy_revocation_and_expiry_block_admission():
    assert evaluate_admission(plan(), policy(enabled=False), now=120).blocking_reason == "POLICY_DISABLED"
    assert evaluate_admission(plan(), policy(), now=181).blocking_reason == "POLICY_EXPIRED"


def test_gpu_and_non_smoke_profiles_are_not_preapproved():
    gpu = plan(device_requirement={"kind": "gpu", "requires_gpu": True, "profile": "smoke"})
    high_impact = plan(device_requirement={"kind": "cpu", "requires_gpu": False, "profile": "training"})
    assert evaluate_admission(gpu, policy(), now=120).blocking_reason == "GPU_NOT_ALLOWED"
    assert evaluate_admission(high_impact, policy(), now=120).blocking_reason == "PROFILE_NOT_ALLOWED"


def test_cost_and_workload_must_match_explicit_free_policy():
    charged = plan(max_cost_usd=Decimal("0.01"))
    assert evaluate_admission(charged, policy(), now=120).blocking_reason == "NONZERO_COST_CAP"
    unknown_cost = plan(cost_evidence=CostEvidence(
        classification="UNKNOWN", additional_cost_usd=None, reference="", observed_at=None, expires_at=None))
    assert evaluate_admission(unknown_cost, policy(), now=120).blocking_reason == "COST_NOT_VERIFIED_FREE"
    other_workload = plan(workload="arbitrary")
    assert evaluate_admission(other_workload, policy(), now=120).blocking_reason == "WORKLOAD_NOT_ALLOWLISTED"


def test_admission_binds_policy_version_and_runtime_ceiling():
    mismatched = plan(authorization_policy_version="local-cpu-v0")
    too_long = plan(runtime_seconds=31)
    assert evaluate_admission(mismatched, policy(), now=120).blocking_reason == "POLICY_VERSION_MISMATCH"
    assert evaluate_admission(too_long, policy(), now=120).blocking_reason == "RUNTIME_LIMIT"


def test_malformed_policy_fails_closed():
    decision = evaluate_admission(plan(), {"enabled": True}, now=120)
    assert decision.allowed is False
    assert decision.blocking_reason == "INVALID_POLICY"


def test_local_plan_idempotency_and_policy_authority_are_distinct(system):
    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    local_policy = policy(valid_until=now + 60)
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={"value": "first"}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=local_policy)
    decision = evaluate_admission(candidate, local_policy, now=now)
    first = system.service.prepare_local(system.owner, candidate, "stable-local-key", local_policy, decision)
    repeated = system.service.prepare_local(system.owner, candidate, "stable-local-key", local_policy, decision)
    assert first["id"] == repeated["id"]
    stored = system.store.read(first["id"])
    assert stored["admission"]["mode"] == "local_policy"
    assert stored["approval_id"] == ""
    with pytest.raises(GatewayError, match="new idempotency key"):
        changed = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
            repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={"value": "second"}, runtime_seconds=20,
            max_cost_usd="0.00", now=now, policy=local_policy)
        system.service.prepare_local(system.owner, changed, "stable-local-key", local_policy,
                                     evaluate_admission(changed, local_policy, now=now))
    fresh = system.service.prepare_local(system.owner, candidate, "another-local-key", local_policy, decision)
    assert fresh["id"] != first["id"]


def test_revoked_local_policy_blocks_submit(tmp_path, monkeypatch, system):
    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    enabled = policy(valid_until=now + 60)
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=enabled)
    prepared = system.service.prepare_local(system.owner, candidate, "revocable-local-key", enabled,
                                             evaluate_admission(candidate, enabled, now))
    policy_path = tmp_path / "local-policy.json"
    revoked = {**enabled, "enabled": False}
    policy_path.write_text(json.dumps(revoked))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    with pytest.raises(GatewayError) as error:
        system.service.submit(system.owner, prepared["id"])
    assert error.value.code == "admission_revoked"
    assert system.store.read(prepared["id"])["state"] == "authorized"


def test_changed_registered_manifest_blocks_submit(tmp_path, monkeypatch, system):
    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    enabled = policy(valid_until=now + 60)
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(enabled))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=enabled)
    prepared = system.service.prepare_local(system.owner, candidate, "manifest-rotation-key", enabled,
                                             evaluate_admission(candidate, enabled, now))
    system.service.workloads["cpu-smoke-v1"] = Workload(provider="local_cpu",
        image_digest="sha256:" + "e" * 64, execution_profile="smoke", requires_gpu=False,
        source_repository="Unjuno/gpu-control", source_sha="f" * 40,
        max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    with pytest.raises(GatewayError) as error:
        system.service.submit(system.owner, prepared["id"])
    assert error.value.code == "admission_revoked"
    assert system.store.read(prepared["id"])["state"] == "authorized"


def test_worker_rechecks_local_policy_before_start(tmp_path, monkeypatch, system):
    class Backend:
        started = 0
        def start(self, job):
            self.started += 1
            return {"container_id": "synthetic-test-handle"}
        def reconcile(self, job): return None
        def inspect(self, handle): raise AssertionError("revoked workload must not be inspected")
        def cancel(self, handle): raise AssertionError("no container should exist")

    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    enabled = policy(valid_until=now + 60)
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=enabled)
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(enabled))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    registration = ProviderRegistration("local_cpu", "local_cpu", lambda _: True, lambda _: None)
    system.service.registry = {"local_cpu": registration}
    prepared = system.service.prepare_local(system.owner, candidate, "worker-revocation-key", enabled,
                                             evaluate_admission(candidate, enabled, now))
    saved = system.store.read(prepared["id"])
    restored = PlanV2.model_validate_json(json.dumps(saved["plan"]))
    assert evaluate_admission(restored, load_local_cpu_policy(), now).allowed
    assert plan_fingerprint(restored) == saved["fingerprint"]
    assert digest(saved["plan"]) == saved["fingerprint"]
    queued = system.service.submit(system.owner, prepared["id"])
    assert queued["state"] == "queued"
    policy_path.write_text(json.dumps({**enabled, "enabled": False}))
    backend = Backend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock,
                    registry=system.service.registry, workloads=system.service.workloads)
    assert worker.tick()
    assert backend.started == 0
    final = system.store.read(prepared["id"])
    assert final["state"] == "expired"
    assert final["error"] == "local_policy_revoked_before_start"


def test_worker_rejects_manifest_rotated_after_submit_before_start(tmp_path, monkeypatch, system):
    class Backend:
        started = 0
        def start(self, job):
            self.started += 1
            return {"container_id": "synthetic-test-handle"}
        def reconcile(self, job): return None
        def inspect(self, handle): raise AssertionError("revoked workload must not be inspected")
        def cancel(self, handle): raise AssertionError("no container should exist")

    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    enabled = policy(valid_until=now + 60)
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(enabled))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=enabled)
    registration = ProviderRegistration("local_cpu", "local_cpu", lambda _: True, lambda _: None)
    system.service.registry = {"local_cpu": registration}
    prepared = system.service.prepare_local(system.owner, candidate, "worker-manifest-rotation-key", enabled,
                                             evaluate_admission(candidate, enabled, now))
    queued = system.service.submit(system.owner, prepared["id"])
    assert queued["state"] == "queued"
    rotated = Workload(provider="local_cpu", image_digest="sha256:" + "e" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="f" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    backend = Backend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock,
                    registry=system.service.registry, workloads={"cpu-smoke-v1": rotated})
    assert worker.tick()
    assert backend.started == 0
    final = system.store.read(prepared["id"])
    assert final["state"] == "expired"
    assert final["error"] == "local_policy_revoked_before_start"


def test_worker_rechecks_artifact_headroom_before_start(tmp_path, monkeypatch, system):
    class Backend:
        started = 0
        def start(self, _job):
            self.started += 1
            return {"container_id": "synthetic-test-handle"}
        def reconcile(self, _job): raise AssertionError("no container should exist")
        def inspect(self, _handle): raise AssertionError("no container should exist")
        def cancel(self, _handle): raise AssertionError("no container should exist")

    workload = Workload(provider="local_cpu", image_digest="sha256:" + "c" * 64,
        execution_profile="smoke", requires_gpu=False, source_repository="Unjuno/gpu-control",
        source_sha="a" * 40, max_runtime_seconds=30, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False})
    system.service.workloads["cpu-smoke-v1"] = workload
    now = int(system.clock())
    enabled = policy(valid_until=now + 60)
    candidate = plan_for_workload(workload_name="cpu-smoke-v1", workload_manifest=workload.model_dump(mode="json"),
        repository="Unjuno/gpu-control", source_sha="a" * 40, parameters={}, runtime_seconds=20,
        max_cost_usd="0.00", now=now, policy=enabled)
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(enabled))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    system.settings = replace(system.settings, artifact_dir=str(artifact_root),
                              artifact_min_free_bytes=10 * 1024 * 1024)
    system.service.settings = system.settings
    original_stat = Path.stat

    def different_devices(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path == artifact_root else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr("gpu_gateway.artifacts.Path.stat", different_devices)
    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", lambda _: SimpleNamespace(
        f_bavail=8, f_frsize=1024 * 1024))
    registration = ProviderRegistration("local_cpu", "local_cpu", lambda _: True, lambda _: None)
    system.service.registry = {"local_cpu": registration}
    prepared = system.service.prepare_local(system.owner, candidate, "worker-capacity-key", enabled,
                                             evaluate_admission(candidate, enabled, now))
    queued = system.service.submit(system.owner, prepared["id"])
    assert queued["state"] == "queued"

    backend = Backend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock,
                    registry=system.service.registry, workloads={"cpu-smoke-v1": workload})
    assert worker.tick()
    final = system.store.read(prepared["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert backend.started == 0
    assert final["state"] == "failed"
    assert final["error"] == "ARTIFACT_STORAGE_UNAVAILABLE"
    assert final["submission_intent"] is None
    assert active == 0


def test_worker_rejects_result_with_wrong_source_binding(system):
    from gpu_gateway.service import Prepare

    legacy = system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="binding-test-0001"))
    expected_plan = plan()
    fingerprint = plan_fingerprint(expected_plan)
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == legacy["id"]).values(
            plan=expected_plan.model_dump(mode="json"), fingerprint=fingerprint,
            state="running", slot_reserved=True, lease_token="worker-token"))
    job = system.store.read(legacy["id"])
    result = {"schema_version": 2, "run_id": legacy["id"], "source_sha": "e" * 40,
              "plan_fingerprint": fingerprint, "provider": "local_cpu", "simulation": False,
              "gpu_used": False, "device": "cpu", "exit_code": 0, "started_at": 100,
              "finished_at": 101, "runtime_seconds": 1.0, "metrics": {}, "checks": [],
              "checksum": None, "artifacts": [], "known_cost_usd": "0",
              "cost_classification": "LOCAL", "cleanup_state": "complete"}
    worker = Worker(system.store, system.settings, {}, system.clock)
    worker.finish({**job, "lease_token": "worker-token"}, "succeeded", result)
    saved = system.store.read(legacy["id"])
    assert saved["state"] == "failed"
    assert saved["error"] == "result_integrity_failed"
    assert saved["cleanup_state"] == "unknown"
