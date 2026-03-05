from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import EmailActionPurpose, EmailActionToken, User


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


async def issue_email_action_token(
    db: AsyncSession,
    user: User,
    purpose: EmailActionPurpose,
    ttl_minutes: int,
) -> str:
    now = datetime.now(timezone.utc)
    raw_token = generate_raw_token()
    token_hash = hash_token(raw_token)

    existing_result = await db.execute(
        select(EmailActionToken).where(
            and_(
                EmailActionToken.user_id == user.id,
                EmailActionToken.purpose == purpose,
                EmailActionToken.used_at.is_(None),
            )
        )
    )
    existing_tokens = existing_result.scalars().all()
    for token in existing_tokens:
        token.used_at = now

    new_token = EmailActionToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    db.add(new_token)
    return raw_token


async def consume_email_action_token(
    db: AsyncSession,
    raw_token: str,
    purpose: EmailActionPurpose,
) -> EmailActionToken | None:
    now = datetime.now(timezone.utc)
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(EmailActionToken)
        .where(
            and_(
                EmailActionToken.token_hash == token_hash,
                EmailActionToken.purpose == purpose,
                EmailActionToken.used_at.is_(None),
                EmailActionToken.expires_at > now,
            )
        )
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if not token:
        return None

    token.used_at = now
    return token
