"""Authenticated, replay-safe Sites-to-Gateway tool delegation boundary."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .migrations import sites_delegation_authorizations, sites_delegation_nonces
from .service import GatewayError, Principal, digest
from .store import runs

MAX_CLOCK_SKEW_SECONDS = 60
MAX_DELEGATION_LIFETIME_SECONDS = 120
_NONCE = re.compile(r"^[0-9a-f]{32,64}$")
_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$")
_TOOL = re.compile(r"^experiment_(?:capabilities|prepare|submit|status|result|artifact|cancel|list)$")
_AUTHORIZATION_ID = re.compile(r"^[0-9a-f]{32}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
AUTHORIZATION_SOURCE = "chatgpt_mcp_write_confirmation"
MAX_AUTHORIZATION_LIFETIME_SECONDS = 600


@dataclass(frozen=True)
class DelegatedRequest:
    key_id: str
    owner: str
    tool: str
    arguments: dict
    nonce: str
    issued_at: int
    expires_at: int


def canonical_payload(value: dict) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise GatewayError("invalid_delegation", "Delegation payload is not canonical JSON") from exc


def signature_for(payload: dict, key: bytes) -> str:
    return hmac.new(key, canonical_payload(payload), hashlib.sha256).hexdigest()


def verify_and_claim(*, payload: object, signed_body: bytes, signature: str | None, settings: Settings,
                     engine, expected_tool: str, now: int | None = None) -> DelegatedRequest:
    """Verify one exact signed request and durably consume its nonce."""
    key = settings.sites_delegation_hmac_key
    if key is None:
        raise GatewayError("delegation_disabled", "Sites delegation is not configured", 503)
    if not isinstance(payload, dict) or set(payload) != {
        "version", "key_id", "owner", "tool", "arguments", "nonce", "issued_at", "expires_at"
    }:
        raise GatewayError("invalid_delegation", "Delegation envelope fields are invalid")
    if payload["version"] != 1 or payload["key_id"] != settings.sites_delegation_key_id:
        raise GatewayError("invalid_delegation", "Delegation key identity is invalid", 401)
    if (not isinstance(signed_body, bytes) or not signed_body or len(signed_body) > settings.max_request_bytes or
            not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature) or
            not hmac.compare_digest(hmac.new(key, signed_body, hashlib.sha256).hexdigest(), signature)):
        raise GatewayError("invalid_delegation", "Delegation signature is invalid", 401)
    owner, tool, arguments = payload["owner"], payload["tool"], payload["arguments"]
    nonce, issued_at, expires_at = payload["nonce"], payload["issued_at"], payload["expires_at"]
    if (not isinstance(owner, str) or not _OWNER.fullmatch(owner) or
            not isinstance(tool, str) or not _TOOL.fullmatch(tool) or tool != expected_tool or
            not isinstance(arguments, dict) or
            not isinstance(nonce, str) or not _NONCE.fullmatch(nonce) or
            type(issued_at) is not int or type(expires_at) is not int):
        raise GatewayError("invalid_delegation", "Delegation identity or arguments are invalid")
    current = int(time.time()) if now is None else now
    if (issued_at > current + MAX_CLOCK_SKEW_SECONDS or expires_at < current or
            expires_at <= issued_at or
            expires_at - issued_at > MAX_DELEGATION_LIFETIME_SECONDS or
            issued_at < current - MAX_DELEGATION_LIFETIME_SECONDS - MAX_CLOCK_SKEW_SECONDS):
        raise GatewayError("delegation_expired", "Delegation validity window is invalid", 401)
    try:
        with engine.begin() as connection:
            connection.execute(delete(sites_delegation_nonces).where(
                sites_delegation_nonces.c.expires_at < current))
            connection.execute(insert(sites_delegation_nonces).values(
                nonce=nonce, key_id=payload["key_id"], owner=owner, tool=tool,
                issued_at=issued_at, expires_at=expires_at,
            ))
    except IntegrityError:
        raise GatewayError("delegation_replayed", "Delegation nonce was already used", 409) from None
    return DelegatedRequest(
        key_id=payload["key_id"], owner=owner, tool=tool, arguments=arguments,
        nonce=nonce, issued_at=issued_at, expires_at=expires_at,
    )


def principal_for(request: DelegatedRequest) -> Principal:
    scopes = {"experiments:read"}
    if request.tool in {"experiment_prepare", "experiment_submit"}:
        scopes.add("experiments:run")
    if request.tool == "experiment_cancel":
        scopes.add("experiments:cancel")
    # Namespace and pseudonymize delegated owners so an OIDC subject can never
    # collide with a Sites edge identity, while staying inside the durable
    # Gateway owner-column bound and avoiding raw edge identifiers in run rows.
    owner_digest = hashlib.sha256(request.owner.encode("utf-8")).hexdigest()
    return Principal(owner=f"sites:{owner_digest}", scopes=frozenset(scopes), browser=False)


def consume_submit_authorization(*, request: DelegatedRequest, service,
                                 now: int | None = None) -> tuple[Principal, dict]:
    """Bind one exact Sites confirmation to one stored plan before submission.

    Provider dispatch is still performed by the ordinary service.submit path.
    A crash after this durable approval and before queueing is recoverable by
    retrying the same authorization ID; a different plan/run cannot reuse it.
    """
    if request.tool != "experiment_submit":
        raise GatewayError("invalid_delegation", "Submit authorization is valid only for experiment_submit")
    arguments = request.arguments
    if set(arguments) != {"run_id", "plan_fingerprint", "approved_plan", "authorization"}:
        raise GatewayError("invalid_arguments", "Delegated submit fields are invalid")
    run_id, fingerprint = arguments["run_id"], arguments["plan_fingerprint"]
    approved_plan, authorization = arguments["approved_plan"], arguments["authorization"]
    if (not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id) or
            not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint) or
            not isinstance(approved_plan, dict) or not isinstance(authorization, dict) or
            set(authorization) != {"authorization_id", "source", "authorized_at", "expires_at"}):
        raise GatewayError("invalid_arguments", "Delegated submit identity is invalid")
    authorization_id = authorization["authorization_id"]
    source = authorization["source"]
    authorized_at, expires_at = authorization["authorized_at"], authorization["expires_at"]
    current = int(service.clock()) if now is None else now
    if (not isinstance(authorization_id, str) or not _AUTHORIZATION_ID.fullmatch(authorization_id) or
            source != AUTHORIZATION_SOURCE or type(authorized_at) is not int or type(expires_at) is not int or
            authorized_at > current or expires_at < current or expires_at <= authorized_at or
            expires_at - authorized_at > MAX_AUTHORIZATION_LIFETIME_SECONDS or
            authorized_at > request.issued_at + MAX_CLOCK_SKEW_SECONDS or
            request.issued_at > expires_at):
        raise GatewayError("delegated_authorization_invalid", "Sites authorization is invalid or expired", 409)
    approved_plan_sha = digest(approved_plan)
    if approved_plan_sha != fingerprint:
        raise GatewayError("plan_changed", "Reviewed plan does not match its fingerprint", 409)
    principal = principal_for(request)
    try:
        with service.store.transaction() as connection:
            service.store.lock_control(connection)
            row = connection.execute(select(runs).where(
                runs.c.id == run_id, runs.c.owner == principal.owner).with_for_update()).mappings().first()
            if row is None:
                raise GatewayError("not_found", "Experiment not found", 404)
            if (row["fingerprint"] != fingerprint or digest(row["plan"]) != fingerprint or
                    row["plan"] != approved_plan):
                raise GatewayError("plan_changed", "Reviewed plan does not match the stored plan", 409)
            existing_by_id = connection.execute(select(sites_delegation_authorizations).where(
                sites_delegation_authorizations.c.authorization_id == authorization_id
            )).mappings().first()
            existing_by_run = connection.execute(select(sites_delegation_authorizations).where(
                sites_delegation_authorizations.c.run_id == run_id
            )).mappings().first()
            expected = {
                "authorization_id": authorization_id, "owner": principal.owner,
                "run_id": run_id, "plan_fingerprint": fingerprint,
                "approved_plan_sha256": approved_plan_sha, "source": source,
                "authorized_at": authorized_at, "expires_at": expires_at,
            }
            for existing in (existing_by_id, existing_by_run):
                if existing is not None and any(existing[key] != value for key, value in expected.items()):
                    raise GatewayError(
                        "delegated_authorization_reused",
                        "Sites authorization is already bound to another plan", 409)
            if existing_by_id is None and existing_by_run is None:
                connection.execute(insert(sites_delegation_authorizations).values(
                    **expected, consumed_at=current))
            if row["state"] == "awaiting_approval":
                connection.execute(update(runs).where(
                    runs.c.id == run_id, runs.c.owner == principal.owner,
                    runs.c.state == "awaiting_approval",
                ).values(state="approved", approval_id=authorization_id,
                         approved_until=expires_at))
            elif row["state"] == "approved":
                if row["approval_id"] != authorization_id or row["approved_until"] != expires_at:
                    raise GatewayError("delegated_authorization_reused", "Run has a different approval", 409)
            elif row["state"] not in {"queued", "submitting", "submit_unknown", "running",
                                     "succeeded", "failed", "cancelled", "expired"}:
                raise GatewayError("invalid_state", "This experiment cannot use delegated approval", 409)
            elif row["approval_id"] != authorization_id:
                raise GatewayError("delegated_authorization_reused", "Run was submitted by another approval", 409)
    except IntegrityError:
        raise GatewayError(
            "delegated_authorization_reused",
            "Sites authorization is already bound to another plan", 409) from None
    return principal, {"run_id": run_id, "plan_fingerprint": fingerprint}
