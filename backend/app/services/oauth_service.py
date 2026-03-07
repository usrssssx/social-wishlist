from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from ..config import get_settings
from ..models import OAuthProvider

settings = get_settings()


class OAuthFlowError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OAuthState:
    provider: OAuthProvider
    nonce: str
    redirect_base: str


@dataclass(frozen=True, slots=True)
class OAuthIdentity:
    provider: OAuthProvider
    provider_user_id: str
    email: str
    email_verified: bool
    name: str


def normalize_provider(provider_raw: str) -> OAuthProvider:
    try:
        return OAuthProvider(provider_raw.lower())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported OAuth provider') from exc


def provider_credentials(provider: OAuthProvider) -> tuple[str, str]:
    if provider is OAuthProvider.google:
        client_id = (settings.oauth_google_client_id or '').strip()
        client_secret = (settings.oauth_google_client_secret or '').strip()
    else:
        client_id = (settings.oauth_github_client_id or '').strip()
        client_secret = (settings.oauth_github_client_secret or '').strip()

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='OAuth provider is not configured',
        )
    return client_id, client_secret


def frontend_auth_url() -> str:
    base = (settings.oauth_redirect_base_url or settings.app_base_url or '').strip().rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='OAuth redirect base URL is invalid',
        )
    return f'{base}/auth'


def callback_redirect_uri(request: Request, provider: OAuthProvider) -> str:
    callback_uri = str(request.url_for('oauth_callback', provider=provider.value))
    parsed = urlparse(callback_uri)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='OAuth callback URL is invalid',
        )
    return callback_uri


