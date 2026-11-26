import pytest

from custom_training_plan import validate_custom_plan


@pytest.fixture
def inputs():
    now = 1_800_000_000
    settings = {"image_id": "im-Abcdefgh1234", "gpu": "L4", "hourly_microusd": 400000,
                "quote_expires_at": now + 600, "now": now}
    plan = {"run_id": "a" * 32, "registration_id": "b" * 32, "execution_spec_id": "c" * 32,
            "repository": "owner/project", "commit": "d" * 40, "command": ["python", "train.py"],
            "image_id": settings["image_id"], "gpu": "L4", "gpu_count": 1, "runtime_seconds": 120,
            "max_cost_microusd": 100000, "hourly_microusd": 400000, "quote_expires_at": now + 600}
    return plan, settings


def test_accepts_only_current_configured_plan(inputs):
    plan, settings = inputs
    validate_custom_plan(plan, **settings)
    for changed in ({"image_id": "im-Other12345"}, {"gpu": "T4"}, {"gpu_count": True}):
        with pytest.raises(ValueError, match="training_profile_mismatch"):
            validate_custom_plan({**plan, **changed}, **settings)


def test_refuses_stale_or_caller_supplied_price_and_low_budget(inputs):
    plan, settings = inputs
    for changed in ({"hourly_microusd": 1}, {"quote_expires_at": settings["now"]}):
        with pytest.raises(ValueError, match="training_quote_invalid"):
            validate_custom_plan({**plan, **changed}, **settings)
    with pytest.raises(ValueError, match="training_budget_invalid"):
        validate_custom_plan({**plan, "max_cost_microusd": 1}, **settings)
    with pytest.raises(ValueError, match="training_quote_invalid"):
        validate_custom_plan(plan, **{**settings, "now": settings["quote_expires_at"]})


def test_rejects_untrusted_source_and_malformed_commands(inputs):
    plan, settings = inputs
    with pytest.raises(ValueError, match="invalid_source"):
        validate_custom_plan({**plan, "repository": "../outside"}, **settings)
    with pytest.raises(ValueError, match="invalid_command"):
        validate_custom_plan({**plan, "command": ["python\x00bad"]}, **settings)
