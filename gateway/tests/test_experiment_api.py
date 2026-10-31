import base64
import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import delete, select, update

from gpu_gateway.config import Workload
from gpu_gateway.backends import Observation, ProviderAccountLeaseRequest
from gpu_gateway.experiment_api import _gpu_requirements, invoke
from gpu_gateway.migrations import provider_account_leases
from gpu_gateway.provider_account_scope import derive_provider_account_scope
from gpu_gateway.protocol import CHATGPT_NAMES, dispatch, tools
from gpu_gateway.provider_evidence import build_signed_observation
from gpu_gateway.registry import ProviderRegistration
from gpu_gateway.service import GatewayError, Prepare, Principal, digest
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker
from gpu_gateway.contracts import PlanV2, plan_fingerprint
from gpu_gateway.candidate_receipts import sign_adapter_candidate_receipt
from gpu_control.workloads import (
    AcceleratorKind,
    NetworkRequirement,
    ResultTransport,
    WorkloadRequirements,
)
from gpu_control.capabilities import (
    Availability, CapabilityEvidence, CostBreakdown, CostClassification,
    OverageBehavior,
)

REPOSITORY = "Unjuno/gpu-control"
SOURCE_SHA = "a" * 40


def fake_dedicated_filesystem(monkeypatch, root):
    original_stat = Path.stat

    def stat_with_separate_device(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_dev=2 if path in {root, root / ".gpu-control-probes"} else result.st_dev,
                               st_mode=result.st_mode)

    monkeypatch.setattr("gpu_gateway.artifacts.Path.stat", stat_with_separate_device)


def create_artifact_probe_directory(root):
    probe = root / ".gpu-control-probes"
    probe.mkdir(mode=0o3770)
    probe.chmod(0o3770)


def _seed_bound_gpu_candidate(system, *, image_digest="sha256:" + "f" * 64):
    now = int(system.clock())
    observed = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
    expires_at = now + 120
    expires = datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z")
    workload = Workload(
        provider="modal", image_id="im-fixed", image_digest=image_digest,
        argv=("python", "run.py"), source_revision="fixed",
        source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, gpu="A10G", cpu=4, memory_mib=16384,
        max_runtime_seconds=300, max_cost_usd="0.25",
        operating_system="linux", architecture="x86_64", gpu_count=1,
        minimum_vram_mib=20000, network_requirement="disabled",
        result_transport="object_storage", max_result_bytes=1024 * 1024,
        cancellation_required=True, cleanup_proof_required=True,
        runtime_requirements=("python:3.12", "cuda:12.4"),
        max_queue_wait_seconds=120,
    )
    system.service.workloads["gpu"] = workload
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
    )
    evidence = CapabilityEvidence(
        provider="modal", resource_id="gpu-type-a10g@dc-1",
        availability=Availability.AVAILABLE,
        cost_classification=CostClassification.PAID,
        costs=CostBreakdown(accelerator_usd=Decimal("0.05"), cpu_usd=Decimal("0"),
                            memory_usd=Decimal("0"), storage_usd=Decimal("0"),
                            egress_usd=Decimal("0"), other_usd=Decimal("0")),
        hard_spend_cap_enforced=None, overage_behavior=OverageBehavior.UNKNOWN,
        evidence_reference="test-observation:resource-1",
        evidence_source="test-provider-source", observed_at_utc=observed,
        valid_until_utc=expires, supported_operating_systems=("linux",),
        supported_architectures=("x86_64",), accelerator_kind=AcceleratorKind.GPU,
        gpu_profiles=("a10g",), max_gpu_count=1, max_vram_mib=24576,
        max_cpu_cores=Decimal("8"), max_memory_mib=32768, max_runtime_seconds=3600,
        max_result_bytes=2 * 1024 * 1024,
        network_modes_supported=(NetworkRequirement.DISABLED,),
        result_transports=(ResultTransport.OBJECT_STORAGE,),
        cancellation_supported=True, cleanup_proof_supported=True,
        supported_runtime_requirements=("python:3.12", "cuda:12.4"),
        estimated_queue_wait_seconds=30,
    )
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_id = "api-test-key"
    system.service.settings = replace(
        system.service.settings,
        provider_evidence_public_keys_json=json.dumps({key_id: public_pem.decode("ascii")}),
    )
    _write_bound_gpu_candidate(system, evidence, private_pem, key_id, version=1,
                               observed_at=now, expires_at=expires_at)
    return workload, evidence, private_pem, key_id, expires_at


def _write_bound_gpu_candidate(system, evidence, private_pem, key_id, *, version,
                               observed_at, expires_at):
    envelope = build_signed_observation(
        provider="modal", source="test-provider-source", source_revision="fixture-v1",
        version=version, observed_at=observed_at, expires_at=expires_at,
        payload={"inventory_complete": True, "candidates": [evidence.to_dict()]},
        key_id=key_id, private_key_pem=private_pem,
    )
    assert system.store.write_provider_observation(
        envelope, system.service.settings.provider_evidence_trusted_keys,
        now=int(system.clock()),
    )


