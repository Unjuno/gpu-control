from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import (JSON, Boolean, Column, Integer, MetaData, String, Table,
                        Text, UniqueConstraint, create_engine, insert, select, update)
from sqlalchemy.pool import NullPool

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
    UniqueConstraint("owner", "idempotency_key", name="gateway_owner_request_v1"),
)
control = Table(
    "gateway_control_v1", metadata,
    Column("id", Integer, primary_key=True),
    Column("active_count", Integer, nullable=False),
    Column("worker_seen_at", Integer, nullable=False),
)


class Store:
    """Durable state shared by API and workers; production never uses local files."""
    def __init__(self, url: str):
        options = {"connect_args": {"check_same_thread": False, "timeout": 10}} if url.startswith("sqlite:") else {"poolclass": NullPool}
        self.engine = create_engine(url, **options)

    def initialize(self) -> None:
        """Explicit schema bootstrap; never performed by an HTTP request."""
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if connection.execute(select(control.c.id).where(control.c.id == 1)).first() is None:
                connection.execute(insert(control).values(id=1, active_count=0, worker_seen_at=0))

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

    def heartbeat(self, now: int):
        with self.transaction() as connection:
            connection.execute(update(control).where(control.c.id == 1).values(worker_seen_at=now))
