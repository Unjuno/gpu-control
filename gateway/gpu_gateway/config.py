from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
import base64
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class Workload(BaseModel):
    """Operator-owned manifest, never supplied by an MCP client."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    image_id: str = ""
    image_digest: str = ""
    execution_profile: str = "general"
    source_revision: str = ""
    source_repository: str = ""
    source_sha: str = ""
    requires_gpu: bool = True
    argv: tuple[str, ...] = ()
    gpu: str = "T4"
    provider_resource_id: str | None = None
    provider_data_center_id: str | None = None
    # Explicit P4 compatibility requirements. None means unknown, never inferred.
    operating_system: str | None = None
    architecture: str | None = None
    gpu_count: int | None = Field(default=None, ge=1, le=16)
    minimum_vram_mib: int | None = Field(default=None, ge=1, le=1_048_576)
    network_requirement: str | None = Field(default=None, pattern=r"^(disabled|restricted|required)$")
    result_transport: str | None = Field(default=None, pattern=r"^(shared_filesystem|object_storage|database|stdout)$")
    max_result_bytes: int | None = Field(default=None, ge=1, le=1_073_741_824)
    cancellation_required: bool | None = None
    cleanup_proof_required: bool | None = None
    runtime_requirements: tuple[str, ...] = ()
    max_queue_wait_seconds: int | None = Field(default=None, ge=0, le=604800)
    cpu: float = Field(default=1, ge=0.125, le=8)
    memory_mib: int = Field(default=4096, ge=128, le=65536)
    max_runtime_seconds: int = Field(default=600, ge=1, le=3600)
    max_cost_usd: Decimal = Field(default=Decimal("1"), gt=0, le=100)
    # Conservative ALL-IN compute quote; not a GPU-only advertised price.
    quoted_usd_per_hour: Decimal | None = Field(default=None, gt=0)
    quote_reference: str = ""
    quote_expires_at: int = 0
    parameter_schema: dict = Field(default_factory=lambda: {"type": "object", "additionalProperties": False})

    @model_validator(mode="after")
    def valid(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(self.parameter_schema)
        def check_refs(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"$ref", "$dynamicRef"} and (not isinstance(item, str) or not item.startswith("#")):
                        raise ValueError("External schema references are not allowed")
                    check_refs(item)
            elif isinstance(value, list):
                for item in value: check_refs(item)
        check_refs(self.parameter_schema)
        if self.parameter_schema.get("type") != "object":
            raise ValueError("parameter_schema must describe an object")
        if self.parameter_schema.get("additionalProperties") is not False:
            raise ValueError("parameter_schema must reject unknown parameters")
        if any(not isinstance(x, str) or not x or "\x00" in x for x in self.argv):
            raise ValueError("argv must contain nonempty NUL-free arguments")
        if (not isinstance(self.runtime_requirements, tuple) or
                any(not isinstance(item, str) or not item or item != item.strip() or
                    any(ord(char) < 32 or ord(char) == 127 for char in item)
                    for item in self.runtime_requirements) or
                len(set(self.runtime_requirements)) != len(self.runtime_requirements)):
            raise ValueError("runtime_requirements must be unique canonical strings")
        if self.provider == "modal":
            if not self.image_id.startswith("im-") or not self.argv or not self.source_revision:
                raise ValueError("Modal requires a prebuilt image ID, fixed argv and source revision")
        if self.execution_profile not in {"general", "smoke", "training"}:
            raise ValueError("execution_profile is unsupported")
        if self.provider == "local_cpu":
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_digest):
                raise ValueError("local_cpu requires an immutable image_digest")
            if self.requires_gpu:
                raise ValueError("local_cpu workload must not require a GPU")
            if self.execution_profile != "smoke":
                raise ValueError("local_cpu policy only supports the smoke profile")
        if bool(self.source_repository) != bool(self.source_sha):
            raise ValueError("source_repository and source_sha must be configured together")
        if bool(self.provider_resource_id) != bool(self.provider_data_center_id):
            raise ValueError("provider_resource_id and provider_data_center_id must be configured together")
        for field_name, value in (("provider_resource_id", self.provider_resource_id),
                                  ("provider_data_center_id", self.provider_data_center_id)):
            if value is not None and (not isinstance(value, str) or not value or
                                      value != value.strip() or len(value) > 128 or
                                      any(ord(char) < 32 or ord(char) == 127 for char in value)):
                raise ValueError(f"{field_name} must be bounded canonical text")
        if self.source_repository and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.source_repository):
            raise ValueError("source_repository must be owner/name")
        if self.source_sha and not re.fullmatch(r"[0-9a-f]{40}", self.source_sha):
            raise ValueError("source_sha must be a canonical full commit SHA")
        return self


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./gateway-local.db"
    public_url: str = "http://127.0.0.1:8000"
    issuer: str = ""
    jwks_url: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    client_id: str = ""
    client_secret: str = ""
    cookie_key: str = ""
    allowed_subjects: tuple[str, ...] = ()
    enable_modal: bool = False
    enable_runpod_bridge: bool = False
    enable_runpod_evidence: bool = False
    runpod_api_key: str = field(default="", repr=False, compare=False)
    runpod_account_scope_id: str = field(default="", repr=False, compare=False)
    runpod_factory: str = ""
    modal_app: str = "gpu-control"
    max_inflight: int = 1
    approval_ttl_seconds: int = 900
    max_request_bytes: int = 65536
    max_output_bytes: int = 65536
    artifact_dir: str = ""
    artifact_min_free_bytes: int = 0
    max_job_cost_usd: Decimal = Decimal("1")
    max_open_requests: int = 100
    hosted: bool = False
    provider_evidence_public_keys_json: str = "{}"
    candidate_receipt_public_keys_json: str = "{}"
    paid_authorization_issuer: str = ""
    paid_authorization_policy_version: str = ""
    paid_authorization_public_keys_json: str = "{}"
    credit_authorization_issuer: str = ""
    credit_authorization_policy_version: str = ""
    credit_authorization_public_keys_json: str = "{}"
    provider_account_scope_hmac_key_b64: str = field(default="", repr=False, compare=False)
    provider_evidence_signing_key_id: str = ""
    provider_evidence_signing_key_pem: bytes | None = field(default=None, repr=False, compare=False)

    @property
    def resource(self) -> str:
        return self.public_url.rstrip("/") + "/mcp"

    @property
    def provider_account_scope_hmac_key(self) -> bytes | None:
        encoded = self.provider_account_scope_hmac_key_b64
        if not encoded:
            return None
        try:
            key = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("provider account scope HMAC key must be valid base64") from exc
        if not 32 <= len(key) <= 4096:
            raise ValueError("provider account scope HMAC key must decode to 32-4096 bytes")
        return key

    @property
    def auth_ready(self) -> bool:
        return bool(self.issuer and self.jwks_url and self.allowed_subjects)

    @property
    def web_auth_ready(self) -> bool:
        return self.auth_ready and bool(self.cookie_key and self.client_id and self.authorization_endpoint and self.token_endpoint)

    @property
    def provider_evidence_trusted_keys(self) -> dict[str, bytes]:
        try:
            raw = json.loads(self.provider_evidence_public_keys_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("provider evidence public-key configuration is invalid JSON") from exc
        if not isinstance(raw, dict) or len(raw) > 16:
            raise ValueError("provider evidence public-key configuration must be an object of at most 16 keys")
        keys = {}
        for key_id, pem in raw.items():
            if (not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id)
                    or not isinstance(pem, str) or not pem or len(pem) > 8192):
                raise ValueError("provider evidence public-key entry is invalid")
            try:
                key = serialization.load_pem_public_key(pem.encode("ascii"))
            except (ValueError, TypeError, UnicodeEncodeError) as exc:
                raise ValueError("provider evidence public key is invalid PEM") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("provider evidence public key must be Ed25519")
            keys[key_id] = pem.encode("ascii")
        return keys

    @property
    def candidate_receipt_trusted_keys(self) -> dict[str, bytes]:
        try:
            raw = json.loads(self.candidate_receipt_public_keys_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("candidate receipt public-key configuration is invalid JSON") from exc
        if not isinstance(raw, dict) or len(raw) > 16:
            raise ValueError("candidate receipt public-key configuration must be an object of at most 16 keys")
        keys = {}
        for key_id, pem in raw.items():
            if (not isinstance(key_id, str) or not re.fullmatch(
                    r"(?:provider|adapter):[a-z][a-z0-9_-]{0,31}:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id)
                    or not isinstance(pem, str) or not pem or len(pem) > 8192):
                raise ValueError("candidate receipt public-key entry is invalid")
            try:
                key = serialization.load_pem_public_key(pem.encode("ascii"))
            except (ValueError, TypeError, UnicodeEncodeError) as exc:
                raise ValueError("candidate receipt public key is invalid PEM") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("candidate receipt public key must be Ed25519")
            keys[key_id] = pem.encode("ascii")
        return keys

    @property
    def paid_authorization_trusted_keys(self) -> dict[str, bytes]:
        try:
            raw = json.loads(self.paid_authorization_public_keys_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("paid authorization public-key configuration is invalid JSON") from exc
        if not isinstance(raw, dict) or len(raw) > 16:
            raise ValueError("paid authorization public-key configuration must be an object of at most 16 keys")
        keys = {}
        for key_id, pem in raw.items():
            if (not isinstance(key_id, str) or
                    not re.fullmatch(r"paid:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id) or
                    not isinstance(pem, str) or not pem or len(pem) > 8192):
                raise ValueError("paid authorization public-key entry is invalid")
            try:
                key = serialization.load_pem_public_key(pem.encode("ascii"))
            except (ValueError, TypeError, UnicodeEncodeError) as exc:
                raise ValueError("paid authorization public key is invalid PEM") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("paid authorization public key must be Ed25519")
            keys[key_id] = pem.encode("ascii")
        return keys

    @property
    def credit_authorization_trusted_keys(self) -> dict[str, bytes]:
        try:
            raw = json.loads(self.credit_authorization_public_keys_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("credit authorization public-key configuration is invalid JSON") from exc
        if not isinstance(raw, dict) or len(raw) > 16:
            raise ValueError("credit authorization public-key configuration must be an object of at most 16 keys")
        keys = {}
        for key_id, pem in raw.items():
            if (not isinstance(key_id, str) or
                    not re.fullmatch(r"credit:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key_id) or
                    not isinstance(pem, str) or not pem or len(pem) > 8192):
                raise ValueError("credit authorization public-key entry is invalid")
            try:
                key = serialization.load_pem_public_key(pem.encode("ascii"))
            except (ValueError, TypeError, UnicodeEncodeError) as exc:
                raise ValueError("credit authorization public key is invalid PEM") from exc
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("credit authorization public key must be Ed25519")
            keys[key_id] = pem.encode("ascii")
        return keys

    def validate(self) -> None:
        parsed = urlsplit(self.public_url)
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("public URL must be an origin without credentials, path, query or fragment")
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local and not self.hosted):
            raise ValueError("HTTPS required except for local development")
        if self.hosted and not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("Hosted deployments require durable PostgreSQL, not SQLite or /tmp")
        if self.hosted and self.artifact_dir:
            artifact_path = Path(self.artifact_dir).expanduser().resolve(strict=False)
            temporary_roots = (Path("/tmp").resolve(), Path("/var/tmp").resolve())
            if (not Path(self.artifact_dir).is_absolute() or
                    any(artifact_path == root or root in artifact_path.parents for root in temporary_roots)):
                raise ValueError("Hosted deployments require an absolute persistent artifact directory")
        for value in (self.issuer, self.jwks_url, self.authorization_endpoint, self.token_endpoint):
            if value:
                p = urlsplit(value)
                if p.scheme != "https" or not p.hostname or p.username or p.fragment:
                    raise ValueError("OIDC URLs must use trusted HTTPS endpoints")
        if not self.max_job_cost_usd.is_finite() or not Decimal("0") < self.max_job_cost_usd <= Decimal("100"):
            raise ValueError("max_job_cost_usd must be finite, positive and at most 100")
        if not 1 <= self.max_inflight <= 10:
            raise ValueError("max_inflight must be between 1 and 10")
        if not 1 <= self.approval_ttl_seconds <= 900:
            raise ValueError("approval TTL must be between 1 and 900 seconds")
        if type(self.artifact_min_free_bytes) is not int or self.artifact_min_free_bytes < 0:
            raise ValueError("artifact_min_free_bytes must be a nonnegative integer")
        trusted_keys = self.provider_evidence_trusted_keys
        self.candidate_receipt_trusted_keys
        self.provider_account_scope_hmac_key
        paid_keys = self.paid_authorization_trusted_keys
        if paid_keys or self.paid_authorization_issuer or self.paid_authorization_policy_version:
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.paid_authorization_issuer) or
                    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.paid_authorization_policy_version) or
                    not paid_keys or any(not key_id.startswith(f"paid:{self.paid_authorization_issuer}:")
                                         for key_id in paid_keys)):
                raise ValueError("paid authorization issuer, policy version, and matching trusted keys are required together")
        credit_keys = self.credit_authorization_trusted_keys
        if credit_keys or self.credit_authorization_issuer or self.credit_authorization_policy_version:
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.credit_authorization_issuer) or
                    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", self.credit_authorization_policy_version) or
                    not credit_keys or any(not key_id.startswith(f"credit:{self.credit_authorization_issuer}:")
                                           for key_id in credit_keys)):
                raise ValueError("credit authorization issuer, policy version, and matching trusted keys are required together")
        if self.provider_evidence_signing_key_pem is not None:
            if not self.provider_evidence_signing_key_id or self.provider_evidence_signing_key_id not in trusted_keys:
                raise ValueError("worker provider evidence signing key ID must be present in the trusted key set")
            try:
                private_key = serialization.load_pem_private_key(
                    self.provider_evidence_signing_key_pem, password=None)
            except (ValueError, TypeError) as exc:
                raise ValueError("worker provider evidence private key is invalid PEM") from exc
            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError("worker provider evidence signing key must be Ed25519")
            expected = serialization.load_pem_public_key(trusted_keys[self.provider_evidence_signing_key_id])
            derived = private_key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            trusted = expected.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            if derived != trusted:
                raise ValueError("worker private key does not match configured trusted public key")
        elif self.provider_evidence_signing_key_id:
            raise ValueError("provider evidence signing key ID is set without a private key")
        if self.enable_runpod_evidence:
            if not self.runpod_api_key or any(character.isspace() for character in self.runpod_api_key):
                raise ValueError("RunPod evidence collection requires a worker-only API key")
            if self.provider_evidence_signing_key_pem is None:
                raise ValueError("RunPod evidence collection requires a worker signing key")

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ

        database_url = e.get("GATEWAY_DATABASE_URL") or e.get("DATABASE_URL") or "sqlite:///./gateway-local.db"
        if database_url.startswith("postgresql://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
        elif database_url.startswith("postgres://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]

        public_url = e.get("GATEWAY_PUBLIC_URL")
        if not public_url:
            production_host = e.get("VERCEL_PROJECT_PRODUCTION_URL")
            public_url = f"https://{production_host}" if production_host else "http://127.0.0.1:8000"

        evidence_private = e.get("GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_B64", "")
        try:
            evidence_private_pem = (base64.b64decode(evidence_private, validate=True)
                                    if evidence_private else None)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("provider evidence signing key must be valid base64") from exc

        value = cls(
            database_url=database_url,
            public_url=public_url.rstrip("/"),
            issuer=e.get("GATEWAY_OIDC_ISSUER", ""),
            jwks_url=e.get("GATEWAY_OIDC_JWKS_URL", ""),
            authorization_endpoint=e.get("GATEWAY_OIDC_AUTHORIZATION_ENDPOINT", ""),
            token_endpoint=e.get("GATEWAY_OIDC_TOKEN_ENDPOINT", ""),
            client_id=e.get("GATEWAY_OIDC_CLIENT_ID", ""),
            client_secret=e.get("GATEWAY_OIDC_CLIENT_SECRET", ""),
            cookie_key=e.get("GATEWAY_COOKIE_KEY", ""),
            allowed_subjects=tuple(s.strip() for s in e.get("GATEWAY_ALLOWED_SUBJECTS", "").split(",") if s.strip()),
            enable_modal=e.get("GATEWAY_ENABLE_MODAL") == "true",
            enable_runpod_bridge=e.get("GATEWAY_ENABLE_RUNPOD_BRIDGE") == "true",
            enable_runpod_evidence=e.get("GATEWAY_ENABLE_RUNPOD_EVIDENCE") == "true",
            runpod_api_key=e.get("RUNPOD_API_KEY", ""),
            runpod_account_scope_id=e.get("GATEWAY_RUNPOD_ACCOUNT_SCOPE_ID", ""),
            runpod_factory=e.get("GATEWAY_RUNPOD_FACTORY", ""),
            modal_app=e.get("GATEWAY_MODAL_APP", "gpu-control"),
            max_inflight=int(e.get("GATEWAY_MAX_INFLIGHT", "1")),
            max_job_cost_usd=Decimal(e.get("GATEWAY_MAX_JOB_COST_USD", "1")),
            artifact_dir=e.get("GATEWAY_ARTIFACT_DIR", ""),
            artifact_min_free_bytes=int(e.get("GATEWAY_ARTIFACT_MIN_FREE_BYTES", "0")),
            hosted=e.get("VERCEL") == "1" or e.get("GATEWAY_HOSTED") == "true",
            provider_evidence_public_keys_json=e.get("GATEWAY_PROVIDER_EVIDENCE_PUBLIC_KEYS_JSON", "{}"),
            candidate_receipt_public_keys_json=e.get("GATEWAY_CANDIDATE_RECEIPT_PUBLIC_KEYS_JSON", "{}"),
            paid_authorization_issuer=e.get("GATEWAY_PAID_AUTHORIZATION_ISSUER", ""),
            paid_authorization_policy_version=e.get("GATEWAY_PAID_AUTHORIZATION_POLICY_VERSION", ""),
            paid_authorization_public_keys_json=e.get("GATEWAY_PAID_AUTHORIZATION_PUBLIC_KEYS_JSON", "{}"),
            credit_authorization_issuer=e.get("GATEWAY_CREDIT_AUTHORIZATION_ISSUER", ""),
            credit_authorization_policy_version=e.get("GATEWAY_CREDIT_AUTHORIZATION_POLICY_VERSION", ""),
            credit_authorization_public_keys_json=e.get("GATEWAY_CREDIT_AUTHORIZATION_PUBLIC_KEYS_JSON", "{}"),
            provider_account_scope_hmac_key_b64=e.get("GATEWAY_PROVIDER_ACCOUNT_SCOPE_HMAC_KEY_B64", ""),
            provider_evidence_signing_key_id=e.get("GATEWAY_PROVIDER_EVIDENCE_SIGNING_KEY_ID", ""),
            provider_evidence_signing_key_pem=evidence_private_pem,
        )
        value.validate()
        return value


def load_workloads() -> dict[str, Workload]:
    """Load only operator-controlled configuration. No URL/file inputs from tools."""
    raw = os.environ.get("GATEWAY_WORKLOADS_JSON")
    path = os.environ.get("GATEWAY_WORKLOADS_FILE")
    data = json.loads(raw) if raw else json.loads(Path(path).read_text()) if path else {"demo": {"provider": "demo"}}
    if not isinstance(data, dict) or len(data) > 100:
        raise ValueError("workload registry must be an object with at most 100 entries")
    return {name: Workload.model_validate(value) for name, value in data.items()}
