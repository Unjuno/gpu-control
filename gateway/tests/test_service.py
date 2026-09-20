from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from gpu_gateway.backends import DemoBackend
from gpu_gateway.config import Settings, Workload
from gpu_gateway.service import GatewayError, Prepare, Principal
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker


def prepare(s, key="test-request-1"):
    return s.service.prepare(s.owner, Prepare(workload="demo", idempotency_key=key))


def queue(s, key="test-request-1"):
    run = prepare(s, key)
    s.service.approve(s.browser, run["id"], run["fingerprint"])
    return s.service.submit(s.owner, run["id"])


def slots(s):
    with s.store.engine.connect() as c:
        return c.execute(select(control.c.active_count)).scalar_one()


def test_prepare_deduplicates_and_rejects_different_inputs(system):
    a = prepare(system); b = prepare(system)
    assert a["id"] == b["id"]
    with pytest.raises(GatewayError, match="new idempotency key"):
        system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="test-request-1", runtime_seconds=10))


def test_parallel_prepare_is_one_row(system):
    with ThreadPoolExecutor(max_workers=10) as pool:
        ids = list(pool.map(lambda _: prepare(system)["id"], range(20)))
    assert len(set(ids)) == 1


def test_explicit_browser_approval_and_fingerprint(system):
    run = prepare(system)
    with pytest.raises(GatewayError, match="approval"):
        system.service.submit(system.owner, run["id"])
    with pytest.raises(GatewayError, match="Web UI"):
        system.service.approve(system.owner, run["id"], run["fingerprint"])
    with pytest.raises(GatewayError, match="exact plan"):
        system.service.approve(system.browser, run["id"], "wrong")
    system.service.approve(system.browser, run["id"], run["fingerprint"])
    system.clock.advance(901)
    with pytest.raises(GatewayError, match="approval"):
        system.service.submit(system.owner, run["id"])


def test_ownership_and_scopes(system):
    run = prepare(system)
    other = replace(system.owner, owner="someone-else")
    for operation in (system.service.get, system.service.submit, system.service.cancel):
        with pytest.raises(GatewayError) as e:
            operation(other, run["id"])
        assert e.value.status == 404
    with pytest.raises(GatewayError) as e:
        system.service.prepare(replace(system.owner, scopes=frozenset({"experiments:read"})), Prepare(workload="demo", idempotency_key="abcdefghi"))
    assert e.value.status == 403


def test_parallel_submit_consumes_one_slot(system):
    run = prepare(system)
    system.service.approve(system.browser, run["id"], run["fingerprint"])
    with ThreadPoolExecutor(max_workers=10) as pool:
        ids = list(pool.map(lambda _: system.service.submit(system.owner, run["id"])["id"], range(20)))
    assert len(set(ids)) == 1
    assert slots(system) == 1
    other = prepare(system, "another-request")
    system.service.approve(system.browser, other["id"], other["fingerprint"])
    with pytest.raises(GatewayError, match="in flight"):
        system.service.submit(system.owner, other["id"])
    assert slots(system) == 1


def test_demo_worker_end_to_end_and_restart(system):
    run = queue(system)
    w = Worker(system.store, system.settings, {"demo": DemoBackend()}, system.clock)
    assert w.tick()
    assert system.store.read(run["id"])["state"] == "running"
    # Reconstruct the worker to prove state is not kept only in its Python process.
    system.clock.advance(2)
    assert Worker(system.store, system.settings, {"demo": DemoBackend()}, system.clock).tick()
    final = system.service.get(system.owner, run["id"])
    assert final["state"] == "succeeded"
    assert final["result"]["simulation"] is True
    assert final["result"]["gpu_used"] is False
    assert slots(system) == 0
    assert not w.tick()


def test_expired_queued_approval_never_starts(system):
    run = queue(system); system.clock.advance(901)
    class NeverStart(DemoBackend):
        def start(self, run): raise AssertionError("Should not start")
    Worker(system.store, system.settings, {"demo": NeverStart()}, system.clock).tick()
    assert system.store.read(run["id"])["state"] == "expired"
    assert slots(system) == 0


def test_cancel_before_start_is_idempotent(system):
    run = queue(system)
    for _ in range(3):
        assert system.service.cancel(system.owner, run["id"])["state"] == "cancelled"
    assert slots(system) == 0


def test_submission_timeout_never_blindly_retries(system):
    run = queue(system)
    class Ambiguous(DemoBackend):
        calls = 0
        def start(self, run):
            self.calls += 1
            raise TimeoutError("provider accepted but reply was lost")
        def reconcile(self, run): return None
    backend = Ambiguous(); w = Worker(system.store, system.settings, {"demo": backend}, system.clock)
    for _ in range(4):
        w.tick(); system.clock.advance(31)
    assert backend.calls == 1
    assert system.store.read(run["id"])["state"] == "submit_unknown"
    assert slots(system) == 1


def test_reconciliation_recovers_handle_without_resubmission(system):
    run = queue(system)
    class Ambiguous(DemoBackend):
        calls = 0
        def start(self, run): self.calls += 1; raise TimeoutError()
        def reconcile(self, run): return {"id": run["id"], "parameters": {}}
    backend = Ambiguous(); w = Worker(system.store, system.settings, {"demo": backend}, system.clock)
    w.tick(); system.clock.advance(6); w.tick()
    assert backend.calls == 1
    assert system.store.read(run["id"])["state"] == "succeeded"
    assert slots(system) == 0


def test_cleanup_failure_remains_visible_and_does_not_free_slot(system):
    run = queue(system)
    class BadCancel(DemoBackend):
        def cancel(self, handle): raise RuntimeError("secret MUST NOT enter user-visible error")
    backend = BadCancel(); w = Worker(system.store, system.settings, {"demo": backend}, system.clock)
    w.tick(); system.service.cancel(system.owner, run["id"]); system.clock.advance(2); w.tick()
    final = system.service.get(system.owner, run["id"])
    assert final["state"] == "running"
    assert final["error"] == "provider_observation_or_cleanup_failed"
    assert slots(system) == 1


def test_tampered_plan_does_not_start(system):
    run = queue(system)
    with system.store.transaction() as c:
        data = dict(system.store.read(run["id"])["plan"])
        data["runtime_seconds"] = 3600
        c.execute(update(runs).where(runs.c.id == run["id"]).values(plan=data))
    Worker(system.store, system.settings, {"demo": DemoBackend()}, system.clock).tick()
    assert system.store.read(run["id"])["error"] == "plan_integrity_failed"


@pytest.mark.parametrize("kwargs", [{"runtime_seconds": 601}, {"max_cost_usd": "0"}, {"max_cost_usd": "2"}, {"parameters": {"command": "unexpected"}}])
def test_workload_limits(system, kwargs):
    with pytest.raises(GatewayError):
        system.service.prepare(system.owner, Prepare(workload="demo", idempotency_key="limit-check", **kwargs))


def test_current_all_in_quote_required(system):
    system.service.workloads["gpu"] = Workload(provider="modal", image_id="im-fixed", argv=("python", "experiment.py"), source_revision="fixed-revision")
    with pytest.raises(GatewayError, match="current all-in"):
        system.service.prepare(system.owner, Prepare(workload="gpu", idempotency_key="quote-check"))


def test_hosted_sqlite_and_unsecured_origin_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(hosted=True).validate()
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(hosted=True, public_url="https://gateway.example").validate()
    with pytest.raises(ValueError):
        Settings(public_url="http://example.com").validate()
