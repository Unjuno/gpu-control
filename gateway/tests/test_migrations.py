from sqlalchemy import create_engine, inspect, select, text, update

from gpu_gateway.migrations import (
    SCHEMA_VERSION, UnsupportedSchemaVersion, migrate, migration_status,
    schema_version,
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
                '{"simulation":true}', '', 0, '', FALSE, FALSE
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
            ('secret-hash', 'refresh', 'client', 'owner', 'scope', 'resource', 200, 50, FALSE)
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

    assert migrate(engine) == 8
    assert migrate(engine) == 8
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
        assert "grant_id" in {column["name"] for column in inspect(connection).get_columns("gateway_oauth_tokens_v1")}
    engine.dispose()


def test_migration_status_is_read_only_for_unversioned_v1(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-preflight.db'}")
    _legacy_v1(engine)
    tables_before = set(inspect(engine).get_table_names())

    status = migration_status(engine)

    assert status == {
        "supported": True,
        "reason": None,
        "current_version": 1,
        "target_version": SCHEMA_VERSION,
        "migration_required": True,
        "planned_versions": list(range(2, SCHEMA_VERSION + 1)),
    }
    assert set(inspect(engine).get_table_names()) == tables_before
    with engine.connect() as connection:
        assert "gateway_schema_version" not in inspect(connection).get_table_names()
        assert connection.execute(text(
            "SELECT token_hash FROM gateway_oauth_tokens_v1"
        )).scalar_one() == "secret-hash"
    engine.dispose()


def test_migration_status_marks_current_database_without_pending_steps(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'current-preflight.db'}")
    store.initialize()

    status = migration_status(store.engine)

    assert status["supported"] is True
    assert status["current_version"] == SCHEMA_VERSION
    assert status["target_version"] == SCHEMA_VERSION
    assert status["migration_required"] is False
    assert status["planned_versions"] == []
    store.engine.dispose()


def test_migration_status_does_not_create_missing_sqlite_database(tmp_path):
    database_path = tmp_path / "not-created.db"
    engine = create_engine(f"sqlite:///{database_path}")

    status = migration_status(engine)

    assert status["supported"] is True
    assert status["current_version"] == 0
    assert status["target_version"] == SCHEMA_VERSION
    assert status["migration_required"] is True
    assert status["planned_versions"] == list(range(1, SCHEMA_VERSION + 1))
    assert database_path.exists() is False
    engine.dispose()


def test_migration_status_rejects_unknown_future_version_without_writes(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'future-preflight.db'}")
    store.initialize()
    with store.engine.begin() as connection:
        connection.execute(update(schema_version).where(
            schema_version.c.id == 1).values(version=99))
    tables_before = set(inspect(store.engine).get_table_names())

    status = migration_status(store.engine)

    assert status == {
        "supported": False,
        "reason": "unsupported_schema_version",
        "current_version": 99,
        "target_version": SCHEMA_VERSION,
        "migration_required": None,
        "planned_versions": [],
    }
    with store.engine.connect() as connection:
        assert connection.execute(select(schema_version.c.version)).scalar_one() == 99
    assert set(inspect(store.engine).get_table_names()) == tables_before
    store.engine.dispose()


def test_migration_status_rejects_malformed_version_table_without_writes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'malformed-preflight.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE gateway_schema_version (id INTEGER PRIMARY KEY)"
        )
    tables_before = set(inspect(engine).get_table_names())

    status = migration_status(engine)

    assert status == {
        "supported": False,
        "reason": "invalid_schema_version_table",
        "current_version": None,
        "target_version": SCHEMA_VERSION,
        "migration_required": None,
        "planned_versions": [],
    }
    assert set(inspect(engine).get_table_names()) == tables_before
    with engine.connect() as connection:
        assert {column["name"] for column in
                inspect(connection).get_columns("gateway_schema_version")} == {"id"}
    engine.dispose()


def test_fresh_database_migrates_before_table_creation(tmp_path):
    database = f"sqlite:///{tmp_path / 'fresh.db'}"
    store = Store(database)
    assert migrate(store.engine) == 8
    store.initialize()
    assert store.read("no-such-run") is None
    engine = store.engine
    engine.dispose()


def test_v6_migration_adds_oauth_grant_id_without_rewriting_existing_tokens(tmp_path):
    store = Store(f"sqlite:///{tmp_path / 'v6.db'}")
    store.initialize()
    with store.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE gateway_oauth_tokens_v1 DROP COLUMN "grant_id"')
        connection.exec_driver_sql("""
            INSERT INTO gateway_oauth_tokens_v1
            (token_hash, kind, client_id, subject, scope, resource, expires_at, created_at, revoked)
            VALUES ('token-hash', 'refresh', 'client', 'owner', 'offline_access',
                    'https://gateway.example/mcp', 1000, 10, 0)
        """)
        connection.execute(schema_version.update().values(version=6))

    assert migrate(store.engine) == 8
    assert migrate(store.engine) == 8
    with store.engine.connect() as connection:
        assert connection.execute(select(schema_version.c.version)).scalar_one() == 8
        assert "grant_id" in {column["name"] for column in
                              inspect(store.engine).get_columns("gateway_oauth_tokens_v1")}
        token = connection.exec_driver_sql(
            "SELECT token_hash, grant_id FROM gateway_oauth_tokens_v1"
        ).one()
        assert token == ("token-hash", None)
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
