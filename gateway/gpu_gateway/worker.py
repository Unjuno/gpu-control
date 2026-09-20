from __future__ import annotations

import argparse
import json
import logging
import secrets
import time
import uuid
from urllib.parse import quote
from decimal import Decimal

from sqlalchemy import select, update

from .backends import Backend, build_backends
from .config import Settings
from .registry import default_registry
from .service import TERMINAL, digest
from .store import Store, control, runs

logger = logging.getLogger(__name__)


class Worker:
    """Short recoverable ticks, executed OUTSIDE the Vercel request lifecycle.

    A stale submitting job is reconciled, never blindly retried. Unknown submissions
    keep their admission slot until an operator/provider supplies reliable evidence.
    """
    def __init__(self, store: Store, settings: Settings, backends: dict[str, Backend], clock=time.time, *, registry=None):
        self.store, self.settings, self.backends, self.clock = store, settings, backends, clock
        self.registry = default_registry() if registry is None else registry

    def claim(self):
        now = int(self.clock())
        token = uuid.uuid4().hex
        with self.store.transaction() as c:
            self.store.lock_control(c)
            c.execute(update(control).where(control.c.id == 1).values(worker_seen_at=now))
            row = c.execute(select(runs).where(
                runs.c.state.in_(["queued", "submitting", "submit_unknown", "running"]),
                runs.c.lease_until <= now,
            ).order_by(runs.c.lease_until, runs.c.created_at).limit(1).with_for_update()).mappings().first()
            if row is None:
                return None
            job = dict(row)
            changes = {"lease_until": now + 120, "lease_token": token}
            if job["state"] == "queued":
                changes.update(state="submitting", started_at=now)
            elif job["state"] == "submitting":
                changes["state"] = "submit_unknown"
            c.execute(update(runs).where(runs.c.id == job["id"]).values(**changes))
            job.update(changes)
            job["was_queued"] = row["state"] == "queued"
            return job

    def update(self, job: dict, **values):
        with self.store.transaction() as c:
            return c.execute(update(runs).where(runs.c.id == job["id"], runs.c.lease_token == job["lease_token"]).values(**values)).rowcount == 1

    def finish(self, job: dict, state: str, result=None, error=""):
        if state not in TERMINAL:
            raise ValueError("Invalid terminal state")
        if result is not None:
            raw = json.dumps(result, allow_nan=False).encode()
            if len(raw) > self.settings.max_output_bytes * 3:
                result = {"result_omitted": True, "reason": "result_size_limit"}
        with self.store.transaction() as c:
            self.store.lock_control(c)
            row = c.execute(select(runs).where(runs.c.id == job["id"])).mappings().one()
            if row["lease_token"] != job["lease_token"] or row["state"] in TERMINAL:
                return
            if row["slot_reserved"]:
                c.execute(update(control).where(control.c.id == 1).values(active_count=control.c.active_count - 1))
            c.execute(update(runs).where(runs.c.id == job["id"]).values(
                state=state, result=result, error=error, slot_reserved=False,
                lease_until=0, lease_token=""))

    def tick(self) -> bool:
        job = self.claim()
        if job is None:
            return False
        now = int(self.clock())
        plan = job["plan"]
        backend = self.backends.get(plan["provider"])
        if backend is None:
            if job["was_queued"]:
                self.finish(job, "failed", error="provider_not_configured")
            else:
                self.update(job, error="provider_not_configured", lease_until=now + 30)
            return True
        if job["was_queued"]:
            manifest = plan["workload_manifest"]
            if digest(plan) != job["fingerprint"]:
                self.finish(job, "failed", error="plan_integrity_failed")
                return True
            if job["approved_until"] <= now:
                self.finish(job, "expired", error="approval_expired_before_submission")
                return True
            registration = self.registry.get(plan["provider"])
            enabled = registration is not None and registration.enabled(self.settings)
            if not enabled:
                self.finish(job, "failed", error="new_submissions_disabled")
                return True
            if Decimal(plan["max_cost_usd"]) > self.settings.max_job_cost_usd:
                self.finish(job, "failed", error="current_operator_cost_limit")
                return True
            if plan["provider"] != "demo":
                if manifest["quote_expires_at"] <= now:
                    self.finish(job, "expired", error="quote_expired_before_submission")
                    return True
                quote = Decimal(manifest["quoted_usd_per_hour"])
                if quote * Decimal(plan["runtime_seconds"]) / Decimal(3600) > Decimal(plan["max_cost_usd"]):
                    self.finish(job, "failed", error="cost_limit")
                    return True
            try:
                handle = backend.start(job)
                if not isinstance(handle, dict) or not handle:
                    raise ValueError("Missing durable provider handle")
                json.dumps(handle, allow_nan=False)
            except Exception:
                # Some failures occur AFTER provider acceptance. No automatic retry.
                self.update(job, state="submit_unknown", error="submission_outcome_unknown", lease_until=now + 5)
                logger.warning("Submission outcome unknown for run %s", job["id"])
                return True
            # Persist a returned handle even if this worker lost its lease. This is
            # evidence of an already-started job, NOT authority to start another.
            with self.store.transaction() as c:
                c.execute(update(runs).where(runs.c.id == job["id"], runs.c.handle.is_(None)).values(handle=handle))
            self.update(job, state="running", lease_until=now + 1, error="")
            return True
        try:
            handle = job["handle"]
            if handle is None:
                handle = backend.reconcile(job)
                if handle is None:
                    self.update(job, state="submit_unknown", error="operator_reconciliation_required", lease_until=now + 30)
                    return True
                self.update(job, handle=handle, state="running", error="")
            latest = self.store.read(job["id"])
            overdue = now > job["started_at"] + plan["runtime_seconds"] + 60
            cancelling = latest["cancel_requested"] or overdue
            if cancelling:
                backend.cancel(handle)
            observation = backend.inspect(handle)
            if observation.state == "running":
                self.update(job, state="running", lease_until=now + 3,
                            error="cancellation_pending" if cancelling else "")
            else:
                state = "cancelled" if cancelling else observation.state
                self.finish(job, state, observation.result)
        except Exception:
            # Observability failure does not prove completion and must not free a slot.
            self.update(job, error="provider_observation_or_cleanup_failed", lease_until=now + 10)
            logger.warning("Observation/recovery needed for run %s", job["id"])
        return True


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init-db", action="store_true")
    mode.add_argument("--bootstrap-auth", action="store_true")
    parser.add_argument("--bootstrap-auth-ttl", type=int, default=3600)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=3)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.database_url)
    if args.init_db:
        store.initialize()
        return
    if args.bootstrap_auth:
        if settings.issuer:
            parser.error("bootstrap-auth is only available for built-in OAuth mode")
        if not 60 <= args.bootstrap_auth_ttl <= 86400:
            parser.error("bootstrap-auth-ttl must be between 60 and 86400 seconds")
        store.initialize()
        from .local_oauth import LocalOAuth
        oauth = LocalOAuth(settings, store)
        if oauth.configured():
            parser.error("owner authentication is already configured")
        token = secrets.token_urlsafe(32)
        oauth.seed_bootstrap(token, ttl_seconds=args.bootstrap_auth_ttl)
        print(settings.public_url.rstrip("/") + "/auth/setup?token=" + quote(token, safe=""))
        return
    if args.poll_seconds < 0.5:
        parser.error("poll-seconds must be at least 0.5")
    worker = Worker(store, settings, build_backends(settings))
    while True:
        worker.tick()
        if args.once:
            break
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
