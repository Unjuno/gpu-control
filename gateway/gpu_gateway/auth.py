from __future__ import annotations

import hashlib
import json
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from fastapi.responses import RedirectResponse

from .config import Settings
from .service import GatewayError, Principal

SCOPES = ("experiments:read", "experiments:run", "experiments:cancel")
SESSION = "gpu_gateway_session"
LOGIN_STATE = "gpu_gateway_login"


class Auth:
    """OIDC resource-server validation plus an independent browser PKCE client.

    The authorization server is external. This module does not issue OAuth tokens.
    Provider API credentials never enter cookies or MCP token exchange.
    """
    def __init__(self, settings: Settings, keys=None):
        self.settings = settings
        self.keys = keys or (jwt.PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=300, timeout=5) if settings.jwks_url else None)
        self.fernet = Fernet(settings.cookie_key.encode()) if settings.cookie_key else None

    def decode(self, token: str, audience: str) -> dict:
        if not self.settings.auth_ready or self.keys is None:
            raise GatewayError("auth_not_configured", "Configure OIDC and the owner allowlist", 503)
        try:
            if len(token) > 16384:
                raise ValueError()
            key = self.keys.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256", "ES256"],
                audience=audience, issuer=self.settings.issuer,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]})
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
        if self.fernet is None:
            raise GatewayError("web_auth_not_configured", "Configure a stable browser cookie key", 503)
        return self.fernet.encrypt(json.dumps(value).encode()).decode()

    def unseal(self, value: str, ttl: int) -> dict:
        try:
            if self.fernet is None:
                raise ValueError()
            return json.loads(self.fernet.decrypt(value.encode(), ttl=ttl))
        except (InvalidToken, ValueError, TypeError, KeyError):
            raise GatewayError("invalid_session", "Sign in again", 401)

    def session(self, request: Request) -> dict:
        return self.unseal(request.cookies.get(SESSION, ""), 3600)

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
        return self.verify(session["access_token"], browser=True)

    def login(self) -> RedirectResponse:
        if not self.settings.web_auth_ready:
            raise GatewayError("web_auth_not_configured", "Configure OIDC browser client and cookie key", 503)
        state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        import base64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = {"response_type": "code", "client_id": self.settings.client_id,
                 "redirect_uri": self.settings.public_url + "/auth/callback",
                 "scope": "openid " + " ".join(SCOPES), "resource": self.settings.resource,
                 "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
        response = RedirectResponse(self.settings.authorization_endpoint + "?" + urlencode(query), 303)
        response.set_cookie(LOGIN_STATE, self.seal({"state": state, "nonce": nonce, "verifier": verifier}),
            httponly=True, secure=self.settings.public_url.startswith("https:"), samesite="lax", max_age=600, path="/auth")
        return response

    def callback(self, request: Request, code: str, state: str) -> RedirectResponse:
        pending = self.unseal(request.cookies.get(LOGIN_STATE, ""), 600)
        if not state or not secrets.compare_digest(state, pending["state"]):
            raise GatewayError("invalid_oauth_state", "OAuth state validation failed", 400)
        payload = {"grant_type": "authorization_code", "code": code,
                   "redirect_uri": self.settings.public_url + "/auth/callback",
                   "client_id": self.settings.client_id, "code_verifier": pending["verifier"],
                   "resource": self.settings.resource}
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
        result.set_cookie(SESSION, sealed, httponly=True, secure=self.settings.public_url.startswith("https:"),
                          samesite="lax", max_age=3600, path="/")
        return result