def test_canonical_tool_surface_is_eight_tools_and_legacy_remains(system):
    listed = tools(system.owner)
    assert {tool["name"] for tool in listed} == CHATGPT_NAMES
    assert len(CHATGPT_NAMES) == 8
    for tool in listed:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["outputSchema"]["required"] == [
            "schema_version", "status", "human_summary", "machine_state",
            "next_allowed_actions", "blocking_reason"]
        assert tool["description"]
    descriptions = {tool["name"]: tool["description"] for tool in listed}
    assert "untrusted data" in descriptions["experiment_status"]
    assert "untrusted data" in descriptions["experiment_result"]
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


@pytest.mark.parametrize(
    ("version", "supports_structured_output"),
    [("2025-03-26", False), ("2025-06-18", True), ("2025-11-25", True),
     ("2026-07-28", True)],
)
def test_protocol_version_gates_output_schema_and_structured_content(
    system, version, supports_structured_output,
):
    listed, status = dispatch(system.service, system.owner, {
        "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
    }, version=version)
    assert status == 200
    advertised = listed["result"]["tools"]
    assert len(advertised) == 8
    assert all(("outputSchema" in tool) is supports_structured_output for tool in advertised)

    called, status = dispatch(system.service, system.owner, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "experiment_capabilities", "arguments": {}},
    }, version=version)
    assert status == 200
    result = called["result"]
    assert ("structuredContent" in result) is supports_structured_output
    assert result["content"][0]["text"].startswith("{")


def test_capabilities_do_not_describe_demo_as_executable(system):
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "NO_QUEUEABLE_RESOURCE"


@pytest.mark.parametrize(("stale_role", "blocking_reason"), [
    ("worker_seen_at", "WORKER_OFFLINE"),
    ("supervisor_seen_at", "RECOVERY_SUPERVISOR_OFFLINE"),
])
def test_capabilities_stop_cpu_admission_when_worker_or_supervisor_heartbeat_is_stale(
        system, tmp_path, monkeypatch, stale_role, blocking_reason):
    now = int(system.clock())
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01", max_runtime_seconds=30,
        execution_profile="smoke", image_digest="sha256:" + "d" * 64,
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    system.service.registry["local_cpu"] = ProviderRegistration(
        "local_cpu", "local_worker_container", lambda _: True, lambda _: None,
    )
    policy = {"version": "local-cpu-v1", "enabled": True,
              "valid_until": now + 60, "workloads": ["cpu"],
              "max_runtime_seconds": 30, "max_cost_usd": "0.00",
              "allowed_profiles": ["smoke"]}
    policy_path = tmp_path / "local-policy.json"
    policy_path.write_text(json.dumps(policy))
    monkeypatch.setenv("GATEWAY_LOCAL_CPU_POLICY_FILE", str(policy_path))

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    create_artifact_probe_directory(artifact_root)
    system.service.settings = replace(system.settings, artifact_dir=str(artifact_root))
    fake_dedicated_filesystem(monkeypatch, artifact_root)

    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now, supervisor_seen_at=now, active_count=0))

    ready = invoke(system.service, system.owner, "experiment_capabilities", {})
    cpu = next(item for item in ready["machine_state"]["resources"]
               if item["workload"] == "cpu")
    assert ready["status"] == "ok"
    assert cpu["availability"] == "queue_ready"
    assert cpu["submission_available"] is True

    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            {stale_role: now - 15}))

    blocked = invoke(system.service, system.owner, "experiment_capabilities", {})
    cpu = next(item for item in blocked["machine_state"]["resources"]
               if item["workload"] == "cpu")
    assert blocked["status"] == "blocked"
    assert cpu["availability"] == "blocked"
    assert cpu["submission_available"] is False
    assert blocking_reason in cpu["blocking_reasons"]


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
    assert gpu["provider_availability"] == "UNAVAILABLE"
    assert gpu["cost_classification"] == "UNKNOWN"
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
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
    )
    system.service.workloads["gpu"] = Workload(
        provider="modal", image_id="im-fixed", argv=("python", "run.py"),
        source_revision="fixed", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, gpu="A10G", cpu=4, memory_mib=16384,
        max_runtime_seconds=300, max_cost_usd="0.25",
        operating_system="linux", architecture="x86_64", gpu_count=1,
        minimum_vram_mib=20000, network_requirement="disabled",
        result_transport="object_storage", max_result_bytes=1024 * 1024,
        cancellation_required=True, cleanup_proof_required=True,
        runtime_requirements=("python:3.12", "cuda:12.4"),
        max_queue_wait_seconds=120,
    )
    system.service.workloads["cpu-smoke"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, execution_profile="smoke",
        image_digest="sha256:" + "e" * 64,
    )
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    gpu = next(item for item in result["machine_state"]["resources"]
               if item["workload"] == "gpu")
    selection = gpu["candidate_selection"]
    assert selection["status"] == "not_evaluated"
    assert selection["blocking_reason"] == "PROVIDER_EVIDENCE_UNAVAILABLE"
    assert selection["missing_workload_requirements"] == []
    assert selection["provider_evidence"] == "NOT_CONFIGURED"
    assert selection["alternatives"] == [
        {"kind": "local_cpu_workload", "workload": "cpu-smoke"},
        {"kind": "paid_gpu_path", "status": "unavailable_until_live_acceptance"},
    ]
    assert gpu["provider_availability"] == "UNKNOWN"
    assert gpu["cost_classification"] == "UNKNOWN"
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
        runtime_requirements=("python:3.12", "cuda:12.4"),
        max_queue_wait_seconds=120,
    )
    assert selection["workload_fingerprint"] == expected_requirements.fingerprint()
    assert selection["selector_result"]["workload_fingerprint"] == expected_requirements.fingerprint()
    assert selection["selector_result"]["blocking_reason"] == "PROVIDER_EVIDENCE_UNAVAILABLE"


