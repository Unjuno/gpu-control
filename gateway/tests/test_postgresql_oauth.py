"""OAuth refresh rotation tests for the dedicated PostgreSQL fixture."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select

from gpu_gateway.config import Settings
from gpu_gateway.local_oauth import LocalOAuth, oauth_tokens
from gpu_gateway.service import GatewayError
from gpu_gateway.store import Store


def test_postgres_refresh_token_can_only_be_consumed_once_concurrently():
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    oauth = LocalOAuth(settings, store)
    registered = oauth.register_client({
        'client_name': 'refresh-race-' + uuid4().hex,
        'redirect_uris': ['https://chatgpt.com/connector_platform_oauth_redirect'],
    })
    client_id = registered['client_id']
    original = oauth._new_token_pair(
        client_id=client_id, subject='owner',
        scope='experiments:read offline_access', resource=settings.resource,
    )
    barrier = threading.Barrier(2)

    def refresh_once():
        barrier.wait(timeout=10)
        try:
            return ('success', oauth.token({
                'grant_type': 'refresh_token', 'client_id': client_id,
                'refresh_token': original['refresh_token'], 'resource': settings.resource,
            }))
        except GatewayError as error:
            return ('error', error.code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: refresh_once(), range(2)))
        successes = [value for status, value in outcomes if status == 'success']
        errors = [value for status, value in outcomes if status == 'error']
        assert len(successes) == 1
        assert errors == ['invalid_grant']
        with store.engine.connect() as connection:
            rows = connection.execute(select(oauth_tokens.c.kind, oauth_tokens.c.revoked).where(
                oauth_tokens.c.client_id == client_id
            )).all()
        assert sorted((kind, revoked) for kind, revoked in rows) == [
            ('access', False), ('access', False), ('refresh', False), ('refresh', True),
        ]
    finally:
        store.engine.dispose()


def test_postgres_refresh_rotation_rolls_back_if_replacement_insert_fails(monkeypatch):
    url = os.environ.get('GATEWAY_TEST_DATABASE_URL')
    if not url:
        pytest.skip('requires a dedicated PostgreSQL test database')
    settings = Settings(database_url=url)
    store = Store(url); store.initialize()
    oauth = LocalOAuth(settings, store)
    registered = oauth.register_client({
        'client_name': 'refresh-rollback-' + uuid4().hex,
        'redirect_uris': ['https://chatgpt.com/connector_platform_oauth_redirect'],
    })
    client_id = registered['client_id']
    original = oauth._new_token_pair(
        client_id=client_id, subject='owner',
        scope='experiments:read offline_access', resource=settings.resource,
    )
    real_insert = oauth._insert_token

    def fail_replacement_refresh(connection, raw, **kwargs):
        if kwargs['kind'] == 'refresh':
            raise RuntimeError('injected PostgreSQL refresh insert failure')
        return real_insert(connection, raw, **kwargs)

    monkeypatch.setattr(oauth, '_insert_token', fail_replacement_refresh)
    try:
        with pytest.raises(RuntimeError, match='injected PostgreSQL refresh insert failure'):
            oauth.token({
                'grant_type': 'refresh_token', 'client_id': client_id,
                'refresh_token': original['refresh_token'], 'resource': settings.resource,
            })

        with store.engine.connect() as connection:
            rows = connection.execute(select(oauth_tokens.c.kind, oauth_tokens.c.revoked).where(
                oauth_tokens.c.client_id == client_id
            )).all()
        assert sorted((kind, revoked) for kind, revoked in rows) == [
            ('access', False), ('refresh', False),
        ]

        monkeypatch.setattr(oauth, '_insert_token', real_insert)
        rotated = oauth.token({
            'grant_type': 'refresh_token', 'client_id': client_id,
            'refresh_token': original['refresh_token'], 'resource': settings.resource,
        })
        assert rotated['refresh_token'] != original['refresh_token']
    finally:
        store.engine.dispose()
