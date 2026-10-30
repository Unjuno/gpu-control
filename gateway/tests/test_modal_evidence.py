from decimal import Decimal
from types import SimpleNamespace

import pytest

from gpu_gateway.modal_evidence import collect_modal_billing_observation


class FakeBilling:
    def __init__(self, *, rates=None, summary=None):
        self.calls = []
        self._rates = rates or {
            "a10g_gpu_per_second": Decimal("0.000306"),
            "cpu_per_vcpu_second": Decimal("0.000013"),
        }
        self._summary = summary or SimpleNamespace(
            metered_cost=Decimal("12.34"),
            billed_cost=Decimal("2.34"),
            adjustments={"credits": Decimal("-10.00")},
            metered_cost_breakdown={"gpu": Decimal("10.00"), "cpu": Decimal("2.34")},
        )

    def rates(self):
        self.calls.append(("rates", None))
        return self._rates

    def summary(self, cycle=None):
        self.calls.append(("summary", cycle))
        return self._summary


def test_modal_billing_adapter_calls_only_read_methods_and_marks_quota_unavailable():
    billing = FakeBilling()
    workspace = SimpleNamespace(billing=billing)

    result = collect_modal_billing_observation(
        workspace, observed_at_utc="2026-10-28T12:30:00Z", cycle="2026-10",
    )

    assert billing.calls == [("rates", None), ("summary", "2026-10")]
    assert result["evidence_scope"] == "billing_only"
    assert result["observed_at_utc"] == "2026-10-28T12:30:00Z"
    assert result["rates"]["a10g_gpu_per_second"] == "0.000306"
    assert result["summary"]["adjustments"] == {"credits": "-10.00"}
    assert result["quota_evidence"] == "NOT_AVAILABLE_FROM_THIS_RESPONSE"
    assert result["selection_eligible"] is False
    assert len(result["fingerprint"]) == 64


def test_modal_billing_adapter_uses_default_cycle_without_provider_mutations():
    billing = FakeBilling()

    result = collect_modal_billing_observation(
        SimpleNamespace(billing=billing), observed_at_utc="2026-10-28T12:30:00+00:00",
    )

    assert billing.calls == [("rates", None), ("summary", None)]
    assert result["cycle"] is None
    assert result["observed_at_utc"] == "2026-10-28T12:30:00Z"


@pytest.mark.parametrize("rates", [
    {"gpu": 0.1},
    {"bad\nkey": Decimal("0.1")},
    {"gpu": Decimal("NaN")},
    {"gpu": Decimal("-0.1")},
])
def test_modal_billing_adapter_rejects_untrusted_or_malformed_rates(rates):
    billing = FakeBilling(rates=rates)
    with pytest.raises(ValueError):
        collect_modal_billing_observation(
            SimpleNamespace(billing=billing), observed_at_utc="2026-10-28T12:30:00Z",
        )


def test_modal_billing_adapter_rejects_incomplete_summary():
    billing = FakeBilling(summary=SimpleNamespace(metered_cost=Decimal("1")))

    with pytest.raises(ValueError, match="billed_cost"):
        collect_modal_billing_observation(
            SimpleNamespace(billing=billing), observed_at_utc="2026-10-28T12:30:00Z",
        )


def test_modal_billing_adapter_rejects_naive_or_non_utc_observation_time():
    billing = FakeBilling()
    workspace = SimpleNamespace(billing=billing)

    with pytest.raises(ValueError, match="UTC"):
        collect_modal_billing_observation(workspace, observed_at_utc="2026-10-28T12:30:00")
    with pytest.raises(ValueError, match="UTC"):
        collect_modal_billing_observation(workspace, observed_at_utc="2026-10-28T12:30:00+09:00")
    assert billing.calls == []


@pytest.mark.parametrize("cycle", ["2026-13", "yesterday", "2026-10-01", ""])
def test_modal_billing_adapter_rejects_unsupported_cycle_before_provider_read(cycle):
    billing = FakeBilling()
    workspace = SimpleNamespace(billing=billing)

    with pytest.raises(ValueError, match="cycle must be"):
        collect_modal_billing_observation(
            workspace, observed_at_utc="2026-10-28T12:30:00Z", cycle=cycle,
        )
    assert billing.calls == []
