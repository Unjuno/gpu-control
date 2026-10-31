import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select, update

from gpu_gateway.config import Workload
from gpu_gateway.experiment_api import _gpu_requirements, invoke
from gpu_gateway.protocol import CHATGPT_NAMES, dispatch, tools
from gpu_gateway.registry import ProviderRegistration
from gpu_gateway.service import GatewayError, Prepare, Principal
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker
from gpu_control.workloads import (
    AcceleratorKind,
    NetworkRequirement,
    ResultTransport,
    WorkloadRequirements,
)

REPOSITORY = "Unjuno/gpu-control"
SOURCE_SHA = "a" * 40


def fake_dedicated_filesystem(monkeypatch, root):
    original_stat = Path.stat

    def stat_with_separate_device(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path == root else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr("gpu_gateway.artifacts.Path.stat", stat_with_separate_device)


def test_canonical_tool_surface_is_eight_tools_and_legacy_remains(system):
    listed = tools(system.owner)
    assert {tool["name"] for tool in listed} == CHATGPT_NAMES
    assert len(CHATGPT_NAMES) == 8
    # Existing clients can still call legacy names, but tools/list is canonical.
    response, status = dispatch(system.service, system.owner, {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "integrations_list", "arguments": {}},
    })
    assert status == 200
    assert "structuredContent" in response["result"]


def test_tool_visibility_follows_scopes(system):
    reader = Principal(system.owner.owner, frozenset({"experiments:read"}))
    names = {tool["name"] for tool in tools(reader)}
    assert {"experiment_capabilities", "experiment_status", "experiment_result",
            "experiment_artifact", "experiment_list"} <= names
    assert "experiment_prepare" not in names
    assert "experiment_cancel" not in names


def test_capabilities_do_not_describe_demo_as_executable(system):
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "NO_QUEUEABLE_RESOURCE"


def test_gpu_capabilities_explain_selection_boundary_without_fabricating_evidence(system):
    system.service.workloads["gpu"] = Workload(
        provider="modal", image_id="im-fixed", argv=("python", "run.py"),
        source_revision="fixed", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, max_cost_usd="0.01",
    )
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, execution_profile="smoke",
        image_digest="sha256:" + "e" * 64,
    )
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    gpu = next(item for item in result["machine_state"]["resources"]
               if item["workload"] == "gpu")
    assert gpu["availability"] == "blocked"
    assert gpu["submission_available"] is False
    assert gpu["candidate_selection"] == {
        "status": "not_evaluated",
        "blocking_reason": "WORKLOAD_REQUIREMENTS_INCOMPLETE",
        "missing_workload_requirements": [
            "operating_system", "architecture", "gpu_count", "minimum_vram_mib",
            "network_requirement", "result_transport", "max_result_bytes",
            "cancellation_required", "cleanup_proof_required",
        ],
        "provider_evidence": "NOT_AVAILABLE",
        "alternatives": [
            {"kind": "local_cpu_workload", "workload": "cpu"},
            {"kind": "paid_gpu_path", "status": "unavailable_until_live_acceptance"},
        ],
    }


def test_gpu_capabilities_run_selector_for_complete_manifest_and_report_missing_evidence(system):
    system.service.workloads["gpu"] = Workload(
        provider="modal", image_id="im-fixed", argv=("python", "run.py"),
        source_revision="fixed", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, gpu="A10G", cpu=4, memory_mib=16384,
        max_runtime_seconds=300, max_cost_usd="0.25",
        operating_system="linux", architecture="x86_64", gpu_count=1,
        minimum_vram_mib=20000, network_requirement="disabled",
        result_transport="object_storage", max_result_bytes=1024 * 1024,
        cancellation_required=True, cleanup_proof_required=True,
    )
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    gpu = next(item for item in result["machine_state"]["resources"]
               if item["workload"] == "gpu")
    selection = gpu["candidate_selection"]
    assert selection["status"] == "not_evaluated"
    assert selection["blocking_reason"] == "PROVIDER_EVIDENCE_UNAVAILABLE"
    assert selection["missing_workload_requirements"] == []
    assert selection["provider_evidence"] == "NOT_AVAILABLE"
    expected_requirements = WorkloadRequirements(
        workload_id="gpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        operating_system="linux", architecture="x86_64",
        accelerator_kind=AcceleratorKind.GPU, gpu_profile="a10g", gpu_count=1,
        minimum_vram_mib=20000, minimum_cpu_cores=Decimal("4"),
        minimum_memory_mib=16384, max_runtime_seconds=300,
        network_requirement=NetworkRequirement.DISABLED,
        result_transport=ResultTransport.OBJECT_STORAGE,
        max_result_bytes=1024 * 1024, cancellation_required=True,
        cleanup_proof_required=True,
    )
    assert selection["workload_fingerprint"] == expected_requirements.fingerprint()
    assert selection["selector_result"]["workload_fingerprint"] == expected_requirements.fingerprint()
    assert selection["selector_result"]["blocking_reason"] == "PROVIDER_EVIDENCE_UNAVAILABLE"


