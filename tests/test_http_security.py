"""Exercise actual urllib redirect handling without opening a network socket."""
from __future__ import annotations

from email.message import Message
from io import BytesIO
import inspect
import json
from urllib.error import HTTPError
from urllib.request import BaseHandler, Request, build_opener
from urllib.response import addinfourl

import pytest

from gpu_control.http_security import (
    MAX_JSON_RESPONSE_BYTES, NoRedirects, ResponseBoundaryError,
    decode_json_body, read_bounded_body, urlopen_no_redirects, validate_timeout,
)
from gpu_control.providers.runpod_v1 import RunPodV1HttpClient
from gpu_control.providers.runpod_v2 import RunPodV2Error, RunPodV2HttpClient
from gpu_control.providers.runpod_current_pricing import RunPodPricingGraphQLClient
from gpu_control.providers.runpod_network_volume import RunPodNetworkVolumeS3Client
from gpu_control import source


@pytest.mark.parametrize('code', [301, 302, 303, 307, 308])
def test_real_redirect_pipeline_does_not_forward_authorization(code: int) -> None:
    calls: list[Request] = []

    class FakeHTTPS(BaseHandler):
        handler_order = 100

        def https_open(self, req: Request):  # type: ignore[no-untyped-def]
            calls.append(req)
            headers = Message()
            headers['Location'] = 'https://not-the-provider.invalid/collect'
            response = addinfourl(BytesIO(b''), headers, req.full_url, code)
            response.msg = 'Redirect'
            return response

    opener = build_opener(NoRedirects(), FakeHTTPS())
    request = Request('https://api.github.com/test', headers={'Authorization': 'Bearer audit-test-key'})
    with pytest.raises(HTTPError, match='redirects are forbidden'):
        opener.open(request, timeout=1)
    assert len(calls) == 1
    assert calls[0].full_url == 'https://api.github.com/test'


def test_every_default_credentialed_client_uses_redirect_rejection() -> None:
    assert source.urlopen is urlopen_no_redirects
    for client in [RunPodV1HttpClient, RunPodV2HttpClient, RunPodPricingGraphQLClient, RunPodNetworkVolumeS3Client]:
        assert inspect.signature(client).parameters['opener'].default is urlopen_no_redirects


@pytest.mark.parametrize('url', ['http://api.github.com/test', 'https://user:pass@api.github.com/test'])
def test_url_boundary_rejects_before_any_network(url: str) -> None:
    with pytest.raises(ResponseBoundaryError):
        urlopen_no_redirects(Request(url), timeout=1)


def test_oversized_content_length_rejected_before_read() -> None:
    class Unreadable:
        headers = {'Content-Length': str(MAX_JSON_RESPONSE_BYTES + 1)}

        def read(self, size: int) -> bytes:
            raise AssertionError('Must reject before read')

    with pytest.raises(ResponseBoundaryError, match='byte limit'):
        read_bounded_body(Unreadable())


def test_unknown_length_read_has_a_hard_byte_request_limit() -> None:
    class Oversized:
        headers = {}

        def read(self, size: int) -> bytes:
            assert size == MAX_JSON_RESPONSE_BYTES + 1
            return b'x' * size

    with pytest.raises(ResponseBoundaryError, match='byte limit'):
        read_bounded_body(Oversized())
    assert read_bounded_body(BytesIO(b'{}')) == b'{}'


@pytest.mark.parametrize('body', [
    b'{"role":1,"role":2}', b'NaN', b'Infinity', b'1e999', b'"\\ud800"', b'"\xff"',
    b'[' * 66 + b'0' + b']' * 66,
])
def test_invalid_or_ambiguous_json_is_rejected(body: bytes) -> None:
    with pytest.raises(ResponseBoundaryError):
        decode_json_body(body)


def test_normal_json_with_unicode_and_numbers_remains_supported() -> None:
    data = {'message': 'GPU検証', 'value': 0.44, 'ready': True, 'optional': None}
    assert decode_json_body(json.dumps(data, ensure_ascii=False).encode()) == data


@pytest.mark.parametrize('timeout', [True, False, float('nan'), float('inf'), -1, 0, 10**1000, '1'])
def test_bad_timeouts_are_rejected(timeout: object) -> None:
    with pytest.raises(ResponseBoundaryError):
        validate_timeout(timeout)


@pytest.mark.parametrize('client_type', [RunPodV1HttpClient, RunPodV2HttpClient])
def test_provider_success_response_has_bounded_reads(client_type) -> None:  # type: ignore[no-untyped-def]
    class Response:
        status = 200
        headers = {'Content-Length': str(MAX_JSON_RESPONSE_BYTES + 1)}

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return False

        def read(self, size):  # type: ignore[no-untyped-def]
            raise AssertionError('Must reject oversized response before reading')

    client = client_type('audit-test-key', opener=lambda *args, **kwargs: Response())
    with pytest.raises(RunPodV2Error, match='byte limit'):
        client.list_pods()


def test_source_verification_rejects_untrusted_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class Response(BytesIO):
        status = 200
    monkeypatch.setattr(source, 'urlopen', lambda *args, **kwargs: Response(b'{"private":true,"private":false}'))
    with pytest.raises(source.SourceVerificationError, match='invalid response'):
        source._get_json('https://api.github.com/test', token=None, timeout=1)
