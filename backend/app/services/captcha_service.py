from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, status

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_captcha_or_skip(token: str | None, remote_ip: str | None) -> None:
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
