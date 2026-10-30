"""One operator-owned registry shared by admission, UI and worker.

Add a GPU provider here and implement Backend; MCP and WebMCP stay unchanged.
Registry entries are trusted application code, never user-supplied import paths.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable

from .config import Settings


@dataclass(frozen=True)
class ProviderRegistration:
    name: str
    execution: str
    enabled: Callable[[Settings], bool]
    factory: Callable
    note: str = ""
    # Candidate-bound PlanV2 needs a backend that consumes the immutable plan,
    # binds provider results to it, and enforces exact-resource lifecycle gates.
    supports_candidate_binding: bool = False
    # Paid execution additionally needs a run-specific LiveExecutionPermit.
    # This opt-in is independent from candidate-bound/free-GPU acceptance.
    supports_paid_execution: bool = False


def candidate_plan_requires_paid_authorization(plan: dict | object) -> bool:
    """Fail closed unless cost evidence proves a zero-additional-cost class."""
    if isinstance(plan, dict):
        evidence = plan.get("cost_evidence")
        provider = plan.get("provider")
    else:
        evidence = getattr(plan, "cost_evidence", None)
        provider = getattr(plan, "provider", None)
    if not isinstance(evidence, dict) and evidence is not None:
        evidence = getattr(evidence, "model_dump", lambda **_: None)(mode="python")
    if not isinstance(evidence, dict):
        return True
    classification = evidence.get("classification")
    amount = evidence.get("additional_cost_usd")
    try:
        additional = Decimal(str(amount)) if amount is not None else None
    except (InvalidOperation, ValueError):
        return True
    zero_cost_classes = {"FREE", "FREE_QUOTA"}
    if provider in {"local_cpu", "local_gpu"}:
        zero_cost_classes.add("LOCAL")
    return not (classification in zero_cost_classes and
                additional is not None and additional == 0)


def supports_candidate_execution(registration: ProviderRegistration | None,
                                 backend: object, plan: dict | object | None = None) -> bool:
    """Require an explicit PlanV2 entry point and the full cleanup lifecycle.

    The registry flag is an operator-reviewed opt-in. The runtime shape check
    prevents a stale or misconfigured registration from sending a bound plan
    through a legacy ``start(run)`` adapter that ignores its selected resource.
    """
    candidate_ready = bool(
        registration is not None and registration.supports_candidate_binding and
        callable(getattr(backend, "start_candidate_bound", None)) and
        callable(getattr(backend, "validate_candidate_observation", None)) and
        all(callable(getattr(backend, name, None))
            for name in ("capture", "cleanup", "is_clean"))
    )
    if not candidate_ready or plan is None:
        return candidate_ready
    if candidate_plan_requires_paid_authorization(plan):
        return bool(registration.supports_paid_execution and
                    callable(getattr(backend, "validate_paid_authorization", None)))
    return True


def default_registry() -> dict[str, ProviderRegistration]:
    # Lazy imports keep provider SDKs out of the API process.
    from .backends import DemoBackend, ExistingRunPodBridge, ModalSandboxBackend
    from .local_backend import LocalContainerBackend
    from .admission import local_cpu_policy_enabled
    entries = (
        ProviderRegistration("demo", "local_simulation_no_gpu", lambda s: True, lambda s: DemoBackend()),
        ProviderRegistration("local_cpu", "local_worker_container", local_cpu_policy_enabled,
                             lambda s: LocalContainerBackend(s),
                             "Registered smoke workloads only; operator policy defaults disabled."),
        ProviderRegistration("modal", "dedicated_worker", lambda s: s.enable_modal, ModalSandboxBackend),
        ProviderRegistration("runpod", "existing_core_bridge",
            lambda s: s.enable_runpod_bridge and bool(s.runpod_factory),
            lambda s: ExistingRunPodBridge(s.runpod_factory),
            "Existing RunPod CI is unchanged; this gateway does not dispatch it."),
    )
    return {entry.name: entry for entry in entries}
