"""Narrow GitHub comment bridge. Comments are data, never code or approval.

No provider SDKs, database passwords or shell execution belong in this module.
The CLI also imports this file; JWT is imported lazily on the server only.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

MAX_COMMENT_BYTES = 8192
ACTIONS_ISSUER = "https://token.actions.githubusercontent.com"
ACTIONS_JWKS = ACTIONS_ISSUER + "/.well-known/jwks"
TOOLS = {
    "integrations": "integrations_list", "list": "experiments_list",
    "prepare": "experiments_prepare", "submit": "experiments_submit",
    "status": "experiments_get", "cancel": "experiments_cancel",
}
SCOPES = frozenset({"experiments:read", "experiments:run", "experiments:cancel"})
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")


class BridgeError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(code)


def strict_json(text: str | bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("non-finite JSON")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise BridgeError("invalid_json") from None


def _ensure(condition):
    if not condition:
        raise ValueError("validation failed")


def positive_int(value):
    return type(value) is int and 0 < value < 2**63


@dataclass(frozen=True)
class Policy:
    enabled: bool
    repository: str
    repository_id: int
    owner_id: int
    actor_id: int
    issue_number: int
    branch: str
    workflow_path: str
    gateway_origin: str

    @classmethod
    def load(cls, path: Path | None = None):
        data = strict_json((path or Path(__file__).with_name("ci_policy.json")).read_bytes())
        try:
            policy = cls(**data)
            _ensure(type(policy.enabled) is bool)
            _ensure(re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', policy.repository))
            _ensure(all((positive_int(x) for x in (policy.repository_id, policy.owner_id, policy.actor_id, policy.issue_number))))
            _ensure(policy.branch == 'main')
            _ensure(policy.workflow_path == '.github/workflows/gateway-comments.yml')
            parsed = urlsplit(policy.gateway_origin)
            _ensure(parsed.scheme == 'https' and parsed.hostname and (not parsed.username))
            _ensure(not parsed.password and (not parsed.query) and (not parsed.fragment))
            _ensure(parsed.path == '' and parsed.port in (None, 443))
            return policy
        except (ValueError, TypeError, AssertionError):
            raise BridgeError("invalid_bridge_policy", 503) from None

    @property
    def audience(self):
        return self.gateway_origin + "/api/ci/comment"

    @property
    def workflow_ref(self):
        return f"{self.repository}/{self.workflow_path}@refs/heads/{self.branch}"

    @property
    def subjects(self):
        owner, repo = self.repository.split("/")
        return {
            f"repo:{self.repository}:ref:refs/heads/{self.branch}",
            f"repo:{owner}@{self.owner_id}/{repo}@{self.repository_id}:ref:refs/heads/{self.branch}",
        }


@dataclass(frozen=True)
class Command:
    operation: str
    arguments: dict

    @property
    def tool(self):
        return TOOLS.get(self.operation)


def parse_command(body: str, *, repository_id: int, comment_id: int) -> Command:
    if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_COMMENT_BYTES:
        raise BridgeError("comment_too_large")
    if not positive_int(repository_id) or not positive_int(comment_id):
        raise BridgeError("invalid_event_identity")
    header, _, remainder = body.strip().partition("\n")
    match = re.fullmatch(r"/gpu (local|integrations|list|prepare|submit|status|cancel)", header.rstrip("\r"))
    if not match:
        raise BridgeError("unknown_command")
    operation = match[1]
    if operation in {"local", "integrations", "list"}:
        if remainder.strip():
            raise BridgeError("unexpected_arguments")
        return Command(operation, {})
    value = strict_json(remainder)
    if not isinstance(value, dict):
        raise BridgeError("arguments_must_be_object")
    if operation != "prepare":
        if set(value) != {"run_id"} or not isinstance(value["run_id"], str) or not RUN_ID.fullmatch(value["run_id"]):
            raise BridgeError("invalid_run_id")
        return Command(operation, value)
    required = {"workload", "runtime_seconds", "max_cost_usd"}
    if not required <= set(value) or set(value) - required - {"parameters"}:
        raise BridgeError("invalid_prepare_fields")
    if not isinstance(value["workload"], str) or not NAME.fullmatch(value["workload"]):
        raise BridgeError("invalid_workload")
    if type(value["runtime_seconds"]) is not int or not 1 <= value["runtime_seconds"] <= 3600:
        raise BridgeError("invalid_runtime")
    if not isinstance(value["max_cost_usd"], str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,6})?", value["max_cost_usd"]):
        raise BridgeError("invalid_cost")
    if not isinstance(value.get("parameters", {}), dict):
        raise BridgeError("invalid_parameters")
    return Command(operation, dict(value, idempotency_key=f"github:{repository_id}:{comment_id}"))


def validate_event(event: dict, environment: dict, policy: Policy) -> tuple[int, Command]:
    """Runner-side early rejection. The server independently re-fetches the comment."""
    try:
        _ensure(policy.enabled)
        _ensure(environment['GITHUB_EVENT_NAME'] == 'issue_comment')
        _ensure(environment['GITHUB_REPOSITORY'] == policy.repository)
        _ensure(environment['GITHUB_REF'] == f'refs/heads/{policy.branch}')
        _ensure(environment['GITHUB_RUN_ATTEMPT'] == '1')
        _ensure(event['action'] == 'created')
        _ensure(event['repository']['id'] == policy.repository_id)
        _ensure(event['repository']['owner']['id'] == policy.owner_id)
        _ensure(event['sender']['id'] == policy.actor_id)
        issue, comment = event["issue"], event["comment"]
        _ensure(issue['number'] == policy.issue_number and 'pull_request' not in issue)
        _ensure(issue['state'] == 'open')
        _ensure(comment['user']['id'] == policy.actor_id and comment['user']['type'] == 'User')
        _ensure(comment['created_at'] == comment['updated_at'])
        _ensure(positive_int(comment['id']))
    except (KeyError, TypeError, ValueError, AssertionError):
        raise BridgeError("unauthorized_comment_event", 403) from None
    return comment["id"], parse_command(comment["body"], repository_id=policy.repository_id, comment_id=comment["id"])


class GitHubOIDC:
    """Validate an Actions identity, NOT an OAuth access token for general MCP tools."""
    def __init__(self, policy: Policy, deployed_sha: str, keys=None):
        import jwt
        self.policy, self.deployed_sha = policy, deployed_sha
        self.keys = keys or jwt.PyJWKClient(ACTIONS_JWKS, cache_keys=True, lifespan=300, timeout=5)

    def verify(self, token: str) -> dict:
        import jwt
        if not self.policy.enabled or not SHA.fullmatch(self.deployed_sha or ""):
            raise BridgeError("bridge_not_configured", 503)
        if not isinstance(token, str) or len(token) > 16384:
            raise BridgeError("invalid_actions_identity", 401)
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            c = jwt.decode(token, key, algorithms=["RS256"], audience=self.policy.audience,
                issuer=ACTIONS_ISSUER, options={"require": ["iss", "sub", "aud", "exp", "iat", "nbf", "jti"]})
            expected = {
                "repository": self.policy.repository,
                "repository_id": str(self.policy.repository_id),
                "repository_owner_id": str(self.policy.owner_id),
                "actor_id": str(self.policy.actor_id),
                "ref": "refs/heads/" + self.policy.branch,
                "event_name": "issue_comment", "run_attempt": "1",
                "workflow_ref": self.policy.workflow_ref,
                "workflow_sha": self.deployed_sha,
                "sha": self.deployed_sha,
                "runner_environment": "github-hosted",
            }
            if any(c.get(k) != v for k, v in expected.items()) or c["sub"] not in self.policy.subjects:
                raise ValueError()
            if c["aud"] != self.policy.audience or not re.fullmatch(r"[1-9][0-9]{0,19}", c.get("run_id", "")):
                raise ValueError()
            if any(type(c[k]) is not int for k in ("iat", "exp", "nbf")) or not 0 < c["exp"] - c["iat"] <= 900:
                raise ValueError()
            return c
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise BridgeError("invalid_actions_identity", 401) from None


def validate_remote_comment(comment: dict, issue: dict, envelope: dict, policy: Policy, now: float | None = None) -> Command:
    """Validate the live API object and the original event body digest; edited requests fail."""
    try:
        _ensure(set(envelope) == {'comment_id', 'body_sha256'})
        _ensure(positive_int(envelope['comment_id']))
        _ensure(isinstance(envelope['body_sha256'], str) and HASH.fullmatch(envelope['body_sha256']))
        _ensure(issue['number'] == policy.issue_number and issue['state'] == 'open' and ('pull_request' not in issue))
        _ensure(comment['id'] == envelope['comment_id'])
        _ensure(comment['user']['id'] == policy.actor_id and comment['user']['type'] == 'User')
        _ensure(comment['issue_url'] == f'https://api.github.com/repos/{policy.repository}/issues/{policy.issue_number}')
        _ensure(comment['created_at'] == comment['updated_at'])
        created = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
        _ensure(created.tzinfo is not None)
        age = (time.time() if now is None else now) - created.timestamp()
        _ensure(-30 <= age <= 1800)
        _ensure(hashlib.sha256(comment['body'].encode()).hexdigest() == envelope['body_sha256'])
    except (KeyError, TypeError, ValueError, AssertionError, AttributeError):
        raise BridgeError("comment_changed_stale_or_unauthorized", 403) from None
    return parse_command(comment["body"], repository_id=policy.repository_id, comment_id=comment["id"])


@dataclass(frozen=True)
class CIPrincipal:
    owner: str
    scopes: frozenset[str] = SCOPES
    browser: bool = False

    def require(self, scope: str):
        if scope not in self.scopes:
            raise BridgeError("insufficient_scope", 403)


def owner_principal(origin: str) -> CIPrincipal:
    # Explicit single-owner local-OAuth mapping. Never infer an external IdP subject.
    return CIPrincipal(hashlib.sha256((origin + "\x00owner").encode()).hexdigest())


PUBLIC_METRICS = {"initial_loss", "final_loss", "loss", "steps", "training_pairs", "vocab_size",
                  "parameters", "elapsed_seconds", "peak_vram_bytes", "tokens_per_second"}
STATES = {"awaiting_approval", "approved", "queued", "submitting", "submit_unknown", "running",
          "succeeded", "failed", "cancelled", "expired"}


def public_summary(result: dict, origin: str) -> dict:
    """Issue/artifact output is intentionally narrower than authenticated Web results.

    Never publish arbitrary stdout/stderr, input parameters, manifests or exception text.
    """
    out = {}
    if isinstance(result.get("id"), str) and RUN_ID.fullmatch(result["id"]):
        out["run_id"] = result["id"]
        out["web_url"] = origin + "/#run=" + result["id"]
    if isinstance(result.get("state"), str) and result["state"] in STATES:
        out["state"] = result["state"]
    if isinstance(result.get("fingerprint"), str) and HASH.fullmatch(result["fingerprint"]):
        out["fingerprint"] = result["fingerprint"]
    if type(result.get("cancel_requested")) is bool:
        out["cancel_requested"] = result["cancel_requested"]
    if isinstance(result.get("providers"), list):
        out["providers"] = [{"id": p["id"], "enabled": p.get("enabled") is True}
                            for p in result["providers"][:20] if isinstance(p, dict) and isinstance(p.get("id"), str) and NAME.fullmatch(p["id"])]
    if isinstance(result.get("workloads"), list):
        out["workloads"] = [{"id": w["id"], "provider": w["provider"]} for w in result["workloads"][:100]
                            if isinstance(w, dict) and all(isinstance(w.get(k), str) and NAME.fullmatch(w[k]) for k in ("id", "provider"))]
    if isinstance(result.get("experiments"), list):
        out["experiments"] = [public_summary({"id": r.get("id"), "state": r.get("state")}, origin) for r in result["experiments"][:50] if isinstance(r, dict)]
    if type(result.get("worker_last_seen_at")) is int:
        out["worker_last_seen_at"] = result["worker_last_seen_at"]
    payload = result.get("result")
    if isinstance(payload, dict):
        for k in ("gpu_used", "simulation"):
            if type(payload.get(k)) is bool:
                out[k] = payload[k]
        metrics = payload.get("metrics", {})
        if isinstance(metrics, dict):
            out["metrics"] = {k: v for k, v in metrics.items() if k in PUBLIC_METRICS and type(v) in (int, float)
                              and abs(v) < 1e100 and math.isfinite(v)}
    return out
