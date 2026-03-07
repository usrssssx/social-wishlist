from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.auth import hash_password
from app.db import AsyncSessionLocal
from app.models import OAuthAccount, OAuthProvider, User
from app.routers import auth as auth_router
from app.services import oauth_service
from app.services.oauth_service import OAuthFlowError


def _set_oauth_settings() -> None:
    for target in (auth_router.settings, oauth_service.settings):
        target.oauth_google_client_id = 'google-client-id'
        target.oauth_google_client_secret = 'google-client-secret'
        target.oauth_github_client_id = 'github-client-id'
        target.oauth_github_client_secret = 'github-client-secret'
        target.oauth_redirect_base_url = 'http://localhost:3000'
        target.app_base_url = 'http://localhost:3000'


def _fake_id_token(nonce: str) -> str:
    def _enc(data: dict[str, str]) -> str:
        raw = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')

    return f'{_enc({"alg": "none", "typ": "JWT"})}.{_enc({"nonce": nonce})}.x'


@pytest.mark.asyncio
async def test_oauth_google_success(monkeypatch) -> None:
    _set_oauth_settings()
    nonce = 'nonce-google-success'

    async def fake_request_payload(method: str, url: str, **kwargs):
        if url == 'https://oauth2.googleapis.com/token':
            return {'access_token': 'google-access-token', 'id_token': _fake_id_token(nonce)}
        if url == 'https://openidconnect.googleapis.com/v1/userinfo':
            return {
                'sub': 'google-user-1',
                'email': 'google.user@example.com',
                'email_verified': True,
                'name': 'Google User',
            }
        raise AssertionError(f'Unexpected OAuth request: {method} {url}')

    monkeypatch.setattr(oauth_service, '_request_payload', fake_request_payload)

    identity = await oauth_service.exchange_code_for_identity(
        OAuthProvider.google,
        code='google-code',
        callback_uri='https://example.com/callback',
        client_id='google-client-id',
        client_secret='google-client-secret',
        expected_nonce=nonce,
    )
    assert identity.provider is OAuthProvider.google
    assert identity.provider_user_id == 'google-user-1'
    assert identity.email == 'google.user@example.com'
    assert identity.email_verified is True


@pytest.mark.asyncio
async def test_oauth_github_success(monkeypatch) -> None:
    _set_oauth_settings()

    async def fake_request_payload(method: str, url: str, **kwargs):
        if url == 'https://github.com/login/oauth/access_token':
            return {'access_token': 'github-access-token'}
        if url == 'https://api.github.com/user':
            return {'id': 4242, 'login': 'ghuser', 'name': 'GitHub User'}
        if url == 'https://api.github.com/user/emails':
            return [{'email': 'github.user@example.com', 'verified': True, 'primary': True}]
        raise AssertionError(f'Unexpected OAuth request: {method} {url}')

    monkeypatch.setattr(oauth_service, '_request_payload', fake_request_payload)

    identity = await oauth_service.exchange_code_for_identity(
        OAuthProvider.github,
        code='github-code',
        callback_uri='https://example.com/callback',
        client_id='github-client-id',
        client_secret='github-client-secret',
        expected_nonce='',
    )
    assert identity.provider is OAuthProvider.github
    assert identity.provider_user_id == '4242'
    assert identity.email == 'github.user@example.com'
    assert identity.email_verified is True


@pytest.mark.asyncio
async def test_oauth_links_existing_user_by_email() -> None:
    _set_oauth_settings()
    email = f'linked_{uuid4().hex[:10]}@example.com'
    provider_user_id = f'google-linked-{uuid4().hex[:10]}'

    async with AsyncSessionLocal() as db:
        user = User(
            email=email,
            password_hash=hash_password('secret1234'),
            name='Linked User',
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        identity = oauth_service.OAuthIdentity(
            provider=OAuthProvider.google,
            provider_user_id=provider_user_id,
            email=email,
            email_verified=True,
            name='Linked User',
        )
        linked_user = await auth_router._resolve_or_create_oauth_user(db, identity)
        await db.commit()

        assert str(linked_user.id) == str(user.id)
        linked_result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == OAuthProvider.google,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        linked_account = linked_result.scalar_one_or_none()
        assert linked_account is not None
        assert str(linked_account.user_id) == str(user.id)

        await db.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()


def test_oauth_invalid_state() -> None:
    _set_oauth_settings()
    with pytest.raises(OAuthFlowError, match='Invalid OAuth state'):
        oauth_service.validate_state(
            'broken-state',
            expected_provider=OAuthProvider.google,
            expected_redirect_base=oauth_service.frontend_auth_url(),
        )


@pytest.mark.asyncio
async def test_oauth_unverified_email_error(monkeypatch) -> None:
    _set_oauth_settings()
    nonce = 'nonce-google-unverified'

    async def fake_request_payload(method: str, url: str, **kwargs):
        if url == 'https://oauth2.googleapis.com/token':
            return {'access_token': 'google-access-token', 'id_token': _fake_id_token(nonce)}
        if url == 'https://openidconnect.googleapis.com/v1/userinfo':
            return {
                'sub': 'google-user-unverified',
                'email': 'unverified@example.com',
                'email_verified': False,
                'name': 'Unverified User',
            }
        raise AssertionError(f'Unexpected OAuth request: {method} {url}')

    monkeypatch.setattr(oauth_service, '_request_payload', fake_request_payload)

    with pytest.raises(OAuthFlowError, match='OAuth email is not verified'):
        await oauth_service.exchange_code_for_identity(
            OAuthProvider.google,
            code='google-unverified-code',
            callback_uri='https://example.com/callback',
            client_id='google-client-id',
            client_secret='google-client-secret',
            expected_nonce=nonce,
        )
