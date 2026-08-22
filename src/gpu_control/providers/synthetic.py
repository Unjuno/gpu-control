from __future__ import annotations

from ..execution import ApprovedExecutionPlan
from ..lifecycle import CleanupState, JobObservation, JobState, SubmissionReceipt
from ..results import ArtifactDisposition, OutputArtifact
from .base import (
    ProviderCleanupSnapshot,
    ProviderResultSnapshot,
    ProviderStatusSnapshot,
    ProviderSubmission,
)


class SyntheticProviderAdapter:
    """Deterministic no-network adapter for local control-plane contract checks.

    This adapter performs no HTTP requests, creates no external resources, reads no
    credentials, and has no billable behavior. It exists only so an installed
    ``gpu-control`` package can exercise the provider controller end-to-end before
    a live provider implementation is enabled.
    """

    provider_name = "synthetic"

    def __init__(self) -> None:
        self._job_id: str | None = None
        self._observations = 0
        self._cleaned = False

    def submit(self, plan: ApprovedExecutionPlan) -> ProviderSubmission:
        if self._job_id is not None:
            raise RuntimeError("synthetic adapter accepts only one submission per instance")
        if plan.provider != self.provider_name:
            raise RuntimeError("synthetic adapter received a plan for another provider")
        self._job_id = f"synthetic-{plan.fingerprint()[7:19]}"
        return ProviderSubmission(provider_job_id=self._job_id)

    def observe(self, receipt: SubmissionReceipt) -> ProviderStatusSnapshot:
        job_id = self._require_job(receipt)
        if self._observations == 0:
            state = JobState.RUNNING
        else:
            state = JobState.SUCCEEDED
        self._observations += 1
        return ProviderStatusSnapshot(
            provider_job_id=job_id,
            state=state,
            status_reference=f"synthetic-status:{job_id}:{state.value}",
        )

    def cleanup(
        self,
        receipt: SubmissionReceipt,
        terminal_observation: JobObservation,
    ) -> ProviderCleanupSnapshot:
        job_id = self._require_job(receipt)
        if not terminal_observation.terminal:
            raise RuntimeError("synthetic cleanup requires terminal state")
        self._cleaned = True
        return ProviderCleanupSnapshot(
            provider_job_id=job_id,
            cleanup_state=CleanupState.COMPLETED,
            cleanup_reference=f"synthetic-cleanup:{job_id}:completed",
        )

    def collect_results(
        self,
        receipt: SubmissionReceipt,
        final_observation: JobObservation,
    ) -> ProviderResultSnapshot:
        job_id = self._require_job(receipt)
        if not self._cleaned or not final_observation.finalized:
            raise RuntimeError("synthetic results require completed cleanup")
        return ProviderResultSnapshot(
            provider_job_id=job_id,
            log_bytes_retained=128,
            logs_truncated=False,
            artifacts=(
                OutputArtifact(
                    name="metrics.json",
                    sha256="sha256:" + "1" * 64,
                    size_bytes=256,
                    media_type="application/json",
                    reference=f"synthetic://{job_id}/metrics.json",
                    disposition=ArtifactDisposition.COLLECTED,
                ),
                OutputArtifact(
                    name="checkpoints/example.safetensors",
                    sha256="sha256:" + "2" * 64,
                    size_bytes=2 * 1024 * 1024 * 1024,
                    media_type="application/octet-stream",
                    reference=f"synthetic://{job_id}/checkpoints/example.safetensors",
                    disposition=ArtifactDisposition.REFERENCE_ONLY,
                ),
            ),
        )

    def _require_job(self, receipt: SubmissionReceipt) -> str:
        if self._job_id is None:
            raise RuntimeError("synthetic adapter has no submitted job")
        if receipt.provider_job_id != self._job_id:
            raise RuntimeError("synthetic receipt does not match submitted job")
        return self._job_id
