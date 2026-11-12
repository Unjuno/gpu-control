from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..execution import ApprovedExecutionPlan
from .runpod_current_pricing import RunPodCurrentPricingEvidence
from .runpod_occupancy import RunPodAccountOccupancyEvidence, build_account_occupancy_evidence
from .runpod_pricing import RunPodCatalogPricingEvidence
from .runpod_reconciliation import RunPodPodInventoryEvidence, build_pod_inventory_evidence
from .runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from .runpod_v2 import RunPodV2Error, RunPodV2HttpClient


RunPodV2CurrentAdapterError = RunPodV2AdapterError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunPodV2OccupancyProbe:
    """Build account-wide occupancy evidence from every REST v2 List Pods page."""

    client: RunPodV2HttpClient
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: int = 30

    def __call__(self, plan: ApprovedExecutionPlan) -> RunPodAccountOccupancyEvidence:
        inventory = self.client.list_pods()
        return build_account_occupancy_evidence(
            plan,
            inventory.get("pods"),
            checked_at_utc=self.clock(),
            ttl_seconds=self.ttl_seconds,
        )


@dataclass(frozen=True)
class RunPodV2InventoryProbe:
    """Build bounded reconciliation evidence from every REST v2 List Pods page."""

    client: RunPodV2HttpClient
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: int = 30

    def __call__(self, plan: ApprovedExecutionPlan) -> RunPodPodInventoryEvidence:
        return build_pod_inventory_evidence(
            plan,
            self.client.list_pods(),
            checked_at_utc=self.clock(),
            ttl_seconds=self.ttl_seconds,
        )


@dataclass(frozen=True)
class RunPodV2CurrentAdapter(RunPodV2Adapter):
    """Canonical v2 adapter requiring current price and exact volume-DC stock proof."""

    current_pricing: RunPodCurrentPricingEvidence | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.current_pricing is None:
            raise RunPodV2CurrentAdapterError("RunPod v2 adapter requires current catalog pricing evidence")
        if self.network_volume is None:
            raise RunPodV2CurrentAdapterError(
                "RunPod v2 paid-canary adapter requires trusted network-volume evidence"
            )
        try:
            self.current_pricing.validate_against_plan(
                self.approved_plan,
                network_volume=self.network_volume,
                now_utc=self.clock(),
            )
            if self.catalog_pricing != self.current_pricing.to_catalog_evidence():
                raise RunPodV2Error("catalog pricing does not match exact current v2 evidence")
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV2CurrentAdapterError(str(exc)) from exc

    def _require_plan_identity(self, plan: ApprovedExecutionPlan, *, now_utc: datetime | None = None) -> None:
        super()._require_plan_identity(plan, now_utc=now_utc)
        assert self.current_pricing is not None
        assert self.network_volume is not None
        try:
            self.current_pricing.validate_against_plan(
                plan,
                network_volume=self.network_volume,
                now_utc=self.clock() if now_utc is None else now_utc,
            )
        except (RunPodV2Error, ValueError) as exc:
            raise RunPodV2CurrentAdapterError(str(exc)) from exc
