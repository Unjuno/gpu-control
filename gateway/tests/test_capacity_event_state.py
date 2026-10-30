import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
sys.path.insert(0, str(DEPLOY))

from capacity_event_state import (
    CapacityEventError, CapacityEventState, JournalPoller, JournalRetentionGap,
    JournalStateUninitialized,
    JournalctlSource,
)
from capacity_event_delivery import CapacityEventDeliveryPump
from capacity_event_bridge import main as capacity_bridge_main


def record(*, cursor="s=1", timestamp="1761600000000000", status="alert",
           journal_overrides=None, **overrides):
    event = {"check": "gpu-control-artifact-capacity", "status": status,
             "available": status == "ok",
             "reason": "below_minimum_free_bytes" if status == "alert" else None}
    if status == "ok":
        event.update(free_bytes=100, minimum_free_bytes=50)
    event.update(overrides)
    journal = {"SYSLOG_IDENTIFIER": "gpu-control-capacity",
               "_SYSTEMD_UNIT": "gpu-control-artifact-capacity.service",
               "__CURSOR": cursor, "__REALTIME_TIMESTAMP": timestamp,
               "MESSAGE": json.dumps(event)}
    journal.update(journal_overrides or {})
    return journal


def test_capacity_state_accepts_alert_then_clear_and_deduplicates(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    alert = state.accept(record())
    duplicate = state.accept(record())
    clear = state.accept(record(cursor="s=2", timestamp="1761600300000000", status="ok"))

    assert (alert.accepted, alert.transition) == (True, "alert")
    assert (duplicate.accepted, duplicate.transition) == (False, None)
    assert (clear.accepted, clear.transition) == (True, "ok")
    assert clear.current_status == "ok"


def test_capacity_state_accepts_journal_order_when_wall_clock_moves_backwards(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="before-clock-change", timestamp="1761600300000000"))

    after_clock_change = state.accept(record(
        cursor="after-clock-change", timestamp="1761600000000000", status="ok"))

    assert after_clock_change.accepted is True
    assert after_clock_change.transition == "ok"
    assert state.checkpoint_cursor() == "after-clock-change"


@pytest.mark.parametrize("changes", [
    {"SYSLOG_IDENTIFIER": "other"},
    {"_SYSTEMD_UNIT": "untrusted.service"},
    {"MESSAGE": "not-json"},
    {"__CURSOR": ""},
    {"__REALTIME_TIMESTAMP": "-1"},
])
def test_capacity_state_rejects_untrusted_or_malformed_journal_records(tmp_path, changes):
    journal_changes = {key: value for key, value in changes.items()
                       if key in {"SYSLOG_IDENTIFIER", "_SYSTEMD_UNIT"}}
    item = record(journal_overrides=journal_changes, **{
        key: value for key, value in changes.items()
        if key not in {"SYSLOG_IDENTIFIER", "_SYSTEMD_UNIT"}})
    with pytest.raises(CapacityEventError):
        CapacityEventState(tmp_path / "state.json").accept(item)


def test_capacity_state_rejects_user_supplied_unit_as_trusted_identity(tmp_path):
    item = record()
    item.pop("_SYSTEMD_UNIT")
    item["SYSTEMD_UNIT"] = "gpu-control-artifact-capacity.service"
    with pytest.raises(CapacityEventError):
        CapacityEventState(tmp_path / "state.json").accept(item)


class FakeJournalctl:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, args, **kwargs):
        from types import SimpleNamespace
        self.calls.append((args, kwargs))
        output = self.outputs.pop(0)
        return SimpleNamespace(returncode=0, stdout=output, stderr="")


def test_journal_poller_resumes_after_durable_cursor_with_fixed_bounded_query(tmp_path):
    previous = record(cursor="prior", timestamp="1761600000000000")
    next_record = record(cursor="next", timestamp="1761600000000001", status="ok")
    runner = FakeJournalctl(
        json.dumps({"__CURSOR": "prior"}) + "\n",
        json.dumps(next_record) + "\n",
        json.dumps({"__CURSOR": "prior"}) + "\n",
    )
    source = JournalctlSource(runner=runner, max_records=12)
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(previous)

    processed = JournalPoller(source, state).poll_once()

    assert len(processed) == 1 and processed[0].transition == "ok"
    query = runner.calls[1][0]
    assert "--after-cursor=prior" in query
    assert "--lines=+12" in query
    assert "--no-pager" in query and "--output=json" in query
    assert "--unit=gpu-control-artifact-capacity.service" in query
    assert "--identifier=gpu-control-capacity" in query
    assert runner.calls[1][1]["shell"] is False


