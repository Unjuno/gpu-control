from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..execution import ApprovedExecutionPlan, ExecutionGateError
from ..lifecycle import JobState


RUNPOD_V2_BASE_URL = "https://api.runpod.io/v2"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_REFERENCE_RE = re.compile(
    r"^[a-z0-9.-]+(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+@sha256:[0-9a-f]{64}$"
)
_EXECUTION_NAME_RE = re.compile(r"^gpu-control-[0-9a-f]{12}-[0-9a-f]{12}$")
_ALLOWED_CLOUDS = {"SECURE", "COMMUNITY"}
_RESULT_MARKER = "GPU_CONTROL_RESULT_JSON_V1:"
_COMPLETION_MARKER = "GPU_CONTROL_COMPLETION_JSON_V2:"


class RunPodV2Error(RuntimeError):
    """Raised when the RunPod API v2 boundary is malformed or unsafe."""


class RunPodV2TransportError(RunPodV2Error):
    """Raised when a request has an ambiguous transport outcome.

    A transport failure during POST /pods may happen after RunPod accepted the
    request. Callers must reconcile account state and must not blindly retry.
    """


class RunPodV2HttpError(RunPodV2Error):
    """RunPod returned a definite HTTP error response."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        suffix = f": {detail}" if detail else ""
        super().__init__(f"RunPod API returned HTTP {status_code}{suffix}")


@dataclass(frozen=True)
class PublishedImageEvidence:
    """Trusted publication evidence for the immutable image submitted to RunPod."""

    plan_fingerprint: str
    image_reference: str
    image_digest: str
    verification_reference: str
    schema_version: int = 1

    def validate_against_plan(self, plan: ApprovedExecutionPlan) -> None:
        plan.validate_shape()
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported published image evidence schema_version")
        if not isinstance(self.plan_fingerprint, str) or not _SHA256_RE.fullmatch(self.plan_fingerprint):
            raise RunPodV2Error("published image plan_fingerprint must be a lowercase sha256 fingerprint")
        if self.plan_fingerprint != plan.fingerprint():
            raise RunPodV2Error("published image evidence does not match the approved plan fingerprint")
        if not isinstance(self.image_digest, str) or not _SHA256_RE.fullmatch(self.image_digest):
            raise RunPodV2Error("published image digest must be a lowercase sha256 digest")
        if self.image_digest != plan.image_digest:
            raise RunPodV2Error("published image digest does not match approved plan")
        if not isinstance(self.image_reference, str) or not _IMAGE_REFERENCE_RE.fullmatch(self.image_reference):
            raise RunPodV2Error("image_reference must be an explicit registry/repository@sha256:digest reference")
        if not self.image_reference.endswith(f"@{self.image_digest}"):
            raise RunPodV2Error("image_reference digest does not match published image digest")
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise RunPodV2Error("published image verification_reference is required")
        if self.verification_reference != self.verification_reference.strip():
            raise RunPodV2Error("published image verification_reference must not contain surrounding whitespace")


def pod_name_for_plan(plan: ApprovedExecutionPlan) -> str:
    """Return the legacy deterministic plan-only name used by offline fixtures."""

    plan.validate_shape()
    return f"gpu-control-{plan.fingerprint()[7:19]}"


def validate_execution_name(value: str) -> str:
    if not isinstance(value, str) or not _EXECUTION_NAME_RE.fullmatch(value):
        raise RunPodV2Error("execution_name must be a gpu-control plan/nonce identity")
    return value


def build_create_pod_payload(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    *,
    disk_gb: int = 20,
    cloud: str = "SECURE",
    execution_name: str | None = None,
    system_env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build the minimal RunPod v2 create-pod body from trusted inputs only.

    ``execution_name`` and ``system_env`` are control-plane-generated values.
    Raw workload or workflow inputs must never be forwarded through either field.
    """

    try:
        plan.validate_shape()
    except ExecutionGateError as exc:
        raise RunPodV2Error(str(exc)) from exc
    if plan.provider != "runpod":
        raise RunPodV2Error("RunPod v2 payload requires a runpod approved plan")
    image.validate_against_plan(plan)
    if isinstance(disk_gb, bool) or not isinstance(disk_gb, int) or disk_gb < 1:
        raise RunPodV2Error("disk_gb must be a positive integer")
    if cloud not in _ALLOWED_CLOUDS:
        raise RunPodV2Error("cloud must be SECURE or COMMUNITY")

    name = pod_name_for_plan(plan) if execution_name is None else validate_execution_name(execution_name)
    payload: dict[str, object] = {
        "name": name,
        "image": image.image_reference,
        "gpu": {
            "id": plan.provider_resource_id,
            "count": plan.gpu_count,
        },
        "disk": disk_gb,
        "cloud": cloud,
        "globalNetworking": False,
    }
    if system_env is not None:
        if not isinstance(system_env, Mapping) or not system_env:
            raise RunPodV2Error("system_env must be a non-empty mapping when supplied")
        normalized: dict[str, str] = {}
        for key, value in system_env.items():
            if not isinstance(key, str) or not re.fullmatch(r"GPU_CONTROL_[A-Z0-9_]+", key):
                raise RunPodV2Error("system_env keys must be GPU_CONTROL_* identifiers")
            if not isinstance(value, str) or not value or value != value.strip():
                raise RunPodV2Error("system_env values must be non-empty trimmed strings")
            if any(ord(character) < 32 or ord(character) == 127 for character in value):
                raise RunPodV2Error("system_env values must not contain control characters")
            normalized[key] = value
        payload["env"] = normalized
    return payload


