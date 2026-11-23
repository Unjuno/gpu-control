"""Shared heartbeat freshness rules for readiness and recovery decisions."""
from __future__ import annotations

HEARTBEAT_STALE_SECONDS = 15
HEARTBEAT_MAX_FUTURE_SKEW_SECONDS = 5


def heartbeat_age(now: int, seen_at: int | None) -> int | None:
    if type(now) is not int or type(seen_at) is not int or seen_at <= 0:
        return None
    return now - seen_at


def heartbeat_is_fresh(now: int, seen_at: int | None) -> bool:
    age = heartbeat_age(now, seen_at)
    return (age is not None and -HEARTBEAT_MAX_FUTURE_SKEW_SECONDS <= age
            < HEARTBEAT_STALE_SECONDS)


def heartbeat_is_stale(now: int, seen_at: int | None) -> bool:
    age = heartbeat_age(now, seen_at)
    return age is not None and age >= HEARTBEAT_STALE_SECONDS
