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
from .synthetic import SyntheticProviderAdapter

__all__ = [
    "ProviderAdapter",
    "ProviderCleanupSnapshot",
    "ProviderContractError",
    "ProviderResultSnapshot",
    "ProviderStatusSnapshot",
    "ProviderSubmission",
    "SubmittedJob",
    "SyntheticProviderAdapter",
    "cleanup_provider_job",
    "collect_provider_results",
    "observe_provider_job",
    "submit_approved_plan",
]
