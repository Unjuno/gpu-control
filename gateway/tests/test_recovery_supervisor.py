from sqlalchemy import select, update

from gpu_gateway.backends import Observation
from gpu_gateway.service import Prepare
from gpu_gateway.store import control, runs
from gpu_gateway.worker import Worker


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
