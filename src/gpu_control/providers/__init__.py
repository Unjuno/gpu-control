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
from .runpod_adapter import RunPodV2Adapter, RunPodV2AdapterError
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
    "ProviderAdapter",
    "ProviderCleanupSnapshot",
    "ProviderContractError",
    "ProviderResultSnapshot",
    "ProviderStatusSnapshot",
    "ProviderSubmission",
    "PublishedImageEvidence",
    "RUNPOD_V2_BASE_URL",
    "RunPodCatalogPricingEvidence",
    "RunPodV2Adapter",
    "RunPodV2AdapterError",
    "RunPodV2Error",
    "RunPodV2HttpClient",
    "SubmittedJob",
    "SyntheticProviderAdapter",
    "build_catalog_pricing_evidence",
    "build_create_pod_payload",
    "build_priced_create_pod_payload",
    "cleanup_provider_job",
    "collect_provider_results",
    "observe_provider_job",
    "submit_approved_plan",
    "translate_pod_status",
    "validate_created_pod",
    "validate_created_pod_with_pricing",
]
