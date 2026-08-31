from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..completion import (
    CompletionChallenge,
    CompletionEvidenceError,
    CompletionEvidenceV3,
    verify_completion_v3,
)
from ..lifecycle import JobState
from .runpod_log_results import (
    _freeze_json,
    _json_object,
    _validate_common_result_identity,
    _validate_result_schema,
)
from .runpod_v2 import RunPodV2Error


MAX_RESULT_FILE_BYTES = 16 * 1024
RUNPOD_NETWORK_VOLUME_MOUNT_PATH = "/outputs"
RESULT_OBJECT_KEY = "result.json"
COMPLETION_V3_OBJECT_KEY = "completion-v3.json"
_SUPPORTED_S3_DATACENTERS = frozenset(
    {
        "EU-CZ-1",
        "EU-RO-1",
        "EUR-IS-1",
        "EUR-NO-1",
        "US-CA-2",
        "US-GA-2",
        "US-IL-1",
        "US-KS-2",
        "US-MD-1",
        "US-MO-1",
        "US-MO-2",
        "US-NC-1",
        "US-NC-2",
        "US-NE-1",
        "US-WA-1",
    }
)
_VOLUME_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_OBJECT_KEY_RE = re.compile(r"^[A-Za-z0-9._/-]{1,256}$")


@dataclass(frozen=True)
class RunPodNetworkVolumeEvidence:
    """Trusted binding for one pre-existing RunPod Network Volume.

    Creating or resizing the volume is deliberately outside this type because both
    operations have persistent billing consequences. The live workflow may only
    consume evidence for an already-provisioned volume in an S3-supported datacenter.
    """

    network_volume_id: str
    data_center_id: str
    verification_reference: str
    mount_path: str = RUNPOD_NETWORK_VOLUME_MOUNT_PATH
    schema_version: int = 1

    def validate_shape(self) -> None:
        if self.schema_version != 1:
            raise RunPodV2Error("unsupported RunPod network-volume evidence schema_version")
        if not isinstance(self.network_volume_id, str) or not _VOLUME_ID_RE.fullmatch(self.network_volume_id):
            raise RunPodV2Error("RunPod network_volume_id is invalid")
        if self.data_center_id not in _SUPPORTED_S3_DATACENTERS:
            raise RunPodV2Error("RunPod network volume is not in a supported S3 datacenter")
        if self.mount_path != RUNPOD_NETWORK_VOLUME_MOUNT_PATH:
            raise RunPodV2Error("RunPod network volume mount path must be /outputs")
        if not isinstance(self.verification_reference, str) or not self.verification_reference.strip():
            raise RunPodV2Error("RunPod network-volume verification_reference is required")
        if self.verification_reference != self.verification_reference.strip():
            raise RunPodV2Error("RunPod network-volume verification_reference must be trimmed")

    @property
    def s3_endpoint(self) -> str:
        self.validate_shape()
        return f"https://s3api-{self.data_center_id.lower()}.runpod.io"


@dataclass(frozen=True)
class RunPodS3Credentials:
    """Ephemeral S3 API credentials. They are never serializable evidence."""

    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)

    def validate_shape(self) -> None:
        if not isinstance(self.access_key_id, str) or not self.access_key_id.strip():
            raise RunPodV2Error("RunPod S3 access key is required")
        if self.access_key_id != self.access_key_id.strip() or any(c.isspace() for c in self.access_key_id):
            raise RunPodV2Error("RunPod S3 access key must not contain whitespace")
        if not isinstance(self.secret_access_key, str) or not self.secret_access_key.strip():
            raise RunPodV2Error("RunPod S3 secret key is required")
        if self.secret_access_key != self.secret_access_key.strip() or any(c.isspace() for c in self.secret_access_key):
            raise RunPodV2Error("RunPod S3 secret key must not contain whitespace")


