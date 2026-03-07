# Social Wish List

Social Wish List - MVP веб-приложения для личных и совместных подарочных списков.

Что уже реализовано:
- владелец создает wishlist и товары;
- делится публичной ссылкой без регистрации гостей;
- гости могут резервировать подарок или вносить вклад в общий сбор;
- владелец видит только агрегаты, без раскрытия персональных данных гостей;
- статус обновляется в реальном времени через WebSocket;
- регистрация и восстановление пароля работают через email (verify/reset);
- удаление аккаунта вынесено в раздел `Настройки аккаунта` (Danger Zone).

## Стек

- Frontend: Next.js 15, React 19, TypeScript
- Backend: FastAPI, SQLAlchemy async, Alembic
- База данных: PostgreSQL
- Realtime: WebSocket hub, Redis pub/sub для multi-instance
- Auth: JWT, verify email, reset password
- OAuth: Google/GitHub вход (опционально)
- Anti-abuse: SlowAPI rate limit, Cloudflare Turnstile
- Email: Resend API (приоритет), fallback SMTP
- Monitoring: Sentry (опционально), health/readiness endpoints

## Архитектура

- `frontend` работает с backend по REST API (`/api/...`) и WebSocket (`/ws/w/{share_token}`).
- `backend` хранит состояние в PostgreSQL и рассылает realtime-события.
- При нескольких инстансах backend синхронизирует realtime через Redis channel (`REALTIME_REDIS_CHANNEL`).
- Письма verify/reset отправляются через Resend или SMTP и имеют HTML + text версии.

## Структура репозитория

- `backend/` - FastAPI, миграции, тесты.
- `frontend/` - Next.js приложение.
- `scripts/` - smoke, backup/restore, on-call уведомления.
- `docs/` - runbook, alerts, backup/restore, production smoke checklist.
- `.github/workflows/` - CI, post-deploy smoke, scheduled backup/restore, healthcheck.
- `render.yaml` - Blueprint для Render (frontend + backend + postgres).

## Продуктовые решения

- Публичный просмотр wishlist доступен без логина.
- Для действий гостя используется легкая guest-сессия (`display_name` + `session_token`).
- Минимальный вклад: `MIN_CONTRIBUTION_AMOUNT` (по умолчанию `100`).
- Полная бронь запрещена, если по позиции уже есть вклады.
- При удалении позиции с активностями она переводится в архив (`archived`) для сохранения контекста.
- После даты события блокируются новые брони и вклады.
- При недосборе к дедлайну позиция получает статус `underfunded`.
- Есть страницы `Условия` и `Политика конфиденциальности`.
- Удаление аккаунта требует пароль и фразу подтверждения `DELETE`.

## Edge-кейсы, которые покрыты

- блокируется двойная бронь одного подарка;
- вклад выше остатка до цели отклоняется;
- вклад/бронь архивного товара отклоняются;
- параллельная гонка на бронь пропускает только один успешный запрос;
- невалидная/просроченная guest-сессия отклоняется;
- невалидный URL автозаполнения возвращает управляемую ошибку API.

## Локальный запуск

### Требования

- Python `3.12` (рекомендовано для совместимости зависимостей)
- Node.js `22`
- PostgreSQL `16+`

### 1) PostgreSQL

Нужен Postgres на `localhost:5432`.

```sql
CREATE ROLE wishlist LOGIN PASSWORD 'wishlist';
CREATE DATABASE wishlist OWNER wishlist;
```

### 2) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Если таблицы были созданы до Alembic:

```bash
cd backend
alembic stamp 20260305_0001
alembic upgrade head
```

### 3) Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Открыть `http://localhost:3000`.

## Docker

```bash
docker compose up -d --build
```

Backend контейнер на старте выполняет `alembic upgrade head`.

## API эндпоинты (основные)