def test_capabilities_feed_only_verified_stored_candidates_into_selector(system):
    now = int(system.clock())
    observed = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
    expires_at = now + 120
    expires = datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z")
    workload = Workload(
        provider="modal", image_id="im-fixed", argv=("python", "run.py"),
        source_revision="fixed", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, gpu="A10G", cpu=4, memory_mib=16384,
        max_runtime_seconds=300, max_cost_usd="0.25",
        operating_system="linux", architecture="x86_64", gpu_count=1,
        minimum_vram_mib=20000, network_requirement="disabled",
        result_transport="object_storage", max_result_bytes=1024 * 1024,
        cancellation_required=True, cleanup_proof_required=True,
        runtime_requirements=("python:3.12", "cuda:12.4"),
        max_queue_wait_seconds=120,
    )
    system.service.workloads["gpu"] = workload
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
    )
    evidence = CapabilityEvidence(
        provider="modal", resource_id="gpu-type-a10g@dc-1",
        availability=Availability.AVAILABLE,
        cost_classification=CostClassification.PAID,
        costs=CostBreakdown(accelerator_usd=Decimal("0.05"), cpu_usd=Decimal("0"),
                            memory_usd=Decimal("0"), storage_usd=Decimal("0"),
                            egress_usd=Decimal("0"), other_usd=Decimal("0")),
        hard_spend_cap_enforced=None, overage_behavior=OverageBehavior.UNKNOWN,
        evidence_reference="test-observation:resource-1",
        evidence_source="test-provider-source", observed_at_utc=observed,
        valid_until_utc=expires, supported_operating_systems=("linux",),
        supported_architectures=("x86_64",), accelerator_kind=AcceleratorKind.GPU,
        gpu_profiles=("a10g",), max_gpu_count=1, max_vram_mib=24576,
        max_cpu_cores=Decimal("8"), max_memory_mib=32768, max_runtime_seconds=3600,
        max_result_bytes=2 * 1024 * 1024,
        network_modes_supported=(NetworkRequirement.DISABLED,),
        result_transports=(ResultTransport.OBJECT_STORAGE,),
        cancellation_supported=True, cleanup_proof_supported=True,
        supported_runtime_requirements=("python:3.12", "cuda:12.4"),
        estimated_queue_wait_seconds=30,
    )
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_id = "api-test-key"
    service_settings = replace(
        system.service.settings,
        provider_evidence_public_keys_json=json.dumps({key_id: public_pem.decode("ascii")}),
    )
    system.service.settings = service_settings
    trusted_keys = service_settings.provider_evidence_trusted_keys
    envelope = build_signed_observation(
        provider="modal", source="test-provider-source", source_revision="fixture-v1",
        version=1, observed_at=now, expires_at=expires_at,
        payload={"inventory_complete": True, "candidates": [evidence.to_dict()]},
        key_id=key_id, private_key_pem=private_pem,
    )
    assert system.store.write_provider_observation(envelope, trusted_keys, now=now)

    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    gpu = next(item for item in result["machine_state"]["resources"]
               if item["workload"] == "gpu")
    selection = gpu["candidate_selection"]
    assert selection["provider_evidence"] == "VERIFIED"
    assert selection["status"] == "candidate_selected"
    assert selection["blocking_reason"] is None
    assert selection["selector_result"]["selected"] == {
        "provider": "modal", "resource_id": evidence.resource_id,
        "evidence_fingerprint": evidence.fingerprint(),
    }
    assert gpu["submission_available"] is False

    system.clock.advance(121)
    expired_result = invoke(system.service, system.owner, "experiment_capabilities", {})
    expired_gpu = next(item for item in expired_result["machine_state"]["resources"]
                       if item["workload"] == "gpu")
    assert expired_gpu["candidate_selection"]["status"] == "not_evaluated"
    assert expired_gpu["candidate_selection"]["blocking_reason"] == "PROVIDER_EVIDENCE_UNAVAILABLE"
    assert expired_gpu["candidate_selection"]["provider_evidence"] == "INVALID_OR_STALE"


def test_gpu_prepare_binds_exact_selected_candidate_and_submit_rejects_changed_evidence(system):
    _, evidence, private_pem, key_id, expires_at = _seed_bound_gpu_candidate(system)
    arguments = {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "bound-gpu-submit-0001",
    }
    prepared = invoke(system.service, system.owner, "experiment_prepare", arguments)
    assert prepared["status"] == "pending"
    assert prepared["blocking_reason"] == "APPROVAL_REQUIRED"
    run_id = prepared["machine_state"]["run_id"]
    run = system.service.get(system.owner, run_id)
    plan = PlanV2.model_validate_json(json.dumps(run["plan"], allow_nan=False))
    assert plan.selection_binding is not None
    assert plan.selection_binding.provider == evidence.provider
    assert plan.selection_binding.resource_id == evidence.resource_id
    assert plan.selection_binding.evidence_fingerprint == evidence.fingerprint()
    assert run["fingerprint"] == plan_fingerprint(plan)

    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, run["fingerprint"])
    changed = replace(evidence, max_cpu_cores=Decimal("9"))
    _write_bound_gpu_candidate(system, changed, private_pem, key_id, version=2,
                               observed_at=int(system.clock()), expires_at=expires_at)
    with pytest.raises(GatewayError, match="exact approved GPU resource") as error:
        system.service.submit(system.owner, run_id)
    assert error.value.code == "provider_evidence_stale"
    assert system.store.read(run_id)["state"] == "approved"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