def issue_state(provider: OAuthProvider, redirect_base: str) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.oauth_state_ttl_seconds)
    payload = {
        'sub': 'oauth_state',
        'provider': provider.value,
        'nonce': nonce,
        'redirect_base': redirect_base,
        'exp': int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, nonce


def validate_state(
    state_token: str,
    *,
    expected_provider: OAuthProvider,
    expected_redirect_base: str,
) -> OAuthState:
    try:
        payload = jwt.decode(state_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise OAuthFlowError('Invalid OAuth state') from exc

    if payload.get('sub') != 'oauth_state':
        raise OAuthFlowError('Invalid OAuth state')
    if payload.get('provider') != expected_provider.value:
        raise OAuthFlowError('Invalid OAuth state')
    if payload.get('redirect_base') != expected_redirect_base:
        raise OAuthFlowError('Invalid OAuth state')

    nonce = str(payload.get('nonce') or '').strip()
    if len(nonce) < 20:
        raise OAuthFlowError('Invalid OAuth state')

    return OAuthState(provider=expected_provider, nonce=nonce, redirect_base=expected_redirect_base)


def authorize_url(
    provider: OAuthProvider,
    *,
    client_id: str,
    callback_uri: str,
    state: str,
    nonce: str,
) -> str:
    if provider is OAuthProvider.google:
        query = urlencode(
            {
                'client_id': client_id,
                'redirect_uri': callback_uri,
                'response_type': 'code',
                'scope': 'openid email profile',
                'state': state,
                'nonce': nonce,
                'prompt': 'select_account',
            }
        )
        return f'https://accounts.google.com/o/oauth2/v2/auth?{query}'

    query = urlencode(
        {
            'client_id': client_id,
            'redirect_uri': callback_uri,
            'scope': 'read:user user:email',
            'state': state,
        }
    )
    return f'https://github.com/login/oauth/authorize?{query}'


def _decode_unverified_jwt_payload(token: str) -> dict[str, object]:
    parts = token.split('.')
    if len(parts) < 2:
        return {}
    payload_part = parts[1]
    padding = '=' * (-len(payload_part) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_part + padding)
        data = json.loads(raw.decode('utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _request_payload(
    method: str,
    url: str,
    *,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    timeout = settings.email_send_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, data=data, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OAuthFlowError('OAuth provider request failed') from exc
    except httpx.HTTPError as exc:
        raise OAuthFlowError('OAuth provider request failed') from exc

    try:
        payload = response.json()
    except Exception as exc:
        raise OAuthFlowError('OAuth provider response is invalid') from exc

    return payload


def _normalize_name(raw_name: str | None, fallback_email: str) -> str:
    candidate = (raw_name or '').strip()
    if candidate:
        return candidate[:120]
    return fallback_email.split('@', 1)[0][:120] or 'User'


async def _exchange_google(
    code: str,
    *,
    callback_uri: str,
    client_id: str,
    client_secret: str,
    expected_nonce: str,
) -> OAuthIdentity:
    token_raw = await _request_payload(
        'POST',
        'https://oauth2.googleapis.com/token',
        data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': callback_uri,
            'grant_type': 'authorization_code',
        },
        headers={'Accept': 'application/json'},
    )
    if not isinstance(token_raw, dict):
        raise OAuthFlowError('OAuth provider response is invalid')
    access_token = str(token_raw.get('access_token') or '').strip()
    id_token = str(token_raw.get('id_token') or '').strip()
    if not access_token:
        raise OAuthFlowError('OAuth provider response is invalid')

    if expected_nonce:
        claims = _decode_unverified_jwt_payload(id_token)
        if str(claims.get('nonce') or '') != expected_nonce:
            raise OAuthFlowError('Invalid OAuth state')

    profile_raw = await _request_payload(
        'GET',
        'https://openidconnect.googleapis.com/v1/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
    )
    if not isinstance(profile_raw, dict):
        raise OAuthFlowError('OAuth provider response is invalid')
    profile = profile_raw

    email = str(profile.get('email') or '').strip().lower()
    if not email:
        raise OAuthFlowError('OAuth email is missing')
    if not bool(profile.get('email_verified')):
        raise OAuthFlowError('OAuth email is not verified')

    provider_user_id = str(profile.get('sub') or '').strip()
    if not provider_user_id:
        raise OAuthFlowError('OAuth provider response is invalid')

    name = _normalize_name(str(profile.get('name') or '').strip(), email)
    return OAuthIdentity(
        provider=OAuthProvider.google,
        provider_user_id=provider_user_id,
        email=email,
        email_verified=True,
        name=name,
    )


async def _exchange_github(
    code: str,
    *,
    callback_uri: str,
    client_id: str,
    client_secret: str,
) -> OAuthIdentity:
    token_raw = await _request_payload(
        'POST',
        'https://github.com/login/oauth/access_token',
        data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': callback_uri,
        },
        headers={'Accept': 'application/json'},
    )
    if not isinstance(token_raw, dict):
        raise OAuthFlowError('OAuth provider response is invalid')
    access_token = str(token_raw.get('access_token') or '').strip()
    if not access_token:
        raise OAuthFlowError('OAuth provider response is invalid')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    profile_raw = await _request_payload('GET', 'https://api.github.com/user', headers=headers)
    if not isinstance(profile_raw, dict):
        raise OAuthFlowError('OAuth provider response is invalid')
    profile = profile_raw
    provider_user_id = str(profile.get('id') or '').strip()
    if not provider_user_id:
        raise OAuthFlowError('OAuth provider response is invalid')

    emails_payload = await _request_payload('GET', 'https://api.github.com/user/emails', headers=headers)
    if isinstance(emails_payload, list):
        emails_raw = emails_payload
    elif isinstance(emails_payload, dict):
        emails_raw = emails_payload.get('items') if isinstance(emails_payload.get('items'), list) else None
        if emails_raw is None:
            maybe_list = emails_payload.get('emails')
            emails_raw = maybe_list if isinstance(maybe_list, list) else None
    else:
        emails_raw = None

    if not isinstance(emails_raw, list):
        raise OAuthFlowError('OAuth provider response is invalid')

    verified_primary: str | None = None
    verified_any: str | None = None
    for item in emails_raw:
        if not isinstance(item, dict):
            continue
        email = str(item.get('email') or '').strip().lower()
        if not email:
            continue
        if bool(item.get('verified')) and bool(item.get('primary')):
            verified_primary = email
            break
        if bool(item.get('verified')) and not verified_any:
            verified_any = email

    email = verified_primary or verified_any
    if not email:
        raise OAuthFlowError('OAuth email is not verified')

    name = _normalize_name(str(profile.get('name') or profile.get('login') or '').strip(), email)
    return OAuthIdentity(
        provider=OAuthProvider.github,
        provider_user_id=provider_user_id,
        email=email,
        email_verified=True,
        name=name,
    )


async def exchange_code_for_identity(
    provider: OAuthProvider,
    *,
    code: str,
    callback_uri: str,
    client_id: str,
    client_secret: str,
    expected_nonce: str,
) -> OAuthIdentity:
    if provider is OAuthProvider.google:
        return await _exchange_google(
            code,
            callback_uri=callback_uri,
            client_id=client_id,
            client_secret=client_secret,
            expected_nonce=expected_nonce,
        )
    return await _exchange_github(
        code,
        callback_uri=callback_uri,
        client_id=client_id,
        client_secret=client_secret,
    )
