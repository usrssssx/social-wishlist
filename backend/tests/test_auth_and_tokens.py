from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.auth import hash_password, verify_password
from app.db import AsyncSessionLocal
from app.models import EmailActionPurpose, EmailActionToken, User
from app.services.token_service import consume_email_action_token, issue_email_action_token


@pytest.mark.asyncio
async def test_email_token_lifecycle() -> None:
    email = f'token_{uuid.uuid4().hex[:10]}@example.com'

    async with AsyncSessionLocal() as db:
        user = User(email=email, password_hash='hash', name='Token User', email_verified=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        raw_token = await issue_email_action_token(db, user, EmailActionPurpose.verify_email, ttl_minutes=10)
        assert raw_token
        await db.commit()

        token = await consume_email_action_token(db, raw_token, EmailActionPurpose.verify_email)
        assert token is not None
        assert token.user_id == user.id
        await db.commit()

        consumed_again = await consume_email_action_token(db, raw_token, EmailActionPurpose.verify_email)
        assert consumed_again is None

        await db.execute(delete(EmailActionToken).where(EmailActionToken.user_id == user.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()
def test_password_hash_roundtrip() -> None:
    password = 'secret1234'
    digest = hash_password(password)
    assert digest != password
    assert verify_password(password, digest) is True
    assert verify_password('wrong-password', digest) is False
