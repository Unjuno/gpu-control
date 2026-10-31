"""Sink-agnostic bounded dispatcher for capacity-event outbox records.

The injected sender owns endpoint selection, authentication, TLS, and finite
network timeouts. This module never reads destination or credential data from
an event and records only fixed result codes in the durable outbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from capacity_event_state import (
    CapacityEventError,
    CapacityEventState,
)


class CapacityEventSender(Protocol):
    def send(self, message: dict, *, idempotency_key: str,
             source_timestamp_us: int) -> str:
        """Return delivered, retryable_failure, or permanent_failure.

        Implementations must enforce finite connect/read timeouts and use only
        operator-configured destinations and credentials.
        """


@dataclass(frozen=True)
class DeliveryBatchResult:
    attempted: int
    delivered: int
    pending: int
    exhausted: int


def _notification_message(event: dict) -> dict:
    """Project validated state onto the fixed, non-sensitive message shape."""
    return {
        "check": event["check"],
        "status": event["status"],
        "reason": event.get("reason"),
        "free_bytes": event.get("free_bytes"),
        "minimum_free_bytes": event.get("minimum_free_bytes"),
    }


class CapacityEventDeliveryPump:
    """Dispatch due outbox entries at least once through an injected sender."""

    def __init__(self, state: CapacityEventState, sender: CapacityEventSender,
                 *, clock_us: Callable[[], int], batch_limit: int = 16):
        if not callable(clock_us):
            raise ValueError("delivery_clock_invalid")
        if type(batch_limit) is not int or not 1 <= batch_limit <= 64:
            raise ValueError("delivery_batch_limit_invalid")
        self.state = state
        self.sender = sender
        self.clock_us = clock_us
        self.batch_limit = batch_limit

    def run_once(self) -> DeliveryBatchResult:
        # Selection and acknowledgement are separate durable operations. Hold
        # a process-wide lock across the injected send so two bridge processes
        # cannot dispatch the same pending transition concurrently.
        with self.state._delivery_lock():
            return self._run_once_locked()

    def _run_once_locked(self) -> DeliveryBatchResult:
        now_us = self.clock_us()
        if type(now_us) is not int or now_us < 0:
            raise CapacityEventError("delivery_timestamp_invalid")
        due = self.state.due_deliveries(now_us=now_us, limit=self.batch_limit)
        delivered = 0
        pending = 0
        exhausted = 0
        attempted = 0

        for item in due:
            attempted += 1
            attempted_at_us = self.clock_us()
            if type(attempted_at_us) is not int or attempted_at_us < 0:
                raise CapacityEventError("delivery_timestamp_invalid")
            result = "retryable_failure"
            acknowledged_at_us = None
            try:
                candidate = self.sender.send(
                    _notification_message(item["event"]),
                    idempotency_key=item["cursor"],
                    source_timestamp_us=item["timestamp_us"],
                )
                if candidate in {"delivered", "retryable_failure", "permanent_failure"}:
                    result = candidate
            except Exception:
                # Do not persist or expose exception strings, response bodies,
                # endpoint URLs, or secret-bearing transport diagnostics.
                result = "retryable_failure"

            if result == "delivered":
                acknowledged_at_us = self.clock_us()
                if (type(acknowledged_at_us) is not int or
                        acknowledged_at_us < attempted_at_us):
                    # Treat an invalid or backwards wall clock as an uncertain
                    # delivery; retry with the same stable idempotency key.
                    result = "retryable_failure"
                    acknowledged_at_us = None

            state = self.state.record_delivery_attempt(
                item["cursor"], result,
                attempted_at_us=attempted_at_us,
                acknowledged_at_us=acknowledged_at_us,
            )
            if state == "acknowledged":
                delivered += 1
            elif state == "exhausted":
                exhausted += 1
            else:
                pending += 1
                if state == "pending":
                    # A retryable failure must not let a later transition
                    # overtake this source-cursor in the same batch.
                    break

        return DeliveryBatchResult(
            attempted=attempted, delivered=delivered,
            pending=pending, exhausted=exhausted,
        )
