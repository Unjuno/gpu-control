from dataclasses import replace

import pytest
from sqlalchemy import select

from gpu_gateway.config import Workload
from gpu_gateway.experiment_api import invoke
from gpu_gateway.protocol import CHATGPT_NAMES, dispatch, tools
from gpu_gateway.service import GatewayError, Prepare, Principal
from gpu_gateway.store import runs

REPOSITORY = "Unjuno/gpu-control"
SOURCE_SHA = "a" * 40


def test_canonical_tool_surface_is_seven_tools_and_legacy_remains(system):
    listed = tools(system.owner)
    assert {tool["name"] for tool in listed} == CHATGPT_NAMES
    assert len(CHATGPT_NAMES) == 7
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
    assert {"experiment_capabilities", "experiment_status", "experiment_result", "experiment_list"} <= names
    assert "experiment_prepare" not in names
    assert "experiment_cancel" not in names


def test_capabilities_do_not_describe_demo_as_executable(system):
    result = invoke(system.service, system.owner, "experiment_capabilities", {})
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "NO_EXECUTABLE_WORKLOAD"


def test_prepare_blocks_unregistered_or_unsafe_backend_without_creating_run(system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    args = {"repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "cpu",
            "parameters": {}, "max_cost_usd": "0.00", "requires_gpu": False,
            "idempotency_key": "cpu-plan-0001"}
    result = invoke(system.service, system.owner, "experiment_prepare", args)
    assert result["blocking_reason"] == "LOCAL_CPU_ADMISSION_UNAVAILABLE"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(runs.c.id)).first() is None


def test_prepare_requires_exact_operator_source_and_device_policy(system):
    system.service.workloads["cpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=False, max_cost_usd="0.01",
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


def test_gpu_required_workload_cannot_fall_back_to_cpu(system):
    system.service.workloads["gpu"] = Workload(
        provider="local_cpu", source_repository=REPOSITORY, source_sha=SOURCE_SHA,
        requires_gpu=True, max_cost_usd="0.01",
        parameter_schema={"type": "object", "properties": {}, "additionalProperties": False},
    )
    result = invoke(system.service, system.owner, "experiment_prepare", {
        "repository": REPOSITORY, "commit": SOURCE_SHA, "workload": "gpu",
        "max_cost_usd": "0.00", "requires_gpu": True, "idempotency_key": "gpu-plan-0001",
    })
    assert result["blocking_reason"] == "GPU_BACKEND_UNAVAILABLE"
    assert result["machine_state"]["provider"] == "local_cpu"
    with system.store.engine.connect() as connection:
        assert connection.execute(select(runs.c.id)).first() is None


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
    assert result["blocking_reason"] == "NO_EXECUTABLE_WORKLOAD"
