from sqlalchemy import select, update

from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker
from gpu_gateway.backends import Observation
from gpu_gateway.service import Prepare

from test_local_admission import plan


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
