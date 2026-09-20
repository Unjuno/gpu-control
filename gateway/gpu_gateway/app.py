from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from .auth import Auth, SCOPES, SESSION
from .config import Settings, load_workloads
from .protocol import dispatch, error, tools, validate_headers
from .service import ExperimentService, GatewayError
from .store import Store

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, *, service=None, auth=None) -> FastAPI:
    configuration_error = False
    try:
        settings = settings or Settings.from_env()
        settings.validate()
        service = service or ExperimentService(Store(settings.database_url), settings, load_workloads())
        auth = auth or Auth(settings)
    except (ValueError, TypeError):
        # Health/UI can explain missing deployment configuration without exposing secrets.
        configuration_error = True
    app = FastAPI(title="GPU Control Gateway", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service, app.state.auth = service, auth

    @app.middleware("http")
    async def headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except SQLAlchemyError:
            response = JSONResponse({"code": "database_unavailable", "message": "Initialize/configure the durable gateway database"}, 503)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path.startswith(("/api", "/mcp", "/auth")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(GatewayError)
    async def gateway_error(request, exc):
        headers = {}
        if exc.status in {401, 403} and settings:
            challenge = f'Bearer resource_metadata="{settings.public_url}/.well-known/oauth-protected-resource/mcp"'
            if exc.code == "insufficient_scope":
                challenge += ', error="insufficient_scope", scope="' + exc.message.removeprefix("Required scope: ") + '"'
            headers["WWW-Authenticate"] = challenge
        return JSONResponse({"code": exc.code, "message": exc.message}, exc.status, headers=headers)

    def ready():
        if configuration_error or service is None or auth is None:
            raise GatewayError("configuration_required", "Configure durable database, OIDC and workload registry", 503)

    async def body(request):
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise GatewayError("content_type", "application/json is required", 415)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > settings.max_request_bytes:
                raise GatewayError("request_too_large", "Request exceeds size limit", 413)
        try:
            def reject_constant(_):
                raise ValueError()
            def pairs(values):
                result = {}
                for key, value in values:
                    if key in result: raise ValueError()
                    result[key] = value
                return result
            return json.loads(data, parse_constant=reject_constant, object_pairs_hook=pairs)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise GatewayError("invalid_json", "Valid JSON with unique keys is required", 400)

    @app.get("/healthz")
    def health():
        return {"service": "gpu-control-gateway", "configured": not configuration_error,
                "auth_configured": bool(not configuration_error and settings.auth_ready),
                "gpu_started_by_health_check": False}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/.well-known/oauth-protected-resource")
    @app.get("/.well-known/oauth-protected-resource/mcp")
    def metadata():
        ready()
        if not settings.auth_ready:
            raise GatewayError("auth_not_configured", "Configure an OAuth authorization server", 503)
        return {"resource": settings.resource, "authorization_servers": [settings.issuer],
                "scopes_supported": list(SCOPES), "bearer_methods_supported": ["header"]}

    @app.get("/auth/login")
    def login():
        ready()
        return auth.login()

    @app.get("/auth/callback")
    def callback(request: Request, code: str, state: str):
        ready()
        return auth.callback(request, code, state)

    @app.get("/api/session")
    def session(request: Request):
        ready()
        principal = auth.authenticate(request, browser_only=True)
        return {"owner": principal.owner, "scopes": sorted(principal.scopes), "csrf": auth.session(request)["csrf"]}

    @app.post("/auth/logout")
    def logout(request: Request):
        ready()
        auth.authenticate(request, mutation=True, browser_only=True)
        response = JSONResponse({"signed_out": True})
        response.delete_cookie(SESSION, path="/")
        return response

    @app.get("/api/tools")
    def get_tools(request: Request):
        ready()
        return {"tools": tools(auth.authenticate(request))}

    @app.post("/api/tools/{name}")
    async def invoke(request: Request, name: str):
        ready()
        principal = await run_in_threadpool(auth.authenticate, request, mutation=True)
        arguments = await body(request)
        if not isinstance(arguments, dict):
            raise GatewayError("invalid_arguments", "An argument object is required")
        return await run_in_threadpool(service.invoke, principal, name, arguments)

    @app.post("/api/approvals/{run_id}")
    async def approve(request: Request, run_id: str):
        ready()
        principal = await run_in_threadpool(auth.authenticate, request, mutation=True, browser_only=True)
        arguments = await body(request)
        if not isinstance(arguments, dict) or set(arguments) != {"fingerprint"}:
            raise GatewayError("invalid_arguments", "Provide only the exact plan fingerprint")
        return await run_in_threadpool(service.approve, principal, run_id, arguments["fingerprint"])

    @app.api_route("/mcp", methods=["POST", "GET", "DELETE"])
    async def mcp(request: Request):
        ready()
        # MCP has a bearer-only boundary, independent of ambient browser cookies.
        origin = request.headers.get("origin")
        if origin is not None and origin != settings.public_url:
            raise GatewayError("invalid_origin", "Origin is not allowed", 403)
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise GatewayError("invalid_token", "Bearer access token is required", 401)
        principal = await run_in_threadpool(auth.verify, authorization[7:])
        if request.method != "POST":
            return Response(status_code=405, headers={"Allow": "POST"})
        accept = request.headers.get("accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            raise GatewayError("not_acceptable", "Accept must include application/json and text/event-stream", 406)
        try:
            payload = await body(request)
        except GatewayError as exc:
            if exc.code == "invalid_json":
                return JSONResponse(error(None, -32700, "Parse error"), 400)
            raise
        version, header_error = validate_headers(payload, request.headers)
        if header_error:
            return JSONResponse(header_error[0], header_error[1])
        value, status = await run_in_threadpool(dispatch, service, principal, payload, version)
        return Response(status_code=status) if value is None else JSONResponse(value, status)

    return app
