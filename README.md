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
- Auth: email + password (JWT)
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
uvicorn app.main:app --reload --port 8000
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

## Проверка realtime

- Откройте публичную ссылку в двух вкладках.
- В одной сделайте бронь/вклад.
- Во второй обновление состояния придёт мгновенно без reload.

## Деплой

В репозитории добавлен `render.yaml` для быстрого деплоя на Render (frontend + backend + postgres).

Важно: из этого окружения нет авторизованных CLI/токенов облачных платформ, поэтому публичный URL автоматически создать нельзя без вашего аккаунта.

Порядок на Render:

1. New > Blueprint, выберите этот репозиторий и `render.yaml`.
2. Render создаст `swl-db`, `swl-backend`, `swl-frontend`.
3. После первого деплоя откройте frontend service и скопируйте его public URL.
4. В backend service задайте `CORS_ORIGINS=<frontend-public-url>` и redeploy backend.
5. В frontend service задайте `NEXT_PUBLIC_API_URL=<backend-public-url>` и redeploy frontend.

## Что ещё можно усилить

- OAuth (Google/GitHub) через отдельный auth-router.
- Redis pub/sub для WebSocket broadcast в multi-instance проде.
- История изменений по товарам + audit log.
- E2E тесты Playwright для пользовательских сценариев.
