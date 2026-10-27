from sqlalchemy import select, update

from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker
from gpu_gateway.backends import ArtifactPayload, Observation
from gpu_gateway.service import Prepare

from test_local_admission import plan


def test_missing_terminal_result_is_failed_and_cleaned_before_slot_release(system):
    candidate = plan()
    now = int(system.clock())
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="missing-result-cleanup-0001"))
    fingerprint = plan_fingerprint(candidate)
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint,
            state="running", handle={"container_id": "c" * 64}, lease_until=0,
            started_at=now - 2, slot_reserved=True, record_version=2,
            cleanup_state="pending"))

    class MissingResultBackend:
        cleanup_calls = 0
        capture_calls = 0

        def start(self, _job):
            raise AssertionError("recovery must not start another container")

        def reconcile(self, _job):
            raise AssertionError("persisted handle must be reused")

        def cancel(self, _handle):
            pass

        def capture(self, _handle):
            self.capture_calls += 1
            payload = ArtifactPayload("unbound.json", b"{}", "application/json")
            return Observation("succeeded", None, (payload,))

        def cleanup(self, _handle):
            self.cleanup_calls += 1
            if self.cleanup_calls == 1:
                raise RuntimeError("injected cleanup failure")

        def is_clean(self, _handle):
            return self.cleanup_calls > 1

    backend = MissingResultBackend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert worker.tick()
    pending = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert pending["state"] == "running"
    assert pending["cleanup_state"] == "pending"
    assert pending["result"]["failure_code"] == "missing_backend_result"
    assert pending["result"]["artifacts"] == []
    assert active == 1

    system.clock.advance(11)
    assert Worker(system.store, system.settings, {"local_cpu": backend}, system.clock).tick()
    final = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert final["state"] == "failed"
    assert final["cleanup_state"] == "complete"
    assert final["result"]["failure_code"] == "missing_backend_result"
    assert final["result"]["artifacts"] == []
    assert backend.capture_calls == 1
    assert active == 0


def test_missing_terminal_result_cannot_be_reported_as_success(system):
    candidate = plan()
    now = int(system.clock())
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="missing-result-no-cleanup-backend"))
    fingerprint = plan_fingerprint(candidate)
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint,
            state="running", handle={"resource_id": "released-by-provider"},
            lease_until=0, started_at=now - 2, slot_reserved=True, record_version=2,
            cleanup_state="not_required"))

    class MissingResultBackend:
        def start(self, _job):
            raise AssertionError("recovery must not start another resource")

        def reconcile(self, _job):
            raise AssertionError("persisted handle must be reused")

        def cancel(self, _handle):
            pass

        def inspect(self, _handle):
            return Observation("succeeded")

    assert Worker(system.store, system.settings, {"local_cpu": MissingResultBackend()},
                  system.clock).tick()
    final = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert final["state"] == "failed"
    assert final["result"]["failure_code"] == "missing_backend_result"
    assert final["result"]["cleanup_state"] == "not_required"
    assert final["cleanup_state"] == "not_required"
    assert active == 0


def test_result_is_persisted_and_slot_retained_until_cleanup_is_confirmed(system):
    candidate = plan()
    now = int(system.clock())
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="cleanup-recovery-0001"))
    handle = {"container_id": "a" * 64}
    fingerprint = plan_fingerprint(candidate)
    result = {
        "schema_version": 2, "run_id": created["id"], "source_sha": candidate.source_sha,
        "plan_fingerprint": fingerprint, "provider": "local_cpu", "simulation": False,
        "gpu_used": False, "device": "cpu", "exit_code": 1, "started_at": now - 2,
        "finished_at": now - 1, "runtime_seconds": 1.0, "metrics": {}, "checks": [],
        "checksum": None, "artifacts": [], "known_cost_usd": "0",
        "cost_classification": "LOCAL", "cleanup_state": "pending",
    }
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint, state="running",
            handle=handle, lease_until=0, started_at=now - 2, slot_reserved=True,
            record_version=2, cleanup_state="pending"))

    class LifecycleBackend:
        cleanup_calls = 0

        def start(self, job):
            raise AssertionError("recovery must not start another container")

        def inspect(self, identity):
            raise AssertionError("persisted terminal result must be cleaned up directly")

        def capture(self, identity):
            return Observation("failed", result)

        def cleanup(self, identity):
            self.cleanup_calls += 1
            if self.cleanup_calls == 1:
                raise RuntimeError("simulated cleanup outage")

        def is_clean(self, identity):
            return self.cleanup_calls > 1

        def cancel(self, identity):
            pass

        def reconcile(self, run):
            raise AssertionError("stored handle should be reused")

    backend = LifecycleBackend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert worker.tick()
    pending = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert pending["state"] == "running"
    assert pending["cleanup_state"] == "pending"
    assert pending["result"]["exit_code"] == 1
    assert active == 1

    system.clock.advance(11)
    restarted_worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert restarted_worker.tick()
    final = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert final["state"] == "failed"
    assert final["cleanup_state"] == "complete"
    assert final["result"]["exit_code"] == 1
    assert active == 0


