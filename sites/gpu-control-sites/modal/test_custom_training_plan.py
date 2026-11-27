import pytest

from custom_training_plan import validate_custom_plan, validate_output_paths


@pytest.fixture
def inputs():
    now = 1_800_000_000
    settings = {"image_id": "im-Abcdefgh1234", "gpu": "L4", "hourly_microusd": 400000,
                "staging_hourly_microusd": 200000,
                "quote_expires_at": now + 600, "max_runtime_seconds": 600,
                "max_cost_ceiling_microusd": 250000, "monthly_microusd": 30000000,
                "control_plane_sha": "1" * 40, "now": now}
    manifest = {"schema_version": 1, "task": "train", "entrypoint": "train.py",
                "dependencies_lock": "requirements.lock", "gpu_profiles": ["L4"],
                "outputs": ["checkpoints", "metrics.json"],
                "python_version": "3.12"}
    plan = {"execution_kind": "owner_selected_python", "run_id": "a" * 32,
            "registration_id": "b" * 32, "execution_spec_id": "c" * 32,
            "repository": "owner/project", "commit": "d" * 40, "command": ["python", "train.py"],
            "manifest": manifest,
            "manifest_sha256": "e" * 64, "lock_sha256": "f" * 64, "dependencies_lock": "requirements.lock",
            "image_id": settings["image_id"], "image_digest": settings["image_id"],
            "provider": "modal", "provider_resource_id": "gpu-control-provider-adapter/owner_training",
            "gpu": "L4", "gpu_count": 1, "runtime_seconds": 120,
            "max_cost_microusd": 100000, "hourly_microusd": 400000, "quote_expires_at": now + 600,
            "estimated_cost_microusd": 70371, "monthly_budget_microusd": 30000000, "task": "train",
            "staging_hourly_microusd": 200000, "staging_runtime_seconds": 300,
            "staging_cpu_cores": 1, "staging_memory_mib": 1024, "control_plane_sha": "1" * 40}
    settings.update(manifest=manifest, lock_sha256="f" * 64)
    return plan, settings


def test_accepts_only_current_configured_plan(inputs):
    plan, settings = inputs
    validate_custom_plan(plan, **settings)
    for changed in ({"image_id": "im-Other12345"}, {"gpu_count": True}):
        with pytest.raises(ValueError, match="training_profile_mismatch"):
            validate_custom_plan({**plan, **changed}, **settings)
    with pytest.raises(ValueError, match="training_manifest_mismatch"):
        validate_custom_plan({**plan, "gpu": "T4"}, **settings)


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
    for command in (["bash", "-c", "python train.py"], ["python", "../outside.py"],
                    ["python", "train.py", "--unreviewed"]):
        with pytest.raises(ValueError, match="invalid_command"):
            validate_custom_plan({**plan, "command": command}, **settings)


def test_output_manifest_only_allows_bounded_declared_artifact_paths():
    assert validate_output_paths(["checkpoints", "metrics.json", "artifacts/eval/results.csv"]) == [
        "artifacts/eval/results.csv"]
    for outputs in (["checkpoints", "metrics.json", "artifacts/../secret"],
                    ["checkpoints", "metrics.json", "artifacts/*.csv"],
                    ["checkpoints", "metrics.json", "private.txt"],
                    ["checkpoints", "metrics.json", "artifacts/x", "artifacts/x"]):
        with pytest.raises(ValueError, match="training_manifest_mismatch"):
            validate_output_paths(outputs)
