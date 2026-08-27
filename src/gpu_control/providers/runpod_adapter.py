from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from ..completion import CompletionChallenge, CompletionEvidenceError, completion_system_env
from ..execution import ApprovedExecutionPlan
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
from .runpod_v2 import (
    PublishedImageEvidence,
    RunPodV2Error,
    RunPodV2HttpClient,
    RunPodV2HttpError,
    RunPodV2TransportError,
    translate_pod_status,
)


class RunPodV2AdapterError(RuntimeError):
    """Raised when the live-provider adapter cannot preserve the control-plane contract."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunPodV2Adapter:
    """RunPod ProviderAdapter with account exclusivity and exact execution identity.

    The completion challenge is created before POST /pods. Its unique execution
    name is used as the provider Pod name, ambiguous-create reconciliation key,
    and authenticated workload-completion identity. RunPod's provider job id is
    learned only after create and remains correlated separately by the receipt.
    """

    client: RunPodV2HttpClient
    approved_plan: ApprovedExecutionPlan
    published_image: PublishedImageEvidence
    catalog_pricing: RunPodCatalogPricingEvidence
    completion_challenge: CompletionChallenge
    completion_secret_key: bytes
    occupancy_probe: Callable[[ApprovedExecutionPlan], RunPodAccountOccupancyEvidence]
    disk_gb: int = 20
    clock: Callable[[], datetime] = _utc_now

    def __post_init__(self) -> None:
        try:
            self.approved_plan.validate_shape()
            self.published_image.validate_against_plan(self.approved_plan)
            self.catalog_pricing.validate_against_plan(self.approved_plan)
            self.completion_challenge.validate_shape()
            completion_system_env(self.completion_challenge, secret_key=self.completion_secret_key)
        except (ValueError, CompletionEvidenceError, RunPodV2Error) as exc:
            raise RunPodV2AdapterError(str(exc)) from exc
        if self.approved_plan.provider != "runpod":
            raise RunPodV2AdapterError("RunPod adapter requires a runpod approved plan")
        if self.completion_challenge.plan_fingerprint != self.approved_plan.fingerprint():
            raise RunPodV2AdapterError("completion challenge does not match approved plan fingerprint")
        if self.completion_challenge.source_sha != self.approved_plan.target_sha:
            raise RunPodV2AdapterError("completion challenge source SHA does not match approved plan")
        if self.completion_challenge.image_digest != self.approved_plan.image_digest:
            raise RunPodV2AdapterError("completion challenge image digest does not match approved plan")
        if not callable(self.occupancy_probe):
            raise RunPodV2AdapterError("RunPod adapter requires an account occupancy probe")
        if not callable(self.clock):
            raise RunPodV2AdapterError("RunPod adapter clock must be callable")
        if isinstance(self.disk_gb, bool) or not isinstance(self.disk_gb, int) or self.disk_gb < 1:
            raise RunPodV2AdapterError("RunPod adapter disk_gb must be a positive integer")

    @property
    def provider_name(self) -> str:
        return "runpod"

    @property
    def execution_name(self) -> str:
        return self.completion_challenge.execution_name

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

    def _terminate_invalid_created_pod(self, pod_id: str, cause: Exception) -> None:
        try:
            self.client.terminate_pod(pod_id)
        except Exception as cleanup_error:
            raise RunPodV2AdapterError(
                "RunPod post-create validation failed and compensating termination also failed"
            ) from cleanup_error
        raise RunPodV2AdapterError(
            "RunPod post-create validation failed; the returned Pod was terminated"
        ) from cause

    def _reconcile_ambiguous_create(self, plan: ApprovedExecutionPlan) -> Mapping[str, object]:
        """Recover a possibly accepted POST without issuing a second create."""

        try:
            payload = self.client.list_pods()
        except Exception as exc:
            raise RunPodV2AdapterError(
                "RunPod create outcome is ambiguous and account reconciliation failed; do not retry create"
            ) from exc
        pods = payload.get("pods")
        if not isinstance(pods, list):
            raise RunPodV2AdapterError(
                "RunPod create outcome is ambiguous and List Pods response is invalid; do not retry create"
            )
        matches = [
            pod for pod in pods
            if isinstance(pod, Mapping) and pod.get("name") == self.execution_name
        ]
        if len(matches) != 1:
            raise RunPodV2AdapterError(
                "RunPod create outcome remains ambiguous; expected exactly one execution-named Pod and will not retry create"
            )
        candidate = matches[0]
        try:
            validate_created_pod_with_pricing(
                plan,
                self.published_image,
                self.catalog_pricing,
                candidate,
                expected_name=self.execution_name,
            )
        except RunPodV2Error as exc:
            candidate_id = candidate.get("id")
            if isinstance(candidate_id, str) and candidate_id.strip():
                self._terminate_invalid_created_pod(candidate_id.strip(), exc)
            raise RunPodV2AdapterError(
                "RunPod reconciled Pod failed validation before a trustworthy Pod id was available"
            ) from exc
        return candidate

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        """Submit exactly once after owner/account exclusivity checks pass."""

        self._require_plan_identity(plan)
        self._probe_before_create(plan)
        payload = build_priced_create_pod_payload(
            plan,
            self.published_image,
            self.catalog_pricing,
            disk_gb=self.disk_gb,
            execution_name=self.execution_name,
            system_env=completion_system_env(
                self.completion_challenge,
                secret_key=self.completion_secret_key,
            ),
        )

        try:
            pod = self.client.create_pod(payload)
        except RunPodV2TransportError:
            pod = self._reconcile_ambiguous_create(plan)

        pod_id = pod.get("id") if isinstance(pod, Mapping) else None
        try:
            validated_id = validate_created_pod_with_pricing(
                plan,
                self.published_image,
                self.catalog_pricing,
                pod,
                expected_name=self.execution_name,
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
                expected_name=self.execution_name,
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

        cleanup_reference = f"runpod-v2:pod:{receipt.provider_job_id}:terminated"
        try:
            self.client.terminate_pod(receipt.provider_job_id)
        except RunPodV2HttpError as exc:
            if exc.status_code != 404:
                raise RunPodV2AdapterError(str(exc)) from exc
            try:
                payload = self.client.list_pods()
            except Exception as reconcile_error:
                raise RunPodV2AdapterError(
                    "RunPod cleanup returned 404 and absence reconciliation failed"
                ) from reconcile_error
            pods = payload.get("pods")
            if not isinstance(pods, list):
                raise RunPodV2AdapterError("RunPod cleanup absence reconciliation returned invalid List Pods data")
            if any(
                isinstance(pod, Mapping) and pod.get("id") == receipt.provider_job_id
                for pod in pods
            ):
                raise RunPodV2AdapterError(
                    "RunPod cleanup returned 404 but the Pod is still present in List Pods"
                )
            cleanup_reference = f"runpod-v2:pod:{receipt.provider_job_id}:already-absent-reconciled"
        except RunPodV2Error as exc:
            raise RunPodV2AdapterError(str(exc)) from exc

        return ProviderCleanupSnapshot(
            provider_job_id=receipt.provider_job_id,
            cleanup_state=CleanupState.COMPLETED,
            cleanup_reference=cleanup_reference,
        )

    def collect_results(
        self,
        receipt: SubmissionReceipt,
        final_observation: JobObservation,
    ) -> ProviderResultSnapshot:
        self._require_receipt_identity(receipt)
        raise RunPodV2AdapterError(
            "RunPod result collection is disabled until authenticated bounded log collection is implemented"
        )
