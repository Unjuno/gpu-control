from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Workload(BaseModel):
    """Operator-owned manifest, never supplied by an MCP client."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    image_id: str = ""
    source_revision: str = ""
    argv: tuple[str, ...] = ()
    gpu: str = "T4"
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
        if self.provider == "modal":
            if not self.image_id.startswith("im-") or not self.argv or not self.source_revision:
                raise ValueError("Modal requires a prebuilt image ID, fixed argv and source revision")
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
    runpod_factory: str = ""
    modal_app: str = "gpu-control"
    max_inflight: int = 1
    approval_ttl_seconds: int = 900
    max_request_bytes: int = 65536
    max_output_bytes: int = 65536
    max_job_cost_usd: Decimal = Decimal("1")
    max_open_requests: int = 100
    hosted: bool = False

    @property
    def resource(self) -> str:
        return self.public_url.rstrip("/") + "/mcp"

    @property
    def auth_ready(self) -> bool:
        return bool(self.issuer and self.jwks_url and self.allowed_subjects)

    @property
    def web_auth_ready(self) -> bool:
        return self.auth_ready and bool(self.cookie_key and self.client_id and self.authorization_endpoint and self.token_endpoint)

    def validate(self) -> None:
        parsed = urlsplit(self.public_url)
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("public URL must be an origin without credentials, path, query or fragment")
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local and not self.hosted):
            raise ValueError("HTTPS required except for local development")
        if self.hosted and not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("Hosted deployments require durable PostgreSQL, not SQLite or /tmp")
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

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        value = cls(
            database_url=e.get("GATEWAY_DATABASE_URL", "sqlite:///./gateway-local.db"),
            public_url=e.get("GATEWAY_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/"),
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
            runpod_factory=e.get("GATEWAY_RUNPOD_FACTORY", ""),
            modal_app=e.get("GATEWAY_MODAL_APP", "gpu-control"),
            max_inflight=int(e.get("GATEWAY_MAX_INFLIGHT", "1")),
            max_job_cost_usd=Decimal(e.get("GATEWAY_MAX_JOB_COST_USD", "1")),
            hosted=e.get("VERCEL") == "1" or e.get("GATEWAY_HOSTED") == "true",
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
