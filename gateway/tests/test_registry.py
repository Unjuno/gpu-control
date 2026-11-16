from gpu_gateway.registry import (
    ProviderRegistration,
    candidate_plan_authorization_kind,
    candidate_plan_requires_paid_authorization,
    supports_candidate_execution,
    default_registry,
    default_artifact_registry,
)
from gpu_gateway.config import Settings
from gpu_gateway.kaggle_backend import KaggleBackend


def test_candidate_execution_requires_reviewed_registration_and_full_lifecycle():
    class CompleteBackend:
        def start_candidate_bound(self, run):
            pass

        def capture(self, handle):
            pass

        def validate_candidate_observation(self, run, observation):
            return True

        def cancel(self, handle):
            pass

        def reconcile(self, run):
            return None

        def cleanup(self, handle):
            pass

        def is_clean(self, handle):
            return True

    backend = CompleteBackend()
    enabled = ProviderRegistration("example", "worker", lambda _settings: True,
                                   lambda _settings: backend,
                                   supports_candidate_binding=True)
    disabled = ProviderRegistration("example", "worker", lambda _settings: True,
                                    lambda _settings: backend)
    assert supports_candidate_execution(enabled, backend)
    assert not supports_candidate_execution(disabled, backend)
    assert not supports_candidate_execution(None, backend)


def test_legacy_start_adapter_cannot_be_marked_candidate_ready():
    class LegacyBackend:
        def start(self, run):
            pass

        def capture(self, handle):
            pass

        def validate_candidate_observation(self, run, observation):
            return True

        def cleanup(self, handle):
            pass

        def is_clean(self, handle):
            return True

    registration = ProviderRegistration("example", "worker", lambda _settings: True,
                                        lambda _settings: None,
                                        supports_candidate_binding=True)
    assert not supports_candidate_execution(registration, LegacyBackend())


def test_paid_candidate_plan_requires_paid_capability_and_run_specific_validator():
    class Backend:
        def start_candidate_bound(self, run):
            pass

        def validate_candidate_observation(self, run, observation):
            return True

        def validate_paid_authorization(self, run):
            return True

        def cancel(self, handle):
            pass

        def reconcile(self, run):
            return None

        def capture(self, handle):
            pass

        def cleanup(self, handle):
            pass

        def is_clean(self, handle):
            return True

        def prepare_provider_account_lease(self, run):
            return None

        def start_candidate_bound_with_account_lease(self, run, request_challenge):
            pass

        def reconcile_candidate_bound_with_account_lease(self, run, request_challenge):
            return None

        def provider_job_id(self, handle):
            return "pod-1"

    plan = {"provider": "runpod", "cost_evidence": {
        "classification": "PAID", "additional_cost_usd": "0.05"}}
    backend = Backend()
    unpaid = ProviderRegistration("runpod", "worker", lambda _settings: True,
                                  lambda _settings: backend,
                                  supports_candidate_binding=True)
    paid = ProviderRegistration("runpod", "worker", lambda _settings: True,
                                lambda _settings: backend,
                                supports_candidate_binding=True,
                                supports_paid_execution=True)
    assert candidate_plan_requires_paid_authorization(plan)
    assert not supports_candidate_execution(unpaid, backend, plan)
    assert supports_candidate_execution(paid, backend, plan)
    assert not candidate_plan_requires_paid_authorization({
        "provider": "modal",
        "cost_evidence": {"classification": "FREE", "additional_cost_usd": "0"},
    })
    assert candidate_plan_requires_paid_authorization({
        "provider": "runpod",
        "cost_evidence": {"classification": "LOCAL", "additional_cost_usd": "0"},
    })


def test_credit_backed_candidate_uses_independent_authority_gate():
    class Backend:
        def start_candidate_bound(self, run): pass
        def validate_candidate_observation(self, run, observation): return True
        def capture(self, handle): pass
        def cancel(self, handle): pass
        def reconcile(self, run): return None
        def cleanup(self, handle): pass
        def is_clean(self, handle): return True
        def validate_paid_authorization(self, run): return True

    plan = {"provider": "modal", "cost_evidence": {
        "classification": "CREDIT_BACKED", "additional_cost_usd": "0"}}
    backend = Backend()
    no_credit_gate = ProviderRegistration(
        "modal", "worker", lambda _settings: True, lambda _settings: backend,
        supports_candidate_binding=True, supports_paid_execution=True,
    )
    credit_gate_without_validator = ProviderRegistration(
        "modal", "worker", lambda _settings: True, lambda _settings: backend,
        supports_candidate_binding=True, supports_credit_execution=True,
    )
    assert candidate_plan_authorization_kind(plan) == "credit"
    assert not candidate_plan_requires_paid_authorization(plan)
    assert not supports_candidate_execution(no_credit_gate, backend, plan)
    assert not supports_candidate_execution(credit_gate_without_validator, backend, plan)

    backend.validate_credit_authorization = lambda run: True
    assert supports_candidate_execution(credit_gate_without_validator, backend, plan)


def test_runpod_candidate_requires_durable_account_lease_contract():
    class CandidateBackend:
        def start_candidate_bound(self, run): pass
        def validate_candidate_observation(self, run, observation): return True
        def capture(self, handle): pass
        def cancel(self, handle): pass
        def reconcile(self, run): return None
        def cleanup(self, handle): pass
        def is_clean(self, handle): return True
        def validate_paid_authorization(self, run): return True

    plan = {"provider": "runpod", "cost_evidence": {
        "classification": "FREE", "additional_cost_usd": "0"}}
    backend = CandidateBackend()
    registration = ProviderRegistration(
        "runpod", "worker", lambda _settings: True, lambda _settings: backend,
        supports_candidate_binding=True,
    )
    assert not supports_candidate_execution(registration, backend, plan)

    class LeaseCapableBackend(CandidateBackend):
        def prepare_provider_account_lease(self, run): pass
        def start_candidate_bound_with_account_lease(self, run, request_challenge): pass
        def reconcile_candidate_bound_with_account_lease(self, run, request_challenge): pass
        def provider_job_id(self, handle): pass

    lease_backend = LeaseCapableBackend()
    assert supports_candidate_execution(registration, lease_backend, plan)


def test_kaggle_is_registered_but_not_falsely_candidate_or_cancel_ready(tmp_path):
    registration = default_registry()["kaggle"]
    disabled = Settings()
    enabled = Settings(
        enable_kaggle=True,
        kaggle_username="owner",
        kaggle_staging_root=str(tmp_path),
    )

    assert registration.enabled(disabled) is False
    assert registration.enabled(enabled) is True
    assert isinstance(registration.factory(enabled), KaggleBackend)
    assert registration.supports_candidate_binding is True
    assert registration.supports_cancellation is False
    assert "cancellation" in registration.note.lower()


def test_huggingface_hub_is_a_separate_artifact_service_not_execution_provider():
    artifacts = default_artifact_registry()
    providers = default_registry()
    settings = Settings(
        hf_token="hf_worker_secret",
        hf_artifact_repositories=("owner/private-artifacts",),
    )

    assert "huggingface_hub" in artifacts
    assert artifacts["huggingface_hub"].enabled(settings) is True
    assert "huggingface_hub" not in providers
