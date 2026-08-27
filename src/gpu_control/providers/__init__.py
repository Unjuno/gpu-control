"""Provider adapter contracts.

No live provider implementation is enabled by this package yet.
"""

from .base import (
    ProviderAdapter,
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)
from .controller import (
    ProviderContractError,
    SubmittedJob,
    cleanup_provider_job,
    collect_provider_results,
    observe_provider_job,
    submit_approved_plan,
)
from .finalization import (
    FinalizedCapturedResults,
    ProviderResultCapture,
    capture_provider_results_before_cleanup,
    finalize_captured_provider_results,
    validate_result_capture_against_lifecycle,
)
from .runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
from .runpod_occupancy import RunPodAccountOccupancyEvidence, build_account_occupancy_evidence
from .runpod_pricing import (
    RunPodCatalogPricingEvidence,
    build_catalog_pricing_evidence,
    build_priced_create_pod_payload,
    validate_created_pod_with_pricing,
)
from .runpod_v2 import (
    RUNPOD_V2_BASE_URL,
    PublishedImageEvidence,
    RunPodV2Error,
    RunPodV2HttpClient,
    build_create_pod_payload,
    translate_pod_status,
    validate_created_pod,
)
from .synthetic import SyntheticProviderAdapter

__all__ = [
    "FinalizedCapturedResults",
    "ProviderAdapter",
    "ProviderCleanupSnapshot",
    "ProviderContractError",
    "ProviderResultCapture",
    "ProviderResultSnapshot",
    "ProviderStatusSnapshot",
    "ProviderSubmission",
    "PublishedImageEvidence",
    "RUNPOD_V2_BASE_URL",
    "RunPodAccountOccupancyEvidence",
    "RunPodCatalogPricingEvidence",
    "RunPodV2Adapter",
    "RunPodV2AdapterError",
    "RunPodV2Error",
    "RunPodV2HttpClient",
    "SubmittedJob",
    "SyntheticProviderAdapter",
    "build_account_occupancy_evidence",
    "build_catalog_pricing_evidence",
    "build_create_pod_payload",
    "build_priced_create_pod_payload",
    "capture_provider_results_before_cleanup",
    "cleanup_provider_job",
    "collect_provider_results",
    "finalize_captured_provider_results",
    "observe_provider_job",
    "submit_approved_plan",
    "translate_pod_status",
    "validate_created_pod",
    "validate_created_pod_with_pricing",
    "validate_result_capture_against_lifecycle",
]