def test_gpu_prepare_idempotent_replay_returns_existing_run_after_evidence_expires(system):
    _seed_bound_gpu_candidate(system)
    arguments = {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "bound-gpu-replay-0001",
    }
    first = invoke(system.service, system.owner, "experiment_prepare", arguments)
    first_state = first["machine_state"]
    saved = system.service.get(system.owner, first_state["run_id"])
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == first_state["run_id"]).values(
            request_hash=digest({"plan": saved["plan"],
                                 "idempotency_key": arguments["idempotency_key"]}),
        ))

    system.clock.advance(121)
    replay = invoke(system.service, system.owner, "experiment_prepare", arguments)

    assert replay["machine_state"]["run_id"] == first_state["run_id"]
    assert replay["machine_state"]["plan_fingerprint"] == first_state["plan_fingerprint"]
    assert system.store.read(first_state["run_id"])["state"] == "awaiting_approval"
    with pytest.raises(GatewayError, match="different inputs") as error:
        invoke(system.service, system.owner, "experiment_prepare",
               arguments | {"runtime_seconds": 121})
    assert error.value.code == "idempotency_conflict"


def test_worker_rejects_paid_candidate_without_run_specific_permit_before_intent(system, monkeypatch):
    _seed_bound_gpu_candidate(system)
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
        supports_candidate_binding=True, supports_paid_execution=True,
    )
    prepared = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "paid-gpu-worker-permit-001",
    })
    run_id = prepared["machine_state"]["run_id"]
    run = system.service.get(system.owner, run_id)
    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, run["fingerprint"])
    assert system.service.submit(system.owner, run_id)["state"] == "queued"
    monkeypatch.setattr("gpu_gateway.worker.load_workloads", lambda: system.service.workloads)

    class Backend:
        started = 0

        def start_candidate_bound(self, _job):
            self.started += 1
            raise AssertionError("provider must not be called without a paid permit")

        def validate_paid_authorization(self, _job):
            return False

        def validate_candidate_observation(self, _job, _observation):
            return True

        def reconcile(self, _job):
            return None

        def cancel(self, _handle):
            raise AssertionError("no provider handle should exist")

        def capture(self, _handle):
            raise AssertionError("no provider handle should exist")

        def cleanup(self, _handle):
            raise AssertionError("no provider handle should exist")

        def is_clean(self, _handle):
            return False

    backend = Backend()
    worker = Worker(system.store, system.service.settings, {"modal": backend},
                    system.clock, registry=system.service.registry)
    assert worker.tick() is True
    saved = system.store.read(run_id)
    assert saved["state"] == "failed"
    assert saved["error"] == "paid_authorization_invalid"
    assert saved["submission_intent"] is None
    assert backend.started == 0
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


def test_candidate_bound_plan_cannot_queue_through_unaccepted_backend(system):
    _seed_bound_gpu_candidate(system)
    prepared = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "bound-gpu-gate-0001",
    })
    run_id = prepared["machine_state"]["run_id"]
    run = system.service.get(system.owner, run_id)
    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, run["fingerprint"])
    with pytest.raises(GatewayError, match="candidate-bound execution acceptance") as error:
        system.service.submit(system.owner, run_id)
    assert error.value.code == "gpu_backend_unavailable"
    assert system.store.read(run_id)["state"] == "approved"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


def test_paid_candidate_plan_requires_separate_registry_authorization(system):
    _seed_bound_gpu_candidate(system)
    prepared = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "paid-gpu-separate-gate-001",
    })
    run_id = prepared["machine_state"]["run_id"]
    run = system.service.get(system.owner, run_id)
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
        supports_candidate_binding=True,
    )
    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, run["fingerprint"])
    with pytest.raises(GatewayError) as error:
        system.service.submit(system.owner, run_id)
    assert error.value.code == "paid_authorization_required"
    assert system.store.read(run_id)["state"] == "approved"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


def test_worker_rechecks_bound_gpu_evidence_immediately_before_backend_start(system, monkeypatch):
    _, evidence, private_pem, key_id, expires_at = _seed_bound_gpu_candidate(system)
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "modal_sandbox", lambda _: True, lambda _: None,
        supports_candidate_binding=True, supports_paid_execution=True,
    )
    prepared = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "bound-gpu-worker-0001",
    })
    run_id = prepared["machine_state"]["run_id"]
    run = system.service.get(system.owner, run_id)
    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, run["fingerprint"])
    assert system.service.submit(system.owner, run_id)["state"] == "queued"

    changed = replace(evidence, max_cpu_cores=Decimal("9"))
    _write_bound_gpu_candidate(system, changed, private_pem, key_id, version=2,
                               observed_at=int(system.clock()), expires_at=expires_at)
    monkeypatch.setattr("gpu_gateway.worker.load_workloads",
                        lambda: system.service.workloads)

    class Backend:
        started = 0

        def start(self, _job):
            self.started += 1
            return {"id": "must-not-start"}

        def inspect(self, _handle):
            raise AssertionError("not expected")

        def cancel(self, _handle):
            raise AssertionError("not expected")

        def reconcile(self, _job):
            raise AssertionError("not expected")

    backend = Backend()
    worker = Worker(system.store, system.service.settings, {"modal": backend},
                    system.clock, registry=system.service.registry)
    assert worker.tick() is True
    saved = system.store.read(run_id)
    assert backend.started == 0
    assert saved["state"] == "expired"
    assert saved["error"] == "provider_evidence_stale"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(control.c.active_count)).scalar_one() == 0


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
    assert cpu["provider_availability"] == "UNAVAILABLE"
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
    create_artifact_probe_directory(root)
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
    create_artifact_probe_directory(root)
    fake_dedicated_filesystem(monkeypatch, root)

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
    assert cpu["provider_availability"] == "UNAVAILABLE"
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
    create_artifact_probe_directory(artifact_root)
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
    create_artifact_probe_directory(artifact_root)
    fake_dedicated_filesystem(monkeypatch, artifact_root)
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


