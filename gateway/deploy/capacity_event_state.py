"""Validate and durably deduplicate capacity journal events.

This module has no notification sink or provider integration. It stores only
the normalized, schema-bounded status needed by a future host-local bridge.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess


class CapacityEventError(ValueError):
    pass


class JournalRetentionGap(CapacityEventError):
    """The persisted checkpoint no longer exists in the retained journal."""


class JournalStateUninitialized(CapacityEventError):
    """An explicit bootstrap is required before consuming new journal events."""


class JournalCheckpointStillRetained(CapacityEventError):
    """Explicit gap reconciliation is only valid after cursor retention loss."""


_ALERT_REASONS = frozenset({
    "invalid_minimum_free_bytes", "invalid_artifact_path", "symlink",
    "not_directory", "not_dedicated_filesystem", "below_minimum_free_bytes",
    "probe_failed",
})
MAX_DELIVERY_HISTORY = 64
MAX_DELIVERY_ATTEMPTS = 8
MAX_SEEN_CURSORS = 256
DELIVERY_RETRY_BASE_SECONDS = 5
DELIVERY_RETRY_MAX_SECONDS = 3600
_DELIVERY_RESULTS = frozenset({"delivered", "retryable_failure", "permanent_failure"})
MAX_CAPACITY_SOURCE_RECORDS = 256


class CapacityEventFileSource:
    """Read the bounded capacity-only event spool shared with the monitor."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _records(self) -> list[dict]:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(self.path, flags)
        except OSError as exc:
            raise CapacityEventError("capacity_event_file_unavailable") from exc
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or
                    stat.S_IMODE(info.st_mode) & 0o640 != 0o640 or
                    stat.S_IMODE(info.st_mode) & 0o027 or info.st_size > 1_048_576):
                raise CapacityEventError("capacity_event_file_permissions_invalid")
            with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as source:
                try:
                    value = json.load(source, object_pairs_hook=_object_without_duplicates)
                except (OSError, ValueError, UnicodeError) as exc:
                    raise CapacityEventError("capacity_event_file_invalid") from exc
        except OSError as exc:
            raise CapacityEventError("capacity_event_file_unreadable") from exc
        finally:
            os.close(fd)
        if (not isinstance(value, dict) or set(value) != {"version", "records"} or
                value["version"] != 1 or not isinstance(value["records"], list) or
                not 1 <= len(value["records"]) <= MAX_CAPACITY_SOURCE_RECORDS):
            raise CapacityEventError("capacity_event_file_invalid")
        previous = 0
        for item in value["records"]:
            if (not isinstance(item, dict) or set(item) != {"cursor", "timestamp_us", "event"} or
                    not isinstance(item["cursor"], str) or not item["cursor"].isascii() or
                    not item["cursor"].isdigit() or len(item["cursor"]) > 20 or
                    int(item["cursor"]) <= previous or type(item["timestamp_us"]) is not int or
                    item["timestamp_us"] < 0 or not isinstance(item["event"], dict)):
                raise CapacityEventError("capacity_event_file_invalid")
            _validate_event(item["event"])
            previous = int(item["cursor"])
        return value["records"]

    @staticmethod
    def _journal_record(item: dict) -> dict:
        return {
            "SYSLOG_IDENTIFIER": "gpu-control-capacity",
            "_SYSTEMD_UNIT": "gpu-control-artifact-capacity.service",
            "__CURSOR": item["cursor"],
            "__REALTIME_TIMESTAMP": str(item["timestamp_us"]),
            "MESSAGE": json.dumps(item["event"], sort_keys=True, separators=(",", ":")),
        }

    def cursor_exists(self, cursor: str) -> bool:
        if not isinstance(cursor, str) or not cursor.isascii() or not cursor.isdigit():
            raise CapacityEventError("capacity_cursor_invalid")
        return any(item["cursor"] == cursor for item in self._records())

    def read_after(self, cursor: str | None) -> list[dict]:
        records = self._records()
        if cursor is None:
            return [self._journal_record(records[-1])]
        index = next((i for i, item in enumerate(records) if item["cursor"] == cursor), None)
        if index is None:
            raise JournalRetentionGap("capacity_checkpoint_expired")
        return [self._journal_record(item) for item in records[index + 1:]]


