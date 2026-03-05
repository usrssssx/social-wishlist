from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix='/api/webhooks', tags=['webhooks'])


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(' ', 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != 'bearer':
        return None
    return parts[1].strip() or None


def _compact_recipient(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            return first
    return None


@router.post('/resend')
async def resend_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    if not settings.resend_webhook_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Webhook is not configured')

    token = _extract_bearer_token(authorization)
    if token != settings.resend_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Webhook signature is invalid')

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid webhook payload') from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid webhook payload')

    event_type = str(payload.get('type') or 'unknown')
    data = payload.get('data')
    data_dict = data if isinstance(data, dict) else {}
    email_id = str(data_dict.get('email_id') or data_dict.get('id') or '')
    recipient = _compact_recipient(data_dict.get('to'))

    if event_type in {'email.bounced', 'email.complained'}:
        logger.warning(
            'Resend webhook alert type=%s email_id=%s to=%s',
            event_type,
            email_id or '-',
            recipient or '-',
        )
    else:
        logger.info(
            'Resend webhook event type=%s email_id=%s to=%s',
            event_type,
            email_id or '-',
            recipient or '-',
        )

    return {'ok': True}
