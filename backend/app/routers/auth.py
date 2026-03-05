from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, hash_password, verify_password
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..models import EmailActionPurpose, User
from ..rate_limit import limiter
from ..schemas import (
    AuthResponse,
    EmailActionConfirmRequest,
    EmailActionRequest,
    GenericMessageResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from ..services.email_service import send_reset_password_email, send_verify_email
from ..services.captcha_service import verify_captcha_or_skip
from ..services.token_service import consume_email_action_token, issue_email_action_token

router = APIRouter(prefix='/api/auth', tags=['auth'])
settings = get_settings()


@router.post('/register', response_model=RegisterResponse)
@limiter.limit('5/minute')
async def register(
    request: Request,
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    await verify_captcha_or_skip(payload.captcha_token, request.client.host if request.client else None)
    existing_result = await db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Email already in use')

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    token = await issue_email_action_token(
        db,
        user,
        EmailActionPurpose.verify_email,
        settings.verify_email_token_ttl_minutes,
    )
    await db.commit()

    await send_verify_email(user.email, token)
    return RegisterResponse(detail='Registration successful. Check your email to verify your account.')


@router.post('/login', response_model=AuthResponse)
@limiter.limit('10/minute')
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    await verify_captcha_or_skip(payload.captcha_token, request.client.host if request.client else None)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Email is not verified. Please confirm email before login.',
        )

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post('/resend-verification', response_model=GenericMessageResponse)
@limiter.limit('5/minute')
async def resend_verification(
    request: Request,
    payload: EmailActionRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    await verify_captcha_or_skip(payload.captcha_token, request.client.host if request.client else None)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user and not user.email_verified:
        token = await issue_email_action_token(
            db,
            user,
            EmailActionPurpose.verify_email,
            settings.verify_email_token_ttl_minutes,
        )
        await db.commit()
        await send_verify_email(user.email, token)

    return GenericMessageResponse(detail='If this email exists, verification instructions were sent.')


@router.post('/verify-email/confirm', response_model=GenericMessageResponse)
@limiter.limit('10/minute')
async def verify_email_confirm(
    request: Request,
    payload: EmailActionConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    _ = request
    token = await consume_email_action_token(db, payload.token, EmailActionPurpose.verify_email)
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired token')

    result = await db.execute(select(User).where(User.id == token.user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    user.email_verified = True
    await db.commit()
    return GenericMessageResponse(detail='Email verified successfully. You can now sign in.')


@router.post('/password-reset/request', response_model=GenericMessageResponse)
@limiter.limit('5/minute')
async def password_reset_request(
    request: Request,
    payload: EmailActionRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    await verify_captcha_or_skip(payload.captcha_token, request.client.host if request.client else None)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user:
        token = await issue_email_action_token(
            db,
            user,
            EmailActionPurpose.reset_password,
            settings.reset_password_token_ttl_minutes,
        )
        await db.commit()
        await send_reset_password_email(user.email, token)

    return GenericMessageResponse(detail='If this email exists, reset instructions were sent.')


@router.post('/password-reset/confirm', response_model=GenericMessageResponse)
@limiter.limit('10/minute')
async def password_reset_confirm(
    request: Request,
    payload: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> GenericMessageResponse:
    _ = request
    token = await consume_email_action_token(db, payload.token, EmailActionPurpose.reset_password)
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired token')

    result = await db.execute(select(User).where(User.id == token.user_id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return GenericMessageResponse(detail='Password updated successfully.')


@router.get('/me', response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
