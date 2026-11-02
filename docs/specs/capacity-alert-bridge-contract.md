# Capacity alert bridge contract

Status: **host-independent contract; durable outbox, bounded journalctl poller, and sink-agnostic delivery pump implemented; no notification sink or bridge service is deployed**.

## Purpose and boundary

The systemd capacity timer emits a small JSON state event to journald under
`SYSLOG_IDENTIFIER=gpu-control-capacity`. A future host-local bridge may turn
validated state transitions into operator notifications. The bridge is a
separate process and failure domain: it must never become a dependency of the
Gateway API, worker, recovery supervisor, artifact writes, or cancellation.

This contract does not select a cloud, notification vendor, recipient, secret
store, retention policy, or alert SLO. Those require the target-host and
operator decisions recorded in `docs/decisions/2026-10-28-p3-deployment-topology.md`.

## Input contract

- Read only records with `SYSLOG_IDENTIFIER=gpu-control-capacity` and trusted
  `_SYSTEMD_UNIT=gpu-control-artifact-capacity.service`. User-supplied
  `SYSTEMD_UNIT` does not establish process identity.
- Parse only the `MESSAGE` field as JSON; validate it against
  `gateway/deploy/capacity-event.schema.json`. Reject unknown fields, invalid
  states, and arbitrary journal records. Never forward raw journal entries,
  filesystem paths, environment variables, exception text, or credentials.
- Require `status=alert` to have `available=false` and a nonempty bounded
  reason. Require `status=ok` to have `available=true`, null reason, and both
  byte counts. The event schema already expresses these invariants.
- Derive one alert key from the fixed `check` value. Keep the last accepted
  state and source event cursor durably so replay after restart does not create
  repeated pages. An `alert` transition opens/updates the alert; a later `ok`
  transition for the same key resolves it. Resume ordering from the opaque
  journal cursor, not wall-clock timestamps: clock corrections may make a
  later journal entry's realtime timestamp smaller. Deduplicate recent cursors
  and never let concurrent readers overwrite each other's newer state.
- Preserve source timestamp, event/cursor identity, delivery attempt, result,
  and acknowledgement timestamp in a bounded private journal. Do not log sink
  credentials or full notification response bodies.
- Treat delivery as at-least-once: a crash after sink acceptance but before the
  local acknowledgement can cause a repeat. Use the stable source cursor as an
  idempotency key when the selected sink supports it; otherwise expose the
  duplicate-delivery possibility to the operator.

## Delivery contract

- Notifications contain only the fixed check name, status, bounded reason, and
  measured/free-space threshold values. They must not claim that `statvfs`
  proves a hard quota or that a delivered alert means the Gateway is healthy.
- Use finite connect/read timeouts, bounded payloads, TLS certificate
  verification, and bounded retry with backoff. Do not silently discard a
  failed transition; expose bridge health and retain a pending-delivery state.
- Sink credentials are root-owned and readable only by the bridge identity.
  They are absent from API, worker, supervisor, migration, and capacity-monitor
  environments. The bridge has no Docker access, database credential, or
  artifact write access.
- The bridge does not confirm arbitrary callbacks, follow caller-supplied URLs,
  or accept a destination from the event. Destination and message template are
  operator configuration, not event content.
- A journal reader outage must resume from a durable cursor and reconcile
  current alert state from retained events. If journald retention has removed
  the required transition, report state as unknown and require an explicit
  reconciliation; do not infer a clear without a retained `status=ok` event.

## Required tests and acceptance

The repository's `gateway/deploy/capacity_event_state.py` currently implements
strict trusted journal identity/event validation, a bounded `journalctl`
source/poller, and a private atomic cursor/status/outbox file. The poller checks
that a saved cursor is still retained both before and after each bounded query;
retention loss raises an explicit unknown-state error and leaves the persisted
cursor and deliveries unchanged. Polling an absent checkpoint is rejected;
operator bootstrap explicitly reads only the latest matching capacity event
as a baseline rather than replaying the host journal. A latest `ok` initializes
state without sending a spurious clear, while a latest `alert` enters the
outbox. Mutations take an advisory process lock in a separate private lock file;
the state file itself is still replaced atomically. The latest 256 source
cursors are retained for duplicate suppression. Realtime timestamps remain
evidence only and are not treated as a total ordering. Unit
coverage exercises alert/clear transitions, duplicate and older
event rejection across object reconstruction, unknown-field rejection, and
state-file mode/symlink boundaries. Alert reasons are restricted to the fixed
codes emitted by `check_artifact_capacity.py`, so arbitrary journal text,
paths, secret-like strings, and duplicate JSON keys are not copied into state.
Persisted state is revalidated and rejected if malformed or group/world
accessible. Each accepted alert/clear transition and its cursor enter a bounded
64-record outbox in the same atomic write. Attempts store only timestamp,
bounded result code, and acknowledgement timestamp. Retries stop after eight
attempts and retain an `exhausted` record; a full outbox with no acknowledged
record refuses to advance the cursor. A bounded `JournalctlSource` and
cursor-resuming `JournalPoller` are implemented with fake-source coverage only.
The sink-agnostic `CapacityEventDeliveryPump` selects due records in bounded
batches, applies deterministic exponential retry delay (5 seconds, doubling
to a 1-hour cap), sends only the fixed message projection, and passes the
source cursor as idempotency key. It records only fixed result codes and
acknowledgement time; sender exceptions and response details are not persisted.
Pending transitions remain in source-cursor order: the selector stops at the
first pending record still in backoff, and a retryable send failure stops the
current batch so a later clear cannot overtake an earlier alert.
Pump invocations sharing the state path are serialized across selection,
network send, and durable acknowledgement, preventing concurrent local bridge
processes from dispatching the same pending transition simultaneously. A
sender must still use the supplied idempotency key because a crash after remote
acceptance and before local acknowledgement remains an at-least-once duplicate
window.