def test_example_gpu_manifest_states_p4_requirements_but_stays_blocked_until_source_identity():
    payload = json.loads((Path(__file__).parent.parent / "examples/workloads.json").read_text())
    workload = Workload.model_validate(payload["gpu-smoke"])
    requirements, missing = _gpu_requirements("gpu-smoke", workload)
    assert requirements is None
    assert missing == ["source_repository", "source_sha"]


def test_capabilities_block_artifact_producing_cpu_without_available_storage(system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
    )
    system.service.registry["local_cpu"] = ProviderRegistration(
        "local_cpu", "local_worker_container", lambda _: True, lambda _: None,
    )
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    state = result["machine_state"]
    cpu = next(resource for resource in state["resources"] if resource["workload"] == "cpu")
    assert state["artifact_storage"]["reason"] == "not_configured"
    assert cpu["submission_available"] is False
    assert "ARTIFACT_STORAGE_UNAVAILABLE" in cpu["blocking_reasons"]
    assert cpu["quota_status"] == "LOCAL_CAPACITY_UNVERIFIED"


def test_capabilities_block_when_artifact_headroom_is_below_configured_floor(system, tmp_path, monkeypatch):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
    )
    system.service.registry["local_cpu"] = ProviderRegistration(
        "local_cpu", "local_worker_container", lambda _: True, lambda _: None,
    )
    root = tmp_path / "artifacts"
    root.mkdir()
    system.service.settings = replace(system.settings, artifact_dir=str(root),
                                      artifact_min_free_bytes=10 * 1024 * 1024)
    fake_dedicated_filesystem(monkeypatch, root)
    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", lambda _: SimpleNamespace(
        f_bavail=8, f_frsize=1024 * 1024))
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    state = result["machine_state"]
    cpu = next(resource for resource in state["resources"] if resource["workload"] == "cpu")
    assert state["artifact_storage"]["reason"] == "below_minimum_free_bytes"
    assert state["artifact_storage"]["minimum_free_bytes"] == 10 * 1024 * 1024
    assert "ARTIFACT_STORAGE_UNAVAILABLE" in cpu["blocking_reasons"]


def test_capabilities_fail_closed_when_artifact_capacity_query_raises(system, tmp_path, monkeypatch):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
    )
    system.service.registry["local_cpu"] = ProviderRegistration(
        "local_cpu", "local_worker_container", lambda _: True, lambda _: None,
    )
    root = tmp_path / "artifacts"
    root.mkdir()

    def capacity_failure(_path):
        raise OSError("simulated statvfs failure")

    system.service.settings = replace(system.settings, artifact_dir=str(root))
    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", capacity_failure)
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    cpu = next(resource for resource in result["machine_state"]["resources"]
               if resource["workload"] == "cpu")
    assert result["status"] == "blocked"
    assert result["machine_state"]["artifact_storage"]["reason"] == "unavailable"
    assert cpu["submission_available"] is False
    assert "ARTIFACT_STORAGE_UNAVAILABLE" in cpu["blocking_reasons"]
    assert cpu["quota_status"] == "LOCAL_CAPACITY_UNVERIFIED"


@pytest.mark.parametrize("failure", ["connection", "missing_control_row"])
def test_capabilities_fail_closed_when_control_store_is_unavailable(system, monkeypatch, failure):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
    )
    system.service.registry["local_cpu"] = ProviderRegistration(
        "local_cpu", "local_worker_container", lambda _: True, lambda _: None,
    )
    if failure == "connection":
        def unavailable():
            raise OSError("simulated control-store outage")
        monkeypatch.setattr(system.store.engine, "connect", unavailable)
    else:
        with system.store.transaction() as connection:
            connection.execute(delete(control).where(control.c.id == 1))

    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    state = result["machine_state"]
    cpu = next(resource for resource in state["resources"] if resource["workload"] == "cpu")
    assert state["control_store"] == {"available": False}
    assert cpu["submission_available"] is False
    assert "CONTROL_STORE_UNAVAILABLE" in cpu["blocking_reasons"]


