from __future__ import annotations

from typing import Any, Mapping

from .runpod_network_volume import RunPodNetworkVolumeEvidence
from .runpod_v2 import RunPodV2Error


def bind_network_volume_to_create_payload(
    payload: Mapping[str, Any],
    evidence: RunPodNetworkVolumeEvidence,
) -> dict[str, object]:
    """Add only the trusted persistent-result volume to a prepared Pod create body."""

    if not isinstance(payload, Mapping):
        raise RunPodV2Error("RunPod create payload must be a mapping")
    evidence.validate_shape()
    if "networkVolumeId" in payload or "volumeMountPath" in payload:
        raise RunPodV2Error("RunPod create payload already contains volume configuration")
    result: dict[str, object] = dict(payload)
    result["networkVolumeId"] = evidence.network_volume_id
    result["volumeMountPath"] = evidence.mount_path
    return result
