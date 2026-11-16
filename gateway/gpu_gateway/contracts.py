"""Strict, versioned persisted plans and experiment result envelopes."""
from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class CandidateBinding(StrictContract):
    """Exact read-only capability selection approved as part of a plan."""

    workload_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    resource_id: str = Field(min_length=1, max_length=256)
    evidence_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("resource_id")
    @classmethod
    def canonical_resource_id(cls, value):
        if (value != value.strip() or
                any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ValueError("resource_id must be canonical text")
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
    selection_binding: CandidateBinding | None = None

    @model_validator(mode="after")
    def selection_provider_matches_plan(self):
        if self.selection_binding is not None and self.selection_binding.provider != self.provider:
            raise ValueError("selection binding provider does not match the approved plan")
        return self

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
    artifact_id: str = Field(min_length=1, max_length=128,
                             pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0, le=1048576)
    media_type: str = Field(min_length=1, max_length=128,
                            pattern=r"^[a-zA-Z0-9!#$&^_.+-]+/[a-zA-Z0-9!#$&^_.+-]+$")
    expires_at: int | None


class ResultV2(StrictContract):
    schema_version: Literal[2]
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    source_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    # Optional for already-persisted schema-v2 records; new local CPU results
    # must bind this value to the immutable image in the plan.
    image_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    simulation: bool
    gpu_used: bool | None
    device: str | None
    exit_code: int | None
    started_at: int | None
    finished_at: int | None
    runtime_seconds: float | None
    metrics: dict[str, int | float]
    checks: list[str] = Field(default_factory=list, max_length=32)
    checksum: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    artifacts: list[ArtifactMetadata] = Field(max_length=10)
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

    @field_validator("checks")
    @classmethod
    def bounded_checks(cls, values):
        if len(values) > 32 or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) for value in values):
            raise ValueError("checks must be bounded lowercase ASCII tokens")
        return values

    @field_validator("known_cost_usd")
    @classmethod
    def finite_known_cost(cls, value):
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("known cost must be finite and nonnegative")
        return value


def plan_payload(plan: PlanV2) -> dict:
    """Return the canonical persisted form, retaining legacy v2 bytes when unbound."""
    payload = plan.model_dump(mode="json")
    # Older schema-v2 plans did not contain this optional field. Keep their
    # fingerprint and persisted representation stable across this extension.
    if plan.selection_binding is None:
        payload.pop("selection_binding", None)
    return payload


def plan_fingerprint(plan: PlanV2) -> str:
    """Hash a canonical JSON representation of the validated immutable plan."""
    canonical = json.dumps(plan_payload(plan), sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_result_binding(plan: PlanV2, fingerprint: str, result: ResultV2) -> None:
    """Reject new worker results that disagree with the persisted plan.

    ``ResultV2.image_digest`` remains optional when reading legacy v2 data,
    but a result accepted for a newly completed plan must bind its exact
    provider and image. This function is only used at the worker finish gate.
    """
    if (fingerprint != plan_fingerprint(plan) or result.source_sha != plan.source_sha or
            result.plan_fingerprint != fingerprint or result.provider != plan.provider or
            result.image_digest != plan.image_digest):
        raise ValueError("result identity does not match the persisted plan")


def validate_candidate_gpu_success(result: ResultV2) -> None:
    """Require normalized evidence from the trusted candidate adapter."""
    if (result.simulation or result.gpu_used is not True or not result.device or
            result.exit_code != 0 or result.cleanup_state != "complete" or
            not {"candidate_resource_verified", "device_identity_verified"}.issubset(result.checks)):
        raise ValueError("terminal result lacks verified GPU and cleanup evidence")
