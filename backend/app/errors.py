from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

_DETAIL_MAP: dict[str, str] = {
    'Captcha token required': 'Подтвердите, что вы не робот.',
    'Invalid captcha token': 'Проверка CAPTCHA не пройдена. Попробуйте еще раз.',
    'Captcha verification failed': 'Не удалось проверить CAPTCHA. Попробуйте еще раз.',
    'Not authenticated': 'Нужно войти в аккаунт.',
    'Invalid token': 'Сессия истекла. Войдите снова.',
    'User not found': 'Пользователь не найден.',
    'Wishlist not found': 'Вишлист не найден.',
    'Viewer session required': 'Сначала войдите как гость.',
    'Invalid viewer session': 'Гостевая сессия недействительна. Войдите как гость снова.',
    'Email already in use': 'Этот email уже занят.',
    'Invalid credentials': 'Неверный email или пароль.',
    'Email is not verified. Please confirm email before login.': 'Подтвердите email перед входом.',
    'Invalid or expired token': 'Ссылка недействительна или устарела.',
    'Item not found': 'Подарок не найден.',
    'Item is archived': 'Этот подарок в архиве, действие недоступно.',
    'Item already reserved': 'Подарок уже забронирован.',
    'Cannot reserve item with active contributions': 'Нельзя забронировать подарок, по нему уже есть взносы.',
    'Reservation not found': 'Бронь не найдена.',
    'Contributions are disabled': 'Сбор для этого подарка отключен.',
    'Goal amount is not set': 'Для сбора не задана целевая сумма.',
    'Goal already reached': 'Целевая сумма уже набрана.',
    'Cannot parse product page': 'Не удалось распознать страницу товара по ссылке.',
    'Invalid URL': 'Введите корректную ссылку.',
    'Set price or goal amount to enable contributions': 'Чтобы включить сбор, укажите цену или цель сбора.',
    'Wishlist deadline passed. New reservations are closed.': 'Срок вишлиста прошел. Новые брони закрыты.',
    'Wishlist deadline passed. Contributions are closed.': 'Срок вишлиста прошел. Вклады закрыты.',
}

_STATUS_DEFAULTS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: 'Проверьте введенные данные.',
    status.HTTP_401_UNAUTHORIZED: 'Нужно войти в систему.',
    status.HTTP_403_FORBIDDEN: 'Доступ запрещен.',
    status.HTTP_404_NOT_FOUND: 'Ничего не найдено.',
    status.HTTP_409_CONFLICT: 'Сейчас это действие недоступно.',
    status.HTTP_422_UNPROCESSABLE_ENTITY: 'Проверьте, как заполнены поля формы.',
    status.HTTP_429_TOO_MANY_REQUESTS: 'Слишком много попыток. Подождите немного и попробуйте снова.',
    status.HTTP_500_INTERNAL_SERVER_ERROR: 'Внутренняя ошибка сервера. Попробуйте позже.',
    status.HTTP_502_BAD_GATEWAY: 'Сервис временно недоступен. Попробуйте позже.',
}

_FIELD_MAP: dict[str, str] = {
    'body.email': 'Email',
    'body.password': 'Пароль',
    'body.new_password': 'Новый пароль',
    'body.name': 'Имя',
    'body.title': 'Название',
    'body.description': 'Описание',
    'body.display_name': 'Имя гостя',
    'body.amount': 'Сумма вклада',
    'body.token': 'Токен',
    'body.url': 'Ссылка',
    'body.event_date': 'Дата события',
    'body.captcha_token': 'CAPTCHA',
    'query.url': 'Ссылка',
    'path.share_token': 'Ссылка на вишлист',
    'path.item_id': 'Подарок',
}


def _russian_for_status(status_code: int) -> str:
    return _STATUS_DEFAULTS.get(status_code, 'Произошла ошибка. Попробуйте позже.')


def _translate_english_detail(detail: str, status_code: int) -> str:
    if detail in _DETAIL_MAP:
        return _DETAIL_MAP[detail]
    return _russian_for_status(status_code)


def _format_loc(loc: Any) -> str:
    if not isinstance(loc, (list, tuple)) or not loc:
        return ''

    normalized = '.'.join(str(x) for x in loc)
    if normalized in _FIELD_MAP:
        return _FIELD_MAP[normalized]
    if normalized.startswith('body.'):
        return 'Поле формы'
    if normalized.startswith('query.'):
        return 'Параметр запроса'
    if normalized.startswith('path.'):
        return 'Параметр ссылки'
    return ''


def _validation_message(item: dict[str, Any]) -> str:
    error_type = str(item.get('type') or '')
    ctx = item.get('ctx') if isinstance(item.get('ctx'), dict) else {}
    field_name = _format_loc(item.get('loc'))

    if error_type == 'missing':
        msg = 'обязательное поле'
    elif error_type == 'value_error.email':
        msg = 'некорректный email'
    elif error_type == 'string_too_short':
        msg = f'минимум {ctx.get("min_length", 1)} символов'
    elif error_type == 'string_too_long':
        msg = f'максимум {ctx.get("max_length", 1)} символов'
    elif error_type in {'int_parsing', 'float_parsing', 'decimal_parsing'}:
        msg = 'нужно число'
    elif error_type == 'greater_than':
        msg = f'значение должно быть больше {ctx.get("gt")}'
    elif error_type == 'greater_than_equal':
        msg = f'значение должно быть не меньше {ctx.get("ge")}'
    elif error_type == 'less_than':
        msg = f'значение должно быть меньше {ctx.get("lt")}'
    elif error_type == 'less_than_equal':
        msg = f'значение должно быть не больше {ctx.get("le")}'
    elif error_type in {'url_parsing', 'url_scheme'}:
        msg = 'некорректная ссылка'
    else:
        msg = 'некорректное значение'

    if field_name:
        return f'{field_name}: {msg}.'
    return f'{msg.capitalize()}.'


def _format_validation_errors(errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        messages.append(_validation_message(item))

    if not messages:
        return _STATUS_DEFAULTS[status.HTTP_422_UNPROCESSABLE_ENTITY]

    return ' '.join(messages[:3])


def _normalize_detail(detail: Any, status_code: int) -> str:
    if isinstance(detail, str):
        return _translate_english_detail(detail, status_code)
    if isinstance(detail, list):
        return _format_validation_errors([x for x in detail if isinstance(x, dict)])
    return _russian_for_status(status_code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(_: Request, __: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={'detail': _russian_for_status(status.HTTP_429_TOO_MANY_REQUESTS)},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={'detail': _format_validation_errors(exc.errors())},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={'detail': _normalize_detail(exc.detail, exc.status_code)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception('Unhandled server error: %s', exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'detail': _russian_for_status(status.HTTP_500_INTERNAL_SERVER_ERROR)},
        )