def test_worker_does_not_start_provider_if_cancel_wins_dispatch_claim(system, monkeypatch):
    prepared = system.service.prepare(
        system.owner,
        Prepare(workload="demo", parameters={}, runtime_seconds=30,
                max_cost_usd="0.10", idempotency_key="cancel-before-dispatch-001"),
    )
    run_id = prepared["id"]
    system.service.approve(system.browser, run_id, prepared["fingerprint"])
    system.service.submit(system.owner, run_id)

    class Backend:
        started = 0

        def start(self, _job):
            self.started += 1
            return {"id": "must-not-start"}

    backend = Backend()
    original_confirm = system.store.confirm_submission_dispatch

    def cancel_then_claim(**kwargs):
        system.service.cancel(system.owner, run_id)
        return original_confirm(**kwargs)

    monkeypatch.setattr(system.store, "confirm_submission_dispatch", cancel_then_claim)
    worker = Worker(system.store, system.service.settings, {"demo": backend},
                    system.clock, registry=system.service.registry)

    assert worker.tick() is True
    saved = system.store.read(run_id)
    assert saved["cancel_requested"] is True
    assert saved["state"] == "cancelled"
    assert saved["error"] == "cancelled_before_submission"
    assert backend.started == 0
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


def test_worker_does_not_start_provider_if_lease_expires_before_dispatch_claim(system, monkeypatch):
    prepared = system.service.prepare(
        system.owner,
        Prepare(workload="demo", parameters={}, runtime_seconds=30,
                max_cost_usd="0.10", idempotency_key="lease-expires-before-dispatch-001"),
    )
    run_id = prepared["id"]
    system.service.approve(system.browser, run_id, prepared["fingerprint"])
    system.service.submit(system.owner, run_id)

    class Backend:
        started = 0

        def start(self, _job):
            self.started += 1
            return {"id": "must-not-start"}

    backend = Backend()
    original_confirm = system.store.confirm_submission_dispatch

    def expire_lease_before_claim(**kwargs):
        system.clock.advance(121)
        return original_confirm(**kwargs)

    monkeypatch.setattr(system.store, "confirm_submission_dispatch", expire_lease_before_claim)
    worker = Worker(system.store, system.service.settings, {"demo": backend},
                    system.clock, registry=system.service.registry)

    assert worker.tick() is True
    saved = system.store.read(run_id)
    assert saved["attempt"] == 1
    assert saved["submission_intent"]["phase"] == "dispatching"
    assert backend.started == 0


def test_worker_expires_run_if_approval_expires_before_dispatch_claim(system, monkeypatch):
    prepared = system.service.prepare(
        system.owner,
        Prepare(workload="demo", parameters={}, runtime_seconds=30,
                max_cost_usd="0.10", idempotency_key="approval-expires-before-dispatch-001"),
    )
    run_id = prepared["id"]
    system.service.approve(system.browser, run_id, prepared["fingerprint"])
    system.service.submit(system.owner, run_id)

    class Backend:
        started = 0

        def start(self, _job):
            self.started += 1
            return {"id": "must-not-start"}

    backend = Backend()
    original_confirm = system.store.confirm_submission_dispatch

    def expire_approval_before_claim(**kwargs):
        with system.store.transaction() as connection:
            connection.execute(runs.update().where(runs.c.id == run_id).values(
                approved_until=int(system.clock()) + 1,
            ))
        system.clock.advance(2)
        return original_confirm(**kwargs)

    monkeypatch.setattr(system.store, "confirm_submission_dispatch", expire_approval_before_claim)
    worker = Worker(system.store, system.service.settings, {"demo": backend},
                    system.clock, registry=system.service.registry)

    assert worker.tick() is True
    saved = system.store.read(run_id)
    assert saved["state"] == "expired"
    assert saved["error"] == "approval_expired_before_submission"
    assert backend.started == 0


def test_prepare_blocks_unregistered_or_unsafe_backend_without_creating_run(system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    args = {"repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "cpu",
            "parameters": {}, "max_cost_usd": "0.00", "requires_gpu": False,
            "idempotency_key": "cpu-plan-0001"}
    result = invoke(system.service, system.owner, "experiment_prepare", args)
    assert result["blocking_reason"] == "POLICY_DISABLED"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(runs.c.id)).first() is None


