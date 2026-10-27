"""Explicit, additive Gateway database migrations.

Schema changes run only during operator initialization, never on API requests.
The current unversioned tables are treated as schema v1. Historical terminal
states do not prove cleanup, so migrated cleanup state is conservatively unknown.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table, inspect, insert, select, update

SCHEMA_VERSION = 3
versions_metadata = MetaData()
schema_version = Table(
    "gateway_schema_version", versions_metadata,
    Column("id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)


class UnsupportedSchemaVersion(RuntimeError):
    """The database was written by a newer or invalid Gateway schema."""


def _columns(engine, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table_name)}


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
    return current
