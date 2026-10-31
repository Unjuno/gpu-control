from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import secrets
import re

from sqlalchemy import (JSON, Boolean, Column, Integer, MetaData, String, Table,
                        Text, UniqueConstraint, create_engine, insert, select, update)
from sqlalchemy.pool import NullPool
from .migrations import (migrate, paid_authorizations, provider_account_leases,
                        provider_observations)


@dataclass(frozen=True)
class ProviderAccountLease:
    provider: str
    account_scope: str
    run_id: str
    owner: str
    plan_fingerprint: str
    core_plan_fingerprint: str | None
    authorization_id: str | None
    request_challenge: dict | None
    request_challenge_sha256: str | None
    state: str
    lease_token: str
    provider_job_id: str | None
    updated_at: int


_PROVIDER_LEASE_TRANSITIONS = {
    "reserved": {"submitting", "released"},
    "submitting": {"uncertain", "active"},
    "uncertain": {"active", "cleanup_pending"},
    "active": {"cleanup_pending"},
    "cleanup_pending": set(),
    "released": set(),
}

metadata = MetaData()
runs = Table(
    "gateway_runs_v1", metadata,
    Column("id", String(40), primary_key=True),
    Column("owner", String(128), nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("plan", JSON, nullable=False),
    Column("state", String(32), nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("started_at", Integer, nullable=False, default=0),
    Column("approved_until", Integer, nullable=False, default=0),
    Column("approval_id", String(64), nullable=False, default=""),
    Column("handle", JSON, nullable=True),
    Column("result", JSON, nullable=True),
    Column("error", Text, nullable=False, default=""),
    Column("lease_until", Integer, nullable=False, default=0),
    Column("lease_token", String(64), nullable=False, default=""),
    Column("cancel_requested", Boolean, nullable=False, default=False),
    Column("slot_reserved", Boolean, nullable=False, default=False),
    # Additive v2 lifecycle fields. Existing v1 rows receive conservative values
    # through migrations; unknown historical cleanup is never promoted to complete.
    Column("record_version", Integer, nullable=False, default=1, server_default="1"),
    Column("cleanup_state", String(16), nullable=False, default="unknown", server_default="unknown"),
    Column("finished_at", Integer, nullable=True),
    Column("result_manifest", JSON, nullable=True),
    Column("admission", JSON, nullable=True),
    Column("attempt", Integer, nullable=False, default=0, server_default="0"),
    Column("submission_intent", JSON, nullable=True),
    Column("last_observed_at", Integer, nullable=True),
    UniqueConstraint("owner", "idempotency_key", name="gateway_owner_request_v1"),
)
control = Table(
    "gateway_control_v1", metadata,
    Column("id", Integer, primary_key=True),
    Column("active_count", Integer, nullable=False),
    Column("worker_seen_at", Integer, nullable=False),
    Column("supervisor_seen_at", Integer, nullable=False, default=0, server_default="0"),
)


class Store:
    """Durable state shared by API and workers; production never uses local files."""
    def __init__(self, url: str):
        options = {"connect_args": {"check_same_thread": False, "timeout": 10}} if url.startswith("sqlite:") else {"poolclass": NullPool}
        self.engine = create_engine(url, **options)

    def initialize(self) -> None:
        """Explicit schema bootstrap; never performed by an HTTP request."""
        # Register optional gateway schemas before create_all. Import is local to
        # avoid making the core store depend on auth during ordinary module import.
        from . import local_oauth  # noqa: F401
        migrate(self.engine)
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if connection.execute(select(control.c.id).where(control.c.id == 1)).first() is None:
                connection.execute(insert(control).values(id=1, active_count=0, worker_seen_at=0,
                                                         supervisor_seen_at=0))

    @contextmanager
    def transaction(self):
        # BEGIN IMMEDIATE serializes local writers. PostgreSQL uses explicit row locks.
        with self.engine.connect() as connection:
            if self.engine.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                connection.begin()
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def lock_control(self, connection):
        row = connection.execute(select(control).where(control.c.id == 1).with_for_update()).mappings().first()
        if row is None:
            raise RuntimeError("Initialize the gateway database before using it")
        return row

    def read(self, run_id: str):
        with self.engine.connect() as connection:
            row = connection.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
            return dict(row) if row else None

    def confirm_submission_dispatch(self, *, run_id: str, owner: str,
                                    plan_fingerprint: str, run_lease_token: str,
                                    attempt: int, now: int, clock=None) -> bool:
        """Claim dispatch only while the worker lease and approval remain live."""
        if (not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None or
                not isinstance(run_lease_token, str) or
                re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(attempt) is not int or attempt < 1 or type(now) is not int or now < 0):
            return False
        with self.transaction() as connection:
            row = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.lease_token == run_lease_token,
                runs.c.lease_until > now, runs.c.state == "submitting",
                runs.c.attempt == attempt, runs.c.cancel_requested.is_(False),
            ).with_for_update()).mappings().first()
            if row is None:
                return False
            # Read time after acquiring the row lock so work spent waiting for
            # the lock cannot make a stale lease or approval look current.
            dispatch_now = int(clock()) if clock is not None else now
            if (dispatch_now < 0 or row["lease_until"] <= dispatch_now or
                    row["approved_until"] <= dispatch_now):
                return False
            intent = row["submission_intent"]
            if (not isinstance(intent, dict) or intent.get("run_id") != run_id or
                    intent.get("owner") != owner or
                    intent.get("plan_fingerprint") != plan_fingerprint or
                    not isinstance(row["plan"], dict) or
                    intent.get("provider") != row["plan"].get("provider") or
                    type(intent.get("attempt")) is not int or intent["attempt"] != attempt or
                    type(intent.get("created_at")) is not int or intent["created_at"] < 0 or
                    intent.get("phase") != "dispatching"):
                return False
            changed = connection.execute(update(runs).where(
                runs.c.id == run_id, runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.lease_token == run_lease_token,
                runs.c.lease_until > dispatch_now, runs.c.state == "submitting",
                runs.c.attempt == attempt, runs.c.cancel_requested.is_(False),
            ).values(submission_intent=intent | {"phase": "provider_call_started"}))
            return changed.rowcount == 1

    def persist_verified_paid_authorization(self, *, run_id: str, owner: str,
                                            plan_fingerprint: str, approval_id: str,
                                            envelope: dict, verified, now: int) -> bool:
        """Persist a previously verified envelope against the current exact approval.

        Callers must run the signature, authority, revocation, and plan verifier
        first. This method independently rechecks identity claims and the live
        browser approval under the run-row lock; it is not an HTTP/MCP input API.
        """
        import json
        from .paid_authorization_bridge import VerifiedPaidAuthorization

        if (not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None or
                not isinstance(approval_id, str) or re.fullmatch(r"[0-9a-f]{32,64}", approval_id) is None or
                type(now) is not int or now < 0 or type(envelope) is not dict):
            raise ValueError("paid authorization persistence binding is invalid")
        if type(verified) is not VerifiedPaidAuthorization:
            raise ValueError("paid authorization must be returned by the trusted verifier")
        authorization_id = verified.authorization_id
        issuer = verified.issuer
        if (not isinstance(authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                not isinstance(issuer, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", issuer) is None or
                verified.run_id != run_id or verified.owner != owner or
                verified.gateway_plan_fingerprint != plan_fingerprint or
                verified.valid_until <= now or
                envelope.get("authorization_id") != authorization_id or envelope.get("issuer") != issuer or
                envelope.get("run_id") != run_id or envelope.get("owner") != owner or
                envelope.get("gateway_plan_fingerprint") != plan_fingerprint or
                envelope.get("core_plan_fingerprint") != verified.core_plan_fingerprint or
                envelope.get("revocation_id") != verified.revocation_id or
                envelope.get("actor") != verified.actor or
                envelope.get("decision_record_id") != verified.decision_record_id or
                envelope.get("authorization_reference") != verified.authorization_reference or
                envelope.get("expires_at") != verified.valid_until):
            raise ValueError("verified paid authorization does not match persistence binding")
        try:
            encoded = json.dumps(envelope, ensure_ascii=True, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("ascii")
        except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
            raise ValueError("paid authorization envelope is not finite JSON") from exc
        if len(encoded) > 16_384:
            raise ValueError("paid authorization envelope exceeds the size limit")
        envelope_sha256 = hashlib.sha256(encoded).hexdigest()
        with self.transaction() as connection:
            run = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == owner).with_for_update()).mappings().first()
            if (run is None or run["state"] != "approved" or run["approval_id"] != approval_id or
                    run["fingerprint"] != plan_fingerprint or run["approved_until"] <= now):
                return False
            old = connection.execute(select(paid_authorizations).where(
                paid_authorizations.c.run_id == run_id).with_for_update()).mappings().first()
            values = dict(run_id=run_id, owner=owner, plan_fingerprint=plan_fingerprint,
                          approval_id=approval_id, authorization_id=authorization_id,
                          issuer=issuer, envelope=envelope,
                          envelope_sha256=envelope_sha256, created_at=now)
            if old is None:
                connection.execute(insert(paid_authorizations).values(**values))
            elif old["approval_id"] != approval_id:
                connection.execute(update(paid_authorizations).where(
                    paid_authorizations.c.run_id == run_id,
                    paid_authorizations.c.approval_id == old["approval_id"],
                ).values(**{key: value for key, value in values.items() if key != "run_id"}))
            elif (old["authorization_id"] != authorization_id or
                  old["envelope_sha256"] != envelope_sha256):
                return False
        return True

    def read_paid_authorization(self, *, run_id: str, owner: str,
                                plan_fingerprint: str, approval_id: str,
                                now: int) -> dict | None:
        """Reload only an unexpired envelope bound to the current approval.

        This checks the durable browser approval and envelope identity at read
        time. Callers must still verify the issuer signature, current revocation
        state, and provider evidence before each consequential boundary.
        """
        import json

        if (not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None or
                not isinstance(approval_id, str) or re.fullmatch(r"[0-9a-f]{32,64}", approval_id) is None or
                type(now) is not int or now < 0):
            raise ValueError("paid authorization read binding is invalid")
        with self.transaction() as connection:
            run = connection.execute(select(runs).where(
                runs.c.id == run_id,
                runs.c.owner == owner,
            ).with_for_update()).mappings().first()
            # Worker.claim atomically moves a queued run to submitting before
            # pre-intent authorization validation. Keep that exact live approval
            # usable in that state, while refusing recovery/terminal states.
            if (run is None or run["state"] not in {"approved", "submitting"} or
                    run["cancel_requested"] is not False or
                    run["approval_id"] != approval_id or
                    run["fingerprint"] != plan_fingerprint or
                    type(run["approved_until"]) is not int or run["approved_until"] <= now):
                return None
            row = connection.execute(select(paid_authorizations).where(
                paid_authorizations.c.run_id == run_id,
                paid_authorizations.c.owner == owner,
                paid_authorizations.c.plan_fingerprint == plan_fingerprint,
                paid_authorizations.c.approval_id == approval_id,
            ).with_for_update()).mappings().first()
        if row is None or type(row["envelope"]) is not dict:
            return None
        envelope = row["envelope"]
        if (envelope.get("authorization_id") != row["authorization_id"] or
                envelope.get("issuer") != row["issuer"] or
                envelope.get("run_id") != run_id or envelope.get("owner") != owner or
                envelope.get("gateway_plan_fingerprint") != plan_fingerprint or
                type(envelope.get("expires_at")) is not int or envelope["expires_at"] <= now):
            return None
        try:
            encoded = json.dumps(envelope, ensure_ascii=True, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("ascii")
        except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
            return None
        if (len(encoded) > 16_384 or
                not secrets.compare_digest(hashlib.sha256(encoded).hexdigest(), row["envelope_sha256"])):
            return None
        return {"authorization_id": row["authorization_id"], "issuer": row["issuer"],
                "envelope": envelope, "envelope_sha256": row["envelope_sha256"]}

    @staticmethod
    def _validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint):
        if (not isinstance(provider, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", provider) is None or
                not isinstance(account_scope, str) or re.fullmatch(r"[0-9a-f]{64}", account_scope) is None or
                not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None):
            raise ValueError("provider account lease identity is invalid")

    @staticmethod
    def _provider_challenge_digest(request_challenge: dict) -> str | None:
        binding = Store._canonical_provider_challenge(request_challenge)
        return binding[1] if binding is not None else None

    @staticmethod
    def _canonical_provider_challenge(request_challenge: dict):
        if not isinstance(request_challenge, dict) or not request_challenge:
            return None
        import json
        try:
            encoded = json.dumps(request_challenge, allow_nan=False, sort_keys=True,
                                 separators=(",", ":"))
            if len(encoded.encode("utf-8")) > 16_384:
                return None

            def contains_secret_key(value):
                if isinstance(value, dict):
                    return any(
                        re.search(r"(secret|credential|password|api.?key|access.?token|bearer|token)", str(key), re.I)
                        or contains_secret_key(item)
                        for key, item in value.items()
                    )
                if isinstance(value, list):
                    return any(contains_secret_key(item) for item in value)
                return False

            if contains_secret_key(request_challenge):
                return None
            normalized = json.loads(encoded)
        except (TypeError, ValueError, RecursionError):
            return None
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return normalized, digest

    def reserve_provider_account_lease(self, *, provider: str, account_scope: str, run_id: str,
                                       owner: str, plan_fingerprint: str,
                                       core_plan_fingerprint: str, authorization_id: str, now: int):
        """Hold one provider account for a run; uncertain/active work never expires by time."""
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None):
            raise ValueError("provider account lease authorization binding is invalid")
        if type(now) is not int or now < 0:
            raise ValueError("provider account lease timestamp is invalid")
        with self.transaction() as connection:
            statement = select(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope).with_for_update()
            row = connection.execute(statement).mappings().first()
            if row is not None:
                if row["state"] == "released":
                    token = secrets.token_hex(32)
                    connection.execute(update(provider_account_leases).where(
                        provider_account_leases.c.account_scope == account_scope,
                        provider_account_leases.c.state == "released",
                    ).values(provider=provider, run_id=run_id, owner=owner,
                             plan_fingerprint=plan_fingerprint, state="reserved",
                             core_plan_fingerprint=core_plan_fingerprint,
                             authorization_id=authorization_id, request_challenge=None,
                             request_challenge_sha256=None,
                             lease_token=token, provider_job_id=None, updated_at=now))
                    row = connection.execute(statement).mappings().one()
                elif (row["provider"] == provider and row["run_id"] == run_id and
                      row["owner"] == owner and row["plan_fingerprint"] == plan_fingerprint and
                      row["core_plan_fingerprint"] == core_plan_fingerprint and
                      row["authorization_id"] == authorization_id):
                    return ProviderAccountLease(**dict(row))
                else:
                    return None
            else:
                token = secrets.token_hex(32)
                if self.engine.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert as dialect_insert
                elif self.engine.dialect.name == "sqlite":
                    from sqlalchemy.dialects.sqlite import insert as dialect_insert
                else:
                    raise RuntimeError("provider account leases require SQLite or PostgreSQL")
                connection.execute(dialect_insert(provider_account_leases).values(
                    account_scope=account_scope, provider=provider, run_id=run_id,
                    owner=owner, plan_fingerprint=plan_fingerprint, state="reserved",
                    core_plan_fingerprint=core_plan_fingerprint,
                    authorization_id=authorization_id, request_challenge=None,
                    request_challenge_sha256=None,
                    lease_token=token, provider_job_id=None, updated_at=now,
                ).on_conflict_do_nothing(index_elements=[provider_account_leases.c.account_scope]))
                row = connection.execute(statement).mappings().first()
                if (row is None or row["provider"] != provider or row["run_id"] != run_id or
                        row["owner"] != owner or row["plan_fingerprint"] != plan_fingerprint):
                    return None
            return ProviderAccountLease(**dict(row))

    def bind_provider_account_lease_challenge(self, *, account_scope: str, run_id: str,
                                              owner: str, plan_fingerprint: str,
                                              core_plan_fingerprint: str,
                                              authorization_id: str, lease_token: str,
                                              request_challenge: dict, now: int,
                                              provider: str = "runpod") -> bool:
        """Persist the exact, bounded provider create challenge before submission."""
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                type(now) is not int or now < 0 or not isinstance(lease_token, str) or
                re.fullmatch(r"[0-9a-f]{64}", lease_token) is None):
            return False
        challenge_binding = self._canonical_provider_challenge(request_challenge)
        if challenge_binding is None:
            return False
        request_challenge, challenge_digest = challenge_binding
        with self.transaction() as connection:
            result = connection.execute(update(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope,
                provider_account_leases.c.provider == provider,
                provider_account_leases.c.run_id == run_id,
                provider_account_leases.c.owner == owner,
                provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                provider_account_leases.c.authorization_id == authorization_id,
                provider_account_leases.c.lease_token == lease_token,
                provider_account_leases.c.state == "reserved",
                provider_account_leases.c.request_challenge_sha256.is_(None),
            ).values(request_challenge=request_challenge,
                     request_challenge_sha256=challenge_digest, updated_at=now))
            return result.rowcount == 1

    def reserve_provider_account_lease_with_submission_intent(
            self, *, provider: str, account_scope: str, run_id: str, owner: str,
            plan_fingerprint: str, core_plan_fingerprint: str, authorization_id: str,
            run_lease_token: str, attempt: int, request_challenge: dict, now: int):
        """Atomically persist the account hold, exact create challenge, and run intent.

        The caller must derive account_scope and validate the authorization and
        provider challenge before invoking this method. No provider I/O occurs
        inside the transaction.
        """
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                not isinstance(run_lease_token, str) or
                re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(attempt) is not int or attempt < 1 or type(now) is not int or now < 0):
            return None
        challenge_binding = self._canonical_provider_challenge(request_challenge)
        if challenge_binding is None:
            return None
        request_challenge, challenge_digest = challenge_binding

        intent = {
            "provider": provider, "owner": owner, "run_id": run_id,
            "attempt": attempt, "plan_fingerprint": plan_fingerprint,
            "account_scope": account_scope,
            "core_plan_fingerprint": core_plan_fingerprint,
            "authorization_id": authorization_id,
            "provider_challenge_sha256": challenge_digest,
            "phase": "dispatching", "created_at": now,
        }

        class _AbortProviderLeaseTransaction(Exception):
            pass

        try:
            with self.transaction() as connection:
                statement = select(provider_account_leases).where(
                    provider_account_leases.c.account_scope == account_scope
                ).with_for_update()
                row = connection.execute(statement).mappings().first()
                if row is not None and row["state"] == "released":
                    lease_token = secrets.token_hex(32)
                    result = connection.execute(update(provider_account_leases).where(
                        provider_account_leases.c.account_scope == account_scope,
                        provider_account_leases.c.state == "released",
                    ).values(
                        provider=provider, run_id=run_id, owner=owner,
                        plan_fingerprint=plan_fingerprint,
                        core_plan_fingerprint=core_plan_fingerprint,
                        authorization_id=authorization_id,
                        request_challenge=request_challenge,
                        request_challenge_sha256=challenge_digest,
                        state="reserved", lease_token=lease_token,
                        provider_job_id=None, updated_at=now,
                    ))
                    if result.rowcount != 1:
                        raise _AbortProviderLeaseTransaction()
                    row = connection.execute(statement).mappings().one()
                elif row is None:
                    lease_token = secrets.token_hex(32)
                    if self.engine.dialect.name == "postgresql":
                        from sqlalchemy.dialects.postgresql import insert as dialect_insert
                    elif self.engine.dialect.name == "sqlite":
                        from sqlalchemy.dialects.sqlite import insert as dialect_insert
                    else:
                        raise RuntimeError("provider account leases require SQLite or PostgreSQL")
                    connection.execute(dialect_insert(provider_account_leases).values(
                        account_scope=account_scope, provider=provider, run_id=run_id,
                        owner=owner, plan_fingerprint=plan_fingerprint,
                        core_plan_fingerprint=core_plan_fingerprint,
                        authorization_id=authorization_id,
                        request_challenge=request_challenge,
                        request_challenge_sha256=challenge_digest,
                        state="reserved", lease_token=lease_token,
                        provider_job_id=None, updated_at=now,
                    ).on_conflict_do_nothing(index_elements=[provider_account_leases.c.account_scope]))
                    row = connection.execute(statement).mappings().first()

                if (row is None or row["provider"] != provider or row["run_id"] != run_id or
                        row["owner"] != owner or row["plan_fingerprint"] != plan_fingerprint or
                        row["core_plan_fingerprint"] != core_plan_fingerprint or
                        row["authorization_id"] != authorization_id or row["state"] != "reserved" or
                        row["request_challenge_sha256"] != challenge_digest):
                    raise _AbortProviderLeaseTransaction()

                changed = connection.execute(update(runs).where(
                    runs.c.id == run_id,
                    runs.c.owner == owner,
                    runs.c.state == "submitting",
                    runs.c.cancel_requested.is_(False),
                    runs.c.lease_token == run_lease_token,
                    runs.c.fingerprint == plan_fingerprint,
                    runs.c.attempt == attempt - 1,
                ).values(attempt=attempt, submission_intent=intent))
                if changed.rowcount != 1:
                    raise _AbortProviderLeaseTransaction()
                lease = ProviderAccountLease(**dict(row))
        except _AbortProviderLeaseTransaction:
            return None
        return lease

    def read_provider_account_lease_for_run(self, *, run_id: str, owner: str,
                                           plan_fingerprint: str,
                                           run_lease_token: str, now: int,
                                           provider: str = "runpod") -> ProviderAccountLease | None:
        """Reload a persisted lease only for the current, unexpired Worker claim.

        Recovery reads the account scope and provider challenge from the durable
        submission intent, then verifies every binding against the lease row.
        The lease row is locked before the run row, matching the reservation
        transaction's lock order and avoiding a lease/run deadlock.
        """
        if (not isinstance(provider, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", provider) is None or
                not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None or
                not isinstance(run_lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(now) is not int or now < 0):
            return None

        with self.transaction() as connection:
            initial = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.lease_token == run_lease_token,
                runs.c.lease_until > now,
                runs.c.state.in_(("submitting", "submit_unknown", "running")),
            )).mappings().first()
            if initial is None:
                return None
            intent = initial["submission_intent"]
            if (not isinstance(intent, dict) or intent.get("provider") != provider or
                    intent.get("run_id") != run_id or intent.get("owner") != owner or
                    intent.get("plan_fingerprint") != plan_fingerprint or
                    type(intent.get("attempt")) is not int or intent["attempt"] < 1 or
                    intent["attempt"] != initial["attempt"] or
                    intent.get("phase") not in {"dispatching", "handle_persisted"}):
                return None
            account_scope = intent.get("account_scope")
            core_plan_fingerprint = intent.get("core_plan_fingerprint")
            authorization_id = intent.get("authorization_id")
            challenge_digest = intent.get("provider_challenge_sha256")
            if (not isinstance(account_scope, str) or re.fullmatch(r"[0-9a-f]{64}", account_scope) is None or
                    not isinstance(core_plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                    not isinstance(authorization_id, str) or
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                    not isinstance(challenge_digest, str) or re.fullmatch(r"[0-9a-f]{64}", challenge_digest) is None):
                return None

            lease_row = connection.execute(select(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope,
            ).with_for_update()).mappings().first()
            current = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.lease_token == run_lease_token,
                runs.c.lease_until > now,
                runs.c.state.in_(("submitting", "submit_unknown", "running")),
            ).with_for_update()).mappings().first()
            if current is None or current["submission_intent"] != intent or lease_row is None:
                return None
            challenge_binding = self._canonical_provider_challenge(lease_row["request_challenge"])
            if (challenge_binding is None or lease_row["request_challenge_sha256"] != challenge_digest or
                    challenge_binding[1] != challenge_digest or
                    lease_row["provider"] != provider or lease_row["run_id"] != run_id or
                    lease_row["owner"] != owner or lease_row["plan_fingerprint"] != plan_fingerprint or
                    lease_row["core_plan_fingerprint"] != core_plan_fingerprint or
                    lease_row["authorization_id"] != authorization_id or
                    lease_row["state"] not in _PROVIDER_LEASE_TRANSITIONS or
                    lease_row["state"] == "released"):
                return None
            if lease_row["state"] in {"active", "cleanup_pending"} and not lease_row["provider_job_id"]:
                return None
            return ProviderAccountLease(**dict(lease_row))

    def transition_provider_account_lease(self, *, account_scope: str, run_id: str, owner: str,
                                          plan_fingerprint: str, lease_token: str,
                                          core_plan_fingerprint: str, authorization_id: str,
                                          expected_state: str, new_state: str, now: int,
                                          provider_job_id: str | None = None,
                                          provider: str = "runpod") -> bool:
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or not authorization_id):
            return False
        if (type(now) is not int or now < 0 or len(lease_token) != 64 or
                new_state not in _PROVIDER_LEASE_TRANSITIONS.get(expected_state, set()) or
                (provider_job_id is not None and (not isinstance(provider_job_id, str) or
                                                  not provider_job_id or len(provider_job_id) > 512))):
            return False
        predicates = [provider_account_leases.c.account_scope == account_scope,
                      provider_account_leases.c.provider == provider,
                      provider_account_leases.c.run_id == run_id,
                      provider_account_leases.c.owner == owner,
                      provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                      provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                      provider_account_leases.c.authorization_id == authorization_id,
                      provider_account_leases.c.lease_token == lease_token,
                      provider_account_leases.c.state == expected_state]
        if expected_state == "reserved" and new_state == "submitting":
            predicates.append(provider_account_leases.c.request_challenge_sha256.is_not(None))
        values = {"state": new_state, "updated_at": now}
        if provider_job_id is not None:
            values["provider_job_id"] = provider_job_id
        with self.transaction() as connection:
            result = connection.execute(update(provider_account_leases).where(*predicates).values(**values))
            return result.rowcount == 1

    def transition_provider_account_lease_for_run(
            self, *, account_scope: str, run_id: str, owner: str,
            plan_fingerprint: str, lease_token: str, run_lease_token: str,
            core_plan_fingerprint: str, authorization_id: str,
            expected_state: str, new_state: str, now: int,
            provider_job_id: str | None = None, provider: str = "runpod") -> bool:
        """Fence a provider lease transition by the current Worker claim.

        A lease token fences successor allocations, while ``run_lease_token``
        fences workers recovering the same allocation after a claim rollover.
        Lock the provider lease before the run row, matching reservation and
        recovery-read lock ordering.
        """
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                not isinstance(lease_token, str) or re.fullmatch(r"[0-9a-f]{64}", lease_token) is None or
                not isinstance(run_lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(now) is not int or now < 0 or
                not isinstance(expected_state, str) or not isinstance(new_state, str) or
                new_state not in _PROVIDER_LEASE_TRANSITIONS.get(expected_state, set()) or
                (provider_job_id is not None and
                 (not isinstance(provider_job_id, str) or not provider_job_id or len(provider_job_id) > 512)) or
                (new_state == "active" and provider_job_id is None)):
            return False

        with self.transaction() as connection:
            lease_row = connection.execute(select(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope,
            ).with_for_update()).mappings().first()
            run_row = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.lease_token == run_lease_token,
                runs.c.lease_until > now,
                runs.c.state.in_(("submitting", "submit_unknown", "running")),
            ).with_for_update()).mappings().first()
            if lease_row is None or run_row is None:
                return False
            intent = run_row["submission_intent"]
            challenge_binding = self._canonical_provider_challenge(lease_row["request_challenge"])
            if (not isinstance(intent, dict) or intent.get("provider") != provider or
                    intent.get("account_scope") != account_scope or
                    intent.get("run_id") != run_id or intent.get("owner") != owner or
                    intent.get("plan_fingerprint") != plan_fingerprint or
                    intent.get("core_plan_fingerprint") != core_plan_fingerprint or
                    intent.get("authorization_id") != authorization_id or
                    type(intent.get("attempt")) is not int or
                    intent.get("attempt") != run_row["attempt"] or
                    intent.get("phase") not in {"dispatching", "handle_persisted"} or
                    intent.get("provider_challenge_sha256") != lease_row["request_challenge_sha256"] or
                    challenge_binding is None or challenge_binding[1] != lease_row["request_challenge_sha256"] or
                    lease_row["provider"] != provider or lease_row["run_id"] != run_id or
                    lease_row["owner"] != owner or lease_row["plan_fingerprint"] != plan_fingerprint or
                    lease_row["core_plan_fingerprint"] != core_plan_fingerprint or
                    lease_row["authorization_id"] != authorization_id or
                    lease_row["lease_token"] != lease_token or
                    lease_row["state"] != expected_state):
                return False
            if expected_state == "reserved" and new_state == "submitting" and not lease_row["request_challenge_sha256"]:
                return False
            if (new_state in {"active", "cleanup_pending"} and
                    provider_job_id is None and not lease_row["provider_job_id"]):
                return False
            if expected_state == "reserved" and new_state == "submitting" and run_row["cancel_requested"] is not False:
                return False
            values = {"state": new_state, "updated_at": now}
            if provider_job_id is not None:
                values["provider_job_id"] = provider_job_id
            changed = connection.execute(update(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope,
                provider_account_leases.c.provider == provider,
                provider_account_leases.c.run_id == run_id,
                provider_account_leases.c.owner == owner,
                provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                provider_account_leases.c.authorization_id == authorization_id,
                provider_account_leases.c.lease_token == lease_token,
                provider_account_leases.c.state == expected_state,
            ).values(**values))
            return changed.rowcount == 1

    def begin_submission(self, *, run_id: str, owner: str, plan_fingerprint: str,
                         run_lease_token: str, attempt: int, intent: dict) -> bool:
        """Persist a non-account-lease dispatch intent only while uncancelled."""
        if (not isinstance(intent, dict) or
                not isinstance(run_id, str) or re.fullmatch(r"[0-9a-f]{32}", run_id) is None or
                not isinstance(owner, str) or not owner or len(owner) > 128 or
                not isinstance(plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", plan_fingerprint) is None or
                intent.get("run_id") != run_id or
                intent.get("owner") != owner or intent.get("plan_fingerprint") != plan_fingerprint or
                type(intent.get("attempt")) is not int or intent["attempt"] != attempt or
                not isinstance(intent.get("provider"), str) or
                re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", intent["provider"]) is None or
                intent.get("phase") != "dispatching" or
                type(intent.get("created_at")) is not int or intent["created_at"] < 0 or
                not isinstance(run_lease_token, str) or
                re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(attempt) is not int or attempt < 1):
            return False
        with self.transaction() as connection:
            changed = connection.execute(update(runs).where(
                runs.c.id == run_id,
                runs.c.owner == owner,
                runs.c.fingerprint == plan_fingerprint,
                runs.c.state == "submitting",
                runs.c.cancel_requested.is_(False),
                runs.c.lease_token == run_lease_token,
                runs.c.attempt == attempt - 1,
            ).values(attempt=attempt, submission_intent=intent))
            return changed.rowcount == 1

    def finish_run_after_provider_cleanup(
            self, *, account_scope: str, run_id: str, owner: str,
            plan_fingerprint: str, lease_token: str, run_lease_token: str,
            core_plan_fingerprint: str, authorization_id: str,
            provider_job_id: str, cleanup_confirmed: bool, state: str,
            result: dict, error: str, record_version: int, now: int,
            provider: str = "runpod") -> bool:
        """Release an account lease and finish its run in one transaction.

        ``cleanup_confirmed`` must come from the trusted adapter's exact-resource
        cleanup check. This method also requires the durable run record to be
        pending cleanup and the adapter-validated provider job ID to match.
        Lock order is provider lease -> control row -> run row.
        """
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                not isinstance(lease_token, str) or re.fullmatch(r"[0-9a-f]{64}", lease_token) is None or
                not isinstance(run_lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                not isinstance(provider_job_id, str) or not provider_job_id or len(provider_job_id) > 512 or
                cleanup_confirmed is not True or state not in {"succeeded", "failed", "cancelled", "expired"} or
                not isinstance(result, dict) or result.get("cleanup_state") != "complete" or
                not isinstance(error, str) or len(error) > 4096 or
                type(record_version) is not int or record_version not in {1, 2} or
                type(now) is not int or now < 0):
            return False

        class _AbortProviderCleanupFinish(Exception):
            pass

        try:
            with self.transaction() as connection:
                lease_row = connection.execute(select(provider_account_leases).where(
                    provider_account_leases.c.account_scope == account_scope,
                ).with_for_update()).mappings().first()
                control_row = self.lock_control(connection)
                run_row = connection.execute(select(runs).where(
                    runs.c.id == run_id, runs.c.owner == owner,
                    runs.c.fingerprint == plan_fingerprint,
                    runs.c.lease_token == run_lease_token,
                    runs.c.lease_until > now,
                    runs.c.state.in_(("submitting", "submit_unknown", "running")),
                ).with_for_update()).mappings().first()
                if lease_row is None or run_row is None:
                    raise _AbortProviderCleanupFinish()
                intent = run_row["submission_intent"]
                challenge_binding = self._canonical_provider_challenge(lease_row["request_challenge"])
                if (not isinstance(intent, dict) or intent.get("provider") != provider or
                        intent.get("account_scope") != account_scope or
                        intent.get("run_id") != run_id or intent.get("owner") != owner or
                        intent.get("plan_fingerprint") != plan_fingerprint or
                        intent.get("core_plan_fingerprint") != core_plan_fingerprint or
                        intent.get("authorization_id") != authorization_id or
                        type(intent.get("attempt")) is not int or
                        intent.get("attempt") != run_row["attempt"] or
                        intent.get("phase") != "handle_persisted" or
                        intent.get("provider_challenge_sha256") != lease_row["request_challenge_sha256"] or
                        challenge_binding is None or challenge_binding[1] != lease_row["request_challenge_sha256"] or
                        lease_row["provider"] != provider or lease_row["run_id"] != run_id or
                        lease_row["owner"] != owner or lease_row["plan_fingerprint"] != plan_fingerprint or
                        lease_row["core_plan_fingerprint"] != core_plan_fingerprint or
                        lease_row["authorization_id"] != authorization_id or
                        lease_row["lease_token"] != lease_token or lease_row["state"] != "cleanup_pending" or
                        lease_row["provider_job_id"] != provider_job_id or
                        run_row["cleanup_state"] != "pending" or run_row["slot_reserved"] is not True or
                        not isinstance(run_row["result"], dict) or
                        type(control_row["active_count"]) is not int or control_row["active_count"] < 1):
                    raise _AbortProviderCleanupFinish()

                import json
                json.dumps(result, allow_nan=False)
                released = connection.execute(update(provider_account_leases).where(
                    provider_account_leases.c.account_scope == account_scope,
                    provider_account_leases.c.provider == provider,
                    provider_account_leases.c.run_id == run_id,
                    provider_account_leases.c.owner == owner,
                    provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                    provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                    provider_account_leases.c.authorization_id == authorization_id,
                    provider_account_leases.c.lease_token == lease_token,
                    provider_account_leases.c.state == "cleanup_pending",
                    provider_account_leases.c.provider_job_id == provider_job_id,
                ).values(state="released", updated_at=now))
                finished = connection.execute(update(runs).where(
                    runs.c.id == run_id, runs.c.lease_token == run_lease_token,
                    runs.c.state.in_(("submitting", "submit_unknown", "running")),
                    runs.c.cleanup_state == "pending", runs.c.slot_reserved.is_(True),
                ).values(
                    state=state, result=result, error=error, slot_reserved=False,
                    lease_until=0, lease_token="", finished_at=now,
                    cleanup_state="complete", record_version=record_version,
                ))
                if released.rowcount != 1 or finished.rowcount != 1:
                    raise _AbortProviderCleanupFinish()
                decremented = connection.execute(update(control).where(
                    control.c.id == 1, control.c.active_count >= 1,
                ).values(active_count=control.c.active_count - 1))
                if decremented.rowcount != 1:
                    raise _AbortProviderCleanupFinish()
        except _AbortProviderCleanupFinish:
            return False
        return True

    def finish_run_after_pre_submission_abort(
            self, *, account_scope: str, run_id: str, owner: str,
            plan_fingerprint: str, lease_token: str, run_lease_token: str,
            core_plan_fingerprint: str, authorization_id: str,
            state: str, result: dict, error: str, record_version: int, now: int,
            provider: str = "runpod") -> bool:
        """Release a reserved account lease when recovery proves create never began.

        A reserved lease is persisted before the worker's reserved→submitting
        transition, which itself precedes provider creation. Releasing it is
        safe only when the exact run intent is still in its dispatching phase
        and the durable lease is still reserved with no provider resource.
        Lease release and terminal run accounting are one transaction.
        """
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or
                re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", authorization_id) is None or
                not isinstance(lease_token, str) or re.fullmatch(r"[0-9a-f]{64}", lease_token) is None or
                not isinstance(run_lease_token, str) or re.fullmatch(r"[0-9a-f]{32}", run_lease_token) is None or
                type(now) is not int or now < 0 or
                state not in {"failed", "cancelled"} or
                not isinstance(result, dict) or result.get("cleanup_state") != "not_required" or
                not isinstance(error, str) or len(error) > 4096 or
                type(record_version) is not int or record_version not in {1, 2}):
            return False

        class _AbortPreSubmissionFinish(Exception):
            pass

        try:
            with self.transaction() as connection:
                lease_row = connection.execute(select(provider_account_leases).where(
                    provider_account_leases.c.account_scope == account_scope,
                ).with_for_update()).mappings().first()
                control_row = self.lock_control(connection)
                run_row = connection.execute(select(runs).where(
                    runs.c.id == run_id, runs.c.owner == owner,
                    runs.c.fingerprint == plan_fingerprint,
                    runs.c.lease_token == run_lease_token,
                    runs.c.lease_until > now,
                    runs.c.state.in_(("submitting", "submit_unknown")),
                ).with_for_update()).mappings().first()
                if lease_row is None or run_row is None:
                    raise _AbortPreSubmissionFinish()
                intent = run_row["submission_intent"]
                challenge_binding = self._canonical_provider_challenge(lease_row["request_challenge"])
                if (not isinstance(intent, dict) or intent.get("provider") != provider or
                        intent.get("account_scope") != account_scope or
                        intent.get("run_id") != run_id or intent.get("owner") != owner or
                        intent.get("plan_fingerprint") != plan_fingerprint or
                        intent.get("core_plan_fingerprint") != core_plan_fingerprint or
                        intent.get("authorization_id") != authorization_id or
                        type(intent.get("attempt")) is not int or
                        intent.get("attempt") != run_row["attempt"] or
                        intent.get("phase") != "dispatching" or
                        intent.get("provider_challenge_sha256") != lease_row["request_challenge_sha256"] or
                        challenge_binding is None or challenge_binding[1] != lease_row["request_challenge_sha256"] or
                        lease_row["provider"] != provider or lease_row["run_id"] != run_id or
                        lease_row["owner"] != owner or lease_row["plan_fingerprint"] != plan_fingerprint or
                        lease_row["core_plan_fingerprint"] != core_plan_fingerprint or
                        lease_row["authorization_id"] != authorization_id or
                        lease_row["lease_token"] != lease_token or lease_row["state"] != "reserved" or
                        lease_row["provider_job_id"] is not None or run_row["handle"] is not None or
                        run_row["slot_reserved"] is not True or
                        run_row["cancel_requested"] is not (state == "cancelled") or
                        type(control_row["active_count"]) is not int or control_row["active_count"] < 1):
                    raise _AbortPreSubmissionFinish()

                import json
                json.dumps(result, allow_nan=False)
                released = connection.execute(update(provider_account_leases).where(
                    provider_account_leases.c.account_scope == account_scope,
                    provider_account_leases.c.provider == provider,
                    provider_account_leases.c.run_id == run_id,
                    provider_account_leases.c.owner == owner,
                    provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                    provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                    provider_account_leases.c.authorization_id == authorization_id,
                    provider_account_leases.c.lease_token == lease_token,
                    provider_account_leases.c.state == "reserved",
                    provider_account_leases.c.provider_job_id.is_(None),
                ).values(state="released", updated_at=now))
                finished = connection.execute(update(runs).where(
                    runs.c.id == run_id, runs.c.owner == owner,
                    runs.c.fingerprint == plan_fingerprint,
                    runs.c.lease_token == run_lease_token,
                    runs.c.state.in_(("submitting", "submit_unknown")),
                    runs.c.cancel_requested.is_(state == "cancelled"),
                    runs.c.slot_reserved.is_(True),
                ).values(
                    state=state, result=result, error=error, slot_reserved=False,
                    lease_until=0, lease_token="", finished_at=now,
                    cleanup_state="not_required", record_version=record_version,
                ))
                if released.rowcount != 1 or finished.rowcount != 1:
                    raise _AbortPreSubmissionFinish()
                decremented = connection.execute(update(control).where(
                    control.c.id == 1, control.c.active_count >= 1,
                ).values(active_count=control.c.active_count - 1))
                if decremented.rowcount != 1:
                    raise _AbortPreSubmissionFinish()
        except _AbortPreSubmissionFinish:
            return False
        return True

    def release_provider_account_lease(self, *, account_scope: str, run_id: str, owner: str,
                                       plan_fingerprint: str, lease_token: str,
                                       core_plan_fingerprint: str, authorization_id: str,
                                       provider_job_id: str, cleanup_confirmed: bool, now: int,
                                       provider: str = "runpod") -> bool:
        self._validate_provider_lease_identity(provider, account_scope, run_id, owner, plan_fingerprint)
        if (not isinstance(core_plan_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", core_plan_fingerprint) is None or
                not isinstance(authorization_id, str) or not authorization_id):
            return False
        if cleanup_confirmed is not True or type(now) is not int or now < 0:
            return False
        with self.transaction() as connection:
            result = connection.execute(update(provider_account_leases).where(
                provider_account_leases.c.account_scope == account_scope,
                provider_account_leases.c.provider == provider,
                provider_account_leases.c.run_id == run_id,
                provider_account_leases.c.owner == owner,
                provider_account_leases.c.plan_fingerprint == plan_fingerprint,
                provider_account_leases.c.core_plan_fingerprint == core_plan_fingerprint,
                provider_account_leases.c.authorization_id == authorization_id,
                provider_account_leases.c.lease_token == lease_token,
                provider_account_leases.c.state == "cleanup_pending",
                provider_account_leases.c.provider_job_id == provider_job_id,
            ).values(state="released", updated_at=now))
            return result.rowcount == 1

    def write_provider_observation(self, envelope: dict, trusted_public_keys, *, now: int) -> bool:
        """Atomically replace one provider snapshot, refusing version rollback.

        The caller signs with the worker-only key and supplies its trusted
        public-key set for verification. This method enforces monotonic
        replacement; readers must still verify signature and expiry before use.
        """
        from .provider_evidence import (
            _canonical,
            verify_signed_observation,
        )

        if not isinstance(envelope, dict):
            raise ValueError("provider observation envelope must be an object")
        try:
            verified = verify_signed_observation(
                envelope, trusted_public_keys, now=now)
            envelope = verified
            serialized = _canonical(envelope)
            provider = envelope["provider"]
            version = envelope["version"]
            observed_at = envelope["observed_at"]
            expires_at = envelope["expires_at"]
            if (not isinstance(provider, str) or type(version) is not int or version < 1 or
                    re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", provider) is None or
                    type(observed_at) is not int or observed_at < 0 or
                    type(expires_at) is not int or expires_at <= observed_at):
                raise ProviderEvidenceError("provider observation storage fields are invalid")
        except KeyError as exc:
            raise ValueError("provider observation envelope is invalid") from exc
        digest_value = hashlib.sha256(serialized).hexdigest()
        with self.transaction() as connection:
            values = {"version": version, "observed_at": observed_at,
                      "expires_at": expires_at, "envelope": envelope,
                      "envelope_sha256": digest_value}
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as dialect_insert
            elif self.engine.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as dialect_insert
            else:
                raise RuntimeError("provider observations require SQLite or PostgreSQL")
            statement = dialect_insert(provider_observations).values(
                provider=provider, **values)
            statement = statement.on_conflict_do_update(
                index_elements=[provider_observations.c.provider],
                set_=values,
                where=provider_observations.c.version < statement.excluded.version,
            )
            result = connection.execute(statement)
            return result.rowcount == 1

    def read_provider_observation(self, provider: str, *, connection=None, lock: bool = False):
        """Return a stored envelope; callers must verify signature and freshness."""
        from .provider_evidence import ProviderEvidenceError, _canonical

        if lock and connection is None:
            raise ValueError("locking provider evidence requires the active transaction connection")
        statement = select(provider_observations).where(
            provider_observations.c.provider == provider)
        if lock:
            statement = statement.with_for_update()
        if connection is not None:
            row = connection.execute(statement).mappings().first()
        else:
            with self.engine.connect() as read_connection:
                row = read_connection.execute(statement).mappings().first()
        if row is None:
            return None
        value = dict(row)
        digest_value = hashlib.sha256(_canonical(value["envelope"])).hexdigest()
        if digest_value != value["envelope_sha256"]:
            raise ProviderEvidenceError("stored provider observation digest mismatch")
        if (not isinstance(value["envelope"], dict) or
                value["envelope"].get("provider") != value["provider"] or
                value["envelope"].get("version") != value["version"] or
                value["envelope"].get("observed_at") != value["observed_at"] or
                value["envelope"].get("expires_at") != value["expires_at"]):
            raise ProviderEvidenceError("stored provider observation index fields mismatch")
        return value

    def read_verified_provider_observation(self, provider: str, trusted_public_keys, *, now: int,
                                           minimum_version: int | None = None,
                                           connection=None, lock: bool = False):
        """Return only a current envelope whose worker signature verifies."""
        from .provider_evidence import verify_signed_observation

        stored = self.read_provider_observation(provider, connection=connection, lock=lock)
        if stored is None:
            return None
        return verify_signed_observation(
            stored["envelope"], trusted_public_keys, now=now,
            minimum_version=minimum_version,
        )

    def heartbeat(self, now: int, *, role: str = "worker"):
        if role not in {"worker", "supervisor"}:
            raise ValueError("unsupported heartbeat role")
        field = control.c.worker_seen_at if role == "worker" else control.c.supervisor_seen_at
        with self.transaction() as connection:
            connection.execute(update(control).where(control.c.id == 1).values({field.key: now}))
