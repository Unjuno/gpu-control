from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..execution import ApprovedExecutionPlan, ExecutionGateError
from .runpod_network_volume import RunPodNetworkVolumeEvidence
from .runpod_v2 import PublishedImageEvidence, RunPodCompletionLaunch, RunPodV2Error


RUNPOD_V1_BASE_URL = "https://rest.runpod.io/v1"
_ALLOWED_CLOUDS = {"SECURE", "COMMUNITY"}
_V1_STATUSES = {"RUNNING", "EXITED", "TERMINATED"}


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunPodV2Error(f"{label} must be a JSON object")
    return value


def _positive_decimal(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RunPodV2Error(f"{label} must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RunPodV2Error(f"{label} must be finite and positive")
    return parsed


def build_create_pod_payload_v1(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    *,
    cloud: str,
    disk_gb: int = 20,
    completion: RunPodCompletionLaunch | None = None,
    network_volume: RunPodNetworkVolumeEvidence | None = None,
) -> dict[str, object]:
    """Build the minimal current RunPod REST v1 create body from trusted state."""

    try:
        plan.validate_shape()
    except ExecutionGateError as exc:
        raise RunPodV2Error(str(exc)) from exc
    if plan.provider != "runpod":
        raise RunPodV2Error("RunPod REST v1 payload requires a runpod approved plan")
    image.validate_against_plan(plan)
    if cloud not in _ALLOWED_CLOUDS:
        raise RunPodV2Error("RunPod REST v1 cloud must be SECURE or COMMUNITY")
    if isinstance(disk_gb, bool) or not isinstance(disk_gb, int) or disk_gb < 1:
        raise RunPodV2Error("RunPod REST v1 disk_gb must be a positive integer")

    name = f"gpu-control-{plan.fingerprint()[7:19]}"
    environment: dict[str, str] | None = None
    if completion is not None:
        environment = completion.provider_environment(plan)
        name = completion.challenge.execution_name

    payload: dict[str, object] = {
        "name": name,
        "imageName": image.image_reference,
        "computeType": "GPU",
        "gpuTypeIds": [plan.provider_resource_id],
        "gpuTypePriority": "custom",
        "gpuCount": plan.gpu_count,
        "containerDiskInGb": disk_gb,
        "cloudType": cloud,
        "globalNetworking": False,
        "interruptible": False,
        "supportPublicIp": False,
        "ports": [],
        "dockerEntrypoint": [],
        "dockerStartCmd": [],
    }
    if environment is not None:
        payload["env"] = environment
    if network_volume is not None:
        network_volume.validate_shape()
        if cloud != "SECURE":
            raise RunPodV2Error("RunPod Network Volume result transport requires SECURE cloud")
        payload["networkVolumeId"] = network_volume.network_volume_id
        payload["volumeMountPath"] = network_volume.mount_path
        payload["dataCenterIds"] = [network_volume.data_center_id]
        payload["dataCenterPriority"] = "custom"
    return payload


def normalize_v1_pod(
    payload: Mapping[str, Any],
    *,
    require_machine: bool,
    expected_network_volume: RunPodNetworkVolumeEvidence | None = None,
) -> dict[str, object]:
    """Normalize the current REST v1 Pod schema to gpu-control's canonical view."""

    pod = _require_mapping(payload, "RunPod REST v1 Pod")
    pod_id = pod.get("id")
    name = pod.get("name")
    image = pod.get("image")
    status = pod.get("desiredStatus")
    gpu = _require_mapping(pod.get("gpu"), "RunPod REST v1 Pod gpu")
    cost = _positive_decimal(pod.get("costPerHr"), "RunPod REST v1 Pod costPerHr")

    if not isinstance(pod_id, str) or not pod_id.strip():
        raise RunPodV2Error("RunPod REST v1 Pod id is required")
    if not isinstance(name, str) or not name.strip():
        raise RunPodV2Error("RunPod REST v1 Pod name is required")
    if not isinstance(image, str) or not image.strip():
        raise RunPodV2Error("RunPod REST v1 Pod image is required")
    if status not in _V1_STATUSES:
        raise RunPodV2Error("RunPod REST v1 Pod desiredStatus is unknown or missing")
    gpu_id = gpu.get("id")
    gpu_count = gpu.get("count")
    if not isinstance(gpu_id, str) or not gpu_id.strip():
        raise RunPodV2Error("RunPod REST v1 Pod gpu.id is required")
    if isinstance(gpu_count, bool) or not isinstance(gpu_count, int) or gpu_count < 1:
        raise RunPodV2Error("RunPod REST v1 Pod gpu.count must be a positive integer")

    machine = pod.get("machine")
    cloud: str | None = None
    data_center_id: str | None = None
    if machine is not None:
        machine_map = _require_mapping(machine, "RunPod REST v1 Pod machine")
        secure = machine_map.get("secureCloud")
        if not isinstance(secure, bool):
            raise RunPodV2Error("RunPod REST v1 Pod machine.secureCloud must be a boolean")
        cloud = "SECURE" if secure else "COMMUNITY"
        candidate_dc = machine_map.get("dataCenterId")
        if candidate_dc is not None and not isinstance(candidate_dc, str):
            raise RunPodV2Error("RunPod REST v1 Pod machine.dataCenterId must be a string")
        data_center_id = candidate_dc
    elif require_machine:
        raise RunPodV2Error("RunPod REST v1 Pod machine evidence is required")

    if expected_network_volume is not None:
        expected_network_volume.validate_shape()
        volume = _require_mapping(pod.get("networkVolume"), "RunPod REST v1 Pod networkVolume")
        if volume.get("id") != expected_network_volume.network_volume_id:
            raise RunPodV2Error("RunPod REST v1 Pod network volume id mismatch")
        if volume.get("dataCenterId") != expected_network_volume.data_center_id:
            raise RunPodV2Error("RunPod REST v1 Pod network volume data center mismatch")
        if pod.get("volumeMountPath") != expected_network_volume.mount_path:
            raise RunPodV2Error("RunPod REST v1 Pod network volume mount path mismatch")
        if data_center_id is not None and data_center_id != expected_network_volume.data_center_id:
            raise RunPodV2Error("RunPod REST v1 Pod machine data center does not match network volume")

    result: dict[str, object] = {
        "id": pod_id.strip(),
        "name": name.strip(),
        "image": image.strip(),
        "gpu": {"id": gpu_id.strip(), "count": gpu_count},
        "cost": cost,
        "status": status,
    }
    if cloud is not None:
        result["cloud"] = cloud
    if data_center_id is not None:
        result["dataCenterId"] = data_center_id
    if expected_network_volume is not None:
        result["networkVolumeId"] = expected_network_volume.network_volume_id
        result["volumeMountPath"] = expected_network_volume.mount_path
    return result


def normalize_v1_inventory(payload: object) -> dict[str, list[dict[str, str]]]:
    """Normalize the REST v1 List Pods array for occupancy/reconciliation code."""

    if not isinstance(payload, list):
        raise RunPodV2Error("RunPod REST v1 List Pods response must be a JSON array")
    pods: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for entry in payload:
        pod = _require_mapping(entry, "RunPod REST v1 List Pods entry")
        pod_id = pod.get("id")
        name = pod.get("name")
        status = pod.get("desiredStatus")
        if not isinstance(pod_id, str) or not pod_id.strip():
            raise RunPodV2Error("RunPod REST v1 inventory Pod id is required")
        if not isinstance(name, str) or not name.strip():
            raise RunPodV2Error("RunPod REST v1 inventory Pod name is required")
        if status not in _V1_STATUSES:
            raise RunPodV2Error("RunPod REST v1 inventory desiredStatus is unknown or missing")
        normalized_id = pod_id.strip()
        if normalized_id in seen_ids:
            raise RunPodV2Error("RunPod REST v1 inventory contains duplicate Pod ids")
        seen_ids.add(normalized_id)
        pods.append({"id": normalized_id, "name": name.strip(), "status": status})
    return {"pods": pods}


class RunPodV1HttpClient:
    """Fixed-origin client for the current stable RunPod Pod REST API v1."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise RunPodV2Error("RunPod API key is required")
        if api_key != api_key.strip() or any(character.isspace() for character in api_key):
            raise RunPodV2Error("RunPod API key must not contain whitespace")
        if timeout <= 0:
            raise RunPodV2Error("RunPod HTTP timeout must be positive")
        if not callable(opener):
            raise RunPodV2Error("RunPod HTTP opener must be callable")
        self._api_key = api_key
        self._timeout = timeout
        self._opener = opener

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int,
        body: Mapping[str, Any] | None = None,
    ) -> object | None:
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
            raise RunPodV2Error("RunPod API path must be an absolute single-origin path")
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "gpu-control",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{RUNPOD_V1_BASE_URL}{path}", data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None)
                raw = response.read()
        except HTTPError as exc:
            detail = ""
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
                if isinstance(error_payload, Mapping):
                    for field in ("message", "detail", "error"):
                        value = error_payload.get(field)
                        if isinstance(value, str) and value.strip():
                            detail = f": {value.strip()}"
                            break
            except Exception:
                pass
            raise RunPodV2Error(f"RunPod API returned HTTP {exc.code}{detail}") from exc
        except URLError as exc:
            raise RunPodV2Error("RunPod API could not be reached") from exc

        if status != expected_status:
            raise RunPodV2Error(f"RunPod API returned unexpected HTTP status {status}")
        if expected_status == 204:
            if raw not in {b"", None}:
                raise RunPodV2Error("RunPod 204 response unexpectedly contained a body")
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RunPodV2Error("RunPod API returned invalid JSON") from exc

    def list_pods(self) -> dict[str, list[dict[str, str]]]:
        raw = self._request("GET", "/pods", expected_status=200)
        return normalize_v1_inventory(raw)

    def create_pod(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise RunPodV2Error("RunPod REST v1 create payload must be a mapping")
        result = self._request("POST", "/pods", expected_status=201, body=payload)
        return _require_mapping(result, "RunPod REST v1 create response")

    def get_pod(self, pod_id: str) -> Mapping[str, Any]:
        encoded = self._pod_id(pod_id)
        query = urlencode({"includeMachine": "true", "includeNetworkVolume": "true"})
        result = self._request("GET", f"/pods/{encoded}?{query}", expected_status=200)
        return _require_mapping(result, "RunPod REST v1 get response")

    def terminate_pod(self, pod_id: str) -> None:
        encoded = self._pod_id(pod_id)
        self._request("DELETE", f"/pods/{encoded}", expected_status=204)

    @staticmethod
    def _pod_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RunPodV2Error("RunPod pod id is required")
        if value != value.strip() or any(character.isspace() for character in value):
            raise RunPodV2Error("RunPod pod id must not contain whitespace")
        return quote(value, safe="")
