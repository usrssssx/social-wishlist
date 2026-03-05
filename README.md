# Social Wish List

Готовое MVP веб-приложения социального вишлиста:
- владелец создаёт wishlist и товары;
- делится публичной ссылкой без обязательной регистрации для гостей;
- друзья резервируют подарок или делают вклад в общий сбор;
- владелец видит только агрегаты (без имён и сумм по людям);
- обновления приходят в realtime через WebSocket.

## Стек

- Frontend: Next.js 15 (React 19, TypeScript)
- Backend: FastAPI + SQLAlchemy async
- DB: PostgreSQL
- Realtime: FastAPI WebSocket hub
- Auth: email + password (JWT) + email verification + reset password
- Rate limiting: SlowAPI (IP-based)
- CAPTCHA: Cloudflare Turnstile (optional)
- Migrations: Alembic
- Observability: Sentry (optional)
- Автозаполнение товара по URL: OpenGraph/JSON-LD parser

## Продуктовые решения

- Публичный просмотр вишлиста доступен без регистрации.
- Для действий (бронь/вклад) гость создаёт лёгкую сессию с именем.
- Минимальный вклад: `100` (настраивается через `MIN_CONTRIBUTION_AMOUNT`).
- Если у товара уже есть вклад, целиком забронировать его нельзя.
- Если товар удаляют после брони/вкладов, он уходит в архив (`archived`) и остаётся видимым с объяснением (чтобы не потерять контекст обещаний).
- При достижении цели сбора товар считается закрытым автоматически.
- После даты события новые брони и вклады закрываются автоматически.
- Если к дедлайну собрана только часть суммы, товар помечается как `underfunded` (показывается, сколько не хватило).
- Владелец вишлиста не видит, кто забронировал и кто сколько внёс.

## Edge-кейсы, которые покрыты

- Двойная бронь одного товара блокируется.
- Вклад выше остатка до цели отклоняется.
- Вклад в архивный товар отклоняется.
- Бронь архивного товара отклоняется.
- Параллельные попытки забронировать один товар: проходит только одна.
- Некорректная/просроченная guest-сессия отклоняется.
- URL автозаполнения невалиден или не парсится: корректная ошибка API.

## Локальный запуск

### 1) PostgreSQL

Нужен Postgres на `localhost:5432`.

Пример создания БД/пользователя:

```sql
CREATE ROLE wishlist LOGIN PASSWORD 'wishlist';
CREATE DATABASE wishlist OWNER wishlist;
```

### 2) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Если БД была создана до Alembic (таблицы уже есть), выполните один раз:

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

Открыть: `http://localhost:3000`

## Docker

Есть `docker-compose.yml`, но нужен запущенный Docker daemon.

```bash
docker compose up -d --build
```

Контейнер backend при старте выполняет `alembic upgrade head`.

## Безопасность и прод-режим

- Регистрация требует подтверждение email (письмо с verify link).
- Вход запрещён для неподтверждённых email.
- Доступен reset password flow через email.
- На auth и публичные write-операции включён rate limit.
- Для production рекомендуется заполнить `SENTRY_DSN` и email-переменные из `backend/.env.example`.
- Если задан `RESEND_API_KEY`, backend отправляет письма через Resend API (приоритетно); иначе использует SMTP.
- Для Resend webhook событий доставки/отказов задайте `RESEND_WEBHOOK_SECRET` и подключите endpoint `POST /api/webhooks/resend`.
- При временных сбоях email-провайдера backend делает повторные попытки отправки (`EMAIL_SEND_RETRIES`).
- Для защиты от ботов можно включить Turnstile: `CAPTCHA_SECRET_KEY` (backend) и `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (frontend).
- Для production с Turnstile обязательно задайте `CAPTCHA_EXPECTED_HOSTNAME` (например, `swl-frontend.onrender.com`).
- Для production тестовые ключи Turnstile запрещены по умолчанию (`ALLOW_TEST_CAPTCHA_IN_PRODUCTION=false`).
- Проверка готовности окружения: `GET /health/readiness`.
- Для E2E проверки Sentry-алертов задайте `ALERTS_TEST_TOKEN` и используйте `POST /health/alerts/test`.

## Проверка realtime

- Откройте публичную ссылку в двух вкладках.
- В одной сделайте бронь/вклад.
- Во второй обновление состояния придёт мгновенно без reload.

## Production smoke после деплоя

- Скрипт: `scripts/smoke_prod.sh`
- Sentry smoke: `scripts/sentry_alert_smoke.sh`
- Чеклист: `docs/production-smoke.md`
- Алерты и наблюдаемость: `docs/alerts.md`
- Backup/restore: `docs/backup-restore.md`
- GitHub Actions smoke: `.github/workflows/production-smoke.yml`

## Backup и восстановление БД

Перед рискованными изменениями схемы/данных:

```bash
DATABASE_URL=postgresql://... ./scripts/db_backup.sh
```

Тестовый restore:

```bash
DATABASE_URL=postgresql://... \
DUMP_FILE=./backups/<dump>.dump \
FORCE_RESTORE=true \
./scripts/db_restore.sh
```

## Деплой

В репозитории добавлен `render.yaml` для быстрого деплоя на Render (frontend + backend + postgres).

Важно: из этого окружения нет авторизованных CLI/токенов облачных платформ, поэтому публичный URL автоматически создать нельзя без вашего аккаунта.

Порядок на Render:

1. New > Blueprint, выберите этот репозиторий и `render.yaml`.
2. Render создаст `swl-db`, `swl-backend`, `swl-frontend`.
3. После первого деплоя откройте frontend service и скопируйте его public URL.
4. В backend service задайте `CORS_ORIGINS=<frontend-public-url>` и redeploy backend.
5. В frontend service задайте `NEXT_PUBLIC_API_URL=<backend-public-url>` и redeploy frontend.
6. В backend service задайте `APP_BASE_URL=<frontend-public-url>` для email ссылок.
7. Если включаете CAPTCHA: задайте `CAPTCHA_SECRET_KEY` (backend) и `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (frontend), затем redeploy обоих сервисов.
8. Для Turnstile в backend задайте `CAPTCHA_EXPECTED_HOSTNAME=<frontend-host-without-https>`.
9. Убедитесь, что `/health/readiness` возвращает `ready=true`.
10. Для email-доставки через Resend задайте `RESEND_API_KEY` в backend service.
11. Для мониторинга delivery/bounce в Resend Webhooks укажите URL:
   `https://<backend>/api/webhooks/resend`
   и заголовок `Authorization: Bearer <RESEND_WEBHOOK_SECRET>`.
12. Для проверки Sentry задайте `SENTRY_DSN` и `ALERTS_TEST_TOKEN`, затем выполните:
   `BACKEND_URL=https://<backend> ALERTS_TEST_TOKEN=<token> ./scripts/sentry_alert_smoke.sh`.

## CI

GitHub Actions workflow: `.github/workflows/ci.yml`

- Backend: Postgres service, `alembic upgrade head`, `pytest`, `compileall`.
- Frontend: `npm ci` + `npm run build`.

## Что ещё можно усилить

- OAuth (Google/GitHub) через отдельный auth-router.
- Redis pub/sub для WebSocket broadcast в multi-instance проде.
- История изменений по товарам + audit log.
- E2E тесты Playwright для пользовательских сценариев.
