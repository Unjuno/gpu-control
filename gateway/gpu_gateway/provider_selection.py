"""Shared fail-closed GPU selection and exact-plan revalidation helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re

from .config import Settings, Workload
from .contracts import CandidateBinding, CostEvidence, PlanV2
from .provider_evidence import ProviderEvidenceError
from .store import Store
from gpu_control.capabilities import CapabilityEvidence
from gpu_control.selection import SelectionBlocker, SelectionResult, revalidate_approved_candidate, select_candidate
from gpu_control.workloads import (
    AcceleratorKind,
    NetworkRequirement,
    ResultTransport,
    WorkloadRequirements,
)
from gpu_control.pricing import PricingVerificationError, parse_utc_timestamp


def gpu_requirements(name: str, workload: Workload) -> tuple[WorkloadRequirements | None, list[str]]:
    """Convert explicit operator requirements; leave missing dimensions unknown."""
    required = {
        "workload_id": bool(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name)),
        "source_repository": bool(workload.source_repository),
        "source_sha": bool(workload.source_sha),
        "operating_system": workload.operating_system is not None,
        "architecture": workload.architecture is not None,
        "gpu_count": workload.gpu_count is not None,
        "minimum_vram_mib": workload.minimum_vram_mib is not None,
        "network_requirement": workload.network_requirement is not None,
        "result_transport": workload.result_transport is not None,
        "max_result_bytes": workload.max_result_bytes is not None,
        "cancellation_required": workload.cancellation_required is not None,
        "cleanup_proof_required": workload.cleanup_proof_required is not None,
    }
    missing = [field for field, configured in required.items() if not configured]
    if missing:
        return None, missing
    try:
        requirements = WorkloadRequirements(
            workload_id=name,
            source_repository=workload.source_repository,
            source_sha=workload.source_sha,
            operating_system=workload.operating_system,
            architecture=workload.architecture,
            accelerator_kind=AcceleratorKind.GPU,
            gpu_profile=workload.gpu.lower(),
            gpu_count=workload.gpu_count,
            minimum_vram_mib=workload.minimum_vram_mib,
            minimum_cpu_cores=Decimal(str(workload.cpu)),
            minimum_memory_mib=workload.memory_mib,
            max_runtime_seconds=workload.max_runtime_seconds,
            network_requirement=NetworkRequirement(workload.network_requirement),
            result_transport=ResultTransport(workload.result_transport),
            max_result_bytes=workload.max_result_bytes,
            cancellation_required=workload.cancellation_required,
            cleanup_proof_required=workload.cleanup_proof_required,
            runtime_requirements=workload.runtime_requirements,
            max_queue_wait_seconds=workload.max_queue_wait_seconds,
        )
    except (TypeError, ValueError):
        return None, ["invalid_workload_requirements"]
    return requirements, []


def verified_provider_candidates(store: Store, settings: Settings, provider: str, now: int):
    """Load only a current, signed, exact-schema provider snapshot."""
    try:
        keys = settings.provider_evidence_trusted_keys
        if not keys:
            return [], False, "NOT_CONFIGURED"
        envelope = store.read_verified_provider_observation(provider, keys, now=now)
    except (ProviderEvidenceError, ValueError, TypeError, KeyError, OverflowError):
        return [], False, "INVALID_OR_STALE"
    if envelope is None:
        return [], False, "NOT_AVAILABLE"
    payload = envelope.get("payload")
    if (not isinstance(payload, dict) or set(payload) != {"inventory_complete", "candidates"} or
            type(payload["inventory_complete"]) is not bool or
            not isinstance(payload["candidates"], list) or len(payload["candidates"]) > 256):
        return [], False, "INVALID_OR_STALE"
    observed = datetime.fromtimestamp(envelope["observed_at"], timezone.utc).isoformat().replace("+00:00", "Z")
    expires = datetime.fromtimestamp(envelope["expires_at"], timezone.utc).isoformat().replace("+00:00", "Z")
    candidates = []
    try:
        for value in payload["candidates"]:
            evidence = CapabilityEvidence.from_dict(value)
            if (evidence.provider != provider or evidence.evidence_source != envelope["source"] or
                    evidence.observed_at_utc != observed or evidence.valid_until_utc != expires):
                return [], False, "INVALID_OR_STALE"
            candidates.append(evidence)
    except (ValueError, TypeError, KeyError, OverflowError):
        return [], False, "INVALID_OR_STALE"
    return candidates, payload["inventory_complete"], "VERIFIED"


def select_registered_candidate(store: Store, settings: Settings, *, name: str,
                                workload: Workload, now: int, max_cost_usd: Decimal):
    requirements, missing = gpu_requirements(name, workload)
    if requirements is None:
        return requirements, None, missing, "NOT_EVALUATED", False
    candidates, inventory_complete, status = verified_provider_candidates(
        store, settings, workload.provider, now)
    now_utc = datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")
    decision = select_candidate(
        requirements, candidates, now_utc=now_utc, max_cost_usd=max_cost_usd,
        free_first=True, inventory_complete=inventory_complete,
    )
    return requirements, decision, [], status, inventory_complete


def plan_for_selected_gpu(*, name: str, workload: Workload,
                          requirements: WorkloadRequirements,
                          evidence: CapabilityEvidence, repository: str,
                          source_sha: str, parameters: dict, runtime_seconds: int,
                          max_cost_usd: str) -> PlanV2:
    """Create an immutable browser-approved plan bound to one selected offer."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", workload.image_digest):
        raise ValueError("GPU workload must pin an immutable image digest")
    observed = int(parse_utc_timestamp(evidence.observed_at_utc, "observed_at_utc").timestamp())
    expires = int(parse_utc_timestamp(evidence.valid_until_utc, "valid_until_utc").timestamp())
    return PlanV2(
        schema_version=2,
        repository=repository,
        source_sha=source_sha,
        workload=name,
        workload_manifest_digest=hashlib.sha256(json.dumps(
            workload.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest(),
        image_digest=workload.image_digest,
        parameters=parameters,
        provider=evidence.provider,
        device_requirement=requirements.to_dict(),
        runtime_seconds=runtime_seconds,
        max_cost_usd=Decimal(max_cost_usd),
        cost_evidence=CostEvidence(
            classification=evidence.cost_classification.value,
            additional_cost_usd=evidence.costs.known_total_usd,
            reference=evidence.evidence_reference,
            observed_at=observed,
            expires_at=expires,
        ),
        authorization_policy_version="browser-approval-required-v1",
        selection_binding=CandidateBinding(
            workload_fingerprint=requirements.fingerprint(),
            provider=evidence.provider,
            resource_id=evidence.resource_id or "",
            evidence_fingerprint=evidence.fingerprint(),
        ),
    )


def current_bound_candidate(store: Store, settings: Settings, workloads: dict[str, Workload],
                            plan: PlanV2, *, now: int, connection=None,
                            lock_observation: bool = False) -> SelectionResult:
    """Revalidate one exact plan resource without selecting a replacement."""
    binding = plan.selection_binding
    if binding is None:
        raise ValueError("candidate-bound plan is required")
    workload = workloads.get(plan.workload)
    if workload is None:
        return _stale_result(plan, binding, "APPROVED_WORKLOAD_MISSING")
    requirements, missing = gpu_requirements(plan.workload, workload)
    if requirements is None:
        return _stale_result(plan, binding, "APPROVED_WORKLOAD_REQUIREMENTS_INCOMPLETE")
    manifest = workload.model_dump(mode="json")
    manifest_digest = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    if (requirements.fingerprint() != binding.workload_fingerprint or
            plan.workload_manifest_digest != manifest_digest or
            plan.provider != workload.provider or
            plan.repository != workload.source_repository or
            plan.source_sha != workload.source_sha or
            plan.image_digest != workload.image_digest or
            plan.device_requirement != requirements.to_dict() or
            plan.runtime_seconds > workload.max_runtime_seconds or
            plan.max_cost_usd > workload.max_cost_usd or
            missing):
        return _stale_result(plan, binding, "APPROVED_WORKLOAD_CHANGED")

    try:
        keys = settings.provider_evidence_trusted_keys
        if not keys:
            raise ProviderEvidenceError("no trusted provider keys")
        envelope = store.read_verified_provider_observation(
            binding.provider, keys, now=now, connection=connection,
            lock=lock_observation,
        )
        if envelope is None:
            raise ProviderEvidenceError("provider observation is missing")
        payload = envelope.get("payload")
        if (not isinstance(payload, dict) or
                set(payload) != {"inventory_complete", "candidates"} or
                type(payload["inventory_complete"]) is not bool or
                not isinstance(payload["candidates"], list) or
                len(payload["candidates"]) > 256):
            raise ProviderEvidenceError("provider observation payload is invalid")
        observed = datetime.fromtimestamp(envelope["observed_at"], timezone.utc).isoformat().replace("+00:00", "Z")
        expires = datetime.fromtimestamp(envelope["expires_at"], timezone.utc).isoformat().replace("+00:00", "Z")
        candidates = []
        for item in payload["candidates"]:
            current = CapabilityEvidence.from_dict(item)
            if (current.provider != binding.provider or current.evidence_source != envelope["source"] or
                    current.observed_at_utc != observed or current.valid_until_utc != expires):
                raise ProviderEvidenceError("provider candidate identity is invalid")
            candidates.append(current)
        complete = payload["inventory_complete"]
    except (ProviderEvidenceError, ValueError, TypeError, KeyError, OverflowError):
        candidates, complete = [], False
    exact = [item for item in candidates if item.resource_id == binding.resource_id]
    if not complete or len(exact) != 1:
        return revalidate_approved_candidate(
            requirements,
            approved_workload_fingerprint=binding.workload_fingerprint,
            approved_provider=binding.provider,
            approved_resource_id=binding.resource_id,
            approved_evidence_fingerprint=binding.evidence_fingerprint,
            current_evidence=None,
            now_utc=datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
            max_cost_usd=plan.max_cost_usd,
        )
    decision = revalidate_approved_candidate(
        requirements,
        approved_workload_fingerprint=binding.workload_fingerprint,
        approved_provider=binding.provider,
        approved_resource_id=binding.resource_id,
        approved_evidence_fingerprint=binding.evidence_fingerprint,
        current_evidence=exact[0],
        now_utc=datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
        max_cost_usd=plan.max_cost_usd,
    )
    evidence = exact[0]
    try:
        cost_time = int(parse_utc_timestamp(evidence.observed_at_utc, "observed_at_utc").timestamp())
        expiry_time = int(parse_utc_timestamp(evidence.valid_until_utc, "valid_until_utc").timestamp())
    except PricingVerificationError:
        return _stale_result(plan, binding, "APPROVED_COST_EVIDENCE_INVALID")
    if (plan.cost_evidence.classification != evidence.cost_classification.value or
            plan.cost_evidence.additional_cost_usd != evidence.costs.known_total_usd or
            plan.cost_evidence.reference != evidence.evidence_reference or
            plan.cost_evidence.observed_at != cost_time or
            plan.cost_evidence.expires_at != expiry_time):
        return _stale_result(plan, binding, "APPROVED_COST_EVIDENCE_CHANGED")
    return decision


def _stale_result(plan: PlanV2, binding: CandidateBinding, reason: str) -> SelectionResult:
    from gpu_control.selection import RejectedCandidate
    return SelectionResult(
        workload_id=plan.workload,
        workload_fingerprint=binding.workload_fingerprint,
        selected=None,
        rejected=(RejectedCandidate(
            provider=binding.provider, resource_id=binding.resource_id,
            evidence_fingerprint=binding.evidence_fingerprint, reasons=(reason,),
        ),),
        blocking_reason=SelectionBlocker.APPROVED_PLAN_STALE,
    )