def _require_mapping(payload: object, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise RunPodV2Error(f"{label} must be a JSON object")
    return payload


def _parse_positive_decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RunPodV2Error(f"{field} must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RunPodV2Error(f"{field} must be finite and positive")
    return parsed


def validate_created_pod(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    pod: Mapping[str, Any],
    *,
    expected_name: str | None = None,
) -> str:
    """Validate RunPod's create/list/get response before it becomes lifecycle identity."""

    image.validate_against_plan(plan)
    pod_id = pod.get("id")
    if not isinstance(pod_id, str) or not pod_id.strip():
        raise RunPodV2Error("RunPod create response is missing pod id")
    if expected_name is None:
        allowed_names = {None, pod_name_for_plan(plan)}
    else:
        allowed_names = {validate_execution_name(expected_name)}
    if pod.get("name") not in allowed_names:
        raise RunPodV2Error("RunPod Pod name does not match approved execution identity")
    if pod.get("image") != image.image_reference:
        raise RunPodV2Error("RunPod create response image does not match published image")
    gpu = _require_mapping(pod.get("gpu"), "RunPod create response gpu")
    if gpu.get("id") != plan.provider_resource_id or gpu.get("count") != plan.gpu_count:
        raise RunPodV2Error("RunPod create response GPU identity does not match approved plan")
    hourly_cost = _parse_positive_decimal(pod.get("cost"), "RunPod create response cost")
    if hourly_cost > plan.verified_hourly_price_usd:
        raise RunPodV2Error("RunPod create response cost exceeds verified approved price")
    translate_pod_status(pod)
    return pod_id.strip()


def translate_pod_status(pod: Mapping[str, Any]) -> JobState:
    """Translate only unambiguous RunPod v2 states into control-plane states."""

    status = pod.get("status")
    if status in {"PROVISIONING", "STARTING"}:
        return JobState.SUBMITTED
    if status == "RUNNING":
        return JobState.RUNNING
    if status == "ERROR":
        return JobState.FAILED
    if status == "TERMINATED":
        return JobState.CANCELLED
    if status == "EXITED":
        raise RunPodV2Error(
            "RunPod EXITED is ambiguous; workload completion evidence is required before assigning a terminal outcome"
        )
    raise RunPodV2Error("RunPod pod status is unknown or missing")


class RunPodV2HttpClient:
    """Small fixed-origin HTTP client for the current RunPod REST API v2 beta."""

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
        self._api_key = api_key
        self._timeout = timeout
        self._opener = opener

    def _http_error(self, exc: HTTPError) -> RunPodV2HttpError:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                detail = payload["detail"]
        except Exception:
            pass
        return RunPodV2HttpError(exc.code, detail)

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not path.startswith("/") or path.startswith("//"):
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
        request = Request(f"{RUNPOD_V2_BASE_URL}{path}", data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None)
                raw = response.read()
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RunPodV2TransportError("RunPod API transport outcome is ambiguous") from exc

        if status != expected_status:
            raise RunPodV2Error(f"RunPod API returned unexpected HTTP status {status}")
        if expected_status == 204:
            if raw not in {b"", None}:
                raise RunPodV2Error("RunPod 204 response unexpectedly contained a body")
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RunPodV2Error("RunPod API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RunPodV2Error("RunPod API returned a non-object JSON response")
        return payload

    def list_pods(self) -> dict[str, Any]:
        payload = self._request("GET", "/pods", expected_status=200)
        assert payload is not None
        if not isinstance(payload.get("pods"), list):
            raise RunPodV2Error("RunPod List Pods response is missing pods")
        return payload

    def list_gpu_types(self, *, cloud: str = "SECURE", count: int = 1) -> dict[str, Any]:
        if cloud not in _ALLOWED_CLOUDS:
            raise RunPodV2Error("cloud must be SECURE or COMMUNITY")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise RunPodV2Error("count must be a positive integer")
        path = f"/catalog/gpus?include=AVAILABILITY&product=POD&count={count}&cloud={quote(cloud)}"
        payload = self._request("GET", path, expected_status=200)
        assert payload is not None
        if not isinstance(payload.get("gpus"), list):
            raise RunPodV2Error("RunPod GPU catalog response is missing gpus")
        return payload

    def create_pod(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = self._request("POST", "/pods", expected_status=201, body=payload)
        assert result is not None
        return result

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        encoded = self._pod_id(pod_id)
        result = self._request("GET", f"/pods/{encoded}", expected_status=200)
        assert result is not None
        return result

    def read_container_log_lines(
        self,
        pod_id: str,
        *,
        tail: int = 5000,
        max_bytes: int = 512 * 1024,
    ) -> tuple[str, ...]:
        """Read bounded container SSE events and stop once both result markers appear."""

        if isinstance(tail, bool) or not isinstance(tail, int) or not 1 <= tail <= 5000:
            raise RunPodV2Error("RunPod log tail must be between 1 and 5000")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise RunPodV2Error("RunPod log max_bytes must be positive")
        encoded = self._pod_id(pod_id)
        path = f"/pods/{encoded}/logs?source=container&tail={tail}"
        request = Request(
            f"{RUNPOD_V2_BASE_URL}{path}",
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "gpu-control",
            },
            method="GET",
        )
        lines: list[str] = []
        total_bytes = 0
        found_result = False
        found_completion = False
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", None)
                if status != 200:
                    raise RunPodV2Error(f"RunPod API returned unexpected HTTP status {status}")
                for raw_line in response:
                    if not isinstance(raw_line, (bytes, bytearray)):
                        raise RunPodV2Error("RunPod log stream yielded a non-bytes line")
                    total_bytes += len(raw_line)
                    if total_bytes > max_bytes:
                        raise RunPodV2Error("RunPod log stream exceeded bounded byte limit")
                    try:
                        text = bytes(raw_line).decode("utf-8").rstrip("\r\n")
                    except UnicodeDecodeError as exc:
                        raise RunPodV2Error("RunPod log stream contained invalid UTF-8") from exc
                    if not text.startswith("data:"):
                        continue
                    raw_data = text[5:].lstrip()
                    try:
                        event = json.loads(raw_data)
                    except json.JSONDecodeError as exc:
                        raise RunPodV2Error("RunPod log SSE data is not valid JSON") from exc
                    if not isinstance(event, Mapping):
                        raise RunPodV2Error("RunPod log SSE data must be an object")
                    if event.get("source") != "container":
                        continue
                    value = event.get("line")
                    if not isinstance(value, str):
                        raise RunPodV2Error("RunPod container log event is missing line")
                    lines.append(value)
                    found_result = found_result or value.startswith(_RESULT_MARKER)
                    found_completion = found_completion or value.startswith(_COMPLETION_MARKER)
                    if found_result and found_completion:
                        break
        except HTTPError as exc:
            raise self._http_error(exc) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RunPodV2TransportError("RunPod log stream could not be read reliably") from exc
        return tuple(lines)

    def terminate_pod(self, pod_id: str) -> None:
        encoded = self._pod_id(pod_id)
        self._request("DELETE", f"/pods/{encoded}", expected_status=204)

    def transition_pod(self, pod_id: str, action: str) -> dict[str, Any] | None:
        if action not in {"start", "stop", "restart", "terminate"}:
            raise RunPodV2Error("unsupported RunPod pod action")
        encoded = self._pod_id(pod_id)
        expected_status = 204 if action == "terminate" else 200
        return self._request(
            "POST",
            f"/pods/{encoded}/action",
            expected_status=expected_status,
            body={"action": action},
        )

    @staticmethod
    def _pod_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise RunPodV2Error("RunPod pod id is required")
        if value != value.strip() or any(character.isspace() for character in value):
            raise RunPodV2Error("RunPod pod id must not contain whitespace")
        return quote(value, safe="")
