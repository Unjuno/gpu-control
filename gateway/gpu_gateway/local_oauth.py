from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import JSON, Boolean, Column, Integer, String, Table, Text, delete, insert, select, update

from .service import GatewayError
from .store import metadata

LOCAL_SCOPES = ("experiments:read", "experiments:run", "experiments:cancel", "offline_access")

oauth_admin = Table(
    "gateway_oauth_admin_v1", metadata,
    Column("id", Integer, primary_key=True),
    Column("salt_hex", String(64), nullable=False),
    Column("password_hash_hex", String(128), nullable=False),
    Column("created_at", Integer, nullable=False),
)
oauth_login_guard = Table(
    "gateway_oauth_login_guard_v1", metadata,
    Column("id", Integer, primary_key=True),
    Column("failures", Integer, nullable=False),
    Column("window_started", Integer, nullable=False),
    Column("locked_until", Integer, nullable=False),
)
oauth_bootstrap = Table(
    "gateway_oauth_bootstrap_v1", metadata,
    Column("id", Integer, primary_key=True),
    Column("token_hash", String(64), nullable=False),
    Column("expires_at", Integer, nullable=False),
)
oauth_sessions = Table(
    "gateway_oauth_sessions_v1", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("csrf", String(96), nullable=False),
    Column("expires_at", Integer, nullable=False),
    Column("created_at", Integer, nullable=False),
)
oauth_clients = Table(
    "gateway_oauth_clients_v1", metadata,
    Column("client_id", String(128), primary_key=True),
    Column("redirect_uris", JSON, nullable=False),
    Column("client_name", String(160), nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=False),
)
oauth_codes = Table(
    "gateway_oauth_codes_v1", metadata,
    Column("code_hash", String(64), primary_key=True),
    Column("client_id", String(128), nullable=False),
    Column("redirect_uri", Text, nullable=False),
    Column("scope", Text, nullable=False),
    Column("resource", Text, nullable=False),
    Column("code_challenge", String(128), nullable=False),
    Column("subject", String(64), nullable=False),
    Column("expires_at", Integer, nullable=False),
    Column("created_at", Integer, nullable=False),
)
oauth_tokens = Table(
    "gateway_oauth_tokens_v1", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("client_id", String(128), nullable=False),
    Column("subject", String(64), nullable=False),
    Column("scope", Text, nullable=False),
    Column("resource", Text, nullable=False),
    Column("expires_at", Integer, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("revoked", Boolean, nullable=False, default=False),
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _valid_next(value: str) -> bool:
    return isinstance(value, str) and value.startswith("/") and not value.startswith("//") and "\x00" not in value


@dataclass(frozen=True)
class LocalSession:
    token: str
    csrf: str
    expires_at: int


class LocalOAuth:
    """Small single-owner OAuth 2.1 authorization server for the gateway.

    It is intentionally narrow: one human owner, public PKCE clients, opaque
    access/refresh tokens, DCR, and exact resource binding. GPU provider secrets
    are unrelated to this token store.
    """

    def __init__(self, settings, store):
        self.settings = settings
        self.store = store

    @property
    def issuer(self) -> str:
        return self.settings.public_url.rstrip("/")

    @property
    def resource(self) -> str:
        return self.settings.resource

    def configured(self) -> bool:
        with self.store.engine.connect() as c:
            return c.execute(select(oauth_admin.c.id).where(oauth_admin.c.id == 1)).first() is not None

    def seed_bootstrap(self, token: str, *, ttl_seconds: int = 3600) -> None:
        if not token or ttl_seconds < 60 or ttl_seconds > 86400:
            raise ValueError("invalid bootstrap token or TTL")
        now = int(time.time())
        with self.store.transaction() as c:
            c.execute(delete(oauth_bootstrap))
            c.execute(insert(oauth_bootstrap).values(id=1, token_hash=_sha(token), expires_at=now + ttl_seconds))

    def bootstrap_admin(self, token: str, password: str) -> None:
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise GatewayError("weak_password", "Password must be 12-256 characters", 400)
        now = int(time.time())
        with self.store.transaction() as c:
            existing = c.execute(select(oauth_admin.c.id).where(oauth_admin.c.id == 1)).first()
            if existing is not None:
                raise GatewayError("already_configured", "Owner authentication is already configured", 409)
            row = c.execute(select(oauth_bootstrap).where(oauth_bootstrap.c.id == 1).with_for_update()).mappings().first()
            if row is None or row["expires_at"] <= now or not secrets.compare_digest(row["token_hash"], _sha(token)):
                raise GatewayError("invalid_setup_token", "Setup link is invalid or expired", 401)
            salt = secrets.token_bytes(16)
            digest = _password_digest(password, salt)
            c.execute(insert(oauth_admin).values(
                id=1, salt_hex=salt.hex(), password_hash_hex=digest.hex(), created_at=now
            ))
            c.execute(delete(oauth_bootstrap))

    def login(self, password: str) -> LocalSession:
        now = int(time.time())
        raw = "gs_" + secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        expires = now + 12 * 3600
        with self.store.transaction() as c:
            row = c.execute(select(oauth_admin).where(oauth_admin.c.id == 1)).mappings().first()
            if row is None:
                raise GatewayError("auth_not_configured", "Complete owner setup first", 503)
            guard = c.execute(select(oauth_login_guard).where(
                oauth_login_guard.c.id == 1
            ).with_for_update()).mappings().first()
            if guard is None:
                c.execute(insert(oauth_login_guard).values(
                    id=1, failures=0, window_started=now, locked_until=0
                ))
                guard = {"failures": 0, "window_started": now, "locked_until": 0}
            if guard["locked_until"] > now:
                raise GatewayError("login_rate_limited", "Too many failed sign-in attempts; try again later", 429)
            try:
                actual = _password_digest(password, bytes.fromhex(row["salt_hex"])).hex()
            except (ValueError, TypeError):
                actual = ""
            if not secrets.compare_digest(actual, row["password_hash_hex"]):
                failures = guard["failures"]
                window_started = guard["window_started"]
                if now - window_started >= 300:
                    failures, window_started = 0, now
                failures += 1
                locked_until = now + 300 if failures >= 5 else 0
                c.execute(update(oauth_login_guard).where(oauth_login_guard.c.id == 1).values(
                    failures=failures, window_started=window_started, locked_until=locked_until
                ))
                if locked_until:
                    raise GatewayError("login_rate_limited", "Too many failed sign-in attempts; try again later", 429)
                raise GatewayError("invalid_credentials", "Invalid credentials", 401)
            c.execute(update(oauth_login_guard).where(oauth_login_guard.c.id == 1).values(
                failures=0, window_started=now, locked_until=0
            ))
            c.execute(delete(oauth_sessions).where(oauth_sessions.c.expires_at <= now))
            c.execute(insert(oauth_sessions).values(
                token_hash=_sha(raw), csrf=csrf, expires_at=expires, created_at=now
            ))
        return LocalSession(raw, csrf, expires)

    def session(self, raw: str) -> dict:
        now = int(time.time())
        if not isinstance(raw, str) or not raw:
            raise GatewayError("invalid_session", "Sign in again", 401)
        with self.store.engine.connect() as c:
            row = c.execute(select(oauth_sessions).where(
                oauth_sessions.c.token_hash == _sha(raw),
                oauth_sessions.c.expires_at > now,
            )).mappings().first()
        if row is None:
            raise GatewayError("invalid_session", "Sign in again", 401)
        return {"sub": "owner", "csrf": row["csrf"], "expires_at": row["expires_at"]}

    def logout(self, raw: str) -> None:
        if not raw:
            return
        with self.store.transaction() as c:
            c.execute(delete(oauth_sessions).where(oauth_sessions.c.token_hash == _sha(raw)))

    def _validate_redirect_uri(self, uri: str) -> str:
        try:
            p = urlsplit(uri)
        except ValueError:
            raise GatewayError("invalid_client_metadata", "Invalid redirect URI", 400)
        host = (p.hostname or "").lower()
        if p.fragment or p.username or p.password:
            raise GatewayError("invalid_client_metadata", "Invalid redirect URI", 400)
        trusted = host == "chatgpt.com" or host.endswith(".chatgpt.com") or host == "openai.com" or host.endswith(".openai.com")
        local = host in {"localhost", "127.0.0.1", "::1"} and p.scheme == "http" and not self.settings.hosted
        if not ((p.scheme == "https" and trusted) or local):
            raise GatewayError("invalid_client_metadata", "OAuth redirect host is not allowed", 400)
        return uri

    def register_client(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise GatewayError("invalid_client_metadata", "Client metadata must be an object", 400)
        redirect_uris = payload.get("redirect_uris")
        if not isinstance(redirect_uris, list) or not 1 <= len(redirect_uris) <= 8:
            raise GatewayError("invalid_client_metadata", "redirect_uris are required", 400)
        redirect_uris = [self._validate_redirect_uri(x) for x in redirect_uris if isinstance(x, str)]
        if len(redirect_uris) != len(payload["redirect_uris"]):
            raise GatewayError("invalid_client_metadata", "redirect_uris must be strings", 400)
        method = payload.get("token_endpoint_auth_method", "none")
        if method != "none":
            raise GatewayError("invalid_client_metadata", "Only public PKCE clients are supported", 400)
        grants = payload.get("grant_types", ["authorization_code", "refresh_token"])
        if not isinstance(grants, list) or any(x not in {"authorization_code", "refresh_token"} for x in grants):
            raise GatewayError("invalid_client_metadata", "Unsupported grant type", 400)
        responses = payload.get("response_types", ["code"])
        if not isinstance(responses, list) or not responses or any(not isinstance(x, str) for x in responses) or set(responses) != {"code"}:
            raise GatewayError("invalid_client_metadata", "Only authorization code response type is supported", 400)
        name = payload.get("client_name", "MCP client")
        if not isinstance(name, str) or not name.strip():
            name = "MCP client"
        name = name.strip()[:160]
        canonical = json.dumps(
            {"redirect_uris": sorted(redirect_uris), "client_name": name},
            sort_keys=True, separators=(",", ":"),
        )
        client_id = "mcp_" + hashlib.sha256(canonical.encode()).hexdigest()[:48]
        now = int(time.time())
        expires_at = now + 3600
        with self.store.transaction() as c:
            c.execute(delete(oauth_clients).where(oauth_clients.c.expires_at <= now))
            existing = c.execute(select(oauth_clients).where(
                oauth_clients.c.client_id == client_id
            ).with_for_update()).mappings().first()
            if existing is None:
                c.execute(insert(oauth_clients).values(
                    client_id=client_id, redirect_uris=redirect_uris, client_name=name,
                    created_at=now, expires_at=expires_at,
                ))
            else:
                c.execute(update(oauth_clients).where(
                    oauth_clients.c.client_id == client_id
                ).values(expires_at=expires_at))
        return {
            "client_id": client_id,
            "client_id_issued_at": now,
            "redirect_uris": redirect_uris,
            "client_name": name,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }

    def _client(self, client_id: str) -> dict:
        now = int(time.time())
        with self.store.engine.connect() as c:
            row = c.execute(select(oauth_clients).where(
                oauth_clients.c.client_id == client_id,
                oauth_clients.c.expires_at > now,
            )).mappings().first()
        if row is None:
            raise GatewayError("invalid_client", "Unknown or expired OAuth client", 400)
        return dict(row)

    def _scope(self, value: str | None) -> str:
        requested = [x for x in (value or "experiments:read").split() if x]
        if not requested or any(x not in LOCAL_SCOPES for x in requested):
            raise GatewayError("invalid_scope", "Unsupported OAuth scope", 400)
        return " ".join(dict.fromkeys(requested))

    def authorize(self, params: dict, session_token: str) -> str:
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        if params.get("response_type") != "code":
            raise GatewayError("unsupported_response_type", "Only response_type=code is supported", 400)
        client = self._client(client_id)
        if redirect_uri not in client["redirect_uris"]:
            raise GatewayError("invalid_request", "redirect_uri does not match registered client", 400)
        if params.get("code_challenge_method") != "S256":
            raise GatewayError("invalid_request", "PKCE S256 is required", 400)
        challenge = params.get("code_challenge", "")
        if not isinstance(challenge, str) or not 43 <= len(challenge) <= 128:
            raise GatewayError("invalid_request", "Valid PKCE code_challenge is required", 400)
        if params.get("resource") != self.resource:
            raise GatewayError("invalid_target", "OAuth resource must match the MCP resource", 400)
        self.session(session_token)
        scope = self._scope(params.get("scope"))
        raw = "gc_" + secrets.token_urlsafe(32)
        now = int(time.time())
        with self.store.transaction() as c:
            c.execute(update(oauth_clients).where(
                oauth_clients.c.client_id == client_id
            ).values(expires_at=now + 30 * 86400))
            c.execute(insert(oauth_codes).values(
                code_hash=_sha(raw), client_id=client_id, redirect_uri=redirect_uri,
                scope=scope, resource=self.resource, code_challenge=challenge,
                subject="owner", expires_at=now + 300, created_at=now
            ))
        return raw

    def _consume_code(self, raw: str) -> dict:
        now = int(time.time())
        with self.store.transaction() as c:
            row = c.execute(select(oauth_codes).where(oauth_codes.c.code_hash == _sha(raw)).with_for_update()).mappings().first()
            if row is None:
                raise GatewayError("invalid_grant", "Authorization code is invalid", 400)
            c.execute(delete(oauth_codes).where(oauth_codes.c.code_hash == _sha(raw)))
        if row["expires_at"] <= now:
            raise GatewayError("invalid_grant", "Authorization code expired", 400)
        return dict(row)

    def _store_token(self, raw: str, *, kind: str, client_id: str, subject: str, scope: str,
                     resource: str, expires_at: int) -> None:
        with self.store.transaction() as c:
            c.execute(insert(oauth_tokens).values(
                token_hash=_sha(raw), kind=kind, client_id=client_id, subject=subject,
                scope=scope, resource=resource, expires_at=expires_at,
                created_at=int(time.time()), revoked=False
            ))

    def _new_token_pair(self, *, client_id: str, subject: str, scope: str, resource: str) -> dict:
        now = int(time.time())
        access = "ga_" + secrets.token_urlsafe(32)
        self._store_token(access, kind="access", client_id=client_id, subject=subject,
                          scope=scope, resource=resource, expires_at=now + 3600)
        value = {"access_token": access, "token_type": "Bearer", "expires_in": 3600, "scope": scope}
        if "offline_access" in scope.split():
            refresh = "gr_" + secrets.token_urlsafe(40)
            self._store_token(refresh, kind="refresh", client_id=client_id, subject=subject,
                              scope=scope, resource=resource, expires_at=now + 30 * 86400)
            value["refresh_token"] = refresh
        return value

    def token(self, form: dict) -> dict:
        grant = form.get("grant_type")
        client_id = form.get("client_id", "")
        self._client(client_id)
        resource = form.get("resource", "")
        if resource != self.resource:
            raise GatewayError("invalid_target", "OAuth resource must match the MCP resource", 400)
        if grant == "authorization_code":
            row = self._consume_code(form.get("code", ""))
            if row["client_id"] != client_id or row["redirect_uri"] != form.get("redirect_uri") or row["resource"] != resource:
                raise GatewayError("invalid_grant", "Authorization code binding mismatch", 400)
            verifier = form.get("code_verifier", "")
            if not isinstance(verifier, str) or not 43 <= len(verifier) <= 128:
                raise GatewayError("invalid_grant", "Valid PKCE verifier is required", 400)
            expected = _b64url(hashlib.sha256(verifier.encode()).digest())
            if not secrets.compare_digest(expected, row["code_challenge"]):
                raise GatewayError("invalid_grant", "PKCE verification failed", 400)
            return self._new_token_pair(client_id=client_id, subject=row["subject"],
                                        scope=row["scope"], resource=resource)
        if grant == "refresh_token":
            raw = form.get("refresh_token", "")
            now = int(time.time())
            with self.store.transaction() as c:
                row = c.execute(select(oauth_tokens).where(
                    oauth_tokens.c.token_hash == _sha(raw),
                    oauth_tokens.c.kind == "refresh",
                    oauth_tokens.c.client_id == client_id,
                    oauth_tokens.c.resource == resource,
                    oauth_tokens.c.revoked.is_(False),
                    oauth_tokens.c.expires_at > now,
                ).with_for_update()).mappings().first()
                if row is None:
                    raise GatewayError("invalid_grant", "Refresh token is invalid or expired", 400)
                c.execute(update(oauth_tokens).where(oauth_tokens.c.token_hash == _sha(raw)).values(revoked=True))
            scope = row["scope"]
            if form.get("scope"):
                narrowed = self._scope(form["scope"])
                if not set(narrowed.split()).issubset(set(scope.split())):
                    raise GatewayError("invalid_scope", "Refresh scope cannot be expanded", 400)
                scope = narrowed
            return self._new_token_pair(client_id=client_id, subject=row["subject"],
                                        scope=scope, resource=resource)
        raise GatewayError("unsupported_grant_type", "Unsupported OAuth grant type", 400)

    def verify_access(self, raw: str) -> dict:
        now = int(time.time())
        with self.store.engine.connect() as c:
            row = c.execute(select(oauth_tokens).where(
                oauth_tokens.c.token_hash == _sha(raw),
                oauth_tokens.c.kind == "access",
                oauth_tokens.c.resource == self.resource,
                oauth_tokens.c.revoked.is_(False),
                oauth_tokens.c.expires_at > now,
            )).mappings().first()
        if row is None:
            raise GatewayError("invalid_token", "Invalid or expired access token", 401)
        return {
            "iss": self.issuer, "sub": row["subject"], "aud": self.resource,
            "scope": row["scope"], "iat": row["created_at"], "exp": row["expires_at"]
        }

    def discovery(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/oauth/authorize",
            "token_endpoint": self.issuer + "/oauth/token",
            "registration_endpoint": self.issuer + "/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": list(LOCAL_SCOPES),
        }