def test_owner_isolation_for_status_result_list_and_cancel(system):
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="owner-isolation-ops-0001"))
    other = replace(system.owner, owner="different-owner")

    for tool in ("experiment_status", "experiment_result", "experiment_cancel"):
        with pytest.raises(GatewayError) as error:
            invoke(system.service, other, tool, {"run_id": prepared["id"]})
        assert error.value.status == 404

    listing = invoke(system.service, other, "experiment_list", {})
    assert listing["experiments"] == []
    assert listing["machine_state"]["count"] == 0


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


def test_status_returns_only_bounded_tail_of_owned_result_logs(system):
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="bounded-status-logs-0001"))
    raw_logs = "x" * 5000
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared["id"]).values(
            state="succeeded", result={"logs": raw_logs}))

    status = invoke(system.service, system.owner, "experiment_status", {"run_id": prepared["id"]})
    assert status["machine_state"]["logs"] == raw_logs[-4096:]
    assert status["machine_state"]["logs_truncated"] is True
    other = replace(system.owner, owner="other")
    with pytest.raises(GatewayError) as error:
        invoke(system.service, other, "experiment_status", {"run_id": prepared["id"]})
    assert error.value.status == 404


def test_omitted_oversized_result_is_not_reported_as_retrieved(system):
    prepared = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="oversized-result-read-0001"))
    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == prepared["id"]).values(
            state="succeeded",
            result={"result_omitted": True, "reason": "result_size_limit"},
        ))

    status = invoke(system.service, system.owner, "experiment_status", {"run_id": prepared["id"]})
    assert status["status"] == "ok"
    assert status["machine_state"]["state"] == "succeeded"
    assert status["machine_state"]["result_omitted"] is True
    assert status["machine_state"]["error_code"] == "result_size_limit"
    assert "サイズ上限" in status["human_summary"]

    read = invoke(system.service, system.owner, "experiment_result", {"run_id": prepared["id"]})
    assert read["status"] == "blocked"
    assert read["blocking_reason"] == "RESULT_OMITTED"
    assert read["machine_state"]["state"] == "succeeded"
    assert read["machine_state"]["result"] is None
    assert read["machine_state"]["result_omitted"] is True


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
    assert result["blocking_reason"] == "WORKLOAD_REQUIREMENTS_INCOMPLETE"
    assert result["machine_state"]["requires_gpu"] is True
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


