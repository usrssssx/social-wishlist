from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.warning('SMTP is not configured. Email to %s with subject "%s": %s', to_email, subject, body)
        return

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = settings.smtp_from_email
    message['To'] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to_email: str, subject: str, body: str) -> None:
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, body)
    except Exception:
        logger.exception('Failed to send email to %s', to_email)


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
