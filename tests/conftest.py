"""The unit/contract suite must never open real network connections."""
import socket

import pytest


@pytest.fixture(autouse=True)
def deny_network_in_offline_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError('Real network access is forbidden in the offline test suite')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket.socket, 'connect_ex', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket, 'getaddrinfo', deny)
