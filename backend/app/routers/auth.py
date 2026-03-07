import logging
import re
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, hash_password, verify_password
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..models import EmailActionPurpose, OAuthAccount, User
from ..rate_limit import limiter
from ..schemas import (
    AuthResponse,
    DeleteAccountRequest,
    EmailActionConfirmRequest,
    EmailActionRequest,
    GenericMessageResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from ..services.email_service import EmailDeliveryError, send_reset_password_email, send_verify_email
from ..services.captcha_service import verify_captcha_or_skip
from ..services.oauth_service import (
    OAuthFlowError,
    OAuthIdentity,
    authorize_url,
    callback_redirect_uri,
    exchange_code_for_identity,
    frontend_auth_url,
    issue_state,
    normalize_provider,
    provider_credentials,
    validate_state,
)
from ..services.token_service import consume_email_action_token, issue_email_action_token

router = APIRouter(prefix='/api/auth', tags=['auth'])
settings = get_settings()
logger = logging.getLogger(__name__)

_OAUTH_ERROR_MAP = {
    'Unsupported OAuth provider': 'Неподдерживаемый OAuth-провайдер.',
    'OAuth provider is not configured': 'OAuth-провайдер не настроен.',
    'OAuth callback code is missing': 'OAuth не вернул код авторизации.',
    'Invalid OAuth state': 'Сессия OAuth недействительна. Повторите вход.',
    'OAuth provider request failed': 'Не удалось связаться с OAuth-провайдером. Попробуйте позже.',
    'OAuth provider response is invalid': 'OAuth-провайдер вернул некорректный ответ.',
    'OAuth email is missing': 'OAuth-провайдер не передал email.',
    'OAuth email is not verified': 'Email у OAuth-провайдера не подтвержден.',
    'OAuth callback failed': 'OAuth-вход временно недоступен. Попробуйте позже.',
}


def _oauth_error_to_ru(message: str) -> str:
    normalized = message.strip()
    if normalized in _OAUTH_ERROR_MAP:
        return _OAUTH_ERROR_MAP[normalized]
    if re.search(r'[А-Яа-яЁё]', normalized):
        return normalized
    return 'OAuth-вход временно недоступен. Попробуйте позже.'


def _oauth_redirect(*, token: str | None = None, error: str | None = None) -> RedirectResponse:
    target = frontend_auth_url()
    fragment_parts: list[str] = []
    if token:
        fragment_parts.append(f'oauth_token={quote(token, safe="")}')
    if error:
        fragment_parts.append(f'oauth_error={quote(_oauth_error_to_ru(error), safe="")}')
    fragment = '&'.join(fragment_parts)
    final_url = f'{target}#{fragment}' if fragment else target
    return RedirectResponse(url=final_url, status_code=status.HTTP_303_SEE_OTHER)


async def _resolve_or_create_oauth_user(db: AsyncSession, identity: OAuthIdentity) -> User:
    linked_result = await db.execute(
        select(OAuthAccount, User)
        .join(User, OAuthAccount.user_id == User.id)
        .where(
            OAuthAccount.provider == identity.provider,
            OAuthAccount.provider_user_id == identity.provider_user_id,
        )
        .with_for_update()
    )
    linked = linked_result.first()
    if linked:
        oauth_account, user = linked
        if oauth_account.email != identity.email:
            oauth_account.email = identity.email
        if identity.email_verified and not user.email_verified:
            user.email_verified = True
        return user

    existing_user_result = await db.execute(
        select(User).where(func.lower(User.email) == identity.email.lower()).with_for_update()
    )
    user = existing_user_result.scalar_one_or_none()
    if not user:
        user = User(
            email=identity.email.lower(),
            password_hash=hash_password(secrets.token_urlsafe(32)),
            name=identity.name.strip()[:120] or identity.email.split('@', 1)[0],
            email_verified=identity.email_verified,
        )
        db.add(user)
        await db.flush()
    elif identity.email_verified and not user.email_verified:
        user.email_verified = True

    oauth_account = OAuthAccount(
        user_id=user.id,
        provider=identity.provider,
        provider_user_id=identity.provider_user_id,
        email=identity.email.lower(),
    )
    db.add(oauth_account)
    return user


@router.get('/oauth/{provider}/start')
@limiter.limit('20/minute')
async def oauth_start(
    request: Request,
    provider: str,
) -> RedirectResponse:
    oauth_provider = normalize_provider(provider)
    client_id, _ = provider_credentials(oauth_provider)
    callback_uri = callback_redirect_uri(request, oauth_provider)
    redirect_target = frontend_auth_url()
    state, nonce = issue_state(oauth_provider, redirect_target)
    url = authorize_url(
        oauth_provider,
        client_id=client_id,
        callback_uri=callback_uri,
        state=state,
        nonce=nonce,
    )
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get('/oauth/{provider}/callback', name='oauth_callback')
@limiter.limit('20/minute')
async def oauth_callback(
    request: Request,
    provider: str,
    code: str | None = None,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    identity: OAuthIdentity | None = None
    try:
        oauth_provider = normalize_provider(provider)
    except HTTPException as exc:
        return _oauth_redirect(error=str(exc.detail))

    if not code:
        return _oauth_redirect(error='OAuth callback code is missing')
    if not state:
        return _oauth_redirect(error='Invalid OAuth state')

    try:
        client_id, client_secret = provider_credentials(oauth_provider)
        callback_uri = callback_redirect_uri(request, oauth_provider)
        redirect_target = frontend_auth_url()
        state_data = validate_state(
            state,
            expected_provider=oauth_provider,
            expected_redirect_base=redirect_target,
        )
        identity = await exchange_code_for_identity(
            oauth_provider,
            code=code,
            callback_uri=callback_uri,
            client_id=client_id,
            client_secret=client_secret,
            expected_nonce=state_data.nonce,
        )
        user = await _resolve_or_create_oauth_user(db, identity)
        await db.commit()
        access_token = create_access_token(user.id)
        return _oauth_redirect(token=access_token)
    except OAuthFlowError as exc:
        await db.rollback()
        return _oauth_redirect(error=str(exc))
    except IntegrityError:
        await db.rollback()
        try:
            if not identity:
                raise RuntimeError('OAuth identity is missing after integrity conflict')
            linked_result = await db.execute(
                select(User)
                .join(OAuthAccount, OAuthAccount.user_id == User.id)
                .where(
                    OAuthAccount.provider == identity.provider,
                    OAuthAccount.provider_user_id == identity.provider_user_id,
                )
            )
            user = linked_result.scalar_one_or_none()
            if not user:
                raise RuntimeError('OAuth linked user not found after integrity conflict')
            await db.commit()
            return _oauth_redirect(token=create_access_token(user.id))
        except Exception:
            await db.rollback()
            logger.exception('OAuth callback integrity conflict')
            return _oauth_redirect(error='OAuth callback failed')
    except HTTPException as exc:
        await db.rollback()
        return _oauth_redirect(error=str(exc.detail))
    except Exception:
        await db.rollback()
        logger.exception('Unexpected OAuth callback error')
        return _oauth_redirect(error='OAuth callback failed')


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
    try:
        await send_verify_email(user.email, token)
    except EmailDeliveryError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Failed to send verification email',
        ) from exc
    await db.commit()
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
        try:
            await send_verify_email(user.email, token)
        except EmailDeliveryError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Failed to send verification email',
            ) from exc
        await db.commit()

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
        try:
            await send_reset_password_email(user.email, token)
        except EmailDeliveryError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Failed to send password reset email',
            ) from exc
        await db.commit()

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


@router.delete('/me', response_model=GenericMessageResponse)
@limiter.limit('3/minute')
async def delete_me(
    request: Request,
    payload: DeleteAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenericMessageResponse:
    _ = request
    if payload.confirm_phrase.strip().upper() != 'DELETE':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Account deletion confirmation phrase mismatch',
        )

    result = await db.execute(select(User).where(User.id == current_user.id).with_for_update())
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')

    await db.delete(user)
    await db.commit()
    return GenericMessageResponse(detail='Аккаунт и персональные данные удалены.')