def test_prepare_rechecks_artifact_storage_headroom_before_creating_run(system, tmp_path, monkeypatch):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    system.service.registry = {"local_cpu": ProviderRegistration("local_cpu", "local_cpu", lambda _: True, lambda _: None)}
    policy = {"version": "local-cpu-v1", "enabled": True,
              "valid_until": int(system.clock()) + 60, "workloads": ["cpu"],
              "max_runtime_seconds": 30, "max_cost_usd": "0.00",
              "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    system.service.settings = replace(system.settings, artifact_dir=str(artifact_root),
                                      artifact_min_free_bytes=10 * 1024 * 1024)
    fake_dedicated_filesystem(monkeypatch, artifact_root)
    monkeypatch.setattr("gpu_gateway.artifacts.os.statvfs", lambda _: SimpleNamespace(
        f_bavail=8, f_frsize=1024 * 1024))
    args = {"repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "cpu",
            "parameters": {}, "runtime_seconds": 20, "max_cost_usd": "0.00", "requires_gpu": False,
            "idempotency_key": "cpu-storage-0001"}
    result = invoke(system.service, system.owner, "experiment_prepare", args)
    assert result["blocking_reason"] == "ARTIFACT_STORAGE_UNAVAILABLE"
    assert result["machine_state"]["artifact_storage"]["reason"] == "below_minimum_free_bytes"
    assert result["machine_state"]["artifact_storage"]["free_bytes"] == 8 * 1024 * 1024
    assert result["machine_state"]["artifact_storage"]["minimum_free_bytes"] == 10 * 1024 * 1024
    with system.store.engine.connect() as connection:
        assert connection.execute(select(runs.c.id)).first() is None


def test_prepare_persists_distinct_operator_local_authorization(tmp_path, monkeypatch, system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", max_runtime_seconds=30,
        execution_profile="smoke", image_digest="sha256:" + "d" * 64,
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    system.service.registry = {"local_cpu": ProviderRegistration("local_cpu", "local_cpu", lambda _: True, lambda _: None)}
    local_policy = {"version": "local-cpu-v1", "enabled": True,
                    "valid_until": int(system.clock()) + 60, "workloads": ["cpu"],
                    "max_runtime_seconds": 30, "max_cost_usd": "0.00",
                    "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(local_policy))
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    system.service.settings = replace(system.settings, artifact_dir=str(artifact_root))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))
    args = {"repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "cpu",
            "runtime_seconds": 20, "max_cost_usd": "0.00", "requires_gpu": False,
            "idempotency_key": "canonical-local-0001"}
    first = invoke(system.service, system.owner, "experiment_prepare", args)
    again = invoke(system.service, system.owner, "experiment_prepare", args)
    state = first["machine_state"]
    assert first["status"] == "ok"
    assert state["state"] == "authorized"
    assert state["run_id"] == again["machine_state"]["run_id"]
    stored = system.store.read(state["run_id"])
    assert stored["admission"]["mode"] == "local_policy"
    assert stored["approval_id"] == ""


def test_prepare_requires_exact_operator_source_and_device_policy(system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", execution_profile="smoke",
        image_digest="sha256:" + "d" * 64,
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    base = {"repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "cpu",
            "max_cost_usd": "0.00", "idempotency_key": "cpu-plan-0002"}
    assert invoke(system.service, system.owner, "experiment_prepare", {**base, "commit": "b" * 40})["blocking_reason"] == "SOURCE_IDENTITY_MISMATCH"
    assert invoke(system.service, system.owner, "experiment_prepare", {**base, "requires_gpu": True})["blocking_reason"] == "DEVICE_REQUIREMENT_MISMATCH"


def test_submit_requires_exact_fingerprint_and_owner_scope(system):
    prepared = system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="canonical-run-0001"))
    with pytest.raises(GatewayError, match="fingerprint"):
        invoke(system.service, system.owner, "experiment_submit", {"run_id": prepared["id"], "plan_fingerprint": "0" * 64})
    other = replace(system.owner, owner="other")
    with pytest.raises(GatewayError) as error:
        invoke(system.service, other, "experiment_status", {"run_id": prepared["id"]})
    assert error.value.status == 404