Auth:
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/resend-verification`
- `POST /api/auth/verify-email/confirm`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `GET /api/auth/oauth/{provider}/start`
- `GET /api/auth/oauth/{provider}/callback`
- `GET /api/auth/me`
- `DELETE /api/auth/me`

Owner:
- `POST /api/wishlists`
- `GET /api/wishlists`
- `GET /api/wishlists/{wishlist_id}`
- `POST /api/wishlists/{wishlist_id}/items`
- `PATCH /api/wishlists/items/{item_id}`
- `DELETE /api/wishlists/items/{item_id}`
- `GET /api/wishlists/items/autofill`

Public:
- `GET /api/public/w/{share_token}`
- `POST /api/public/w/{share_token}/sessions`
- `POST /api/public/w/{share_token}/items/{item_id}/reserve`
- `DELETE /api/public/w/{share_token}/items/{item_id}/reserve`
- `POST /api/public/w/{share_token}/items/{item_id}/contributions`

Webhooks:
- `POST /api/webhooks/resend`

Health/ops:
- `GET /health`
- `GET /health/readiness`
- `GET /health/metrics`
- `POST /health/alerts/test`

## Переменные окружения

Полные примеры:
- `backend/.env.example`
- `frontend/.env.example`

Ключевые переменные backend для production:

| Переменная | Обязательно | Назначение |
| --- | --- | --- |
| `DATABASE_URL` | Да | Подключение к PostgreSQL |
| `JWT_SECRET` | Да | Подпись JWT |
| `CORS_ORIGINS` | Да | Origin фронтенда |
| `APP_BASE_URL` | Да | База ссылок в email verify/reset |
| `ENVIRONMENT=production` | Да | Режим production |
| `CAPTCHA_SECRET_KEY` | Да | Secret Turnstile |
| `CAPTCHA_EXPECTED_HOSTNAME` | Да | Хост фронтенда без `https://` |
| `RESEND_API_KEY` или `SMTP_HOST` | Да | Провайдер отправки email |
| `RESEND_WEBHOOK_SECRET` | Да при Resend | Валидация webhook `/api/webhooks/resend` |
| `OAUTH_GOOGLE_CLIENT_ID` | Нет (если нужен Google OAuth) | OAuth client id Google |
| `OAUTH_GOOGLE_CLIENT_SECRET` | Нет (если нужен Google OAuth) | OAuth client secret Google |
| `OAUTH_GITHUB_CLIENT_ID` | Нет (если нужен GitHub OAuth) | OAuth client id GitHub |
| `OAUTH_GITHUB_CLIENT_SECRET` | Нет (если нужен GitHub OAuth) | OAuth client secret GitHub |
| `OAUTH_REDIRECT_BASE_URL` | Нет (рекомендовано для OAuth) | URL фронтенда для возврата после OAuth |
| `REDIS_URL` | Нет (рекомендовано) | Realtime в multi-instance |
| `SENTRY_DSN` | Нет (рекомендовано) | Ошибки и алерты |
| `ALERTS_TEST_TOKEN` | Нет (рекомендовано) | Защита `POST /health/alerts/test` |

Ключевые переменные frontend:

| Переменная | Обязательно | Назначение |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | Да | Базовый URL backend |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Да при включенной CAPTCHA | Site key Turnstile |

## Readiness и health

- `/health` показывает доступность БД, счетчики ошибок, итоговый статус.
- `/health/readiness` возвращает детальные флаги готовности.
- Важно: `ready=true` зависит от `captcha_ok` и `email_ok`.
- `alerts_ok` и `realtime_ok` в readiness сейчас носят advisory-характер и не блокируют `ready`.

## OAuth (Google/GitHub)

Как включить:

1. В backend задайте `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET` для Google OAuth.
2. В backend задайте `OAUTH_GITHUB_CLIENT_ID`, `OAUTH_GITHUB_CLIENT_SECRET` для GitHub OAuth.
3. В backend задайте `OAUTH_REDIRECT_BASE_URL=<frontend-url>` (например `https://swl-frontend.onrender.com`).
4. Проверьте, что в frontend выставлен `NEXT_PUBLIC_API_URL=<backend-url>`.

Redirect URI у провайдеров:

- Google: `https://<backend>/api/auth/oauth/google/callback`
- GitHub: `https://<backend>/api/auth/oauth/github/callback`

Проверка:

1. Откройте `/auth`.
2. Нажмите “Войти через Google” или “Войти через GitHub”.
3. После callback пользователь должен попасть в `/dashboard` с активной JWT-сессией.

## Деплой на Render

В репозитории есть `render.yaml` (frontend + backend + postgres).

Рекомендованный порядок:

1. Создать Blueprint из `render.yaml`.
2. Дождаться первого деплоя сервисов `swl-db`, `swl-backend`, `swl-frontend`.
3. Выставить `NEXT_PUBLIC_API_URL=<backend-url>` в frontend.
4. Выставить `CORS_ORIGINS=<frontend-url>` и `APP_BASE_URL=<frontend-url>` в backend.
5. Настроить CAPTCHA: `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (frontend), `CAPTCHA_SECRET_KEY` и `CAPTCHA_EXPECTED_HOSTNAME=<frontend-host>` (backend).
6. Настроить email: `RESEND_API_KEY` и `SMTP_FROM_EMAIL` (домен отправителя должен быть верифицирован в Resend).
7. Задать `RESEND_WEBHOOK_SECRET` в backend.
8. Настроить webhook в Resend: `POST https://<backend>/api/webhooks/resend` + header `Authorization: Bearer <RESEND_WEBHOOK_SECRET>`.
9. При необходимости OAuth задайте `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`, `OAUTH_GITHUB_CLIENT_ID`, `OAUTH_GITHUB_CLIENT_SECRET`, `OAUTH_REDIRECT_BASE_URL=<frontend-url>`.
10. При multi-instance realtime добавить `REDIS_URL`.
11. Для мониторинга добавить `SENTRY_DSN` и `ALERTS_TEST_TOKEN`.
12. Проверить `GET /health/readiness` -> `ready=true`.