@dataclass(frozen=True)
class AuthenticatedRunPodVolumeResult:
    state: JobState
    process_exit_code: int
    result_bytes: bytes
    completion_bytes: bytes
    result_payload: Mapping[str, Any]
    completion_evidence: CompletionEvidenceV3
    collection_reference: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date: str, region: str) -> bytes:
    date_key = _hmac(("AWS4" + secret).encode("utf-8"), date)
    region_key = hmac.new(date_key, region.encode("utf-8"), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def _validate_object_key(value: str) -> str:
    if not isinstance(value, str) or not _OBJECT_KEY_RE.fullmatch(value):
        raise RunPodV2Error("RunPod S3 object key is invalid")
    if value.startswith("/") or value.endswith("/") or "//" in value or any(part in {".", ".."} for part in value.split("/")):
        raise RunPodV2Error("RunPod S3 object key must be a canonical relative path")
    return value


class RunPodNetworkVolumeS3Client:
    """Minimal fixed-origin SigV4 GET client for bounded RunPod volume files."""

    def __init__(
        self,
        evidence: RunPodNetworkVolumeEvidence,
        credentials: RunPodS3Credentials,
        *,
        timeout: float = 10.0,
        opener: Callable[..., Any] = urlopen,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        evidence.validate_shape()
        credentials.validate_shape()
        if timeout <= 0:
            raise RunPodV2Error("RunPod S3 timeout must be positive")
        if not callable(opener) or not callable(clock):
            raise RunPodV2Error("RunPod S3 opener and clock must be callable")
        self._evidence = evidence
        self._credentials = credentials
        self._timeout = timeout
        self._opener = opener
        self._clock = clock

    def _request(self, object_key: str) -> Request:
        key = _validate_object_key(object_key)
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
            raise RunPodV2Error("RunPod S3 clock must return timezone-aware UTC")
        now = now.astimezone(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        region = self._evidence.data_center_id
        host = f"s3api-{region.lower()}.runpod.io"
        encoded_bucket = quote(self._evidence.network_volume_id, safe="-_.~")
        encoded_key = "/".join(quote(part, safe="-_.~") for part in key.split("/"))
        canonical_uri = f"/{encoded_bucket}/{encoded_key}"
        payload_hash = _sha256_hex(b"")
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            ["GET", canonical_uri, "", canonical_headers, signed_headers, payload_hash]
        )
        scope = f"{date_stamp}/{region}/s3/aws4_request"
        string_to_sign = "\n".join(
            ["AWS4-HMAC-SHA256", amz_date, scope, _sha256_hex(canonical_request.encode("utf-8"))]
        )
        signature = hmac.new(
            _signing_key(self._credentials.secret_access_key, date_stamp, region),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self._credentials.access_key_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return Request(
            f"https://{host}{canonical_uri}",
            headers={
                "Accept": "application/octet-stream",
                "Authorization": authorization,
                "Host": host,
                "User-Agent": "gpu-control",
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
            },
            method="GET",
        )

    def get_object(self, object_key: str, *, max_bytes: int = MAX_RESULT_FILE_BYTES) -> bytes:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= MAX_RESULT_FILE_BYTES:
            raise RunPodV2Error("RunPod S3 max_bytes must be between 1 and 16384")
        request = self._request(object_key)
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RunPodV2Error("RunPod S3 object read returned an unexpected status")
                content_length = None
                headers = getattr(response, "headers", None)
                if headers is not None:
                    content_length = headers.get("Content-Length")
                if content_length is not None:
                    try:
                        length = int(content_length)
                    except (TypeError, ValueError) as exc:
                        raise RunPodV2Error("RunPod S3 Content-Length is invalid") from exc
                    if length < 0 or length > max_bytes:
                        raise RunPodV2Error("RunPod S3 object exceeds bounded result size")
                payload = response.read(max_bytes + 1)
        except HTTPError as exc:
            if exc.code == 404:
                raise RunPodV2Error("RunPod S3 result object is missing") from exc
            raise RunPodV2Error(f"RunPod S3 object read failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RunPodV2Error("RunPod S3 API could not be reached") from exc
        if not isinstance(payload, bytes):
            raise RunPodV2Error("RunPod S3 object body must be bytes")
        if len(payload) > max_bytes:
            raise RunPodV2Error("RunPod S3 object exceeds bounded result size")
        if not payload:
            raise RunPodV2Error("RunPod S3 result object is empty")
        return payload


def authenticate_runpod_volume_result(
    result_bytes: bytes,
    completion_bytes: bytes,
    *,
    challenge: CompletionChallenge,
    secret_key: bytes,
    expected_workload_id: str,
    collection_reference: str,
) -> AuthenticatedRunPodVolumeResult:
    """Authenticate exact durable result bytes without trusting provider exit status."""

    if not isinstance(result_bytes, bytes) or not result_bytes or len(result_bytes) > MAX_RESULT_FILE_BYTES:
        raise RunPodV2Error("RunPod network-volume result bytes are invalid or oversized")
    if not isinstance(completion_bytes, bytes) or not completion_bytes or len(completion_bytes) > MAX_RESULT_FILE_BYTES:
        raise RunPodV2Error("RunPod network-volume completion bytes are invalid or oversized")
    if not isinstance(collection_reference, str) or not collection_reference.strip():
        raise RunPodV2Error("RunPod network-volume collection_reference is required")

    result_payload = _json_object(result_bytes, "result")
    completion_payload = _json_object(completion_bytes, "completion v3")
    try:
        evidence = CompletionEvidenceV3.from_dict(completion_payload)
        result_digest = "sha256:" + hashlib.sha256(result_bytes).hexdigest()
        verify_completion_v3(
            challenge,
            evidence,
            secret_key=secret_key,
            expected_result_sha256=result_digest,
        )
    except CompletionEvidenceError as exc:
        raise RunPodV2Error(str(exc)) from exc

    status = _validate_common_result_identity(
        result_payload,
        challenge=challenge,
        expected_workload_id=expected_workload_id,
    )
    _validate_result_schema(result_payload)
    if status == "pass":
        if evidence.process_exit_code != 0:
            raise RunPodV2Error("authenticated pass result disagrees with signed nonzero process exit code")
        state = JobState.SUCCEEDED
    else:
        if evidence.process_exit_code == 0:
            raise RunPodV2Error("authenticated fail result disagrees with signed zero process exit code")
        state = JobState.FAILED

    frozen_payload = _freeze_json(result_payload)
    assert isinstance(frozen_payload, Mapping)
    return AuthenticatedRunPodVolumeResult(
        state=state,
        process_exit_code=evidence.process_exit_code,
        result_bytes=result_bytes,
        completion_bytes=completion_bytes,
        result_payload=frozen_payload,
        completion_evidence=evidence,
        collection_reference=collection_reference.strip(),
    )


def collect_runpod_network_volume_result(
    client: RunPodNetworkVolumeS3Client,
    *,
    challenge: CompletionChallenge,
    secret_key: bytes,
    expected_workload_id: str,
) -> AuthenticatedRunPodVolumeResult:
    if not isinstance(client, RunPodNetworkVolumeS3Client):
        raise RunPodV2Error("RunPod network-volume collector requires the fixed-origin S3 client")
    result_bytes = client.get_object(RESULT_OBJECT_KEY)
    completion_bytes = client.get_object(COMPLETION_V3_OBJECT_KEY)
    evidence = client._evidence
    reference = (
        f"runpod-s3:{evidence.data_center_id}:{evidence.network_volume_id}:"
        f"{challenge.execution_name}:completion-v3"
    )
    return authenticate_runpod_volume_result(
        result_bytes,
        completion_bytes,
        challenge=challenge,
        secret_key=secret_key,
        expected_workload_id=expected_workload_id,
        collection_reference=reference,
    )
