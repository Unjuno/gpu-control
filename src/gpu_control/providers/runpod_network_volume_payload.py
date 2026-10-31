from __future__ import annotations

from typing import Any, Mapping

from .runpod_network_volume import RunPodNetworkVolumeEvidence
from .runpod_v2 import RunPodV2Error


def bind_network_volume_to_create_payload(
    payload: Mapping[str, Any],
    evidence: RunPodNetworkVolumeEvidence,
) -> dict[str, object]:
    """Add the trusted volume using the current REST v2 ``mounts`` schema."""

    if not isinstance(payload, Mapping):
        raise RunPodV2Error("RunPod create payload must be a mapping")
    evidence.validate_shape()
    if payload.get("cloud") != "SECURE":
        raise RunPodV2Error("RunPod Network Volume result transport requires SECURE cloud")
    if any(key in payload for key in ("mounts", "networkVolumeId", "volumeMountPath", "dataCenterIds")):
        raise RunPodV2Error("RunPod create payload already contains volume configuration")
    result: dict[str, object] = dict(payload)
    result["dataCenterIds"] = [evidence.data_center_id]
    result["mounts"] = {
        "network": [{"volumeId": evidence.network_volume_id, "path": evidence.mount_path}]
    }
    return result
