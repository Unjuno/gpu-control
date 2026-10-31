"""Explicit, additive Gateway database migrations.

Schema changes run only during operator initialization, never on API requests.
The current unversioned tables are treated as schema v1. Historical terminal
states do not prove cleanup, so migrated cleanup state is conservatively unknown.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import (JSON, Column, Integer, MetaData, String, Table,
                        UniqueConstraint, inspect, insert, select, update)

SCHEMA_VERSION = 13
versions_metadata = MetaData()
schema_version = Table(
    "gateway_schema_version", versions_metadata,
    Column("id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)
provider_observations = Table(
    "gateway_provider_observations_v1", MetaData(),
    Column("provider", String(32), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("observed_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=False),
    Column("envelope", JSON, nullable=False),
    Column("envelope_sha256", String(64), nullable=False),
)
provider_account_leases = Table(
    "gateway_provider_account_leases_v1", MetaData(),
    Column("account_scope", String(64), primary_key=True),
    Column("provider", String(32), nullable=False),
    Column("run_id", String(40), nullable=False),
    Column("owner", String(128), nullable=False),
    Column("plan_fingerprint", String(64), nullable=False),
    Column("core_plan_fingerprint", String(64), nullable=True),
    Column("authorization_id", String(128), nullable=True),
    Column("request_challenge", JSON, nullable=True),
    Column("request_challenge_sha256", String(64), nullable=True),
    Column("state", String(24), nullable=False),
    Column("lease_token", String(64), nullable=False),
    Column("provider_job_id", String(512), nullable=True),
    Column("updated_at", Integer, nullable=False),
    UniqueConstraint("run_id", name="gateway_provider_account_lease_run_v1"),
)
paid_authorizations = Table(
    "gateway_paid_authorizations_v1", MetaData(),
    Column("run_id", String(40), primary_key=True),
    Column("owner", String(128), nullable=False),
    Column("plan_fingerprint", String(64), nullable=False),
    Column("approval_id", String(64), nullable=False),
    Column("authorization_id", String(128), nullable=False, unique=True),
    Column("issuer", String(64), nullable=False),
    Column("envelope", JSON, nullable=False),
    Column("envelope_sha256", String(64), nullable=False),
    Column("created_at", Integer, nullable=False),
)


class UnsupportedSchemaVersion(RuntimeError):
    """The database was written by a newer or invalid Gateway schema."""


def _columns(engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


def migration_status(engine) -> dict:
    """Describe the pending schema upgrade without creating or changing data."""
    database = engine.url.database
    if (engine.dialect.name == "sqlite" and database not in {None, "", ":memory:"}
            and not Path(database).exists()):
        return {
            "supported": True,
            "reason": None,
            "current_version": 0,
            "target_version": SCHEMA_VERSION,
            "migration_required": True,
            "planned_versions": list(range(1, SCHEMA_VERSION + 1)),
        }

    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        has_runs = "gateway_runs_v1" in tables
        has_version_table = schema_version.name in tables

        if has_version_table:
            columns = {column["name"] for column in inspector.get_columns(schema_version.name)}
            if not {"id", "version"}.issubset(columns):
                return {
                    "supported": False,
                    "reason": "invalid_schema_version_table",
                    "current_version": None,
                    "target_version": SCHEMA_VERSION,
                    "migration_required": None,
                    "planned_versions": [],
                }
            versions = connection.execute(select(schema_version.c.version).where(
                schema_version.c.id == 1)).scalars().all()
            if len(versions) > 1:
                return {
                    "supported": False,
                    "reason": "multiple_schema_version_rows",
                    "current_version": None,
                    "target_version": SCHEMA_VERSION,
                    "migration_required": None,
                    "planned_versions": [],
                }
            current = versions[0] if versions else (1 if has_runs else 0)
        else:
            current = 1 if has_runs else 0

        if type(current) is not int or current < 0 or current > SCHEMA_VERSION:
            return {
                "supported": False,
                "reason": "unsupported_schema_version",
                "current_version": current if type(current) is int else None,
                "target_version": SCHEMA_VERSION,
                "migration_required": None,
                "planned_versions": [],
            }

        return {
            "supported": True,
            "reason": None,
            "current_version": current,
            "target_version": SCHEMA_VERSION,
            "migration_required": current < SCHEMA_VERSION,
            "planned_versions": list(range(current + 1, SCHEMA_VERSION + 1)),
        }


def migrate(engine) -> int:
    """Upgrade a Gateway database to the current version and return its version."""
    versions_metadata.create_all(engine, tables=[schema_version])
    with engine.begin() as connection:
        row = connection.execute(
            select(schema_version.c.version).where(schema_version.c.id == 1).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            # Before this table existed, the Gateway schema was unversioned v1.
            has_runs = "gateway_runs_v1" in inspect(connection).get_table_names()
            current = 1 if has_runs else 0
            connection.execute(insert(schema_version).values(id=1, version=current))
        else:
            current = row

        if type(current) is not int or current < 0 or current > SCHEMA_VERSION:
            raise UnsupportedSchemaVersion("Gateway database schema version is unsupported")

        if current < 2:
            tables = set(inspect(connection).get_table_names())
            if "gateway_runs_v1" in tables:
                existing = _columns(connection, "gateway_runs_v1")
                additions = (
                    ("record_version", "INTEGER NOT NULL DEFAULT 1"),
                    ("cleanup_state", "VARCHAR(16) NOT NULL DEFAULT 'unknown'"),
                    ("finished_at", "INTEGER"),
                    ("result_manifest", "JSON"),
                )
                for name, definition in additions:
                    if name not in existing:
                        connection.exec_driver_sql(
                            f'ALTER TABLE gateway_runs_v1 ADD COLUMN "{name}" {definition}'
                        )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=2))
            current = 2
        if current < 3:
            tables = set(inspect(connection).get_table_names())
            if "gateway_runs_v1" in tables:
                existing = _columns(connection, "gateway_runs_v1")
                if "admission" not in existing:
                    connection.exec_driver_sql(
                        'ALTER TABLE gateway_runs_v1 ADD COLUMN "admission" JSON'
                    )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=3))
            current = 3
        if current < 4:
            tables = set(inspect(connection).get_table_names())
            if "gateway_runs_v1" in tables:
                existing = _columns(connection, "gateway_runs_v1")
                additions = (
                    ("attempt", "INTEGER NOT NULL DEFAULT 0"),
                    ("submission_intent", "JSON"),
                )
                for name, definition in additions:
                    if name not in existing:
                        connection.exec_driver_sql(
                            f'ALTER TABLE gateway_runs_v1 ADD COLUMN "{name}" {definition}'
                        )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=4))
            current = 4
        if current < 5:
            tables = set(inspect(connection).get_table_names())
            if "gateway_control_v1" in tables and "supervisor_seen_at" not in _columns(connection, "gateway_control_v1"):
                connection.exec_driver_sql(
                    'ALTER TABLE gateway_control_v1 ADD COLUMN "supervisor_seen_at" INTEGER NOT NULL DEFAULT 0'
                )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=5))
            current = 5
        if current < 6:
            tables = set(inspect(connection).get_table_names())
            if ("gateway_runs_v1" in tables and
                    "last_observed_at" not in _columns(connection, "gateway_runs_v1")):
                connection.exec_driver_sql(
                    'ALTER TABLE gateway_runs_v1 ADD COLUMN "last_observed_at" INTEGER'
                )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=6))
            current = 6
        if current < 7:
            tables = set(inspect(connection).get_table_names())
            if ("gateway_oauth_tokens_v1" in tables and
                    "grant_id" not in _columns(connection, "gateway_oauth_tokens_v1")):
                connection.exec_driver_sql(
                    'ALTER TABLE gateway_oauth_tokens_v1 ADD COLUMN "grant_id" VARCHAR(64)'
                )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=7))
            current = 7
        if current < 8:
            provider_observations.create(connection, checkfirst=True)
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=8))
            current = 8
        if current < 9:
            tables = set(inspect(connection).get_table_names())
            clients = "gateway_oauth_clients_v1"
            tokens = "gateway_oauth_tokens_v1"
            if clients in tables:
                if "persistent" not in _columns(connection, clients):
                    default = "FALSE" if engine.dialect.name == "postgresql" else "0"
                    connection.exec_driver_sql(
                        f'ALTER TABLE "{clients}" ADD COLUMN "persistent" BOOLEAN NOT NULL DEFAULT {default}'
                    )
                if tokens in tables:
                    connection.exec_driver_sql(
                        f'UPDATE "{clients}" AS client SET "persistent" = TRUE '
                        f'WHERE EXISTS (SELECT 1 FROM "{tokens}" AS token '
                        'WHERE token.client_id = client.client_id)'
                    )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=9))
            current = 9
        if current < 10:
            provider_account_leases.create(connection, checkfirst=True)
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=10))
            current = 10
        if current < 11:
            tables = set(inspect(connection).get_table_names())
            if provider_account_leases.name in tables:
                columns = _columns(connection, provider_account_leases.name)
                if "core_plan_fingerprint" not in columns:
                    connection.exec_driver_sql(
                        'ALTER TABLE "gateway_provider_account_leases_v1" '
                        'ADD COLUMN "core_plan_fingerprint" VARCHAR(64)'
                    )
                if "authorization_id" not in columns:
                    connection.exec_driver_sql(
                        'ALTER TABLE "gateway_provider_account_leases_v1" '
                        'ADD COLUMN "authorization_id" VARCHAR(128)'
                    )
                if "request_challenge" not in columns:
                    column_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
                    connection.exec_driver_sql(
                        'ALTER TABLE "gateway_provider_account_leases_v1" '
                        f'ADD COLUMN "request_challenge" {column_type}'
                    )
                if "request_challenge_sha256" not in columns:
                    connection.exec_driver_sql(
                        'ALTER TABLE "gateway_provider_account_leases_v1" '
                        'ADD COLUMN "request_challenge_sha256" VARCHAR(64)'
                    )
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=11))
            current = 11
        if current < 12:
            paid_authorizations.create(connection, checkfirst=True)
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=12))
            current = 12
        if current < 13:
            tables = set(inspect(connection).get_table_names())
            clients = "gateway_oauth_clients_v1"
            if clients in tables and "persistent" in _columns(connection, clients):
                # Schema v9 inferred owner consent from arbitrary historical
                # token rows. Legacy state cannot prove an explicit consent
                # POST, so require reauthorization before persistence.
                connection.execute(update(Table(
                    clients, MetaData(), autoload_with=connection
                )).values(persistent=False))
            connection.execute(update(schema_version).where(schema_version.c.id == 1).values(version=13))
            current = 13
    return current