def test_journal_poller_serializes_cursor_read_query_and_batch_application(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="initial", timestamp="1761600000000000"))
    first_query_entered = threading.Event()
    release_first_query = threading.Event()
    second_started = threading.Event()
    second_source_entered = threading.Event()
    second_cursors = []
    errors = []

    class FirstSource:
        def cursor_exists(self, cursor):
            assert cursor == "initial"
            return True

        def read_after(self, cursor):
            assert cursor == "initial"
            first_query_entered.set()
            if not release_first_query.wait(2):
                raise AssertionError("first poll was not released")
            return [record(cursor="clear", timestamp="1761600000000001", status="ok")]

    class SecondSource:
        def cursor_exists(self, cursor):
            second_source_entered.set()
            second_cursors.append(cursor)
            return True

        def read_after(self, cursor):
            second_cursors.append(cursor)
            return [record(cursor="later", timestamp="1761600000000002")]

    first_poller = JournalPoller(FirstSource(), state)
    second_poller = JournalPoller(SecondSource(), CapacityEventState(state.path))

    def poll(poller):
        try:
            poller.poll_once()
        except Exception as exc:  # surface worker-thread failures in the test thread
            errors.append(exc)

    first_thread = threading.Thread(target=poll, args=(first_poller,))
    second_thread = threading.Thread(
        target=lambda: (second_started.set(), poll(second_poller)))
    first_thread.start()
    assert first_query_entered.wait(1)
    second_thread.start()
    assert second_started.wait(1)
    assert not second_source_entered.wait(0.1)

    release_first_query.set()
    first_thread.join(3)
    second_thread.join(3)

    assert not first_thread.is_alive() and not second_thread.is_alive()
    assert errors == []
    assert second_cursors == ["clear", "clear", "clear"]
    assert state.checkpoint_cursor() == "later"
    assert state.delivery_health()["current_status"] == "alert"


def test_journal_poll_lock_excludes_a_separate_process(tmp_path):
    state_path = tmp_path / "state.json"
    state = CapacityEventState(state_path)
    state.accept(record(cursor="initial"))
    lock_path = tmp_path / ".state.json.poll.lock"
    child_blocked = tmp_path / "child-blocked"
    child_acquired = tmp_path / "child-acquired"
    child_unexpectedly_acquired = tmp_path / "child-unexpectedly-acquired"
    child_script = r'''
import fcntl
import os
from pathlib import Path
import sys
from capacity_event_state import CapacityEventState

fd = os.open(sys.argv[2], os.O_RDWR)
try:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        Path(sys.argv[3]).touch()
        with CapacityEventState(sys.argv[1])._poll_lock():
            Path(sys.argv[4]).touch()
    else:
        Path(sys.argv[5]).touch()
finally:
    os.close(fd)
'''
    child = None
    try:
        with state._poll_lock():
            child = subprocess.Popen(
                [sys.executable, "-c", child_script, str(state_path),
                 str(lock_path), str(child_blocked), str(child_acquired),
                 str(child_unexpectedly_acquired)],
                env={**os.environ, "PYTHONPATH": str(DEPLOY)},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 3
            while not child_blocked.exists() and child.poll() is None and \
                    time.monotonic() < deadline:
                time.sleep(0.01)
            assert child_blocked.exists(), "child did not observe the held process lock"
            assert not child_acquired.exists()
            assert not child_unexpectedly_acquired.exists()

        assert child.wait(timeout=3) == 0
        assert child_acquired.exists()
        assert not child_unexpectedly_acquired.exists()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=3)


