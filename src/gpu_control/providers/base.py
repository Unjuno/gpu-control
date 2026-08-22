from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..execution import ApprovedExecutionPlan
from ..lifecycle import CleanupState, JobObservation, JobState, SubmissionReceipt
from ..results import OutputArtifact


@dataclass(frozen=True)
class ProviderSubmission:
    """Minimal untrusted response returned when a provider accepts a job."""

    provider_job_id: str


@dataclass(frozen=True)
class ProviderStatusSnapshot:
    """Provider-reported job status before control-plane correlation."""

    provider_job_id: str
    state: JobState
    status_reference: str


@dataclass(frozen=True)
class ProviderCleanupSnapshot:
    """Provider-reported cleanup state for a terminal job."""

    provider_job_id: str
    cleanup_state: CleanupState
    cleanup_reference: str


@dataclass(frozen=True)
class ProviderResultSnapshot:
    """Provider-translated result metadata before result-policy validation."""

    provider_job_id: str
    log_bytes_retained: int
    logs_truncated: bool
    artifacts: tuple[OutputArtifact, ...]


@runtime_checkable
class ProviderAdapter(Protocol):
    """Narrow boundary implemented by a concrete GPU provider backend.

    Provider adapters receive only an already-approved plan or lifecycle state.
    They must not accept raw workflow/user inputs as an alternative allocation path.
    Returned provider data remains untrusted until the control-plane controller
    validates identity, transitions, and result policy.
    """

    @property
    def provider_name(self) -> str:
        """Canonical provider identifier handled by this adapter."""
        ...

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        """Perform one provider submission request and return its job identity."""
        ...

    def observe(self, receipt: SubmissionReceipt) -> ProviderStatusSnapshot:
        """Read current provider status for a previously submitted job."""
        ...

    def cleanup(
        self,
        receipt: SubmissionReceipt,
        terminal_observation: JobObservation,
    ) -> ProviderCleanupSnapshot:
        """Stop/delete provider resources for a terminal job."""
        ...

    def collect_results(
        self,
        receipt: SubmissionReceipt,
        final_observation: JobObservation,
    ) -> ProviderResultSnapshot:
        """Translate bounded provider result metadata after cleanup completes."""
        ...
