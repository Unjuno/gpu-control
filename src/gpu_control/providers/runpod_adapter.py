from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..execution import ApprovedExecutionPlan
from ..human_authorization import HumanAuthorizationError, LiveExecutionPermit
from ..lifecycle import CleanupState, JobObservation, SubmissionReceipt
from .base import (
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)
from .runpod_occupancy import RunPodAccountOccupancyEvidence
from .runpod_pricing import (
    RunPodCatalogPricingEvidence,
    build_priced_create_pod_payload,
    validate_created_pod_with_pricing,
)
from .runpod_reconciliation import (
    RunPodPodInventoryEvidence,
    cleanup_reconciled,
    reconcile_ambiguous_create,
)
from .runpod_v2 import (
    PublishedImageEvidence,
    RunPodCompletionLaunch,
    RunPodV2Error,
    RunPodV2HttpClient,
    translate_pod_status,
)


class RunPodV2AdapterError(RuntimeError):
    """Raised when the live-provider adapter cannot preserve the control-plane contract."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunPodV2Adapter:
    """RunPod ProviderAdapter with paid submission guarded by an exact live permit.

    In addition to plan/image/pricing identity, construction and every submission
    require a non-expired ``LiveExecutionPermit`` for the exact approved plan.
    Account occupancy is checked before and after create. Optional reconciliation
    wiring can recover one ambiguous create only when a per-execution completion
    identity and a fresh full Pod inventory are both available. The same inventory
    contract can prove release after an ambiguous normal or compensating termination
    without converting an active Pod to cleanup success.

    Live workflow/credential wiring remains disabled elsewhere by repository policy.
    """

    client: RunPodV2HttpClient
    approved_plan: ApprovedExecutionPlan
    published_image: PublishedImageEvidence
    catalog_pricing: RunPodCatalogPricingEvidence
    occupancy_probe: Callable[[ApprovedExecutionPlan], RunPodAccountOccupancyEvidence]
    live_permit: LiveExecutionPermit
    inventory_probe: Callable[[ApprovedExecutionPlan], RunPodPodInventoryEvidence] | None = None
    completion_launch: RunPodCompletionLaunch | None = None
    disk_gb: int = 20
    clock: Callable[[], datetime] = _utc_now

    def __post_init__(self) -> None:
        if not callable(self.clock):
            raise RunPodV2AdapterError("RunPod adapter clock must be callable")
        if not isinstance(self.live_permit, LiveExecutionPermit):
            raise RunPodV2AdapterError("RunPod adapter requires a validated live execution permit")
        try:
            self.approved_plan.validate_shape()
            self.published_image.validate_against_plan(self.approved_plan)
            self.catalog_pricing.validate_against_plan(self.approved_plan)
            self.live_permit.validate_for_plan(self.approved_plan, now_utc=self.clock())
            if self.completion_launch is not None:
                self.completion_launch.validate_against_plan(self.approved_plan)
        except (ValueError, RunPodV2Error, HumanAuthorizationError) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        if self.approved_plan.provider != "runpod":
            raise RunPodV2AdapterError("RunPod adapter requires a runpod approved plan")
        if not callable(self.occupancy_probe):
            raise RunPodV2AdapterError("RunPod adapter requires an account occupancy probe")
        if self.inventory_probe is not None and not callable(self.inventory_probe):
            raise RunPodV2AdapterError("RunPod inventory_probe must be callable when configured")
        if isinstance(self.disk_gb, bool) or not isinstance(self.disk_gb, int) or self.disk_gb < 1:
            raise RunPodV2AdapterError("RunPod adapter disk_gb must be a positive integer")

    @property
    def provider_name(self) -> str:
        return "runpod"

    def _require_plan_identity(self, plan: ApprovedExecutionPlan) -> None:
        try:
            plan.validate_shape()
            self.live_permit.validate_for_plan(plan, now_utc=self.clock())
        except (ValueError, HumanAuthorizationError) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        if plan.fingerprint() != self.approved_plan.fingerprint():
            raise RunPodV2AdapterError("RunPod adapter received a different approved plan")

    def _require_receipt_identity(self, receipt: SubmissionReceipt) -> None:
        try:
            receipt.validate_shape()
        except ValueError as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        if receipt.provider != self.provider_name:
            raise RunPodV2AdapterError("RunPod receipt provider mismatch")
        if receipt.plan_fingerprint != self.approved_plan.fingerprint():
            raise RunPodV2AdapterError("RunPod receipt plan fingerprint mismatch")
        if receipt.provider_resource_id != self.approved_plan.provider_resource_id:
            raise RunPodV2AdapterError("RunPod receipt GPU identity mismatch")
        if receipt.image_digest != self.approved_plan.image_digest:
            raise RunPodV2AdapterError("RunPod receipt image digest mismatch")

    def _probe_before_create(self, plan: ApprovedExecutionPlan) -> None:
        try:
            evidence = self.occupancy_probe(plan)
            if not isinstance(evidence, RunPodAccountOccupancyEvidence):
                raise RunPodV2Error("RunPod occupancy probe returned an invalid evidence type")
            evidence.validate_before_create(plan, now_utc=self.clock())
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc

    def _probe_after_create(self, plan: ApprovedExecutionPlan, pod_id: str) -> None:
        evidence = self.occupancy_probe(plan)
        if not isinstance(evidence, RunPodAccountOccupancyEvidence):
            raise RunPodV2Error("RunPod occupancy probe returned an invalid evidence type")
        evidence.validate_after_create(plan, expected_pod_id=pod_id, now_utc=self.clock())

    def _probe_inventory(self, plan: ApprovedExecutionPlan) -> RunPodPodInventoryEvidence:
        if self.inventory_probe is None:
            raise RunPodV2AdapterError("RunPod reconciliation inventory is not configured")
        try:
            evidence = self.inventory_probe(plan)
            if not isinstance(evidence, RunPodPodInventoryEvidence):
                raise RunPodV2Error("RunPod inventory probe returned an invalid evidence type")
            evidence.validate_against_plan(plan, now_utc=self.clock())
            return evidence
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc

    def _prove_pod_released(self, pod_id: str) -> None:
        """Fail unless fresh inventory proves the exact Pod absent or TERMINATED."""

        evidence = self._probe_inventory(self.approved_plan)
        try:
            released = cleanup_reconciled(
                evidence,
                self.approved_plan,
                pod_id,
                now_utc=self.clock(),
            )
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV2AdapterError("RunPod Pod release reconciliation evidence is invalid") from exc
        if not released:
            raise RunPodV2AdapterError("RunPod Pod remains active after ambiguous terminate request")

    def _terminate_invalid_created_pod(self, pod_id: str, cause: Exception) -> None:
        try:
            self.client.terminate_pod(pod_id)
        except RunPodV2Error as cleanup_error:
            if self.inventory_probe is None:
                raise RunPodV2AdapterError(
                    "RunPod post-create validation failed and compensating termination also failed"
                ) from cleanup_error
            try:
                self._prove_pod_released(pod_id)
            except RunPodV2AdapterError as reconciliation_error:
                raise RunPodV2AdapterError(
                    "RunPod post-create validation failed and the invalid Pod could not be proven released"
                ) from reconciliation_error
            raise RunPodV2AdapterError(
                "RunPod post-create validation failed; invalid Pod release was reconciled"
            ) from cause
        raise RunPodV2AdapterError(
            "RunPod post-create validation failed; the returned Pod was terminated"
        ) from cause

    def _reconcile_create_failure(self, plan: ApprovedExecutionPlan, create_error: RunPodV2Error) -> ProviderSubmission:
        if self.completion_launch is None or self.inventory_probe is None:
            raise create_error
        try:
            evidence = self._probe_inventory(plan)
            candidate_id = reconcile_ambiguous_create(
                evidence,
                plan,
                self.completion_launch.challenge,
                now_utc=self.clock(),
            )
            candidate = self.client.get_pod(candidate_id)
            validated_id = validate_created_pod_with_pricing(
                plan,
                self.published_image,
                self.catalog_pricing,
                candidate,
                completion=self.completion_launch,
            )
            if validated_id != candidate_id:
                raise RunPodV2Error("RunPod reconciled Pod id changed during validation")
            self._probe_after_create(plan, validated_id)
        except RunPodV2AdapterError:
            raise
        except (RunPodV2Error, ValueError) as reconciliation_error:
            raise RunPodV2AdapterError(
                "RunPod create outcome is ambiguous and could not be reconciled to one trusted execution"
            ) from reconciliation_error
        return ProviderSubmission(provider_job_id=validated_id)

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        """Submit exactly once after exact authorization and account checks pass."""

        self._require_plan_identity(plan)
        self._probe_before_create(plan)
        payload = build_priced_create_pod_payload(
            plan,
            self.published_image,
            self.catalog_pricing,
            disk_gb=self.disk_gb,
            completion=self.completion_launch,
        )

        # Deliberately one create request. A failed transport may be reconciled
        # by exact pre-create execution identity, but create itself is never retried.
        try:
            pod = self.client.create_pod(payload)
        except RunPodV2Error as create_error:
            return self._reconcile_create_failure(plan, create_error)

        pod_id = pod.get("id") if isinstance(pod, dict) else None
        try:
            validated_id = validate_created_pod_with_pricing(
                plan,
                self.published_image,
                self.catalog_pricing,
                pod,
                completion=self.completion_launch,
            )
        except RunPodV2Error as validation_error:
            if isinstance(pod_id, str) and pod_id.strip():
                self._terminate_invalid_created_pod(pod_id.strip(), validation_error)
            raise RunPodV2AdapterError(
                "RunPod post-create validation failed before a trustworthy Pod id was available"
            ) from validation_error

        try:
            self._probe_after_create(plan, validated_id)
        except Exception as occupancy_error:
            self._terminate_invalid_created_pod(validated_id, occupancy_error)
        return ProviderSubmission(provider_job_id=validated_id)

    def observe(self, receipt: SubmissionReceipt) -> ProviderStatusSnapshot:
        self._require_receipt_identity(receipt)
        pod = self.client.get_pod(receipt.provider_job_id)
        pod_id = pod.get("id") if isinstance(pod, dict) else None
        if pod_id != receipt.provider_job_id:
            raise RunPodV2AdapterError("RunPod status response Pod id does not match submission receipt")
        try:
            validate_created_pod_with_pricing(
                self.approved_plan,
                self.published_image,
                self.catalog_pricing,
                pod,
                completion=self.completion_launch,
            )
            state = translate_pod_status(pod)
        except RunPodV2Error as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        return ProviderStatusSnapshot(
            provider_job_id=receipt.provider_job_id,
            state=state,
            status_reference=f"runpod-v2:pod:{receipt.provider_job_id}:status",
        )

    def cleanup(
        self,
        receipt: SubmissionReceipt,
        terminal_observation: JobObservation,
    ) -> ProviderCleanupSnapshot:
        self._require_receipt_identity(receipt)
        if terminal_observation.provider_job_id != receipt.provider_job_id:
            raise RunPodV2AdapterError("RunPod cleanup observation job id mismatch")
        if terminal_observation.plan_fingerprint != receipt.plan_fingerprint:
            raise RunPodV2AdapterError("RunPod cleanup observation plan fingerprint mismatch")
        if not terminal_observation.terminal:
            raise RunPodV2AdapterError("RunPod cleanup requires a terminal observation")
        try:
            self.client.terminate_pod(receipt.provider_job_id)
            cleanup_reference = f"runpod-v2:pod:{receipt.provider_job_id}:terminated"
        except RunPodV2Error as cleanup_error:
            if self.inventory_probe is None:
                raise cleanup_error
            try:
                self._prove_pod_released(receipt.provider_job_id)
            except RunPodV2AdapterError as reconciliation_error:
                raise RunPodV2AdapterError(
                    "RunPod cleanup failed and the exact Pod could not be proven released"
                ) from reconciliation_error
            cleanup_reference = f"runpod-v2:pod:{receipt.provider_job_id}:reconciled-released"
        return ProviderCleanupSnapshot(
            provider_job_id=receipt.provider_job_id,
            cleanup_state=CleanupState.COMPLETED,
            cleanup_reference=cleanup_reference,
        )

    def collect_results(
        self,
        receipt: SubmissionReceipt,
        lifecycle_observation: JobObservation,
    ) -> ProviderResultSnapshot:
        self._require_receipt_identity(receipt)
        raise RunPodV2AdapterError(
            "RunPod result collection is disabled until a production-supported authenticated collection transport is verified"
        )
