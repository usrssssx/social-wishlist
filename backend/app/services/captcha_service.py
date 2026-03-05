from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, status

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _is_turnstile_test_secret(secret: str | None) -> bool:
    if not secret:
        return False
    # Cloudflare published testing secret key
    return secret.strip() == '1x0000000000000000000000000000000AA'


async def verify_captcha_or_skip(token: str | None, remote_ip: str | None) -> None:
    if settings.environment == 'production':
        if not settings.captcha_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Captcha is not configured for production',
            )
        if _is_turnstile_test_secret(settings.captcha_secret_key) and not settings.allow_test_captcha_in_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Test captcha key is not allowed in production',
            )

    if not settings.captcha_secret_key:
        return

    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Captcha token required')

    payload = {
        'secret': settings.captcha_secret_key,
        'response': token,
    }
    if remote_ip:
        payload['remoteip'] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(settings.captcha_verify_url, data=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception('Captcha verification request failed')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Captcha verification failed')

    if not data.get('success'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid captcha token')

    expected_hostname = settings.captcha_expected_hostname
    if expected_hostname:
        token_hostname = str(data.get('hostname') or '').strip().lower()
        if token_hostname and token_hostname != expected_hostname.strip().lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Captcha hostname mismatch')