def test_free_candidate_backend_success_requires_bound_receipt_and_confirmed_cleanup(system, monkeypatch):
    workload, evidence, provider_key, provider_key_id, expires_at = _seed_bound_gpu_candidate(system)
    free_evidence = replace(
        evidence,
        cost_classification=CostClassification.FREE,
        costs=CostBreakdown(
            accelerator_usd=Decimal("0"), cpu_usd=Decimal("0"),
            memory_usd=Decimal("0"), storage_usd=Decimal("0"),
            egress_usd=Decimal("0"), other_usd=Decimal("0"),
        ),
        hard_spend_cap_enforced=True,
        overage_behavior=OverageBehavior.NOT_APPLICABLE,
    )
    _write_bound_gpu_candidate(
        system, free_evidence, provider_key, provider_key_id,
        version=2, observed_at=int(system.clock()), expires_at=expires_at,
    )
    adapter_key = Ed25519PrivateKey.generate()
    adapter_public = adapter_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    system.service.settings = replace(
        system.service.settings,
        candidate_receipt_public_keys_json=json.dumps({
            "adapter:modal:gateway-v1": adapter_public.decode("ascii"),
        }),
    )
    prepared = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "parameters": {}, "runtime_seconds": 120, "max_cost_usd": "0.10",
        "requires_gpu": True, "idempotency_key": "free-gpu-bound-success-001",
    })
    run_id = prepared["machine_state"]["run_id"]
    plan = PlanV2.model_validate_json(json.dumps(
        system.service.get(system.owner, run_id)["plan"], allow_nan=False,
    ))
    assert plan.cost_evidence.classification == "FREE"
    assert plan.cost_evidence.additional_cost_usd == Decimal("0")

    class FakeCandidateBackend:
        def __init__(self):
            self.created = 0
            self.captured = 0
            self.cleaned = False
            self.handle = None
            self.result = {
                "schema_version": 2, "run_id": run_id,
                "source_sha": plan.source_sha,
                "plan_fingerprint": plan_fingerprint(plan),
                "provider": plan.provider, "image_digest": plan.image_digest,
                "simulation": False, "gpu_used": True,
                "device": "NVIDIA A10", "exit_code": 0,
                "started_at": int(system.clock()),
                "finished_at": int(system.clock()) + 1,
                "runtime_seconds": 1.0, "metrics": {"iterations": 4},
                "checks": [], "checksum": "f" * 64, "artifacts": [],
                "known_cost_usd": "0", "cost_classification": "FREE",
                "cleanup_state": "pending",
            }

        def start_candidate_bound(self, job):
            self.created += 1
            saved_plan = PlanV2.model_validate_json(json.dumps(job["plan"], allow_nan=False))
            assert saved_plan.selection_binding.resource_id == free_evidence.resource_id
            self.handle = {
                "provider_execution_id": "fake-pod-1",
                "resource_id": saved_plan.selection_binding.resource_id,
            }
            return self.handle

        def validate_candidate_observation(self, job, observation):
            receipt = observation.candidate_receipt
            return bool(
                self.handle is not None and
                self.handle["resource_id"] == job["plan"]["selection_binding"]["resource_id"] and
                isinstance(receipt, dict) and
                receipt.get("payload", {}).get("provider_execution_id") ==
                self.handle["provider_execution_id"] and
                receipt.get("payload", {}).get("resource_id") == self.handle["resource_id"]
            )

        def capture(self, handle):
            self.captured += 1
            assert handle == self.handle
            now = int(system.clock())
            receipt = sign_adapter_candidate_receipt(
                private_key=adapter_key, key_id="adapter:modal:gateway-v1",
                issued_at=now, expires_at=now + 60, now=now,
                plan=plan, fingerprint=plan_fingerprint(plan), run_id=run_id,
                result=self.result, provider_execution_id=handle["provider_execution_id"],
                device_id="GPU-test-uuid", evidence_source="modal.sandbox.get",
                provider_object_projection={
                    "id": handle["provider_execution_id"],
                    "resource_id": handle["resource_id"],
                    "state": "EXITED", "device_id": "GPU-test-uuid",
                },
            )
            return Observation("succeeded", self.result, candidate_receipt=receipt)

        def cancel(self, _handle):
            raise AssertionError("successful candidate run must not be cancelled")

        def reconcile(self, _job):
            raise AssertionError("persisted candidate handle must be reused")

        def cleanup(self, handle):
            assert handle == self.handle
            self.cleaned = True

        def is_clean(self, _handle):
            return self.cleaned

    backend = FakeCandidateBackend()
    system.service.registry["modal"] = ProviderRegistration(
        "modal", "fake_candidate_backend", lambda _settings: True,
        lambda _settings: backend, supports_candidate_binding=True,
    )
    browser = Principal(system.owner.owner, system.owner.scopes, browser=True)
    system.service.approve(browser, run_id, prepared["machine_state"]["plan_fingerprint"])
    assert system.service.submit(system.owner, run_id)["state"] == "queued"
    monkeypatch.setattr("gpu_gateway.worker.load_workloads", lambda: system.service.workloads)
    assert Worker(system.store, system.service.settings, {"modal": backend},
                  system.clock, registry=system.service.registry).tick()
    system.clock.advance(2)
    assert Worker(system.store, system.service.settings, {"modal": backend},
                  system.clock, registry=system.service.registry).tick()

    final = system.service.get(system.owner, run_id)
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert final["state"] == "succeeded"
    assert final["result"]["cleanup_state"] == "complete"
    assert final["result"]["gpu_used"] is True
    assert final["result"]["checks"] == ["candidate_resource_verified", "device_identity_verified"]
    assert final["result"]["candidate_receipt"]["payload"]["resource_id"] == free_evidence.resource_id
    assert backend.created == backend.captured == 1
    assert backend.cleaned is True
    assert active == 0


