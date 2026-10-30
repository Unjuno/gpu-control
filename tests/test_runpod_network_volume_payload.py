from __future__ import annotations

import pytest

from gpu_control.providers.runpod_network_volume import RunPodNetworkVolumeEvidence
from gpu_control.providers.runpod_network_volume_payload import bind_network_volume_to_create_payload
from gpu_control.providers.runpod_v2 import RunPodV2Error


def evidence() -> RunPodNetworkVolumeEvidence:
    return RunPodNetworkVolumeEvidence(
        network_volume_id="volume-123",
        data_center_id="US-KS-2",
        verification_reference="runpod-volume:test",
    )


def test_network_volume_uses_rest_v2_mounts_shape_without_mutating_input():
    payload = {
        "name": "gpu-control-test",
        "image": "repo/image@sha256:" + "a" * 64,
        "cloud": "SECURE",
    }

    result = bind_network_volume_to_create_payload(payload, evidence())

    assert result == {
        "name": "gpu-control-test",
        "image": "repo/image@sha256:" + "a" * 64,
        "cloud": "SECURE",
        "dataCenterIds": ["US-KS-2"],
        "mounts": {"network": [{"volumeId": "volume-123", "path": "/outputs"}]},
    }
    assert payload == {
        "name": "gpu-control-test",
        "image": "repo/image@sha256:" + "a" * 64,
        "cloud": "SECURE",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"cloud": "SECURE", "networkVolumeId": "untrusted"},
        {"cloud": "SECURE", "volumeMountPath": "/other"},
        {"cloud": "SECURE", "dataCenterIds": ["US-IL-1"]},
        {"cloud": "SECURE", "mounts": {"network": [{"volumeId": "other", "path": "/outputs"}]}},
        {"cloud": "SECURE", "mounts": {"persistent": {"size": 10, "path": "/outputs"}}},
    ],
)
def test_network_volume_rejects_existing_mount_configuration(payload):
    with pytest.raises(RunPodV2Error, match="already contains volume configuration"):
        bind_network_volume_to_create_payload(payload, evidence())


def test_network_volume_requires_secure_cloud():
    with pytest.raises(RunPodV2Error, match="requires SECURE cloud"):
        bind_network_volume_to_create_payload(
            {"cloud": "COMMUNITY"}, evidence()
        )
