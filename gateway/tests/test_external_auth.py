from dataclasses import replace
import json
from types import SimpleNamespace

import pytest
from jwt import jwks_client
from jwt.exceptions import PyJWKClientConnectionError

from gpu_gateway import auth as auth_module
from gpu_gateway.auth import Auth, LOGIN_STATE
from gpu_gateway.service import GatewayError


def test_oidc_callback_stops_reading_oversized_token_response(system, web, monkeypatch):
    body = b'{"padding":"' + b"x" * 70000 + b'"}'

    class ResponseStream:
        def __init__(self):
            self.read_bytes = 0

        def __iter__(self):
            for offset in range(0, len(body), 4096):
                chunk = body[offset:offset + 4096]
                self.read_bytes += len(chunk)
                yield chunk

        def close(self):
            pass

    stream = ResponseStream()

    class Response:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            pass

        def json(self):
            return json.loads(b"".join(iter(stream)))

        def iter_raw(self):
            return iter(stream)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            stream.close()

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, *_args, **_kwargs):
            return Response()

        def stream(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(auth_module.httpx, "Client", Client)
    settings = replace(
        system.settings,
        cookie_key=web.settings.cookie_key,
        client_id="gateway-client",
        authorization_endpoint="https://issuer.example/authorize",
        token_endpoint="https://issuer.example/token",
    )
    auth = Auth(settings, keys=web.auth.keys)
    request = SimpleNamespace(cookies={
        LOGIN_STATE: auth.seal({"state": "expected", "nonce": "nonce", "verifier": "verifier"}),
    })

    with pytest.raises(GatewayError, match="OAuth exchange failed"):
        auth.callback(request, "authorization-code", "expected")

    assert stream.read_bytes < len(body)


def test_oidc_jwks_stops_reading_oversized_response(system, monkeypatch):
    body = b'{"keys":[],"padding":"' + b"x" * 70000 + b'"}'

    class ResponseStream:
        def __init__(self):
            self.read_bytes = 0

        def __iter__(self):
            for offset in range(0, len(body), 4096):
                chunk = body[offset:offset + 4096]
                self.read_bytes += len(chunk)
                yield chunk

    stream = ResponseStream()

    class Response:
        headers = {}

        def raise_for_status(self):
            pass

        def read(self, size=-1):
            data = b"".join(iter(stream))
            return data if size < 0 else data[:size]

        def iter_raw(self):
            return iter(stream)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def stream(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(auth_module.httpx, "Client", Client)
    monkeypatch.setattr(jwks_client.urllib.request, "urlopen",
                        lambda *_args, **_kwargs: Response())
    settings = replace(system.settings, jwks_url="https://issuer.example/jwks")
    auth = Auth(settings)

    with pytest.raises(PyJWKClientConnectionError):
        auth.keys.fetch_data()

    assert stream.read_bytes < len(body)
