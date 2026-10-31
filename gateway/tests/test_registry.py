from gpu_gateway.registry import (
    ProviderRegistration,
    candidate_plan_requires_paid_authorization,
    supports_candidate_execution,
)


def test_candidate_execution_requires_reviewed_registration_and_full_lifecycle():
    class CompleteBackend:
        def start_candidate_bound(self, run):
            pass

        def capture(self, handle):
            pass

        def validate_candidate_observation(self, run, observation):
            return True

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

        def capture(self, handle):
            pass

        def cleanup(self, handle):
            pass

        def is_clean(self, handle):
            return True

    plan = {"cost_evidence": {"classification": "PAID", "additional_cost_usd": "0.05"}}
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
