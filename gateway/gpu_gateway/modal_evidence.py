"""Read-only Modal billing observations, deliberately separate from quota proof.

This adapter accepts an already-authenticated SDK workspace object so the
normal Gateway/API path never imports Modal or reads provider credentials.
It calls only documented billing rates/summary methods and never mutates the
workspace or creates a Sandbox.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
import hashlib
import json
import re
from typing import Any

from gpu_control.pricing import PricingVerificationError, parse_utc_timestamp


_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/ -]{0,127}$")
_BILLING_CYCLE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_ITEMS = 512
_MAX_DEPTH = 6


def _decimal(value: Any, *, allow_negative: bool) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Modal billing values must be finite Decimal values")
    if not allow_negative and value < 0:
        raise ValueError("Modal rates and costs must be nonnegative")
    return format(value, "f")


def _json_billing_value(value: Any, *, allow_negative: bool,
                        depth: int = 0, count: list[int] | None = None) -> Any:
    """Normalize bounded billing data without accepting floats or opaque objects."""
    if count is None:
        count = [0]
    count[0] += 1
    if count[0] > _MAX_ITEMS or depth > _MAX_DEPTH:
        raise ValueError("Modal billing response exceeds structural bounds")
    if isinstance(value, Decimal):
        return _decimal(value, allow_negative=allow_negative)
    if isinstance(value, Mapping):
        if len(value) > _MAX_ITEMS:
            raise ValueError("Modal billing mapping exceeds item bound")
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _SAFE_KEY.fullmatch(key):
                raise ValueError("Modal billing mapping has an invalid key")
            normalized[key] = _json_billing_value(
                item, allow_negative=allow_negative, depth=depth + 1, count=count,
            )
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, (tuple, list)):
        if len(value) > _MAX_ITEMS:
            raise ValueError("Modal billing list exceeds item bound")
        return [
            _json_billing_value(item, allow_negative=allow_negative,
                                depth=depth + 1, count=count)
            for item in value
        ]
    if value is None or type(value) is bool or type(value) is int:
        return value
    raise ValueError("Modal billing response contains an unsupported value")


def _required_attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except AttributeError as exc:
        raise ValueError(f"Modal billing summary is missing {name}") from exc


def collect_modal_billing_observation(
    workspace: Any, *, observed_at_utc: str, cycle: str | None = None,
) -> dict[str, Any]:
    """Collect the documented rates and billing summary; never infer quota.

    `workspace` is an injected SDK Workspace value. This function does not
    obtain credentials, instantiate the SDK, access provider inventory, or
    start/cancel a workload. The returned envelope is informational evidence
    only and cannot be supplied directly to `CapabilityEvidence` or
    `QuotaEvidence`.
    """
    if workspace is None:
        raise TypeError("workspace must be an injected Modal Workspace")
    if cycle is not None and (not isinstance(cycle, str) or
                              cycle not in {"this month", "last month"} and
                              not _BILLING_CYCLE.fullmatch(cycle)):
        raise ValueError("cycle must be YYYY-MM, 'this month', 'last month', or None")
    try:
        observed = parse_utc_timestamp(observed_at_utc, "observed_at_utc")
    except PricingVerificationError as exc:
        raise ValueError(str(exc)) from exc
    timestamp = observed.isoformat().replace("+00:00", "Z")

    billing = _required_attr(workspace, "billing")
    rates_method = _required_attr(billing, "rates")
    summary_method = _required_attr(billing, "summary")
    if not callable(rates_method) or not callable(summary_method):
        raise ValueError("Modal workspace billing methods are unavailable")

    rates = rates_method()
    summary = summary_method(cycle=cycle) if cycle is not None else summary_method()
    if not isinstance(rates, Mapping):
        raise ValueError("Modal billing rates must be a mapping")

    normalized_rates: dict[str, str] = {}
    if len(rates) > _MAX_ITEMS:
        raise ValueError("Modal rates mapping exceeds item bound")
    for key, value in rates.items():
        if not isinstance(key, str) or not _SAFE_KEY.fullmatch(key):
            raise ValueError("Modal rates mapping has an invalid key")
        normalized_rates[key] = _decimal(value, allow_negative=False)

    summary_data = {
        "metered_cost": _decimal(_required_attr(summary, "metered_cost"), allow_negative=False),
        "billed_cost": _decimal(_required_attr(summary, "billed_cost"), allow_negative=False),
        "adjustments": _json_billing_value(
            _required_attr(summary, "adjustments"), allow_negative=True,
        ),
        "metered_cost_breakdown": _json_billing_value(
            _required_attr(summary, "metered_cost_breakdown"), allow_negative=False,
        ),
    }
    payload = {
        "schema_version": 1,
        "provider": "modal",
        "evidence_scope": "billing_only",
        "observed_at_utc": timestamp,
        "cycle": cycle,
        "rates": {key: normalized_rates[key] for key in sorted(normalized_rates)},
        "summary": summary_data,
        "quota_evidence": "NOT_AVAILABLE_FROM_THIS_RESPONSE",
        "selection_eligible": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("utf-8")
    return payload | {"fingerprint": hashlib.sha256(canonical).hexdigest()}