@dataclass(frozen=True)
class AcceptedEvent:
    accepted: bool
    transition: str | None
    current_status: str | None
    event: dict | None = None


def _normalized_record(record: object) -> tuple[int, str, dict]:
    if not isinstance(record, dict):
        raise CapacityEventError("journal_record_invalid")
    if (record.get("SYSLOG_IDENTIFIER") != "gpu-control-capacity" or
            record.get("_SYSTEMD_UNIT") != "gpu-control-artifact-capacity.service"):
        raise CapacityEventError("journal_identity_invalid")
    cursor = record.get("__CURSOR")
    timestamp = record.get("__REALTIME_TIMESTAMP")
    message = record.get("MESSAGE")
    if (not isinstance(cursor, str) or not cursor or len(cursor) > 4096 or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in cursor)):
        raise CapacityEventError("journal_cursor_invalid")
    if (not isinstance(timestamp, str) or not timestamp.isascii() or
            not timestamp.isdigit() or len(timestamp) > 20):
        raise CapacityEventError("journal_timestamp_invalid")
    if not isinstance(message, str) or len(message.encode("utf-8")) > 4096:
        raise CapacityEventError("capacity_message_invalid")
    try:
        event = json.loads(message, object_pairs_hook=_object_without_duplicates)
    except (ValueError, UnicodeError) as exc:
        raise CapacityEventError("capacity_message_invalid") from exc
    _validate_event(event)
    return int(timestamp), cursor, event


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CapacityEventError("capacity_event_duplicate_key")
        result[key] = value
    return result


def _validate_event(event: object) -> None:
    if not isinstance(event, dict) or set(event) - {
            "check", "status", "available", "reason", "free_bytes", "minimum_free_bytes"}:
        raise CapacityEventError("capacity_event_schema_invalid")

    status = event.get("status")
    if event.get("check") != "gpu-control-artifact-capacity":
        raise CapacityEventError("capacity_event_schema_invalid")
    if status == "alert":
        reason = event.get("reason")
        if (event.get("available") is not False or not isinstance(reason, str) or
                reason not in _ALERT_REASONS):
            raise CapacityEventError("capacity_event_schema_invalid")
        if any(key in event for key in ("free_bytes", "minimum_free_bytes")):
            if (type(event.get("free_bytes")) is not int or event["free_bytes"] < 0 or
                    type(event.get("minimum_free_bytes")) is not int or
                    event["minimum_free_bytes"] <= 0):
                raise CapacityEventError("capacity_event_schema_invalid")
    elif status == "ok":
        if (event.get("available") is not True or event.get("reason") is not None or
                type(event.get("free_bytes")) is not int or event["free_bytes"] < 0 or
                type(event.get("minimum_free_bytes")) is not int or
                event["minimum_free_bytes"] <= 0):
            raise CapacityEventError("capacity_event_schema_invalid")
    else:
        raise CapacityEventError("capacity_event_schema_invalid")


def validate_capacity_event(event: object) -> None:
    """Validate a producer event against the same bounded bridge contract."""
    _validate_event(event)