def test_capacity_delivery_lock_excludes_a_separate_process(tmp_path):
    state_path = tmp_path / "state.json"
    state = CapacityEventState(state_path)
    lock_path = tmp_path / ".state.json.delivery.lock"
    child_blocked = tmp_path / "delivery-child-blocked"
    child_acquired = tmp_path / "delivery-child-acquired"
    child_unexpectedly_acquired = tmp_path / "delivery-child-unexpectedly-acquired"
    child_script = r'''
import fcntl
import os
from pathlib import Path
import sys
from capacity_event_state import CapacityEventState

fd = os.open(sys.argv[2], os.O_RDWR)
try:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        Path(sys.argv[3]).touch()
        with CapacityEventState(sys.argv[1])._delivery_lock():
            Path(sys.argv[4]).touch()
    else:
        Path(sys.argv[5]).touch()
finally:
    os.close(fd)
'''
    child = None
    try:
        with state._delivery_lock():
            child = subprocess.Popen(
                [sys.executable, "-c", child_script, str(state_path),
                 str(lock_path), str(child_blocked), str(child_acquired),
                 str(child_unexpectedly_acquired)],
                env={**os.environ, "PYTHONPATH": str(DEPLOY)},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 3
            while not child_blocked.exists() and child.poll() is None and \
                    time.monotonic() < deadline:
                time.sleep(0.01)
            assert child_blocked.exists(), "child did not observe the held delivery lock"
            assert not child_acquired.exists()
            assert not child_unexpectedly_acquired.exists()

        assert child.wait(timeout=3) == 0
        assert child_acquired.exists()
        assert not child_unexpectedly_acquired.exists()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=3)


def test_journal_poller_fails_unknown_if_checkpoint_was_vacuumed(tmp_path):
    runner = FakeJournalctl(json.dumps({"__CURSOR": "other-cursor"}) + "\n")
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="missing", timestamp="1761600000000000"))

    with pytest.raises(JournalRetentionGap):
        JournalPoller(JournalctlSource(runner=runner), state).poll_once()
    assert state._read()["cursor"] == "missing"
    assert state.delivery_records()[0]["state"] == "pending"


def test_journal_poller_explicitly_reconciles_retention_gap_and_preserves_outbox(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="expired-alert", status="alert"))
    latest = record(cursor="retained-ok", timestamp="1761600000000001", status="ok")

    class ExpiredCursorSource:
        def __init__(self):
            self.cursor_checks = 0
            self.reads = []

        def cursor_exists(self, cursor):
            assert cursor == "expired-alert"
            self.cursor_checks += 1
            return False

        def read_after(self, cursor):
            self.reads.append(cursor)
            assert cursor is None
            return [latest]

    source = ExpiredCursorSource()
    result = JournalPoller(source, state).reconcile_latest()

    assert result.accepted is True
    assert result.transition == "reconciled_ok"
    assert source.cursor_checks == 2
    assert source.reads == [None]
    assert state.checkpoint_cursor() == "retained-ok"
    deliveries = state.delivery_records()
    assert [item["cursor"] for item in deliveries] == ["expired-alert", "retained-ok"]
    assert all(item["state"] == "pending" for item in deliveries)


def test_journal_poller_reconciliation_reannounces_same_current_status(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="expired-alert", status="alert"))
    latest = record(cursor="latest-alert", status="alert")

    class ExpiredCursorSource:
        def cursor_exists(self, cursor):
            return False

        def read_after(self, cursor):
            assert cursor is None
            return [latest]

    result = JournalPoller(ExpiredCursorSource(), state).reconcile_latest()

    assert result.transition == "reconciled_alert"
    assert [item["cursor"] for item in state.delivery_records()] == [
        "expired-alert", "latest-alert"]


def test_journal_poller_refuses_reconcile_while_checkpoint_is_retained(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="still-retained"))

    class RetainedCursorSource:
        def cursor_exists(self, cursor):
            assert cursor == "still-retained"
            return True

        def read_after(self, cursor):
            raise AssertionError("must not read latest state during normal recovery")

    with pytest.raises(CapacityEventError, match="journal_checkpoint_still_retained"):
        JournalPoller(RetainedCursorSource(), state).reconcile_latest()

    assert state.checkpoint_cursor() == "still-retained"
    assert [item["cursor"] for item in state.delivery_records()] == ["still-retained"]


