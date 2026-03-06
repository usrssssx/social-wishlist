from __future__ import annotations

import asyncio
import html
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


def _render_action_email_html(
    *,
    preheader: str,
    title: str,
    intro: str,
    action_label: str,
    action_url: str,
    footer_note: str,
) -> str:
    preheader_safe = html.escape(preheader)
    title_safe = html.escape(title)
    intro_safe = html.escape(intro)
    action_label_safe = html.escape(action_label)
    action_url_safe = html.escape(action_url, quote=True)
    footer_note_safe = html.escape(footer_note)
    app_name_safe = html.escape(settings.app_name)

    return f"""\
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_safe}</title>
  </head>
  <body style="margin:0;padding:0;background:#f4f7fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader_safe}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f4f7fb;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 14px 40px rgba(15,23,42,0.10);">
            <tr>
              <td style="padding:28px 28px 22px;background:linear-gradient(135deg,#0f172a,#1d4ed8);">
                <div style="font-size:13px;line-height:18px;color:rgba(255,255,255,0.85);letter-spacing:0.35px;text-transform:uppercase;">{app_name_safe}</div>
                <h1 style="margin:10px 0 0;font-size:30px;line-height:36px;color:#ffffff;font-weight:800;">{title_safe}</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <p style="margin:0 0 18px;font-size:16px;line-height:26px;color:#334155;">{intro_safe}</p>
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="border-radius:12px;background:#2563eb;">
                      <a href="{action_url_safe}" style="display:inline-block;padding:14px 22px;font-size:16px;font-weight:700;line-height:20px;color:#ffffff;text-decoration:none;">{action_label_safe}</a>
                    </td>
                  </tr>
                </table>
                <p style="margin:20px 0 0;font-size:14px;line-height:22px;color:#64748b;">Если кнопка не работает, откройте ссылку:<br><a href="{action_url_safe}" style="color:#1d4ed8;text-decoration:none;word-break:break-all;">{action_url_safe}</a></p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 28px 28px;">
                <div style="padding:14px 16px;border-radius:12px;background:#f8fafc;border:1px solid #e2e8f0;font-size:13px;line-height:20px;color:#475569;">{footer_note_safe}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _send_via_resend(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> EmailSendResult:
    timeout = settings.email_send_timeout_seconds
    if settings.resend_api_key:
        payload = {
            'from': settings.smtp_from_email,
            'to': [to_email],
            'subject': subject,
            'text': text_body,
        }
        if html_body:
            payload['html'] = html_body
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


def _send_via_smtp(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> EmailSendResult:
    timeout = int(settings.email_send_timeout_seconds)

    if not settings.smtp_host:
        if settings.environment == 'production':
            raise RuntimeError('Email provider is not configured')
        logger.warning(
            'Email provider is not configured. Email to %s with subject "%s": %s',
            to_email,
            subject,
            text_body,
        )
        return EmailSendResult(provider='noop', message_id=None)

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = settings.smtp_from_email
    message['To'] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype='html')

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return EmailSendResult(provider='smtp', message_id=None)


def _send_email_sync(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> EmailSendResult:
    if settings.resend_api_key:
        return _send_via_resend(to_email, subject, text_body, html_body)
    return _send_via_smtp(to_email, subject, text_body, html_body)


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


async def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> EmailSendResult:
    retries = max(1, settings.email_send_retries)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            result = await asyncio.to_thread(_send_email_sync, to_email, subject, text_body, html_body)
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
    text_body = (
        'Подтверждение email для Social Wish List\n\n'
        f'Перейдите по ссылке для подтверждения email:\n{verify_url}\n\n'
        'Ссылка действует 24 часа.\n\n'
        'Если это были не вы, просто проигнорируйте письмо.'
    )
    html_body = _render_action_email_html(
        preheader='Подтвердите email и завершите регистрацию в Social Wish List',
        title='Подтверждение email',
        intro='Нажмите кнопку ниже, чтобы подтвердить email и завершить регистрацию.',
        action_label='Подтвердить email',
        action_url=verify_url,
        footer_note='Ссылка действует 24 часа. Если это были не вы, просто проигнорируйте письмо.',
    )
    await send_email(to_email, 'Подтверждение email', text_body, html_body)


async def send_reset_password_email(to_email: str, token: str) -> None:
    reset_url = f'{settings.app_base_url}/auth?reset_token={token}'
    text_body = (
        'Сброс пароля для Social Wish List\n\n'
        f'Перейдите по ссылке для сброса пароля:\n{reset_url}\n\n'
        'Ссылка действует ограниченное время. Если это были не вы, проигнорируйте письмо.'
    )
    html_body = _render_action_email_html(
        preheader='Запрос на сброс пароля в Social Wish List',
        title='Сброс пароля',
        intro='Мы получили запрос на смену пароля. Нажмите кнопку ниже, чтобы задать новый пароль.',
        action_label='Сбросить пароль',
        action_url=reset_url,
        footer_note='Если вы не запрашивали сброс пароля, ничего делать не нужно.',
    )
    await send_email(to_email, 'Сброс пароля', text_body, html_body)
