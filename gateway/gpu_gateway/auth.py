from __future__ import annotations

import hashlib
import html
import json
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import Settings
from .local_oauth import LocalOAuth
from .service import GatewayError, Principal

SCOPES = ("experiments:read", "experiments:run", "experiments:cancel")
SESSION = "gpu_gateway_session"
LOGIN_STATE = "gpu_gateway_login"


def _safe_next(value: str | None) -> str:
    return value if isinstance(value, str) and value.startswith("/") and not value.startswith("//") and "\x00" not in value else "/"


class Auth:
    """External OIDC resource server or built-in single-owner OAuth 2.1.

    External OIDC remains supported when GATEWAY_OIDC_ISSUER is configured.
    Otherwise the gateway uses its durable local OAuth server. Provider API
    credentials never enter either authentication path.
    """

    def __init__(self, settings: Settings, store=None, keys=None):
        self.settings = settings
        self.external = bool(settings.issuer)
        self.local = None if self.external else (LocalOAuth(settings, store) if store is not None else None)
        self.keys = keys or (
            jwt.PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=300, timeout=5)
            if self.external and settings.jwks_url else None
        )
        self.fernet = Fernet(settings.cookie_key.encode()) if self.external and settings.cookie_key else None

    def configured(self) -> bool:
        if self.external:
            return self.settings.auth_ready
        return bool(self.local and self.local.configured())

    @property
    def authorization_server(self) -> str:
        return self.settings.issuer if self.external else self.settings.public_url

    def decode(self, token: str, audience: str) -> dict:
        if not self.external:
            if self.local is None or audience != self.settings.resource:
                raise GatewayError("invalid_token", "Invalid token audience", 401)
            return self.local.verify_access(token)
        if not self.settings.auth_ready or self.keys is None:
            raise GatewayError("auth_not_configured", "Configure OIDC and the owner allowlist", 503)
        try:
            if len(token) > 16384:
                raise ValueError()
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256", "ES256"],
                audience=audience, issuer=self.settings.issuer,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
            if claims["sub"] not in self.settings.allowed_subjects:
                raise ValueError()
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise GatewayError("invalid_token", "Invalid or unauthorized access token", 401)

    def verify(self, token: str, *, browser=False) -> Principal:
        claims = self.decode(token, self.settings.resource)
        scope = claims.get("scope", "")
        if not isinstance(scope, str):
            raise GatewayError("invalid_token", "Invalid scope claim", 401)
        owner = hashlib.sha256((claims["iss"] + "\x00" + claims["sub"]).encode()).hexdigest()
        return Principal(owner, frozenset(scope.split()), browser)

    def seal(self, value: dict) -> str:
        if not self.external or self.fernet is None:
            raise GatewayError("web_auth_not_configured", "External OIDC cookie sealing is not configured", 503)
        return self.fernet.encrypt(json.dumps(value).encode()).decode()

    def unseal(self, value: str, ttl: int) -> dict:
        try:
            if not self.external or self.fernet is None:
                raise ValueError()
            return json.loads(self.fernet.decrypt(value.encode(), ttl=ttl))
        except (InvalidToken, ValueError, TypeError, KeyError):
            raise GatewayError("invalid_session", "Sign in again", 401)

    def session(self, request: Request) -> dict:
        raw = request.cookies.get(SESSION, "")
        if not self.external:
            if self.local is None:
                raise GatewayError("auth_not_configured", "Authentication store is unavailable", 503)
            return self.local.session(raw)
        return self.unseal(raw, 3600)

    def authenticate(self, request: Request, *, mutation=False, browser_only=False) -> Principal:
        origin = request.headers.get("origin")
        if origin is not None and origin != self.settings.public_url:
            raise GatewayError("invalid_origin", "Origin is not allowed", 403)
        authorization = request.headers.get("authorization", "")
        if authorization:
            if browser_only or not authorization.startswith("Bearer "):
                raise GatewayError("browser_approval_required", "Use the authenticated Web approval page", 403)
            return self.verify(authorization[7:])
        session = self.session(request)
        if mutation:
            csrf = request.headers.get("x-csrf-token", "")
            if origin != self.settings.public_url or not csrf or not secrets.compare_digest(csrf, session.get("csrf", "")):
                raise GatewayError("csrf_failed", "Browser request failed CSRF validation", 403)
        if not self.external:
            claims = {"iss": self.settings.public_url, "sub": session["sub"]}
            owner = hashlib.sha256((claims["iss"] + "\x00" + claims["sub"]).encode()).hexdigest()
            return Principal(owner, frozenset(SCOPES), True)
        return self.verify(session["access_token"], browser=True)

    def _login_html(self, next_path: str, error: str = "") -> HTMLResponse:
        err = f"<p role='alert'>{html.escape(error)}</p>" if error else ""
        value = html.escape(_safe_next(next_path), quote=True)
        return HTMLResponse(
            "<!doctype html><html lang='ja'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>GPU Control Login</title><body><main style='max-width:32rem;margin:4rem auto;font-family:system-ui'>"
            "<h1>GPU Control</h1><p>所有者パスワードでログインしてください。</p>" + err +
            "<form method='post' action='/auth/login'><input type='hidden' name='next' value='" + value + "'>"
            "<label>パスワード <input name='password' type='password' minlength='12' required autocomplete='current-password'></label>"
            "<button type='submit'>ログイン</button></form></main></body></html>",
            headers={"Cache-Control": "no-store"},
        )

    def _setup_html(self, token: str, error: str = "") -> HTMLResponse:
        err = f"<p role='alert'>{html.escape(error)}</p>" if error else ""
        value = html.escape(token, quote=True)
        return HTMLResponse(
            "<!doctype html><html lang='ja'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>GPU Control Setup</title><body><main style='max-width:32rem;margin:4rem auto;font-family:system-ui'>"
            "<h1>初期認証設定</h1><p>このgateway専用の所有者パスワードを設定します。</p>" + err +
            "<form method='post' action='/auth/setup'><input type='hidden' name='token' value='" + value + "'>"
            "<label>新しいパスワード <input name='password' type='password' minlength='12' required autocomplete='new-password'></label>"
            "<button type='submit'>設定</button></form></main></body></html>",
            headers={"Cache-Control": "no-store"},
        )

    def login(self, request: Request | None = None):
        if not self.external:
            return self._login_html(_safe_next(request.query_params.get("next") if request else "/"))
        if not self.settings.web_auth_ready:
            raise GatewayError("web_auth_not_configured", "Configure OIDC browser client and cookie key", 503)
        state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        import base64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = {
            "response_type": "code", "client_id": self.settings.client_id,
            "redirect_uri": self.settings.public_url + "/auth/callback",
            "scope": "openid " + " ".join(SCOPES), "resource": self.settings.resource,
            "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
        }
        response = RedirectResponse(self.settings.authorization_endpoint + "?" + urlencode(query), 303)
        response.set_cookie(
            LOGIN_STATE, self.seal({"state": state, "nonce": nonce, "verifier": verifier}),
            httponly=True, secure=self.settings.public_url.startswith("https:"),
            samesite="lax", max_age=600, path="/auth",
        )
        return response

    def login_password(self, password: str, next_path: str) -> RedirectResponse:
        if self.external or self.local is None:
            raise GatewayError("invalid_auth_mode", "Password login is unavailable", 404)
        session = self.local.login(password)
        response = RedirectResponse(_safe_next(next_path), 303)
        response.set_cookie(
            SESSION, session.token, httponly=True, secure=self.settings.public_url.startswith("https:"),
            samesite="lax", max_age=12 * 3600, path="/",
        )
        return response

    def setup(self, token: str, password: str | None = None):
        if self.external or self.local is None:
            raise GatewayError("invalid_auth_mode", "Local setup is unavailable", 404)
        if password is None:
            return self._setup_html(token)
        self.local.bootstrap_admin(token, password)
        return RedirectResponse("/auth/login", 303)

    def logout(self, request: Request) -> None:
        if not self.external and self.local is not None:
            self.local.logout(request.cookies.get(SESSION, ""))

    def callback(self, request: Request, code: str, state: str) -> RedirectResponse:
        if not self.external:
            raise GatewayError("invalid_auth_mode", "OIDC callback is unavailable", 404)
        pending = self.unseal(request.cookies.get(LOGIN_STATE, ""), 600)
        if not state or not secrets.compare_digest(state, pending["state"]):
            raise GatewayError("invalid_oauth_state", "OAuth state validation failed", 400)
        payload = {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": self.settings.public_url + "/auth/callback",
            "client_id": self.settings.client_id, "code_verifier": pending["verifier"],
            "resource": self.settings.resource,
        }
        basic = (self.settings.client_id, self.settings.client_secret) if self.settings.client_secret else None
        try:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.post(self.settings.token_endpoint, data=payload, auth=basic)
                response.raise_for_status()
                tokens = response.json()
            identity = self.decode(tokens["id_token"], self.settings.client_id)
            if identity.get("nonce") != pending["nonce"]:
                raise ValueError()
            claims = self.decode(tokens["access_token"], self.settings.resource)
            if claims["sub"] != identity["sub"]:
                raise ValueError()
            self.verify(tokens["access_token"], browser=True)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise GatewayError("oauth_exchange_failed", "OAuth exchange failed; verify client, resource and scopes", 401)
        result = RedirectResponse("/", 303)
        result.delete_cookie(LOGIN_STATE, path="/auth")
        sealed = self.seal({"access_token": tokens["access_token"], "csrf": secrets.token_urlsafe(32)})
        if len(sealed) > 3800:
            raise GatewayError("token_too_large", "Configure opaque server-side sessions for this identity provider", 503)
        result.set_cookie(
            SESSION, sealed, httponly=True, secure=self.settings.public_url.startswith("https:"),
            samesite="lax", max_age=3600, path="/",
        )
        return result