class JournalctlSource:
    """Bounded read-only journald adapter using fixed journalctl arguments."""

    _FIELDS = "__CURSOR,__REALTIME_TIMESTAMP,SYSLOG_IDENTIFIER,_SYSTEMD_UNIT,MESSAGE"

    def __init__(self, *, binary: str = "/usr/bin/journalctl", timeout_seconds: int = 15,
                 max_records: int = 128, runner=subprocess.run):
        if not isinstance(binary, str) or not binary.startswith("/"):
            raise ValueError("journalctl_binary_must_be_absolute")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
            raise ValueError("journalctl_timeout_invalid")
        if type(max_records) is not int or not 1 <= max_records <= 256:
            raise ValueError("journalctl_batch_size_invalid")
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.max_records = max_records
        self.runner = runner

    @staticmethod
    def _decode_lines(stdout: object) -> list[dict]:
        if not isinstance(stdout, str):
            raise CapacityEventError("journalctl_output_invalid")
        records = []
        for line in stdout.splitlines():
            if not line:
                continue
            try:
                record = json.loads(line, object_pairs_hook=_object_without_duplicates)
            except (ValueError, UnicodeError) as exc:
                raise CapacityEventError("journalctl_output_invalid") from exc
            if not isinstance(record, dict):
                raise CapacityEventError("journalctl_output_invalid")
            records.append(record)
        return records

    def _run(self, args: list[str]) -> list[dict]:
        try:
            result = self.runner(
                [self.binary, *args], shell=False, capture_output=True, text=True,
                timeout=self.timeout_seconds,
                env={"LC_ALL": "C", "PATH": "/usr/bin:/bin", "SYSTEMD_COLORS": "0",
                     "SYSTEMD_PAGER": "cat", "SYSTEMD_URLIFY": "0"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CapacityEventError("journalctl_unavailable") from exc
        if getattr(result, "returncode", 1) != 0:
            raise CapacityEventError("journalctl_failed")
        return self._decode_lines(getattr(result, "stdout", None))

    def cursor_exists(self, cursor: str) -> bool:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 4096:
            raise CapacityEventError("journal_cursor_invalid")
        records = self._run([
            "--no-pager", "--quiet", "--output=json", "--output-fields=__CURSOR",
            "--lines=+1", f"--cursor={cursor}",
        ])
        return bool(records) and records[0].get("__CURSOR") == cursor

    def read_after(self, cursor: str | None) -> list[dict]:
        args = ["--no-pager", "--quiet", "--output=json",
                f"--output-fields={self._FIELDS}",
                "--identifier=gpu-control-capacity",
                "--unit=gpu-control-artifact-capacity.service"]
        if cursor is None:
            # Establish a bounded current-state baseline instead of replaying
            # the host's entire historical journal on first installation.
            args.append("--lines=1")
        else:
            args.extend((f"--after-cursor={cursor}", f"--lines=+{self.max_records}"))
        records = self._run(args)
        if len(records) > (1 if cursor is None else self.max_records):
            raise CapacityEventError("journalctl_batch_limit_exceeded")
        return records


class JournalPoller:
    """Resume only from a retained checkpoint; never infer a clear on a gap."""

    def __init__(self, source: CapacityEventFileSource | JournalctlSource,
                 state: "CapacityEventState"):
        self.source = source
        self.state = state

    def poll_once(self) -> list["AcceptedEvent"]:
        # Serialize the entire read/query/apply transaction across processes.
        # The per-write state lock alone is insufficient: a delayed poller
        # could otherwise apply an older event after another poller advanced
        # the checkpoint beyond the deduplication window.
        with self.state._poll_lock():
            cursor = self.state.checkpoint_cursor()
            if cursor is None:
                raise JournalStateUninitialized("journal_state_requires_bootstrap")
            if not self.source.cursor_exists(cursor):
                raise JournalRetentionGap("journal_checkpoint_expired")
            records = self.source.read_after(cursor)
            # Recheck after reading to detect retention racing the query before
            # advancing any event/outbox state.
            if not self.source.cursor_exists(cursor):
                raise JournalRetentionGap("journal_checkpoint_expired")
            return [self.state.accept(record) for record in records]

    def bootstrap_latest(self) -> list["AcceptedEvent"]:
        with self.state._poll_lock():
            if self.state.checkpoint_cursor() is not None:
                raise CapacityEventError("journal_state_already_initialized")
            records = self.source.read_after(None)
            if len(records) != 1:
                raise JournalStateUninitialized("journal_baseline_unavailable")
            return [self.state.accept(records[0])]

    def reconcile_latest(self) -> "AcceptedEvent":
        """Explicitly rebase after retention loss, preserving pending deliveries.

        The latest retained status is emitted as a fresh notification even if
        it matches the last known status: events may have been missed during
        the gap. The operator must review this reconciliation output.
        """
        with self.state._poll_lock():
            cursor = self.state.checkpoint_cursor()
            if cursor is None:
                raise JournalStateUninitialized("journal_state_requires_bootstrap")
            if self.source.cursor_exists(cursor):
                raise JournalCheckpointStillRetained("journal_checkpoint_still_retained")
            records = self.source.read_after(None)
            if len(records) != 1:
                raise JournalStateUninitialized("journal_reconciliation_baseline_unavailable")
            if self.source.cursor_exists(cursor):
                raise JournalRetentionGap("journal_checkpoint_retention_raced_reconcile")
            return self.state.accept_reconciled(records[0])


class CapacityEventState:
    """Atomic 0600 state file for the latest accepted event and alert status."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def _exclusive_lock(self, *, suffix: str, error_prefix: str):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_component = f".{self.path.name}"
        if suffix:
            lock_component += f".{suffix}"
        lock_path = self.path.with_name(f"{lock_component}.lock")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            raise CapacityEventError(f"{error_prefix}_lock_unavailable") from exc
        try:
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
                    raise CapacityEventError(f"{error_prefix}_lock_permissions_invalid")
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as exc:
                raise CapacityEventError(f"{error_prefix}_lock_failed") from exc
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)

    def _file_lock(self):
        return self._exclusive_lock(suffix="", error_prefix="state")

    def _poll_lock(self):
        """Serialize cursor read, journal query, and complete poll application."""
        return self._exclusive_lock(suffix="poll", error_prefix="poll")

    def _delivery_lock(self):
        """Serialize delivery selection, network send, and acknowledgement."""
        return self._exclusive_lock(suffix="delivery", error_prefix="delivery")

    def _read(self) -> dict | None:
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            raise CapacityEventError("state_file_not_regular")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise CapacityEventError("state_file_permissions_invalid")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise CapacityEventError("state_file_unreadable") from exc
        if (not isinstance(value, dict) or set(value) != {
                "timestamp_us", "cursor", "event", "deliveries", "seen_cursors"} or
                type(value["timestamp_us"]) is not int or value["timestamp_us"] < 0 or
                not isinstance(value["cursor"], str) or not value["cursor"] or
                len(value["cursor"]) > 4096 or not isinstance(value["event"], dict) or
                not isinstance(value["deliveries"], list) or
                len(value["deliveries"]) > MAX_DELIVERY_HISTORY or
                not isinstance(value["seen_cursors"], list) or
                not 1 <= len(value["seen_cursors"]) <= MAX_SEEN_CURSORS or
                any(not isinstance(cursor, str) or not cursor or len(cursor) > 4096
                    for cursor in value["seen_cursors"]) or
                len(set(value["seen_cursors"])) != len(value["seen_cursors"]) or
                value["seen_cursors"][-1] != value["cursor"]):
            raise CapacityEventError("state_file_invalid")
        try:
            _validate_event(value["event"])
            for delivery in value["deliveries"]:
                self._validate_delivery(delivery)
        except CapacityEventError as exc:
            raise CapacityEventError("state_file_invalid") from exc
        return value

    def checkpoint_cursor(self) -> str | None:
        state = self._read()
        return None if state is None else state["cursor"]

    @staticmethod
    def _validate_delivery(delivery: object) -> None:
        if (not isinstance(delivery, dict) or set(delivery) != {
                "timestamp_us", "cursor", "event", "attempt_history", "state"} or
                type(delivery["timestamp_us"]) is not int or delivery["timestamp_us"] < 0 or
                not isinstance(delivery["cursor"], str) or not delivery["cursor"] or
                len(delivery["cursor"]) > 4096 or not isinstance(delivery["event"], dict) or
                not isinstance(delivery["attempt_history"], list) or
                len(delivery["attempt_history"]) > MAX_DELIVERY_ATTEMPTS or
                not isinstance(delivery["state"], str) or
                delivery["state"] not in {"pending", "acknowledged", "exhausted"}):
            raise CapacityEventError("delivery_state_invalid")
        _validate_event(delivery["event"])
        for attempt in delivery["attempt_history"]:
            if (not isinstance(attempt, dict) or set(attempt) != {
                    "attempted_at_us", "result", "acknowledged_at_us"} or
                    type(attempt["attempted_at_us"]) is not int or attempt["attempted_at_us"] < 0 or
                    not isinstance(attempt["result"], str) or
                    attempt["result"] not in _DELIVERY_RESULTS or
                    (attempt["acknowledged_at_us"] is not None and
                     (type(attempt["acknowledged_at_us"]) is not int or
                      attempt["acknowledged_at_us"] < attempt["attempted_at_us"])) or
                    (attempt["result"] == "delivered") !=
                    (attempt["acknowledged_at_us"] is not None)):
                raise CapacityEventError("delivery_attempt_invalid")
        last_attempt = delivery["attempt_history"][-1] if delivery["attempt_history"] else None
        if (delivery["state"] == "acknowledged" and
                (last_attempt is None or last_attempt["result"] != "delivered")):
            raise CapacityEventError("delivery_state_invalid")
        if (delivery["state"] == "pending" and
                (len(delivery["attempt_history"]) >= MAX_DELIVERY_ATTEMPTS or
                 (last_attempt is not None and
                  last_attempt["result"] != "retryable_failure"))):
            raise CapacityEventError("delivery_state_invalid")
        if (delivery["state"] == "exhausted" and
                (last_attempt is None or
                 (last_attempt["result"] != "permanent_failure" and
                  len(delivery["attempt_history"]) != MAX_DELIVERY_ATTEMPTS))):
            raise CapacityEventError("delivery_state_invalid")

    def _write(self, value: dict) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            info = None
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise CapacityEventError("state_file_not_regular")
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(12)}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600, follow_symlinks=False)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def accept(self, record: object) -> AcceptedEvent:
        timestamp, cursor, event = _normalized_record(record)
        with self._file_lock():
            previous = self._read()
            if previous is not None:
                if cursor in previous["seen_cursors"]:
                    return AcceptedEvent(False, None, previous["event"]["status"])
            prior_status = None if previous is None else previous["event"]["status"]
            transition = (event["status"] if event["status"] != prior_status and
                          not (prior_status is None and event["status"] == "ok") else None)
            deliveries = [] if previous is None else previous["deliveries"]
            seen_cursors = [] if previous is None else previous["seen_cursors"]
            if transition is not None:
                if len(deliveries) >= MAX_DELIVERY_HISTORY:
                    completed_index = next((index for index, item in enumerate(deliveries)
                                            if item["state"] == "acknowledged"), None)
                    if completed_index is None:
                        raise CapacityEventError("delivery_journal_full")
                    deliveries = deliveries[:completed_index] + deliveries[completed_index + 1:]
                deliveries = [*deliveries, {
                    "timestamp_us": timestamp, "cursor": cursor, "event": event,
                    "attempt_history": [], "state": "pending",
                }]
            seen_cursors = [*seen_cursors, cursor][-MAX_SEEN_CURSORS:]
            self._write({"timestamp_us": timestamp, "cursor": cursor,
                         "event": event, "deliveries": deliveries,
                         "seen_cursors": seen_cursors})
        return AcceptedEvent(True, transition, event["status"], event)

    def accept_reconciled(self, record: object) -> AcceptedEvent:
        """Persist a new journal baseline and enqueue its current status.

        Unlike normal deduplication, reconciliation always emits the latest
        status because transitions may have been lost during journal vacuum.
        Existing outbox entries are retained and capacity remains fail-closed.
        """
        timestamp, cursor, event = _normalized_record(record)
        with self._file_lock():
            previous = self._read()
            if previous is None:
                raise JournalStateUninitialized("journal_state_requires_bootstrap")
            if cursor in previous["seen_cursors"]:
                raise CapacityEventError("journal_reconciliation_no_progress")
            deliveries = list(previous["deliveries"])
            if len(deliveries) >= MAX_DELIVERY_HISTORY:
                completed_index = next((index for index, item in enumerate(deliveries)
                                        if item["state"] == "acknowledged"), None)
                if completed_index is None:
                    raise CapacityEventError("delivery_journal_full")
                deliveries = deliveries[:completed_index] + deliveries[completed_index + 1:]
            deliveries.append({
                "timestamp_us": timestamp, "cursor": cursor, "event": event,
                "attempt_history": [], "state": "pending",
            })
            seen_cursors = [*previous["seen_cursors"], cursor][-MAX_SEEN_CURSORS:]
            self._write({"timestamp_us": timestamp, "cursor": cursor,
                         "event": event, "deliveries": deliveries,
                         "seen_cursors": seen_cursors})
        return AcceptedEvent(True, f"reconciled_{event['status']}", event["status"], event)

    def pending_deliveries(self) -> list[dict]:
        return [item for item in self.delivery_records() if item["state"] == "pending"]

    def due_deliveries(self, *, now_us: int, limit: int = 16) -> list[dict]:
        """Return a bounded ordered batch whose persisted retry delay elapsed."""
        if type(now_us) is not int or now_us < 0:
            raise CapacityEventError("delivery_timestamp_invalid")
        if type(limit) is not int or not 1 <= limit <= MAX_DELIVERY_HISTORY:
            raise CapacityEventError("delivery_batch_limit_invalid")
        due = []
        for item in self.pending_deliveries():
            history = item["attempt_history"]
            if history:
                previous_attempt = history[-1]["attempted_at_us"]
                delay_seconds = min(
                    DELIVERY_RETRY_BASE_SECONDS * (2 ** (len(history) - 1)),
                    DELIVERY_RETRY_MAX_SECONDS,
                )
                if now_us < previous_attempt + delay_seconds * 1_000_000:
                    # Preserve source-cursor order. Sending a later clear while
                    # an earlier alert is backing off can leave the recipient
                    # with a stale open alert after the clear has arrived.
                    break
            due.append(item)
            if len(due) >= limit:
                break
        return due

    def delivery_records(self) -> list[dict]:
        state = self._read()
        if state is None:
            return []
        return [{**item, "attempt_history": list(item["attempt_history"])}
                for item in state["deliveries"]]

    def delivery_health(self) -> dict:
        """Expose bounded operational counters without event or secret data."""
        state = self._read()
        if state is None:
            return {
                "initialized": False,
                "current_status": None,
                "pending": 0,
                "acknowledged": 0,
                "exhausted": 0,
                "delivery_attempts": 0,
                "delivered_attempts": 0,
                "retryable_failures": 0,
                "permanent_failures": 0,
            }
        deliveries = state["deliveries"]
        attempts = [attempt for delivery in deliveries
                    for attempt in delivery["attempt_history"]]
        return {
            "initialized": True,
            "current_status": state["event"]["status"],
            "pending": sum(item["state"] == "pending" for item in deliveries),
            "acknowledged": sum(item["state"] == "acknowledged" for item in deliveries),
            "exhausted": sum(item["state"] == "exhausted" for item in deliveries),
            "delivery_attempts": len(attempts),
            "delivered_attempts": sum(item["result"] == "delivered" for item in attempts),
            "retryable_failures": sum(item["result"] == "retryable_failure"
                                       for item in attempts),
            "permanent_failures": sum(item["result"] == "permanent_failure"
                                       for item in attempts),
        }

    def record_delivery_attempt(self, cursor: str, result: str, *,
                                attempted_at_us: int,
                                acknowledged_at_us: int | None = None) -> str:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 4096:
            raise CapacityEventError("delivery_cursor_invalid")
        if not isinstance(result, str) or result not in _DELIVERY_RESULTS:
            raise CapacityEventError("delivery_result_invalid")
        if type(attempted_at_us) is not int or attempted_at_us < 0:
            raise CapacityEventError("delivery_timestamp_invalid")
        if result == "delivered":
            if type(acknowledged_at_us) is not int or acknowledged_at_us < attempted_at_us:
                raise CapacityEventError("delivery_acknowledgement_invalid")
        elif acknowledged_at_us is not None:
            raise CapacityEventError("delivery_acknowledgement_invalid")

        with self._file_lock():
            state = self._read()
            if state is None:
                raise CapacityEventError("delivery_not_found")
            deliveries = list(state["deliveries"])
            index = next((i for i, item in enumerate(deliveries) if item["cursor"] == cursor), None)
            if index is None:
                raise CapacityEventError("delivery_not_found")
            delivery = dict(deliveries[index])
            history = list(delivery["attempt_history"])
            if delivery["state"] != "pending" or len(history) >= MAX_DELIVERY_ATTEMPTS:
                raise CapacityEventError("delivery_not_pending")
            history.append({"attempted_at_us": attempted_at_us, "result": result,
                            "acknowledged_at_us": acknowledged_at_us})
            if result == "delivered":
                delivery_state = "acknowledged"
            elif result == "permanent_failure" or len(history) >= MAX_DELIVERY_ATTEMPTS:
                delivery_state = "exhausted"
            else:
                delivery_state = "pending"
            delivery.update(attempt_history=history, state=delivery_state)
            deliveries[index] = delivery
            state["deliveries"] = deliveries
            self._write(state)
        return delivery_state