def test_pending_result_does_not_claim_success_and_cancel_is_owner_scoped(system):
    prepared = system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="canonical-run-0003"))
    result = invoke(system.service, system.owner, "experiment_result", {"run_id": prepared["id"]})
    assert result["status"] == "pending"
    assert "result" not in result["machine_state"]
    assert result["next_allowed_actions"] == ["experiment_status"]
    other = replace(system.owner, owner="other")
    with pytest.raises(GatewayError) as error:
        invoke(system.service, other, "experiment_cancel", {"run_id": prepared["id"]})
    assert error.value.status == 404


def test_last_backend_observation_is_owner_scoped_in_status_and_lists(system):
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="last-backend-observation-0001"))
    observed_at = int(system.clock()) - 17
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared["id"]).values(
            last_observed_at=observed_at, state="submit_unknown"))

    status = invoke(system.service, system.owner, "experiment_status", {"run_id": prepared["id"]})
    assert status["machine_state"]["last_observed_at"] == observed_at
    pending_result = invoke(system.service, system.owner, "experiment_result",
                            {"run_id": prepared["id"]})
    assert pending_result["machine_state"]["last_observed_at"] == observed_at
    listed = invoke(system.service, system.owner, "experiment_list", {})
    assert listed["experiments"][0]["last_observed_at"] == observed_at
    assert system.service.get(system.owner, prepared["id"])["last_observed_at"] == observed_at
    other = replace(system.owner, owner="other")
    with pytest.raises(GatewayError) as error:
        invoke(system.service, other, "experiment_status", {"run_id": prepared["id"]})
    assert error.value.status == 404


def test_gpu_required_workload_cannot_fall_back_to_cpu(system):
    system.service.workloads["gpu"] = Workload(
        provider="modal", image_id="im-fixed", argv=("python", "run.py"),
        source_revision="fixed", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    result = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "max_cost_usd": "0.00", "requires_gpu": True, "idempotency_key": "gpu-plan-0001",
    })
    assert result["blocking_reason"] == "GPU_BACKEND_UNAVAILABLE"
    assert result["machine_state"]["provider"] == "modal"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(runs.c.id)).first() is None


def test_local_cpu_workload_requires_operator_image_digest_and_profile():
    with pytest.raises(ValueError, match="image_digest"):
        Workload(provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
                 requires_gpu=False, execution_profile="smoke")
    workload = Workload(provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
                        requires_gpu=False, execution_profile="smoke",
                        image_digest="sha256:" + "d" * 64)
    assert workload.image_digest == "sha256:" + "d" * 64
    with pytest.raises(ValueError, match="must not require a GPU"):
        Workload(provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
                 requires_gpu=True, execution_profile="smoke", image_digest="sha256:" + "d" * 64)


def test_result_never_calls_simulation_a_real_success(system):
    prepared = system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="canonical-run-0002"))
    system.service.approve(system.browser, prepared["id"], prepared["fingerprint"])
    queued = system.service.submit(system.owner, prepared["id"])
    from gpu_gateway.backends import DemoBackend
    from gpu_gateway.worker import Worker
    Worker(system.store, system.settings, {"demo": DemoBackend()}, system.clock).tick()
    system.clock.advance(2)
    Worker(system.store, system.settings, {"demo": DemoBackend()}, system.clock).tick()
    result = invoke(system.service, system.owner, "experiment_result", {"run_id": queued["id"]})
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "SIMULATION_RESULT"
    assert result["machine_state"]["result"]["simulation"] is True


def test_list_cursor_is_owner_bound_and_filters_are_applied(system):
    for key in ("cursor-test-0001", "cursor-test-0002"):
        system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key=key))
    first = invoke(system.service, system.owner, "experiment_list", {"limit": 1})
    assert first["machine_state"]["count"] == 1
    assert first["next_cursor"]
    second = invoke(system.service, system.owner, "experiment_list", {"limit": 1, "cursor": first["next_cursor"]})
    assert second["experiments"][0]["run_id"] != first["experiments"][0]["run_id"]
    with pytest.raises(GatewayError, match="cursor"):
        invoke(system.service, replace(system.owner, owner="other"), "experiment_list", {"limit": 1, "cursor": first["next_cursor"]})


def test_protocol_routes_canonical_calls_and_returns_structured_envelope(system):
    response, status = dispatch(system.service, system.owner, {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "experiment_capabilities", "arguments": {}},
    })
    assert status == 200
    result = response["result"]["structuredContent"]
    assert result["schema_version"] == 2
    assert result["blocking_reason"] == "NO_QUEUEABLE_RESOURCE"
