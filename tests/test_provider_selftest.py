import gpu_control.source as source_module
from gpu_control.provider_selftest import run_provider_contract_self_test


def test_provider_contract_self_test_does_not_use_github_network(monkeypatch) -> None:
    def fail_network(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("offline provider self-test attempted network access")

    monkeypatch.setattr(source_module, "urlopen", fail_network)

    result = run_provider_contract_self_test()

    assert result["status"] == "ok"
    assert result["network_access"] is False
    assert result["external_resources_created"] is False
    assert result["billable_compute"] is False


def test_provider_contract_self_test_is_deterministic() -> None:
    first = run_provider_contract_self_test()
    second = run_provider_contract_self_test()

    assert first["plan_fingerprint"] == second["plan_fingerprint"]
    assert first["submission_receipt_fingerprint"] == second["submission_receipt_fingerprint"]
    assert first["result_manifest_fingerprint"] == second["result_manifest_fingerprint"]
    assert first["artifact_dispositions"] == second["artifact_dispositions"]