def test_capacity_bridge_cli_reports_explicit_reconciliation(tmp_path, capsys):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="expired", status="alert"))
    latest = record(cursor="current", timestamp="1761600000000001", status="ok")
    runner = FakeJournalctl(
        json.dumps({"__CURSOR": "another-retained-cursor"}) + "\n",
        json.dumps(latest) + "\n",
        json.dumps({"__CURSOR": "another-retained-cursor"}) + "\n",
    )
    source = JournalctlSource(runner=runner)

    result = capacity_bridge_main(
        ["--reconcile-latest", "--state-path", str(tmp_path / "state.json")],
        source_factory=lambda: source,
        state_factory=lambda _path: state,
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["reconciled"] is True
    assert output["reconciled_status"] == "ok"
    assert output["health"]["pending"] == 2


def test_capacity_bridge_health_cli_is_journal_free_and_redacted(tmp_path, capsys):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="private-cursor-value", status="alert"))

    def unexpected_journal_access():
        raise AssertionError("health query must not access journald")

    result = capacity_bridge_main(
        ["--show-health", "--state-path", str(tmp_path / "state.json")],
        source_factory=unexpected_journal_access,
        state_factory=lambda _path: state,
    )

    output_text = capsys.readouterr().out
    output = json.loads(output_text)
    assert result == 0
    assert output["health"]["initialized"] is True
    assert output["health"]["pending"] == 1
    assert "private-cursor-value" not in output_text
    assert "below_minimum_free_bytes" not in output_text


def test_capacity_bridge_health_cli_redacts_corrupt_state_errors(tmp_path, capsys):
    state_path = tmp_path / "state.json"
    state_path.write_text("{invalid json", encoding="utf-8")
    state_path.chmod(0o600)

    def unexpected_journal_access():
        raise AssertionError("health query must not access journald")

    result = capacity_bridge_main(
        ["--show-health", "--state-path", str(state_path)],
        source_factory=unexpected_journal_access,
        state_factory=lambda path: CapacityEventState(path),
    )

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert captured.err.strip() == "capacity_bridge_result=journal_or_state_error"
    assert str(state_path) not in captured.err
    assert "invalid json" not in captured.err


def test_journal_poller_bootstraps_from_latest_capacity_event_only(tmp_path):
    latest = record(cursor="latest", timestamp="1761600000000000")
    runner = FakeJournalctl(json.dumps(latest) + "\n")
    source = JournalctlSource(runner=runner, max_records=5)
    state = CapacityEventState(tmp_path / "state.json")

    processed = JournalPoller(source, state).bootstrap_latest()

    assert processed[0].transition == "alert"
    query = runner.calls[0][0]
    assert "--lines=1" in query
    assert not any(arg.startswith("--after-cursor=") for arg in query)


def test_journal_poller_requires_explicit_bootstrap_when_checkpoint_is_absent(tmp_path):
    runner = FakeJournalctl(json.dumps(record(cursor="latest")) + "\n")
    state = CapacityEventState(tmp_path / "state.json")

    with pytest.raises(JournalStateUninitialized):
        JournalPoller(JournalctlSource(runner=runner), state).poll_once()
    assert runner.calls == []
    assert state.checkpoint_cursor() is None


def test_initial_ok_bootstrap_sets_baseline_without_creating_clear_delivery(tmp_path):
    latest = record(cursor="latest", status="ok")
    runner = FakeJournalctl(json.dumps(latest) + "\n")
    state = CapacityEventState(tmp_path / "state.json")

    processed = JournalPoller(JournalctlSource(runner=runner), state).bootstrap_latest()

    assert processed[0].transition is None
    assert state.checkpoint_cursor() == "latest"
    assert state.delivery_records() == []


def test_capacity_state_rejects_schema_extensions_and_replayed_old_events(tmp_path):
    path = tmp_path / "state.json"
    state = CapacityEventState(path)
    state.accept(record(cursor="old", timestamp="1761600000000001"))
    state.accept(record(cursor="new", timestamp="1761600000000002", status="ok"))
    with pytest.raises(CapacityEventError):
        state.accept(record(cursor="bad", timestamp="1761600000000003", extra="secret"))

    restarted = CapacityEventState(path)
    older = restarted.accept(record(cursor="old", timestamp="1761600000000003"))
    assert (older.accepted, older.transition, older.current_status) == (False, None, "ok")