Примечание: если в Render возникают проблемы с зависимостями Python, зафиксируйте runtime на `3.12.x`.

## Тестирование

### Backend

```bash
cd backend
python -m compileall app
pytest -q
```

E2E-gate тесты:

```bash
cd backend
pytest -q tests/test_e2e_public_realtime_flow.py tests/test_e2e_account_deletion.py
pytest -q tests/test_oauth_flow.py
```

### Frontend

```bash
cd frontend
npm ci
npm run build
```

### Smoke на проде

```bash
BACKEND_URL=https://<backend> \
FRONTEND_URL=https://<frontend> \
SHARE_TOKEN=<optional_share_token> \
CAPTCHA_TOKEN=<optional_turnstile_token> \
./scripts/smoke_prod.sh
```

- если `SHARE_TOKEN` не передан, guest/public шаги будут `SKIP`.
- если `CAPTCHA_TOKEN` не передан при включенной CAPTCHA, guest-сессия может упасть по `400`.

Sentry smoke:

```bash
BACKEND_URL=https://<backend> ALERTS_TEST_TOKEN=<token> ./scripts/sentry_alert_smoke.sh
```

## Backup/restore

Backup:

```bash
DATABASE_URL=postgresql://... ./scripts/db_backup.sh
```

Restore:

```bash
DATABASE_URL=postgresql://... \
DUMP_FILE=./backups/<dump>.dump \
FORCE_RESTORE=true \
./scripts/db_restore.sh
```

## CI/CD и операции

Workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/production-smoke.yml`
- `.github/workflows/oncall-healthcheck.yml`
- `.github/workflows/scheduled-db-backup.yml`
- `.github/workflows/scheduled-restore-drill.yml`

Операционная документация:
- `docs/production-smoke.md`
- `docs/alerts.md`
- `docs/runbook.md`
- `docs/backup-restore.md`

## Troubleshooting

### 1) "Проверка CAPTCHA не пройдена", хотя виджет на странице показывает успех

Проверьте:
- соответствие пары ключей (`NEXT_PUBLIC_TURNSTILE_SITE_KEY` и `CAPTCHA_SECRET_KEY`) одному и тому же виджету;
- `CAPTCHA_EXPECTED_HOSTNAME` равен реальному хосту фронтенда без протокола;
- в production не используется test secret при `ALLOW_TEST_CAPTCHA_IN_PRODUCTION=false`.

### 2) Не отправляется письмо verify/reset

Проверьте:
- задан ли `RESEND_API_KEY` или SMTP-настройки (`SMTP_HOST` и т.д.);
- корректен ли `SMTP_FROM_EMAIL` (для Resend нужен верифицированный домен/адрес);
- при Resend задан ли `RESEND_WEBHOOK_SECRET` и настроен webhook;
- корректен ли `APP_BASE_URL` (иначе ссылки в письме будут неверными).

### 3) `/health/readiness` возвращает `ready=false`

Смотрите поля:
- `captcha_reason` для проблем CAPTCHA-конфига;
- `email_reason` для проблем email-конфига;
- `alerts_reason` и `realtime_reason` для advisory-диагностики.

### 4) Нет realtime-обновлений между вкладками/инстансами

Проверьте:
- WebSocket путь `/ws/w/{share_token}`;
- наличие `REDIS_URL` при горизонтальном масштабировании;
- отсутствие сетевых ограничений на WebSocket в инфраструктуре.

### 5) OAuth не логинит пользователя

Проверьте:
- корректны ли `OAUTH_*` client id/client secret;
- корректно ли выставлен `OAUTH_REDIRECT_BASE_URL`;
- совпадают ли redirect URI в Google/GitHub и backend;
- есть ли во fragment URL `oauth_error` после callback.

## Что можно усилить дальше

- Управление подключенными OAuth-провайдерами в профиле (link/unlink).
- История изменений с audit log для важных действий.
- Версионирование публичных юридических документов.
