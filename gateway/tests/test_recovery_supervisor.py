import json
import os
import subprocess
import sys

from sqlalchemy import select, update

from gpu_gateway.backends import Observation
from gpu_gateway.contracts import plan_fingerprint
from gpu_gateway.service import Prepare
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker

from test_local_admission import plan


def test_recovery_supervisor_does_not_claim_new_queue_or_impersonate_worker(system):
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="supervisor-does-not-start-queue"))
    now = int(system.clock())
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now - 20, supervisor_seen_at=0, active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            state="queued", slot_reserved=True, lease_until=0))

    supervisor = Worker(system.store, system.settings, {}, system.clock, role="supervisor")
    assert supervisor.tick() is False
    row = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        state = connection.execute(select(control)).mappings().one()
    assert row["state"] == "queued"
    assert state["worker_seen_at"] == now - 20
    assert state["supervisor_seen_at"] == now


def test_recovery_supervisor_reconciles_expired_cancelled_run(system):
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="supervisor-recovers-cancel"))
    now = int(system.clock())
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now - 20, supervisor_seen_at=0, active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            state="running", handle={"id": "existing-provider-resource"}, started_at=now,
            lease_until=0, lease_token="dead-worker-lease", slot_reserved=True,
            cancel_requested=True))

    class ExistingResourceBackend:
        def __init__(self):
            self.cancelled = []

        def start(self, _job):
            raise AssertionError("recovery must never submit a new resource")

        def reconcile(self, _job):
            raise AssertionError("persisted handle must be reused")

        def cancel(self, handle):
            self.cancelled.append(handle)

        def inspect(self, _handle):
            return Observation("cancelled", {"simulation": True})

    backend = ExistingResourceBackend()
    supervisor = Worker(system.store, system.settings, {"demo": backend}, system.clock,
                        role="supervisor")
    assert supervisor.tick() is True
    row = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        active = connection.execute(select(control.c.active_count)).scalar_one()
        timestamps = connection.execute(select(control.c.worker_seen_at,
                                               control.c.supervisor_seen_at)).one()
    assert backend.cancelled == [{"id": "existing-provider-resource"}]
    assert row["state"] == "cancelled"
    assert active == 0
    assert timestamps == (now - 20, now)


def test_recovery_supervisor_uses_stale_worker_heartbeat_to_reconcile_submission(system):
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="supervisor-stale-submission"))
    now = int(system.clock())
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(
            worker_seen_at=now - 16, supervisor_seen_at=0))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            state="submitting", started_at=now, lease_until=now + 100,
            lease_token="dead-worker-lease", slot_reserved=True,
            submission_intent={"provider": "demo", "owner": system.owner.owner,
                               "run_id": created["id"], "attempt": 1,
                               "plan_fingerprint": created["fingerprint"],
                               "phase": "dispatching", "created_at": now}))

    supervisor = Worker(system.store, system.settings, {}, system.clock, role="supervisor")
    claim = supervisor.claim()
    assert claim is not None
    assert claim["id"] == created["id"]
    assert claim["state"] == "submit_unknown"
    assert claim["lease_token"] != "dead-worker-lease"
    assert claim["was_queued"] is False
    assert system.store.read(created["id"])["handle"] is None


def test_restarted_supervisor_finishes_cancel_after_crash_during_cleanup_pending(system):
    candidate = plan()
    now = int(system.clock())
    created = system.service.prepare(system.owner, Prepare(
        workload="demo", idempotency_key="supervisor-crash-cleanup-pending"))
    fingerprint = plan_fingerprint(candidate)
    handle = {"container_id": "a" * 64}
    result = {
        "schema_version": 2, "run_id": created["id"], "source_sha": candidate.source_sha,
        "plan_fingerprint": fingerprint, "provider": "local_cpu", "simulation": False,
        "gpu_used": False, "device": "cpu", "exit_code": 0,
        "started_at": now - 3, "finished_at": now - 1, "runtime_seconds": 2.0,
        "metrics": {}, "checks": [], "checksum": None, "artifacts": [],
        "known_cost_usd": "0", "cost_classification": "LOCAL", "cleanup_state": "pending",
    }
    with system.store.transaction() as connection:
        connection.execute(update(control).where(control.c.id == 1).values(active_count=1))
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(
            plan=candidate.model_dump(mode="json"), fingerprint=fingerprint,
            state="running", handle=handle, started_at=now - 3, lease_until=0,
            slot_reserved=True, cancel_requested=True, record_version=2,
            cleanup_state="pending"))

    crash_supervisor = r'''
import json, os, sys
from gpu_gateway.backends import Observation
from gpu_gateway.config import Settings
from gpu_gateway.store import Store
from gpu_gateway.worker import Worker
url, raw_result = sys.argv[1], sys.argv[2]
result = json.loads(raw_result)
class CrashDuringCleanup:
    def start(self, _job): raise AssertionError("must not start")
    def reconcile(self, _job): raise AssertionError("stored handle required")
    def cancel(self, _handle): pass
    def capture(self, _handle): return Observation("cancelled", result)
    def cleanup(self, _handle): os._exit(73)
    def is_clean(self, _handle): return False
worker = Worker(Store(url), Settings(database_url=url),
                {"local_cpu": CrashDuringCleanup()}, role="supervisor")
worker.tick()
os._exit(74)
'''
    process = subprocess.run(
        [sys.executable, "-c", crash_supervisor, system.settings.database_url,
         json.dumps(result, separators=(",", ":"))],
        cwd=os.path.dirname(os.path.dirname(__file__)), capture_output=True, timeout=20)
    assert process.returncode == 73, process.stderr.decode("utf-8", "replace")[-2000:]

    interrupted = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        reserved = connection.execute(select(control.c.active_count)).scalar_one()
    assert interrupted["state"] == "running"
    assert interrupted["cancel_requested"] is True
    assert interrupted["cleanup_state"] == "pending"
    assert interrupted["error"] == "cleanup_pending:cancelled"
    assert interrupted["result"]["run_id"] == created["id"]
    assert reserved == 1

    # The replacement supervisor owns a new process/lease and completes only the
    # persisted cleanup; it must neither recapture nor discard the saved result.
    class ReplacementBackend:
        def __init__(self):
            self.cleanup_calls = 0

        def start(self, _job):
            raise AssertionError("recovery must not start")

        def reconcile(self, _job):
            raise AssertionError("persisted handle must be reused")

        def cancel(self, _handle):
            raise AssertionError("cancel already completed before cleanup")

        def capture(self, _handle):
            raise AssertionError("saved result must be retained")

        def cleanup(self, _handle):
            self.cleanup_calls += 1

        def is_clean(self, _handle):
            return self.cleanup_calls == 1

    with system.store.transaction() as connection:
        connection.execute(update(runs).where(runs.c.id == created["id"]).values(lease_until=0))
    backend = ReplacementBackend()
    replacement = Worker(system.store, system.settings, {"local_cpu": backend},
                         system.clock, role="supervisor")
    assert replacement.tick() is True
    final = system.store.read(created["id"])
    with system.store.engine.connect() as connection:
        reserved = connection.execute(select(control.c.active_count)).scalar_one()
    assert backend.cleanup_calls == 1
    assert final["state"] == "cancelled"
    assert final["cleanup_state"] == "complete"
    assert final["result"]["run_id"] == created["id"]
    assert final["result"]["cleanup_state"] == "complete"
    assert reserved == 0