def test_capacity_state_rejects_unrecognized_reason_text(tmp_path):
    item = record(reason="/private/path secret=do-not-persist")
    with pytest.raises(CapacityEventError):
        CapacityEventState(tmp_path / "state.json").accept(item)


def test_capacity_state_rejects_duplicate_json_keys(tmp_path):
    item = record()
    item["MESSAGE"] = ('{"check":"gpu-control-artifact-capacity",'
                       '"status":"alert","status":"alert",'
                       '"available":false,"reason":"below_minimum_free_bytes"}')
    with pytest.raises(CapacityEventError):
        CapacityEventState(tmp_path / "state.json").accept(item)


def test_capacity_state_fails_closed_on_corrupt_persisted_state(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"timestamp_us":1,"cursor":"x","event":{}}')
    path.chmod(0o600)
    with pytest.raises(CapacityEventError):
        CapacityEventState(path).accept(record(cursor="next", timestamp="2"))


def test_capacity_state_persists_pending_delivery_and_attempt_before_ack(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    event = record(cursor="alert-1")
    accepted = state.accept(event)

    pending = state.pending_deliveries()
    assert len(pending) == 1
    assert pending[0]["cursor"] == "alert-1"
    assert pending[0]["attempt_history"] == []
    assert state.record_delivery_attempt(
        "alert-1", "retryable_failure", attempted_at_us=1761600000500000) == "pending"
    assert len(state.pending_deliveries()[0]["attempt_history"]) == 1

    restarted = CapacityEventState(tmp_path / "state.json")
    assert restarted.pending_deliveries()[0]["attempt_history"][0]["result"] == "retryable_failure"
    assert restarted.record_delivery_attempt(
        "alert-1", "delivered", attempted_at_us=1761600000400000,
        acknowledged_at_us=1761600000400000) == "acknowledged"
    assert restarted.pending_deliveries() == []


def test_capacity_state_does_not_advance_cursor_if_delivery_journal_is_full(tmp_path):
    from capacity_event_state import MAX_DELIVERY_HISTORY

    state = CapacityEventState(tmp_path / "state.json")
    for index in range(MAX_DELIVERY_HISTORY):
        state.accept(record(cursor=f"alert-{index}", timestamp=str(1761600000000000 + index),
                            status="alert" if index % 2 == 0 else "ok"))
    with pytest.raises(CapacityEventError):
        state.accept(record(cursor="overflow", timestamp=str(1761600000000000 + MAX_DELIVERY_HISTORY),
                            status="alert" if MAX_DELIVERY_HISTORY % 2 == 0 else "ok"))
    state = CapacityEventState(tmp_path / "state.json")
    assert state._read()["cursor"] == f"alert-{MAX_DELIVERY_HISTORY - 1}"


def test_capacity_state_rejects_acknowledged_record_without_successful_attempt(tmp_path):
    path = tmp_path / "state.json"
    CapacityEventState(path).accept(record(cursor="alert-1"))
    payload = json.loads(path.read_text())
    payload["deliveries"][0]["state"] = "acknowledged"
    path.write_text(json.dumps(payload))
    path.chmod(0o600)
    with pytest.raises(CapacityEventError):
        CapacityEventState(path).delivery_records()
    with pytest.raises(CapacityEventError):
        CapacityEventState(path).record_delivery_attempt(
            "alert-1", "delivered", attempted_at_us=20, acknowledged_at_us=20)


def test_capacity_state_serializes_concurrent_checkpoint_updates(tmp_path):
    path = tmp_path / "state.json"
    CapacityEventState(path).accept(record(cursor="base", status="ok"))
    older_state = CapacityEventState(path)
    newer_state = CapacityEventState(path)
    old_write_started = threading.Event()
    release_old_write = threading.Event()
    newer_started = threading.Event()
    newer_done = threading.Event()
    failures = []
    original_write = older_state._write

    def delayed_old_write(value):
        old_write_started.set()
        if not release_old_write.wait(3):
            raise AssertionError("timed out waiting to serialize old event")
        original_write(value)

    older_state._write = delayed_old_write

    def accept_old():
        try:
            older_state.accept(record(cursor="older", timestamp="1761600000000001"))
        except Exception as exc:
            failures.append(exc)

    def accept_newer():
        newer_started.set()
        try:
            newer_state.accept(record(cursor="newer", timestamp="1761600000000002", status="ok"))
        except Exception as exc:
            failures.append(exc)
        finally:
            newer_done.set()

    older_thread = threading.Thread(target=accept_old)
    newer_thread = threading.Thread(target=accept_newer)
    older_thread.start()
    assert old_write_started.wait(2)
    newer_thread.start()
    assert newer_started.wait(2)
    # With the state lock, the newer writer is waiting for the old write.
    # Without it, the newer snapshot commits first and the old snapshot wins.
    newer_done.wait(0.1)
    release_old_write.set()
    older_thread.join(3)
    newer_thread.join(3)

    assert not older_thread.is_alive() and not newer_thread.is_alive()
    assert failures == []
    assert CapacityEventState(path).checkpoint_cursor() == "newer"


def test_capacity_state_preserves_write_oserror_and_releases_lock(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")

    def fail_write(_value):
        raise OSError("disk full")

    state._write = fail_write
    with pytest.raises(OSError, match="disk full"):
        state.accept(record(cursor="failed-write"))

    # The failed protected operation must not leave the file lock held.
    recovered = CapacityEventState(tmp_path / "state.json")
    assert recovered.accept(record(cursor="recovered-write")).accepted is True


def test_capacity_state_bounds_retries_and_retains_exhausted_delivery(tmp_path):
    from capacity_event_state import MAX_DELIVERY_ATTEMPTS

    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="alert-1"))
    for _ in range(MAX_DELIVERY_ATTEMPTS):
        result = state.record_delivery_attempt(
            "alert-1", "retryable_failure", attempted_at_us=1761600001000000)
    assert result == "exhausted"
    assert state.pending_deliveries() == []
    assert state.delivery_records()[0]["state"] == "exhausted"
    assert len(state.delivery_records()[0]["attempt_history"]) == MAX_DELIVERY_ATTEMPTS


