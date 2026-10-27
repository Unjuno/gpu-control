"""Strict, versioned persisted plans and experiment result envelopes."""
from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CostClassification = Literal[
    "LOCAL", "FREE", "FREE_QUOTA", "CREDIT_BACKED", "PAID",
    "MANUAL_ONLY", "UNSUPPORTED", "UNKNOWN",
]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CostEvidence(StrictContract):
    classification: CostClassification
    additional_cost_usd: Decimal | None
    reference: str
    observed_at: int | None
    expires_at: int | None

    @field_validator("additional_cost_usd")
    @classmethod
    def finite_cost(cls, value):
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("cost must be finite and nonnegative")
        return value


class PlanV2(StrictContract):
    schema_version: Literal[2]
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    workload: str = Field(min_length=1, max_length=100)
    workload_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parameters: dict
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    device_requirement: dict
    runtime_seconds: int = Field(ge=1, le=86400)
    max_cost_usd: Decimal = Field(ge=0, le=Decimal("100000"))
    cost_evidence: CostEvidence
    authorization_policy_version: str = Field(min_length=1, max_length=64)

    @field_validator("source_sha")
    @classmethod
    def canonical_sha(cls, value):
        if not SHA40.fullmatch(value):
            raise ValueError("source SHA must be lowercase canonical hex")
        return value

    @field_validator("workload_manifest_digest")
    @classmethod
    def canonical_manifest_digest(cls, value):
        if not SHA256.fullmatch(value):
            raise ValueError("manifest digest must be lowercase canonical hex")
        return value

    @field_validator("max_cost_usd")
    @classmethod
    def finite_max_cost(cls, value):
        if not value.is_finite() or value < 0:
            raise ValueError("maximum cost must be finite and nonnegative")
        return value


class ArtifactMetadata(StrictContract):
    artifact_id: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1, max_length=128)
    expires_at: int | None


class ResultV2(StrictContract):
    schema_version: Literal[2]
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    simulation: bool
    gpu_used: bool | None
    device: str | None
    exit_code: int | None
    started_at: int | None
    finished_at: int | None
    runtime_seconds: float | None
    metrics: dict[str, int | float]
    artifacts: list[ArtifactMetadata]
    known_cost_usd: Decimal | None
    cost_classification: CostClassification
    cleanup_state: Literal["not_required", "pending", "complete", "unknown"]

    @field_validator("metrics")
    @classmethod
    def finite_metrics(cls, values):
        if any(not isinstance(key, str) or not key.isascii() or
               not isinstance(value, (int, float)) or isinstance(value, bool) or
               not math.isfinite(value) for key, value in values.items()):
            raise ValueError("metrics must have ASCII names and finite numeric values")
        return values

    @field_validator("known_cost_usd")
    @classmethod
    def finite_known_cost(cls, value):
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("known cost must be finite and nonnegative")
        return value


def plan_fingerprint(plan: PlanV2) -> str:
    """Hash a canonical JSON representation of the validated immutable plan."""
    canonical = json.dumps(plan.model_dump(mode="json"), sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_result_binding(plan: PlanV2, fingerprint: str, result: ResultV2) -> None:
    """Reject result identity that disagrees with its persisted run plan."""
    if (fingerprint != plan_fingerprint(plan) or result.source_sha != plan.source_sha or
            result.plan_fingerprint != fingerprint):
        raise ValueError("result identity does not match the persisted plan")
