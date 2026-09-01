from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..execution import ApprovedExecutionPlan
from .base import ProviderSubmission
from .runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from .runpod_current_pricing import RunPodCurrentPricingEvidence
from .runpod_occupancy import RunPodAccountOccupancyEvidence, build_account_occupancy_evidence
from .runpod_pricing import validate_created_pod_with_pricing
from .runpod_reconciliation import RunPodPodInventoryEvidence, build_pod_inventory_evidence
from .runpod_v1 import RunPodV1HttpClient, build_create_pod_payload_v1
from .runpod_v2 import RunPodV2Error


RunPodV1AdapterError = RunPodV2AdapterError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunPodV1OccupancyProbe:
    """Build short-lived occupancy evidence from the current REST v1 List Pods API."""

    client: RunPodV1HttpClient
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: int = 30

    def __call__(self, plan: ApprovedExecutionPlan) -> RunPodAccountOccupancyEvidence:
        inventory = self.client.list_pods()
        pods = inventory.get("pods")
        if not isinstance(pods, list):
            raise RunPodV2Error("RunPod REST v1 normalized inventory is missing pods")
        return build_account_occupancy_evidence(
            plan,
            pods,
            checked_at_utc=self.clock(),
            ttl_seconds=self.ttl_seconds,
        )


@dataclass(frozen=True)
class RunPodV1InventoryProbe:
    """Build bounded reconciliation evidence from the current REST v1 List Pods API."""

    client: RunPodV1HttpClient
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: int = 30

    def __call__(self, plan: ApprovedExecutionPlan) -> RunPodPodInventoryEvidence:
        inventory = self.client.list_pods()
        return build_pod_inventory_evidence(
            plan,
            inventory,
            checked_at_utc=self.clock(),
            ttl_seconds=self.ttl_seconds,
        )


@dataclass(frozen=True)
class RunPodV1Adapter(RunPodV2Adapter):
    """Canonical paid-canary adapter on current REST v1 and current pricing evidence.

    The parent class retains authorization, lifecycle, reconciliation, durable-result,
    and cleanup invariants. This class replaces provider-version-specific create/list
    wiring and additionally requires short-lived current price/stock evidence for the
    exact GPU and the exact datacenter of the trusted Network Volume.
    """

    client: RunPodV1HttpClient
    current_pricing: RunPodCurrentPricingEvidence | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.current_pricing is None:
            raise RunPodV1AdapterError("RunPod REST v1 adapter requires current pricing evidence")
        if self.network_volume is None:
            raise RunPodV1AdapterError("RunPod REST v1 paid-canary adapter requires trusted network-volume evidence")
        try:
            self.current_pricing.validate_against_plan(
                self.approved_plan,
                network_volume=self.network_volume,
                now_utc=self.clock(),
            )
            if self.catalog_pricing != self.current_pricing.to_catalog_evidence():
                raise RunPodV2Error("legacy pricing view does not exactly match current RunPod pricing evidence")
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV1AdapterError(str(exc)) from exc

    def _require_plan_identity(self, plan: ApprovedExecutionPlan) -> None:
        super()._require_plan_identity(plan)
        assert self.current_pricing is not None
        assert self.network_volume is not None
        try:
            self.current_pricing.validate_against_plan(
                plan,
                network_volume=self.network_volume,
                now_utc=self.clock(),
            )
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV1AdapterError(str(exc)) from exc

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        """Submit exactly once through current REST v1 after fresh price/stock checks."""

        self._require_plan_identity(plan)
        self._probe_before_create(plan)
        payload = build_create_pod_payload_v1(
            plan,
            self.published_image,
            cloud=self.catalog_pricing.cloud,
            disk_gb=self.disk_gb,
            completion=self.completion_launch,
            network_volume=self.network_volume,
        )

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
            raise RunPodV1AdapterError(
                "RunPod REST v1 post-create validation failed before a trustworthy Pod id was available"
            ) from validation_error

        try:
            self._probe_after_create(plan, validated_id)
        except Exception as occupancy_error:
            self._terminate_invalid_created_pod(validated_id, occupancy_error)
        return ProviderSubmission(provider_job_id=validated_id)