class FakeCapacitySender:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def send(self, message, *, idempotency_key, source_timestamp_us):
        self.calls.append((message, idempotency_key, source_timestamp_us))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClock:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


def test_capacity_delivery_pump_sends_fixed_payload_and_persists_ack(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="alert-cursor", free_bytes=10, minimum_free_bytes=20))
    sender = FakeCapacitySender("delivered")
    pump = CapacityEventDeliveryPump(
        state, sender, clock_us=FakeClock(100, 101), batch_limit=4)

    result = pump.run_once()

    assert result.attempted == result.delivered == 1
    message, idempotency_key, source_timestamp_us = sender.calls[0]
    assert message == {
        "check": "gpu-control-artifact-capacity", "status": "alert",
        "reason": "below_minimum_free_bytes", "free_bytes": 10,
        "minimum_free_bytes": 20,
    }
    assert idempotency_key == "alert-cursor"
    assert source_timestamp_us == 1761600000000000
    assert state.delivery_records()[0]["state"] == "acknowledged"


def test_capacity_delivery_pump_honors_retry_backoff(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="retry-cursor"))
    sender = FakeCapacitySender("retryable_failure", "delivered")
    pump = CapacityEventDeliveryPump(state, sender, clock_us=FakeClock(10, 10))

    first = pump.run_once()
    too_early = state.due_deliveries(now_us=10 + 4_999_999)
    due = state.due_deliveries(now_us=10 + 5_000_000)
    second = CapacityEventDeliveryPump(
        state, sender, clock_us=FakeClock(10 + 5_000_000, 10 + 5_000_001))
    second_result = second.run_once()

    assert first.pending == 1
    assert too_early == []
    assert [item["cursor"] for item in due] == ["retry-cursor"]
    assert second_result.delivered == 1
    assert sender.calls[0][1] == sender.calls[1][1] == "retry-cursor"


