from types import SimpleNamespace
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gpu_gateway.config import Settings, Workload
from gpu_gateway.free_provider_inventory import (
    collect_huggingface_space_inventory,
    collect_kaggle_inventory,
)
from gpu_gateway.store import Store
from gpu_gateway.worker import Worker
import gpu_gateway.worker as worker_module


def _workload(provider, resource, *, runtime=100, cancellation=False, gpu=None):
    return Workload(
        provider=provider,
        image_digest="sha256:" + "1" * 64,
        source_repository="Unjuno/orbitune",
        source_sha="4" * 40,
        source_revision="e" * 40 if provider == "huggingface_space" else "",
        provider_resource_id=resource,
        gpu=gpu or ("NvidiaTeslaT4" if provider == "kaggle" else "zero-gpu-large"),
        operating_system="linux",
        architecture="x86_64",
        gpu_count=1,
        minimum_vram_mib=1,
        network_requirement="disabled",
        result_transport="object_storage",
        max_result_bytes=1024,
        cancellation_required=cancellation,
        cleanup_proof_required=True,
        runtime_requirements=("pytorch", "cuda"),
        max_queue_wait_seconds=600,
        max_runtime_seconds=runtime,
    )


def test_kaggle_inventory_is_free_quota_and_honest_about_cancellation():
    payload = collect_kaggle_inventory(
        {"orbitune": _workload("kaggle", "owner/orbitune")},
        {"gpu": {"remainingSeconds": "600s"}},
        observed_at=1000, expires_at=1120,
    )
    assert payload["inventory_complete"] is True
    candidate = payload["candidates"][0]
    assert candidate["resource_id"] == "owner/orbitune"
    assert candidate["cost_classification"] == "FREE_QUOTA"
    assert set(candidate["costs"].values()) == {"0"}
    assert candidate["overage_behavior"] == "STOPS"
    assert candidate["cancellation_supported"] is False


def test_unknown_kaggle_quota_never_advertises_a_candidate():
    payload = collect_kaggle_inventory(
        {"orbitune": _workload("kaggle", "owner/orbitune")}, {},
        observed_at=1000, expires_at=1120,
    )
    assert payload == {"inventory_complete": False, "candidates": []}


def test_registered_requirements_cannot_inflate_provider_capability_evidence():
    oversized = _workload("kaggle", "owner/orbitune").model_copy(update={
        "cpu": 8, "memory_mib": 65536, "minimum_vram_mib": 65536,
    })
    payload = collect_kaggle_inventory(
        {"orbitune": oversized}, {"gpu": {"remainingSeconds": "600s"}},
        observed_at=1000, expires_at=1120,
    )
    candidate = payload["candidates"][0]
    assert candidate["max_cpu_cores"] == "4"
    assert candidate["max_memory_mib"] == 29 * 1024
    assert candidate["max_vram_mib"] == 30 * 1024


def test_zero_gpu_inventory_blocks_overquota_and_requires_enough_included_seconds():
    workloads = {"eval": _workload("huggingface_space", "owner/eval", runtime=30,
                                     cancellation=False)}
    blocked = collect_huggingface_space_inventory(
        workloads, SimpleNamespace(remaining=100, overquota_used=1),
        verified_space_ids={"owner/eval"}, observed_at=1000, expires_at=1120,
    )
    assert blocked == {"inventory_complete": False, "candidates": []}

    payload = collect_huggingface_space_inventory(
        workloads, SimpleNamespace(remaining=100, overquota_used=0),
        verified_space_ids={"owner/eval"}, observed_at=1000, expires_at=1120,
    )
    candidate = payload["candidates"][0]
    assert payload["inventory_complete"] is True
    assert candidate["resource_id"] == "owner/eval"
    assert candidate["cost_classification"] == "FREE_QUOTA"
    assert candidate["overage_behavior"] == "STOPS"
    assert candidate["cancellation_supported"] is False

    for unsafe in (
        SimpleNamespace(remaining=float("nan"), overquota_used=0),
        SimpleNamespace(remaining=float("inf"), overquota_used=0),
        SimpleNamespace(remaining=100, overquota_used=None),
    ):
        assert collect_huggingface_space_inventory(
            workloads, unsafe, verified_space_ids={"owner/eval"},
            observed_at=1000, expires_at=1120,
        ) == {"inventory_complete": False, "candidates": []}


def test_worker_signs_both_free_provider_snapshots_without_submitting(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings = Settings(
        enable_kaggle_evidence=True,
        kaggle_api_token="kaggle-token",
        enable_huggingface_space_evidence=True,
        hf_space_read_token="worker-only",
        provider_evidence_public_keys_json=json.dumps({"worker-test": public_pem.decode()}),
        provider_evidence_signing_key_id="worker-test",
        provider_evidence_signing_key_pem=private_pem,
    )
    settings.validate()
    store = Store(f"sqlite:///{tmp_path / 'collector.db'}")
    store.initialize()
    monkeypatch.setattr(worker_module, "load_workloads", lambda: {
        "train": _workload("kaggle", "owner/orbitune"),
        "eval": _workload("huggingface_space", "owner/eval", runtime=30,
                          cancellation=False),
    })

    class FakeKaggle:
        def __init__(self, _settings): pass
        def quota_snapshot(self): return {"gpu": {"remainingSeconds": "600s"}}

    class FakeSpace:
        def __init__(self, _settings): pass
        def quota_snapshot(self): return SimpleNamespace(remaining=60, overquota_used=0)
        def verified_space_ids(self, _workloads): return {"owner/eval"}

    monkeypatch.setattr(worker_module, "KaggleBackend", FakeKaggle)
    monkeypatch.setattr(worker_module, "HuggingFaceSpaceBackend", FakeSpace)
    worker = Worker(store, settings, {}, clock=lambda: 1001, registry={})
    worker._maybe_collect_free_provider_evidence(1000)

    for provider in ("kaggle", "huggingface_space"):
        envelope = store.read_verified_provider_observation(
            provider, settings.provider_evidence_trusted_keys, now=1001,
        )
        assert envelope["payload"]["inventory_complete"] is True
        assert envelope["payload"]["candidates"][0]["provider"] == provider
