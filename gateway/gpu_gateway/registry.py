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
    # Credits require their own owner decision and gross-debit evidence;
    # account credits alone are not consent to use them.
    supports_credit_execution: bool = False


def candidate_plan_requires_paid_authorization(plan: dict | object) -> bool:
    """Return true for paid or unclassified plans; credits use a separate gate."""
    return candidate_plan_authorization_kind(plan) == "paid"


def candidate_plan_authorization_kind(plan: dict | object) -> str | None:
    """Classify the independent authority gate required by a candidate plan.

    ``CREDIT_BACKED`` is deliberately separate from paid execution. It remains
    inadmissible until an adapter validates a run-specific owner decision and
    gross-credit-debit evidence. Unknown/malformed classes remain fail-closed.
    """
    if isinstance(plan, dict):
        evidence = plan.get("cost_evidence")
        provider = plan.get("provider")
    else:
        evidence = getattr(plan, "cost_evidence", None)
        provider = getattr(plan, "provider", None)
    if not isinstance(evidence, dict) and evidence is not None:
        evidence = getattr(evidence, "model_dump", lambda **_: None)(mode="python")
    if not isinstance(evidence, dict):
        return "paid"
    classification = evidence.get("classification")
    if classification == "CREDIT_BACKED":
        return "credit"
    amount = evidence.get("additional_cost_usd")
    try:
        additional = Decimal(str(amount)) if amount is not None else None
    except (InvalidOperation, ValueError):
        return "paid"
    zero_cost_classes = {"FREE", "FREE_QUOTA"}
    if provider in {"local_cpu", "local_gpu"}:
        zero_cost_classes.add("LOCAL")
    if classification in zero_cost_classes and additional is not None and additional == 0:
        return None
    return "paid"


def supports_candidate_execution(registration: ProviderRegistration | None,
                                 backend: object, plan: dict | object | None = None) -> bool:
    """Require the complete candidate-bound dispatch and recovery lifecycle.

    The registry flag is an operator-reviewed opt-in. The runtime shape check
    prevents a stale or misconfigured registration from sending a bound plan
    through a legacy ``start(run)`` adapter that ignores its selected resource.
    Cancellation and no-create reconciliation are required too: the worker
    calls them during timeout/cancel and ambiguous-start recovery.
    """
    required = (
        "start_candidate_bound", "validate_candidate_observation", "capture",
        "cancel", "reconcile", "cleanup", "is_clean",
    )
    candidate_ready = bool(
        registration is not None and registration.supports_candidate_binding and
        all(callable(getattr(backend, name, None)) for name in required)
    )
    if not candidate_ready or plan is None:
        return candidate_ready
    provider = plan.get("provider") if isinstance(plan, dict) else getattr(plan, "provider", None)
    if provider == "runpod":
        lease_contract = (
            "prepare_provider_account_lease",
            "start_candidate_bound_with_account_lease",
            "reconcile_candidate_bound_with_account_lease",
            "provider_job_id",
        )
        if not all(callable(getattr(backend, name, None)) for name in lease_contract):
            return False
    authorization_kind = candidate_plan_authorization_kind(plan)
    if authorization_kind == "paid":
        return bool(registration.supports_paid_execution and
                    callable(getattr(backend, "validate_paid_authorization", None)))
    if authorization_kind == "credit":
        return bool(registration.supports_credit_execution and
                    callable(getattr(backend, "validate_credit_authorization", None)))
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