def test_capacity_delivery_pump_keeps_later_clear_behind_alert_retry(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    state.accept(record(cursor="ordered-alert", status="alert"))
    state.accept(record(cursor="ordered-clear", status="ok",
                        timestamp="1761600000000001"))
    sender = FakeCapacitySender("retryable_failure", "delivered", "delivered")

    first = CapacityEventDeliveryPump(
        state, sender, clock_us=FakeClock(100, 100), batch_limit=8).run_once()
    during_backoff = CapacityEventDeliveryPump(
        state, sender, clock_us=FakeClock(100 + 4_999_999), batch_limit=8).run_once()
    after_backoff = CapacityEventDeliveryPump(
        state, sender,
        clock_us=FakeClock(100 + 5_000_000, 100 + 5_000_001,
                           100 + 5_000_002, 100 + 5_000_003),
        batch_limit=8).run_once()

    assert first.attempted == first.pending == 1
    assert during_backoff.attempted == 0
    assert after_backoff.attempted == after_backoff.delivered == 2
    assert [call[1] for call in sender.calls] == [
        "ordered-alert", "ordered-alert", "ordered-clear"]


def test_capacity_delivery_pump_redacts_sender_exception(tmp_path):
    path = tmp_path / "state.json"
    state = CapacityEventState(path)
    state.accept(record(cursor="exception-cursor"))
    sender = FakeCapacitySender(RuntimeError("token=do-not-persist"))
    result = CapacityEventDeliveryPump(
        state, sender, clock_us=FakeClock(100)).run_once()

    assert result.pending == 1
    assert "do-not-persist" not in path.read_text()
    assert state.delivery_records()[0]["attempt_history"][0]["result"] == "retryable_failure"


def test_capacity_delivery_health_exposes_only_bounded_counters(tmp_path):
    state = CapacityEventState(tmp_path / "state.json")
    assert state.delivery_health() == {
        "initialized": False, "current_status": None,
        "pending": 0, "acknowledged": 0, "exhausted": 0,
        "delivery_attempts": 0, "delivered_attempts": 0,
        "retryable_failures": 0, "permanent_failures": 0,
    }
    state.accept(record(cursor="health-cursor"))
    state.record_delivery_attempt(
        "health-cursor", "retryable_failure", attempted_at_us=100)
    health = state.delivery_health()

    assert health == {
        "initialized": True, "current_status": "alert",
        "pending": 1, "acknowledged": 0, "exhausted": 0,
        "delivery_attempts": 1, "delivered_attempts": 0,
        "retryable_failures": 1, "permanent_failures": 0,
    }
    assert "cursor" not in health and "event" not in health


def test_capacity_bridge_cli_requires_explicit_bootstrap_and_hides_cursor(tmp_path, capsys):
    latest = record(cursor="private-journal-cursor")
    runner = FakeJournalctl(json.dumps(latest) + "\n")

    result = capacity_bridge_main(
        ["--bootstrap-latest", "--state-path", str(tmp_path / "bridge.json")],
        source_factory=lambda: JournalctlSource(runner=runner),
    )

    output = capsys.readouterr().out
    assert result == 0
    assert '"initialized":true' in output
    assert '"pending":1' in output
    assert "private-journal-cursor" not in output
    assert '"event"' not in output


def test_capacity_bridge_cli_refuses_implicit_bootstrap(tmp_path, capsys):
    runner = FakeJournalctl(json.dumps(record()) + "\n")

    result = capacity_bridge_main(
        ["--poll-once", "--state-path", str(tmp_path / "bridge.json")],
        source_factory=lambda: JournalctlSource(runner=runner),
    )

    output = capsys.readouterr()
    assert result == 4
    assert "capacity_bridge_result=bootstrap_required" in output.err
    assert runner.calls == []


def test_capacity_state_file_is_private_and_rejects_symlink(tmp_path):
    path = tmp_path / "state.json"
    CapacityEventState(path).accept(record())
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".state.json.lock").stat().st_mode & 0o777 == 0o600

    target = tmp_path / "target"
    target.write_text("{}")
    link = tmp_path / "linked-state"
    link.symlink_to(target)
    with pytest.raises(CapacityEventError):
        CapacityEventState(link).accept(record())
    assert target.read_text() == "{}"
