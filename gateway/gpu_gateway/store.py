from __future__ import annotations

from contextlib import contextmanager
import hashlib
import re

from sqlalchemy import (JSON, Boolean, Column, Integer, MetaData, String, Table,
                        Text, UniqueConstraint, create_engine, insert, select, update)
from sqlalchemy.pool import NullPool
from .migrations import migrate, provider_observations

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