@pytest.mark.parametrize("recover_after_unconfirmed_cleanup", [False, True])
def test_worker_cleanup_releases_provider_lease_with_terminal_commit(
        system, recover_after_unconfirmed_cleanup):
    run_id = "e" * 32
    owner = system.owner.owner
    fingerprint = "a" * 64
    worker_token = "1" * 32
    scope = "b" * 64
    now = int(system.clock())
    challenge = {"template_id": "template-a", "name": "gpu-control-" + run_id}
    plan = {"schema_version": 1, "provider": "runpod", "runtime_seconds": 600,
            "workload_manifest": {"quote_expires_at": now + 600,
                                  "quoted_usd_per_hour": "0"}}
    with system.store.transaction() as connection:
        connection.execute(runs.insert().values(
            id=run_id, owner=owner, idempotency_key="lease-cleanup-worker-test",
            request_hash="c" * 64, fingerprint=fingerprint, plan=plan,
            state="submitting", created_at=now, started_at=now,
            approved_until=now + 600, approval_id="approval-test",
            handle=None, result=None, error="", lease_until=now + 120,
            lease_token=worker_token, cancel_requested=False, slot_reserved=True,
            record_version=1, cleanup_state="unknown", finished_at=None,
            result_manifest=None, admission=None, attempt=0, submission_intent=None,
            last_observed_at=None,
        ))
        connection.execute(control.update().where(control.c.id == 1).values(active_count=1))
    lease = system.store.reserve_provider_account_lease_with_submission_intent(
        provider="runpod", account_scope=scope, run_id=run_id, owner=owner,
        plan_fingerprint=fingerprint, core_plan_fingerprint="c" * 64,
        authorization_id="paid-auth-test", run_lease_token=worker_token,
        attempt=1, request_challenge=challenge, now=now,
    )
    assert lease is not None
    assert system.store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner=owner, plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=worker_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-test",
        expected_state="reserved", new_state="submitting", now=now,
    )
    assert system.store.transition_provider_account_lease_for_run(
        account_scope=scope, run_id=run_id, owner=owner, plan_fingerprint=fingerprint,
        lease_token=lease.lease_token, run_lease_token=worker_token,
        core_plan_fingerprint="c" * 64, authorization_id="paid-auth-test",
        expected_state="submitting", new_state="active", provider_job_id="pod-worker-test", now=now,
    )
    intent = system.store.read(run_id)["submission_intent"] | {"phase": "handle_persisted"}
    with system.store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            state="running", handle={"pod_id": "pod-worker-test"},
            submission_intent=intent, lease_until=0,
        ))

    class FakeRunPodLifecycle:
        cleaned = False
        cleanup_calls = 0
        clean_checks = 0

        def provider_job_id(self, handle):
            return handle["pod_id"]

        def capture(self, _handle):
            return Observation("succeeded", {"cleanup_state": "pending", "checks": []})

        def cleanup(self, handle):
            assert handle["pod_id"] == "pod-worker-test"
            self.cleanup_calls += 1
            self.cleaned = True

        def is_clean(self, handle):
            self.clean_checks += 1
            return (self.cleaned and handle["pod_id"] == "pod-worker-test" and
                    (not recover_after_unconfirmed_cleanup or self.clean_checks > 1))

        def cancel(self, _handle):
            raise AssertionError("run did not request cancellation")

        def reconcile(self, _job):
            raise AssertionError("persisted provider handle must be reused")

        def reconcile_candidate_bound_with_account_lease(self, _job, _challenge):
            raise AssertionError("persisted provider handle must be reused")

    backend = FakeRunPodLifecycle()
    worker = Worker(system.store, system.service.settings, {"runpod": backend}, system.clock)
    assert worker.tick() is True
    if recover_after_unconfirmed_cleanup:
        pending = system.store.read(run_id)
        assert pending["state"] == "running"
        assert pending["cleanup_state"] == "pending"
        assert system.clock.advance(11) is None
        assert worker.tick() is True

    saved = system.store.read(run_id)
    assert saved["state"] == "succeeded"
    assert saved["cleanup_state"] == "complete"
    assert saved["result"]["cleanup_state"] == "complete"
    with system.store.engine.connect() as connection:
        lease_state = connection.execute(select(provider_account_leases.c.state)).scalar_one()
        active_count = connection.execute(select(control.c.active_count)).scalar_one()
    assert lease_state == "released"
    assert active_count == 0
    assert backend.cleanup_calls == (2 if recover_after_unconfirmed_cleanup else 1)


def test_worker_runpod_candidate_reserves_hmac_lease_and_uses_persisted_challenge(system):
    run_id = "d" * 32
    owner = system.owner.owner
    now = int(system.clock())
    challenge = {"template_id": "template-test", "name": "gpu-control-" + run_id}
    plan = {
        "schema_version": 1,
        "provider": "runpod",
        "runtime_seconds": 120,
        "max_cost_usd": "0.10",
        "selection_binding": {"provider": "runpod", "resource_id": "gpu-resource-1"},
        "cost_evidence": {"classification": "FREE", "additional_cost_usd": "0"},
        "workload_manifest": {"quote_expires_at": now + 600,
                              "quoted_usd_per_hour": "0"},
    }
    fingerprint = digest(plan)
    with system.store.transaction() as connection:
        connection.execute(runs.insert().values(
            id=run_id, owner=owner, idempotency_key="runpod-lease-worker-test",
            request_hash="c" * 64, fingerprint=fingerprint, plan=plan,
            state="queued", created_at=now, started_at=0,
            approved_until=now + 600, approval_id="approval-test",
            handle=None, result=None, error="", lease_until=0, lease_token="",
            cancel_requested=False, slot_reserved=True, record_version=1,
            cleanup_state="unknown", finished_at=None, result_manifest=None,
            admission=None, attempt=0, submission_intent=None, last_observed_at=None,
        ))
        connection.execute(control.update().where(control.c.id == 1).values(active_count=1))
    hmac_key = b"account-scope-hmac-key-for-worker-test"
    system.service.settings = replace(
        system.service.settings, runpod_api_key="worker-runpod-credential",
        runpod_account_scope_id="runpod-primary",
        provider_account_scope_hmac_key_b64=base64.b64encode(hmac_key).decode("ascii"),
    )

    class FakeRunPodCandidateBackend:
        passed_challenge = None
        reconciled_challenge = None
        create_calls = 0

        def prepare_provider_account_lease(self, _job):
            return ProviderAccountLeaseRequest("c" * 64, "allocation-decision-1", challenge)

        def start_candidate_bound_with_account_lease(self, _job, request_challenge):
            self.create_calls += 1
            self.passed_challenge = request_challenge
            return {"pod_id": "fake-runpod-pod-1"}

        def reconcile_candidate_bound_with_account_lease(self, _job, request_challenge):
            self.reconciled_challenge = request_challenge
            return {"pod_id": "fake-runpod-pod-1"}

        def provider_job_id(self, handle):
            return handle["pod_id"]

        def start_candidate_bound(self, _job):
            raise AssertionError("RunPod create must receive the persisted challenge")

        def validate_candidate_observation(self, _job, _observation): return True
        def capture(self, _handle): return Observation("running")
        def cancel(self, _handle): pass
        def reconcile(self, _job): return None
        def cleanup(self, _handle): pass
        def is_clean(self, _handle): return False

    backend = FakeRunPodCandidateBackend()
    registration = ProviderRegistration(
        "runpod", "fake_runpod_candidate", lambda _settings: True,
        lambda _settings: backend, supports_candidate_binding=True,
    )
    worker = Worker(system.store, system.service.settings, {"runpod": backend},
                    system.clock, registry={"runpod": registration})
    assert worker.tick() is True

    saved = system.store.read(run_id)
    expected_scope = derive_provider_account_scope(
        "runpod", "runpod-primary", hmac_key)
    assert saved["state"] == "running"
    assert backend.passed_challenge == challenge
    assert saved["handle"] == {"pod_id": "fake-runpod-pod-1"}
    assert saved["submission_intent"]["account_scope"] == expected_scope
    assert saved["submission_intent"]["authorization_id"] == "allocation-decision-1"
    assert "worker-runpod-credential" not in json.dumps(saved["submission_intent"])
    assert backend.passed_challenge == challenge
    with system.store.engine.connect() as connection:
        lease = connection.execute(select(provider_account_leases)).mappings().one()
    assert lease["state"] == "active"
    assert lease["provider_job_id"] == "fake-runpod-pod-1"
    assert lease["request_challenge"] == challenge

    # Simulate a worker crash after the provider lease became active but before
    # the handle was durably visible to the successor.
    with system.store.transaction() as connection:
        connection.execute(runs.update().where(runs.c.id == run_id).values(
            state="submit_unknown", handle=None, lease_until=0,
        ))
    assert worker.tick() is True
    recovered = system.store.read(run_id)
    assert recovered["state"] == "running"
    assert recovered["handle"] == {"pod_id": "fake-runpod-pod-1"}
    assert backend.reconciled_challenge == challenge
    assert backend.create_calls == 1


