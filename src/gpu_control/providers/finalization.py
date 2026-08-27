from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..lifecycle import CleanupState, JobObservation, LifecycleError, SubmissionReceipt, validate_observation
from ..results import ResultManifest, ResultPolicy, build_result_manifest
from .base import ProviderAdapter, ProviderResultSnapshot
from .controller import ProviderContractError, cleanup_provider_job


@dataclass(frozen=True)
class CollectedThenCleanedJob:
    """Finalized provider state plus a manifest captured before destructive cleanup."""

    final_observation: JobObservation
    result_manifest: ResultManifest


def collect_results_then_cleanup(
    adapter: ProviderAdapter,
    receipt: SubmissionReceipt,
    terminal_observation: JobObservation,
    *,
    collected_at_utc: datetime,
    cleanup_observed_at_utc: datetime,
    policy: ResultPolicy | None = None,
) -> CollectedThenCleanedJob:
    """Collect ephemeral result evidence before cleanup, then bind it to finalized state.

    Some providers delete ephemeral logs together with the resource. This helper
    preserves the existing invariant that the durable ResultManifest binds to a
    cleanup-finalized observation while requiring the adapter to return its bounded
    result snapshot before cleanup starts.
    """

    try:
        receipt.validate_shape()
        validate_observation(receipt, terminal_observation)
        if not terminal_observation.terminal:
            raise LifecycleError("provider result collection requires a terminal observation")
        if terminal_observation.cleanup_state is not CleanupState.NOT_STARTED:
            raise LifecycleError("pre-cleanup result collection requires cleanup_state not_started")
    except LifecycleError as exc:
        raise ProviderContractError(str(exc)) from exc

    response = adapter.collect_results(receipt, terminal_observation)
    if not isinstance(response, ProviderResultSnapshot):
        raise ProviderContractError("provider collect_results must return ProviderResultSnapshot")
    if response.provider_job_id != receipt.provider_job_id:
        raise ProviderContractError("provider result job id does not match submission receipt")
    if not isinstance(response.artifacts, tuple):
        raise ProviderContractError("provider result artifacts must be a tuple")

    final_observation = cleanup_provider_job(
        adapter,
        receipt,
        terminal_observation,
        observed_at_utc=cleanup_observed_at_utc,
    )
    manifest = build_result_manifest(
        receipt,
        final_observation,
        artifacts=response.artifacts,
        log_bytes_retained=response.log_bytes_retained,
        logs_truncated=response.logs_truncated,
        collected_at_utc=collected_at_utc,
        policy=policy,
    )
    return CollectedThenCleanedJob(
        final_observation=final_observation,
        result_manifest=manifest,
    )
