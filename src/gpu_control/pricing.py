from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


class PricingVerificationError(ValueError):
    """Raised when provider pricing evidence is malformed or unusable."""


def parse_utc_timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PricingVerificationError(f"{field} is required")

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PricingVerificationError(f"{field} must be an ISO 8601 timestamp") from exc

    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PricingVerificationError(f"{field} must be timezone-aware UTC")
    return parsed


@dataclass(frozen=True)
class PricingVerificationResult:
    """Evidence that a specific provider resource had a verified bounded price.

    The control-plane profile is kept separately from the provider resource id so
    a future backend can resolve an abstract profile such as ``cheap-24gb`` to a
    concrete provider offering without losing the identity of the priced resource.
    """

    provider: str
    gpu_profile: str
    provider_resource_id: str
    hourly_price_usd: Decimal
    verification_reference: str
    verified_at_utc: str
    valid_until_utc: str
    price_verified: bool
    availability_verified: bool

    def validate_shape(self) -> tuple[datetime, datetime]:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise PricingVerificationError("pricing provider is required")
        if not isinstance(self.gpu_profile, str) or not self.gpu_profile.strip():
            raise PricingVerificationError("pricing gpu_profile is required")
        if not isinstance(self.provider_resource_id, str) or not self.provider_resource_id.strip():
            raise PricingVerificationError("provider_resource_id is required")
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise PricingVerificationError("pricing verification_reference is required")
        if not isinstance(self.hourly_price_usd, Decimal):
            raise PricingVerificationError("hourly_price_usd must be a Decimal")
        if not self.hourly_price_usd.is_finite() or self.hourly_price_usd <= 0:
            raise PricingVerificationError("hourly_price_usd must be finite and positive")

        verified_at = parse_utc_timestamp(self.verified_at_utc, "verified_at_utc")
        valid_until = parse_utc_timestamp(self.valid_until_utc, "valid_until_utc")
        if valid_until <= verified_at:
            raise PricingVerificationError("valid_until_utc must be after verified_at_utc")
        return verified_at, valid_until
