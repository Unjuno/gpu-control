from __future__ import annotations

from gpu_gateway.config import Workload
from gpu_gateway import worker as worker_module
from gpu_gateway.runpod_inventory import SOURCE, collect_runpod_inventory
from gpu_control.capabilities import Availability, CapabilityEvidence
from gpu_gateway.config import Settings
from gpu_gateway.store import Store
from gpu_gateway.worker import Worker
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class FakeClient:
    def __init__(self, gpu_types=None, data_centers=None):
        self._gpu_types = gpu_types if gpu_types is not None else [{
            "id": "GPU-4090", "memoryInGb": 24, "secureCloud": True,
            "securePrice": 0.44, "maxGpuCountSecureCloud": 8,
        }]
        self._data_centers = data_centers if data_centers is not None else [{
            "id": "US-TX-1", "gpuAvailability": [{
                "gpuTypeId": "GPU-4090", "available": True,
                "availableCount": 2, "stockStatus": "HIGH",
            }],
        }]

    def gpu_types(self):
        return self._gpu_types

    def data_centers(self):
        return self._data_centers


def _workload(**changes):
    value = {
        "provider": "runpod", "gpu": "RTX 4090", "gpu_count": 1,
        "max_runtime_seconds": 600, "provider_resource_id": "GPU-4090",
        "provider_data_center_id": "US-TX-1",
    }
    value.update(changes)
    return Workload.model_validate(value)


def test_inventory_binds_exact_operator_mapped_resource_and_keeps_execution_unknown():
    result = collect_runpod_inventory(
        {"registered": _workload()}, FakeClient(), observed_at=1_800_000_000,
        expires_at=1_800_000_120,
    )
    assert result["inventory_complete"] is True
    assert len(result["candidates"]) == 1
    evidence = CapabilityEvidence.from_dict(result["candidates"][0])
    assert evidence.evidence_source == SOURCE
    assert evidence.availability is Availability.AVAILABLE
    assert evidence.resource_id == "GPU-4090@US-TX-1"
    assert evidence.max_vram_mib == 24 * 1024
    assert evidence.costs.accelerator_usd is not None
    assert evidence.costs.known_total_usd is None
    assert evidence.max_runtime_seconds is None
    assert evidence.supported_operating_systems is None
    assert evidence.result_transports is None


def test_inventory_does_not_call_partial_or_ambiguous_catalog_complete():
    workload = _workload()
    missing_dc = FakeClient(data_centers=[])
    result = collect_runpod_inventory(
        {"registered": workload}, missing_dc, observed_at=1_800_000_000,
        expires_at=1_800_000_120,
    )
    assert result == {"inventory_complete": False, "candidates": []}

    duplicate = FakeClient(gpu_types=[FakeClient().gpu_types()[0]] * 2)
    result = collect_runpod_inventory(
        {"registered": workload}, duplicate, observed_at=1_800_000_000,
        expires_at=1_800_000_120,
    )
    assert result == {"inventory_complete": False, "candidates": []}


def test_inventory_marks_explicit_zero_stock_unavailable():
    workload = _workload()
    client = FakeClient(data_centers=[{
        "id": "US-TX-1", "gpuAvailability": [{
            "gpuTypeId": "GPU-4090", "available": False,
            "availableCount": 0, "stockStatus": "LOW",
        }],
    }])
    result = collect_runpod_inventory(
        {"registered": workload}, client, observed_at=1_800_000_000,
        expires_at=1_800_000_120,
    )
    assert result["inventory_complete"] is True
    evidence = CapabilityEvidence.from_dict(result["candidates"][0])
    assert evidence.availability is Availability.UNAVAILABLE


def test_worker_collects_only_when_enabled_and_never_from_supervisor(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings = Settings(
        enable_runpod_evidence=True,
        runpod_api_key="test-read-only-key",
        provider_evidence_public_keys_json=json.dumps({"worker-test": public_pem.decode()}),
        provider_evidence_signing_key_id="worker-test",
        provider_evidence_signing_key_pem=private_pem,
    )
    settings.validate()
    store = Store(f"sqlite:///{tmp_path / 'collector.db'}")
    store.initialize()
    monkeypatch.setattr(worker_module, "load_workloads", lambda: {"registered": _workload()})
    monkeypatch.setattr(worker_module, "runpod_evidence_client", lambda _key: FakeClient())

    worker = Worker(store, settings, {}, clock=lambda: 1_800_000_001, registry={})
    worker._maybe_collect_runpod_evidence(1_800_000_000)
    envelope = store.read_verified_provider_observation(
        "runpod", settings.provider_evidence_trusted_keys, now=1_800_000_001,
    )
    assert envelope["source"] == SOURCE
    assert envelope["source_revision"] == "graphql-spec-1.1.0"
    assert envelope["observed_at"] == 1_800_000_000
    assert envelope["payload"]["candidates"][0]["observed_at_utc"] == "2027-01-15T08:00:00Z"
    assert envelope["payload"]["inventory_complete"] is True

    class ForbiddenClient:
        def __init__(self, _key):
            raise AssertionError("provider client must not be created")

    monkeypatch.setattr(worker_module, "runpod_evidence_client", ForbiddenClient)
    supervisor = Worker(store, settings, {}, clock=lambda: 1_800_000_120,
                        registry={}, role="supervisor")
    supervisor._maybe_collect_runpod_evidence(1_800_000_120)
