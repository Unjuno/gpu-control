from sqlalchemy import create_engine, select, text

from gpu_gateway.migrations import (
    UnsupportedSchemaVersion, migrate, schema_version,
)
from gpu_gateway.store import Store


def _legacy_v1(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE gateway_runs_v1 (
                id VARCHAR(40) PRIMARY KEY, owner VARCHAR(128) NOT NULL,
                idempotency_key VARCHAR(128) NOT NULL, request_hash VARCHAR(64) NOT NULL,
                fingerprint VARCHAR(64) NOT NULL, plan JSON NOT NULL,
                state VARCHAR(32) NOT NULL, created_at INTEGER NOT NULL,
                started_at INTEGER NOT NULL, approved_until INTEGER NOT NULL,
                approval_id VARCHAR(64) NOT NULL, handle JSON, result JSON,
                error TEXT NOT NULL, lease_until INTEGER NOT NULL,
                lease_token VARCHAR(64) NOT NULL, cancel_requested BOOLEAN NOT NULL,
                slot_reserved BOOLEAN NOT NULL,
                CONSTRAINT gateway_owner_request_v1 UNIQUE(owner, idempotency_key)
            )
        """)
        connection.exec_driver_sql("""
            INSERT INTO gateway_runs_v1 VALUES (
                '0123456789abcdef0123456789abcdef', 'owner-a', 'stable-key',
                'request-hash', 'plan-fingerprint', '{"schema_version":1}',
                'succeeded', 100, 110, 0, '', '{"id":"provider-id"}',
                '{"simulation":true}', '', 0, '', 0, 0
            )
        """)
        connection.exec_driver_sql("""
            CREATE TABLE gateway_oauth_tokens_v1 (
                token_hash VARCHAR(64) PRIMARY KEY, kind VARCHAR(16) NOT NULL,
                client_id VARCHAR(128) NOT NULL, subject VARCHAR(64) NOT NULL,
                scope TEXT NOT NULL, resource TEXT NOT NULL, expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL, revoked BOOLEAN NOT NULL
            )
        """)
        connection.exec_driver_sql("""
            INSERT INTO gateway_oauth_tokens_v1 VALUES
            ('secret-hash', 'refresh', 'client', 'owner', 'scope', 'resource', 200, 50, 0)
        """)
        connection.exec_driver_sql("""
            CREATE TABLE gateway_control_v1 (
                id INTEGER PRIMARY KEY, active_count INTEGER NOT NULL,
                worker_seen_at INTEGER NOT NULL
            )
        """)
        connection.exec_driver_sql("INSERT INTO gateway_control_v1 VALUES (1, 0, 123)")


def test_v1_rows_and_oauth_tokens_survive_idempotent_migration(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    _legacy_v1(engine)

    assert migrate(engine) == 6
    assert migrate(engine) == 6
    store = Store(str(engine.url))
    store.initialize()

    row = store.read("0123456789abcdef0123456789abcdef")
    assert row["owner"] == "owner-a"
    assert row["idempotency_key"] == "stable-key"
    assert row["fingerprint"] == "plan-fingerprint"
    assert row["plan"] == {"schema_version": 1}
    assert row["handle"] == {"id": "provider-id"}
    assert row["result"] == {"simulation": True}
    assert row["state"] == "succeeded"
    assert row["record_version"] == 1
    assert row["cleanup_state"] == "unknown"
    assert row["finished_at"] is None
    assert row["admission"] is None
    assert row["attempt"] == 0
    assert row["submission_intent"] is None
    assert row["last_observed_at"] is None
    with engine.connect() as connection:
        assert connection.execute(text("SELECT token_hash FROM gateway_oauth_tokens_v1")).scalar_one() == "secret-hash"
        assert connection.execute(text("SELECT worker_seen_at, supervisor_seen_at FROM gateway_control_v1 WHERE id=1")).one() == (123, 0)
    engine.dispose()


def test_fresh_database_migrates_before_table_creation(tmp_path):
    database = f"sqlite:///{tmp_path / 'fresh.db'}"
    store = Store(database)
    assert migrate(store.engine) == 6
    store.initialize()
    assert store.read("no-such-run") is None
    engine = store.engine
    engine.dispose()


def test_v5_migration_adds_nullable_last_observed_at(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'v5.db'}")
    store.initialize()
    with store.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE gateway_runs_v1 DROP COLUMN "last_observed_at"')
        connection.execute(schema_version.update().values(version=5))

    assert migrate(store.engine) == 6
    assert migrate(store.engine) == 6
    row = store.read("missing")
    assert row is None
    with store.engine.connect() as connection:
        assert connection.execute(select(schema_version.c.version)).scalar_one() == 6
    store.engine.dispose()


def test_unknown_future_schema_fails_closed(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'future.db'}")
    schema_version.create(engine)
    with engine.begin() as connection:
        connection.execute(schema_version.insert().values(id=1, version=99))

    try:
        migrate(engine)
    except UnsupportedSchemaVersion:
        pass
    else:
        raise AssertionError("future database schema must be rejected")
    engine.dispose()
