from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import httpx
import sentry_sdk

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailDeliveryError(Exception):
    pass


@dataclass(slots=True)
class EmailSendResult:
    provider: str
    message_id: str | None


def _send_via_resend(to_email: str, subject: str, body: str) -> EmailSendResult:
    timeout = settings.email_send_timeout_seconds
    if settings.resend_api_key:
        payload = {
            'from': settings.smtp_from_email,
            'to': [to_email],
            'subject': subject,
            'text': body,
        }
        headers = {
            'Authorization': f'Bearer {settings.resend_api_key}',
            'Content-Type': 'application/json',
        }
        response = httpx.post(settings.resend_api_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json() if response.content else {}
        message_id = str(data.get('id')) if isinstance(data, dict) and data.get('id') else None
        return EmailSendResult(provider='resend', message_id=message_id)

    raise RuntimeError('Resend API key is not configured')


def _send_via_smtp(to_email: str, subject: str, body: str) -> EmailSendResult:
    timeout = int(settings.email_send_timeout_seconds)

    if not settings.smtp_host:
        if settings.environment == 'production':
            raise RuntimeError('Email provider is not configured')
        logger.warning('Email provider is not configured. Email to %s with subject "%s": %s', to_email, subject, body)
        return EmailSendResult(provider='noop', message_id=None)

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = settings.smtp_from_email
    message['To'] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return EmailSendResult(provider='smtp', message_id=None)


def _send_email_sync(to_email: str, subject: str, body: str) -> EmailSendResult:
    if settings.resend_api_key:
        return _send_via_resend(to_email, subject, body)
    return _send_via_smtp(to_email, subject, body)


def _is_transient_send_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    if isinstance(exc, smtplib.SMTPServerDisconnected | smtplib.SMTPConnectError):
        return True
    if isinstance(exc, smtplib.SMTPResponseException):
        return exc.smtp_code >= 500 or exc.smtp_code == 421
    return False


async def send_email(to_email: str, subject: str, body: str) -> EmailSendResult:
    retries = max(1, settings.email_send_retries)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            result = await asyncio.to_thread(_send_email_sync, to_email, subject, body)
            extra = {'provider': result.provider, 'message_id': result.message_id}
            logger.info('Email sent to %s (%s)', to_email, json.dumps(extra, ensure_ascii=False))
            return result
        except Exception as exc:
            last_error = exc
            transient = _is_transient_send_error(exc)
            logger.warning(
                'Email send failed (attempt %s/%s, transient=%s) to %s: %s',
                attempt,
                retries,
                transient,
                to_email,
                exc,
            )
            if attempt < retries and transient:
                await asyncio.sleep(settings.email_send_retry_backoff_seconds * attempt)
                continue
            logger.exception('Email delivery permanently failed for %s', to_email)
            sentry_sdk.capture_message(f'Email delivery permanently failed for {to_email}', level='error')
            break

    raise EmailDeliveryError('Email delivery failed') from last_error


async def send_verify_email(to_email: str, token: str) -> None:
    verify_url = f'{settings.app_base_url}/auth?verify_token={token}'
    body = (
        'Подтверждение email для Social Wish List\n\n'
        f'Перейдите по ссылке для подтверждения email:\n{verify_url}\n\n'
        'Если это были не вы, просто проигнорируйте письмо.'
    )
    await send_email(to_email, 'Подтверждение email', body)


async def send_reset_password_email(to_email: str, token: str) -> None:
    reset_url = f'{settings.app_base_url}/auth?reset_token={token}'
    body = (
        'Сброс пароля для Social Wish List\n\n'
        f'Перейдите по ссылке для сброса пароля:\n{reset_url}\n\n'
        'Ссылка действует ограниченное время. Если это были не вы, проигнорируйте письмо.'
    )
    await send_email(to_email, 'Сброс пароля', body)