def test_worker_runpod_paid_candidate_stays_blocked_without_persisted_signed_authorization(system):
    run_id = "f" * 32
    owner = system.owner.owner
    now = int(system.clock())
    plan = {
        "schema_version": 1, "provider": "runpod", "runtime_seconds": 120,
        "max_cost_usd": "0.10",
        "selection_binding": {"provider": "runpod", "resource_id": "gpu-resource-1"},
        "cost_evidence": {"classification": "PAID", "additional_cost_usd": "0.05"},
        "workload_manifest": {"quote_expires_at": now + 600,
                              "quoted_usd_per_hour": "0.05"},
    }
    fingerprint = digest(plan)
    with system.store.transaction() as connection:
        connection.execute(runs.insert().values(
            id=run_id, owner=owner, idempotency_key="runpod-paid-no-persisted-auth-test",
            request_hash="d" * 64, fingerprint=fingerprint, plan=plan,
            state="queued", created_at=now, started_at=0,
            approved_until=now + 600, approval_id="approval-test",
            handle=None, result=None, error="", lease_until=0, lease_token="",
            cancel_requested=False, slot_reserved=True, record_version=1,
            cleanup_state="unknown", finished_at=None, result_manifest=None,
            admission=None, attempt=0, submission_intent=None, last_observed_at=None,
        ))
        connection.execute(control.update().where(control.c.id == 1).values(active_count=1))

    class FakeRunPodBackend:
        started = 0

        def prepare_provider_account_lease(self, _job):
            return ProviderAccountLeaseRequest("c" * 64, "paid-auth-test", {
                "template_id": "template-test", "name": "gpu-control-" + run_id,
            })

        def start_candidate_bound_with_account_lease(self, _job, _challenge):
            self.started += 1
            return {"pod_id": "must-not-create"}

        def reconcile_candidate_bound_with_account_lease(self, _job, _challenge): return None
        def provider_job_id(self, handle): return handle["pod_id"]
        def validate_paid_authorization(self, _job): return True
        def start_candidate_bound(self, _job): raise AssertionError("legacy create path is forbidden")
        def validate_candidate_observation(self, _job, _observation): return True
        def capture(self, _handle): return Observation("running")
        def cancel(self, _handle): pass
        def reconcile(self, _job): return None
        def cleanup(self, _handle): pass
        def is_clean(self, _handle): return False

    backend = FakeRunPodBackend()
    registration = ProviderRegistration(
        "runpod", "fake_runpod_candidate", lambda _settings: True,
        lambda _settings: backend, supports_candidate_binding=True,
        supports_paid_execution=True,
    )
    worker = Worker(system.store, system.service.settings, {"runpod": backend},
                    system.clock, registry={"runpod": registration})
    assert worker.tick() is True

    saved = system.store.read(run_id)
    assert saved["state"] == "failed"
    assert saved["error"] == "runpod_authorization_persistence_unavailable"
    assert saved["submission_intent"] is None
    assert backend.started == 0
    with system.store.engine.connect() as connection:
        assert connection.execute(select(provider_account_leases.c.run_id)).first() is None
