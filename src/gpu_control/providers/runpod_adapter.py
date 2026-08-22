from __future__ import annotations

from dataclasses import dataclass

from ..execution import ApprovedExecutionPlan
from ..lifecycle import CleanupState, JobObservation, SubmissionReceipt
from .base import (
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)
from .runpod_pricing import (
    RunPodCatalogPricingEvidence,
    build_priced_create_pod_payload,
    validate_created_pod_with_pricing,
)
from .runpod_v2 import PublishedImageEvidence, RunPodV2Error, RunPodV2HttpClient, translate_pod_status


class RunPodV2AdapterError(RuntimeError):
    """Raised when the live-provider adapter cannot preserve the control-plane contract."""


@dataclass(frozen=True)
class RunPodV2Adapter:
    """RunPod ProviderAdapter implementation with live wiring intentionally disabled.

    The adapter is constructed only from an already-approved plan plus provider-
    specific image and catalog evidence. Repository tests inject a fake HTTP client;
    no public CLI or workflow constructs this adapter with a real API key yet.
    """

    client: RunPodV2HttpClient
    approved_plan: ApprovedExecutionPlan
    published_image: PublishedImageEvidence
    catalog_pricing: RunPodCatalogPricingEvidence
    disk_gb: int = 20

    def __post_init__(self) -> None:
        try:
            self.approved_plan.validate_shape()
            self.published_image.validate_against_plan(self.approved_plan)
            self.catalog_pricing.validate_against_plan(self.approved_plan)
        except (ValueError, RunPodV2Error) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        if self.approved_plan.provider != "runpod":
            raise RunPodV2AdapterError("RunPod adapter requires a runpod approved plan")
        if isinstance(self.disk_gb, bool) or not isinstance(self.disk_gb, int) or self.disk_gb < 1:
            raise RunPodV2AdapterError("RunPod adapter disk_gb must be a positive integer")

    @property
    def provider_name(self) -> str:
        return "runpod"

    def _require_plan_identity(self, plan: ApprovedExecutionPlan) -> None:
        try:
            plan.validate_shape()
        except ValueError as exc:
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

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        """Submit exactly once; this method never retries POST /pods automatically."""

        self._require_plan_identity(plan)
        payload = build_priced_create_pod_payload(
            plan,
            self.published_image,
            self.catalog_pricing,
            disk_gb=self.disk_gb,
        )

        # Deliberately one request. A transport failure after the server may have
        # accepted POST /pods is ambiguous and must be reconciled, not blindly retried.
        pod = self.client.create_pod(payload)
        pod_id = pod.get("id") if isinstance(pod, dict) else None
        try:
            validated_id = validate_created_pod_with_pricing(
                plan,
                self.published_image,
                self.catalog_pricing,
                pod,
            )
        except RunPodV2Error as validation_error:
            if isinstance(pod_id, str) and pod_id.strip():
                try:
                    self.client.terminate_pod(pod_id.strip())
                except Exception as cleanup_error:
                    raise RunPodV2AdapterError(
                        "RunPod post-create validation failed and compensating termination also failed"
                    ) from cleanup_error
                raise RunPodV2AdapterError(
                    "RunPod post-create validation failed; the returned Pod was terminated"
                ) from validation_error
            raise RunPodV2AdapterError(
                "RunPod post-create validation failed before a trustworthy Pod id was available"
            ) from validation_error
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
        self.client.terminate_pod(receipt.provider_job_id)
        return ProviderCleanupSnapshot(
            provider_job_id=receipt.provider_job_id,
            cleanup_state=CleanupState.COMPLETED,
            cleanup_reference=f"runpod-v2:pod:{receipt.provider_job_id}:terminated",
        )

    def collect_results(
        self,
        receipt: SubmissionReceipt,
        final_observation: JobObservation,
    ) -> ProviderResultSnapshot:
        self._require_receipt_identity(receipt)
        raise RunPodV2AdapterError(
            "RunPod result collection is disabled until authenticated workload-completion evidence is implemented"
        )
