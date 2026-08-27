from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..completion import CompletionChallenge, CompletionEvidenceError
from ..execution import ApprovedExecutionPlan, ExecutionGateError
from ..lifecycle import JobState


RUNPOD_V2_BASE_URL = "https://api.runpod.io/v2"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_REFERENCE_RE = re.compile(
    r"^[a-z0-9.-]+(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+@sha256:[0-9a-f]{64}$"
)
_ALLOWED_CLOUDS = {"SECURE", "COMMUNITY"}


class RunPodV2Error(RuntimeError):
    """Raised when the RunPod API v2 boundary is malformed or unsafe."""


@dataclass(frozen=True)
class PublishedImageEvidence:
    """Trusted publication evidence for the immutable image submitted to RunPod.

    The approved plan binds the image content by digest. This evidence adds the
    pullable registry location and binds it back to the exact approved-plan
    fingerprint. It is intentionally not accepted as arbitrary workflow input.
    """

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
            raise RunPodV2Error("published image digest does not match the approved plan")
        if not isinstance(self.image_reference, str) or not _IMAGE_REFERENCE_RE.fullmatch(self.image_reference):
            raise RunPodV2Error("image_reference must be an explicit registry/repository@sha256:digest reference")
        if not self.image_reference.endswith(f"@{self.image_digest}"):
            raise RunPodV2Error("image_reference digest does not match published image digest")
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise RunPodV2Error("published image verification_reference is required")
        if self.verification_reference != self.verification_reference.strip():
            raise RunPodV2Error("published image verification_reference must not contain surrounding whitespace")


@dataclass(frozen=True)
class RunPodCompletionLaunch:
    """Ephemeral trusted completion material used only while creating one Pod.

    The challenge is safe to persist separately. The secret key is intentionally
    non-serializable here and must be supplied from protected control-plane state.
    This type is the only supported path for injecting environment variables into
    a RunPod create request; arbitrary user-provided environment mappings remain
    outside the trusted provider boundary.
    """

    challenge: CompletionChallenge
    secret_key: bytes

    def validate_against_plan(self, plan: ApprovedExecutionPlan) -> None:
        try:
            self.challenge.validate_shape()
        except CompletionEvidenceError as exc:
            raise RunPodV2Error(str(exc)) from exc
        plan.validate_shape()
        if self.challenge.plan_fingerprint != plan.fingerprint():
            raise RunPodV2Error("completion challenge does not match approved plan fingerprint")
        if self.challenge.source_sha != plan.target_sha:
            raise RunPodV2Error("completion challenge source_sha does not match approved plan")
        if self.challenge.image_digest != plan.image_digest:
            raise RunPodV2Error("completion challenge image_digest does not match approved plan")
        if not isinstance(self.secret_key, bytes) or len(self.secret_key) < 32:
            raise RunPodV2Error("completion secret key must contain at least 32 bytes")

    def provider_environment(self, plan: ApprovedExecutionPlan) -> dict[str, str]:
        self.validate_against_plan(plan)
        return {
            "GPU_CONTROL_COMPLETION_KEY_B64": base64.b64encode(self.secret_key).decode("ascii"),
            "GPU_CONTROL_COMPLETION_KEY_ID": self.challenge.key_id,
            "GPU_CONTROL_COMPLETION_NONCE": self.challenge.nonce,
            "GPU_CONTROL_EXECUTION_NAME": self.challenge.execution_name,
            "GPU_CONTROL_PLAN_FINGERPRINT": self.challenge.plan_fingerprint,
            "GPU_CONTROL_IMAGE_DIGEST": self.challenge.image_digest,
        }


def build_create_pod_payload(
    plan: ApprovedExecutionPlan,
    image: PublishedImageEvidence,
    *,
    disk_gb: int = 20,
    cloud: str = "SECURE",
    completion: RunPodCompletionLaunch | None = None,
) -> dict[str, object]:
    """Build the minimal RunPod v2 create-pod body from trusted inputs only."""

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

    name = f"gpu-control-{plan.fingerprint()[7:19]}"
    environment = None
    if completion is not None:
        environment = completion.provider_environment(plan)
        name = completion.challenge.execution_name

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
    if environment is not None:
        payload["env"] = environment
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
) -> str:
    """Validate RunPod's create response before it becomes lifecycle identity."""

    image.validate_against_plan(plan)
    pod_id = pod.get("id")
    if not isinstance(pod_id, str) or not pod_id.strip():
        raise RunPodV2Error("RunPod create response is missing pod id")
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
    """Small fixed-origin HTTP client for RunPod REST API v2.

    The class is not wired to any CLI or workflow. Tests inject an opener so CI
    never contacts RunPod. The production default origin is fixed to prevent an
    API key from being redirected to an arbitrary host.
    """

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
            detail = ""
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                    detail = f": {payload['detail']}"
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
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RunPodV2Error("RunPod API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RunPodV2Error("RunPod API returned a non-object JSON response")
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