def test_expired_worker_lease_fences_stale_result_writes(system):
    candidate = plan()
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="lease-fencing-0001"))
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=plan_fingerprint(candidate),
            state="running", started_at=int(system.clock()), lease_until=0,
            slot_reserved=True, record_version=2, cleanup_state="pending"))
    first = Worker(system.store, system.settings, {}, system.clock)
    stale_claim = first.claim()
    assert stale_claim is not None

    system.clock.advance(121)
    replacement = Worker(system.store, system.settings, {}, system.clock)
    current_claim = replacement.claim()
    assert current_claim is not None
    assert current_claim["lease_token"] != stale_claim["lease_token"]
    assert first.update(stale_claim, result={"stale": True}, state="failed") is False
    first.finish(stale_claim, "failed", {"stale": True})
    saved = system.store.read(created["id"])
    assert saved["lease_token"] == current_claim["lease_token"]
    assert saved["result"] is None
    assert saved["state"] == "running"


def test_result_database_write_failure_keeps_container_and_slot_for_retry(system):
    candidate = plan()
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="result-db-retry-0001"))
    fingerprint = plan_fingerprint(candidate)
    result = {
        "schema_version": 2, "run_id": created["id"], "source_sha": candidate.source_sha,
        "plan_fingerprint": fingerprint, "provider": "local_cpu", "simulation": False,
        "gpu_used": False, "device": "cpu", "exit_code": 0, "started_at": int(system.clock()) - 2,
        "finished_at": int(system.clock()) - 1, "runtime_seconds": 1.0, "metrics": {},
        "checks": ["result_valid"], "checksum": "e" * 64, "artifacts": [],
        "known_cost_usd": "0", "cost_classification": "LOCAL", "cleanup_state": "pending",
    }
    handle = {"container_id": "a" * 64}
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint, state="running",
            handle=handle, lease_until=0, started_at=int(system.clock()) - 2,
            slot_reserved=True, record_version=2, cleanup_state="pending"))

    class Backend:
        cleanup_calls = 0
        def start(self, job): raise AssertionError("must not resubmit")
        def inspect(self, identity): raise AssertionError("capture contract expected")
        def capture(self, identity): return Observation("succeeded", result)
        def cleanup(self, identity): self.cleanup_calls += 1
        def is_clean(self, identity): return self.cleanup_calls > 0
        def cancel(self, identity): pass
        def reconcile(self, run): raise AssertionError("stored handle expected")

    backend = Backend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    update_method = worker.update

    def fail_result_write(job, **values):
        if "result" in values:
            raise RuntimeError("injected database write outage")
        return update_method(job, **values)

    worker.update = fail_result_write
    assert worker.tick()
    pending = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert pending["result"] is None
    assert pending["state"] == "running"
    assert active == 1
    assert backend.cleanup_calls == 0

    system.clock.advance(11)
    retry = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert retry.tick()
    final = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
    assert final["state"] == "succeeded"
    assert final["result"]["checksum"] == "e" * 64
    assert final["cleanup_state"] == "complete"
    assert active == 0


def test_timeout_terminal_intent_survives_cleanup_failure(system):
    candidate = plan()
    now = int(system.clock())
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="timeout-cleanup-intent-0001"))
    fingerprint = plan_fingerprint(candidate)
    result = {
        "schema_version": 2, "run_id": created["id"], "source_sha": candidate.source_sha,
        "plan_fingerprint": fingerprint, "provider": "local_cpu", "simulation": False,
        "gpu_used": False, "device": "cpu", "exit_code": 0,
        "started_at": now - 400, "finished_at": now - 1, "runtime_seconds": 399.0,
        "metrics": {}, "checks": [], "checksum": None, "artifacts": [],
        "known_cost_usd": "0", "cost_classification": "LOCAL", "cleanup_state": "pending",
    }
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint, state="running",
            handle={"container_id": "b" * 64}, lease_until=0,
            started_at=now - 400, slot_reserved=True, record_version=2,
            cleanup_state="not_required"))

    class TimeoutBackend:
        def __init__(self):
            self.cleanup_calls = 0

        def start(self, _job):
            raise AssertionError("recovery must not start another container")

        def reconcile(self, _job):
            raise AssertionError("persisted handle must be reused")

        def cancel(self, _handle):
            pass

        def capture(self, _handle):
            return Observation("cancelled", result)

        def cleanup(self, _handle):
            self.cleanup_calls += 1
            if self.cleanup_calls == 1:
                raise RuntimeError("injected cleanup failure")

        def is_clean(self, _handle):
            return self.cleanup_calls > 1

    backend = TimeoutBackend()
    worker = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert worker.tick()
    pending = system.store.read(created["id"])
    assert pending["cancel_requested"] is False
    assert pending["state"] == "running"
    assert pending["cleanup_state"] == "pending"
    assert pending["error"] == "cleanup_pending:cancelled"

    system.clock.advance(11)
    replacement = Worker(system.store, system.settings, {"local_cpu": backend}, system.clock)
    assert replacement.tick()
    final = system.store.read(created["id"])
    assert final["state"] == "cancelled"
    assert final["cleanup_state"] == "complete"
    assert final["result"]["exit_code"] == 0
    assert final["result"]["cleanup_state"] == "complete"
