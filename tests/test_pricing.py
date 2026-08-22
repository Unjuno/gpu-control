from decimal import Decimal

import pytest

from gpu_control.pricing import PricingVerificationError, PricingVerificationResult


def make_pricing(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "provider": "runpod",
        "gpu_profile": "cheap-24gb",
        "provider_resource_id": "synthetic-offer-3090",
        "hourly_price_usd": Decimal("0.34"),
        "verification_reference": "pricing-check:synthetic-123",
        "verified_at_utc": "2026-08-22T16:00:00Z",
        "valid_until_utc": "2026-08-22T16:15:00Z",
        "price_verified": True,
        "availability_verified": True,
    }
    values.update(overrides)
    return PricingVerificationResult(**values)


def test_accepts_well_formed_pricing_evidence() -> None:
    verified_at, valid_until = make_pricing().validate_shape()

    assert verified_at.isoformat() == "2026-08-22T16:00:00+00:00"
    assert valid_until.isoformat() == "2026-08-22T16:15:00+00:00"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "", "provider"),
        ("gpu_profile", "", "gpu_profile"),
        ("provider_resource_id", "", "provider_resource_id"),
        ("verification_reference", "", "verification_reference"),
        ("hourly_price_usd", Decimal("0"), "hourly_price_usd"),
        ("hourly_price_usd", Decimal("-1"), "hourly_price_usd"),
        ("hourly_price_usd", Decimal("NaN"), "hourly_price_usd"),
        ("verified_at_utc", "2026-08-22T16:00:00", "timezone-aware UTC"),
        ("verified_at_utc", "2026-08-22T18:00:00+02:00", "timezone-aware UTC"),
        ("valid_until_utc", "not-a-time", "ISO 8601"),
        ("valid_until_utc", "2026-08-22T16:00:00Z", "after verified_at_utc"),
    ],
)
def test_rejects_malformed_pricing_evidence(field: str, value: object, message: str) -> None:
    pricing = make_pricing(**{field: value})

    with pytest.raises(PricingVerificationError, match=message):
        pricing.validate_shape()


def test_rejects_non_decimal_price_even_if_numeric_text() -> None:
    pricing = make_pricing(hourly_price_usd="0.34")  # type: ignore[arg-type]

    with pytest.raises(PricingVerificationError, match="must be a Decimal"):
        pricing.validate_shape()