After retention loss, `JournalPoller.reconcile_latest()` and the CLI's explicit
`--reconcile-latest` action require the persisted cursor to be absent, read one
latest trusted capacity event, and recheck the gap before updating state. The
operation preserves existing pending deliveries and emits a fresh current-
status notification, including a `status=ok` clear only when that exact latest
retained event says `ok`. Reannouncing the current status cannot recover any
intermediate transitions that journald vacuumed; command output must be
recorded and reviewed by an operator. Fake-source regressions cover cursor
retention checks, pending outbox preservation, and reannouncement when the
latest status matches the last known status. This is local contract evidence,
not live journald recovery acceptance.
The pump must be invoked by a future service/timer, and each concrete sender
must enforce finite network timeouts. No sink dispatch, notification service,
or live notification exists. Retention loss remains an explicit unknown-state
condition for operator reconciliation, not an automatic replay or inferred
clear.

### Poll transaction serialization

Current-worktree regression refresh (2026-10-28): capacity journal/outbox and
backup generation modules passed 53 focused tests, including the sink-agnostic
delivery pump; deployment unit contracts passed 14 tests. Exact commands,
environment, and scope limits are recorded in
[`capacity bridge regression evidence`](../acceptance/2026-10-28-capacity-bridge-regression.md).
This is fake-source/fake-sender and template evidence only; a real sink, target
host, recipient/SLO, and delivery acceptance remain open.

`JournalPoller.poll_once()` and `bootstrap_latest()` hold a separate
process-wide `flock` from checkpoint read through journal query and full batch
application. The per-state-mutation lock remains separate, so nested state
updates do not release poll serialization. A deterministic regression uses two
pollers with independent state instances for the same path: the second waits
while the first query is blocked, then reads the first poll's updated cursor.
A separate-process regression attempts a nonblocking lock while the parent
holds the poll lock, proves the child is excluded, then confirms it acquires
the lock after release. The focused state and deploy-unit suites passed 45
tests on 2026-10-28; the full Gateway offline suite passed 339 tests with 9
optional skips. The exact cross-process file lock was also exercised in a
network-isolated Linux container with a pinned Python 3.12 image; see
`docs/acceptance/2026-10-28-linux-capacity-poll-lock.md`. This is process-lock
evidence only; no live Linux journal or host service was exercised.

`CapacityEventState.delivery_health()` exposes only initialization/current
status, bounded outbox counts, and fixed attempt-result counters. It omits
event bodies, cursors, exception strings, and response data. These counters
describe local bridge state only; they do not prove a human received or
acknowledged a notification, and they do not capture journal-reader outages.
The manual CLI exposes the same projection through `--show-health` without
invoking `journalctl`; tests verify the action does not construct or query a
journal source and that event-specific cursor/reason data is absent.

Before a sink is selected, contract tests must cover schema rejection,
irrelevant journal records, duplicate/reordered events, restart at each cursor
boundary, alert/clear transitions, bounded retry timing, fixed message
projection, idempotency key preservation, and secret/payload redaction. Tests
must use a fake journal and fake sink and cannot pass notification acceptance.

On the selected host, inject a below-threshold condition using a disposable
filesystem or injected probe. An independent operator must confirm delivery
within a predeclared SLO, acknowledge the alert, restore capacity, receive a
clear notification, and verify API/worker/supervisor remain healthy throughout.
Record source and delivery timestamps, route identity (not its secret), retry
history, acknowledgement, and recovery notification in the P3 acceptance
record. Do not fill the production artifact volume.

## Sink selection gate

Select a sink only after the host/provider, region, cost ceiling, reachable
origin or outbound route, operator recipient, credential storage, and delivery
SLO are known. Compare a host-native metrics/log alert route with a direct
notification API on authentication, required ingress/egress, retry semantics,
cost, regional availability, and independent delivery evidence. No AWS SNS,
email, Slack, webhook, or other sink is implied by this contract.
