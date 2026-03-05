# Production Smoke Checklist

Запускается после каждого деплоя frontend/backend.

## Быстрый автоматический прогон

```bash
BACKEND_URL=https://swl-backend.onrender.com \
FRONTEND_URL=https://swl-frontend.onrender.com \
SHARE_TOKEN=<public_share_token> \
CAPTCHA_TOKEN=<turnstile_token_if_enabled> \
./scripts/smoke_prod.sh
```

## Ручной чеклист (обязательный)

1. Открыть frontend URL на десктопе и мобильном viewport.
2. Проверить регистрацию, verify email, login.
3. Создать вишлист и 2 подарка (обычный + совместный сбор).
4. Открыть публичную ссылку в двух вкладках.
5. Вкладка A: войти как гость и внести вклад.
6. Вкладка B: убедиться, что прогресс обновился без reload (realtime).
7. Вкладка A: забронировать подарок без сбора.
8. Вкладка B: проверить моментальное обновление статуса брони.
9. Проверить reset password end-to-end (запрос + письмо + установка нового пароля).
10. Проверить, что CAPTСHA работает на auth и guest-входе.
11. Проверить Sentry smoke:
    `BACKEND_URL=https://... ALERTS_TEST_TOKEN=... ./scripts/sentry_alert_smoke.sh`

## Критерии "деплой ок"

- `/health` возвращает `status=ok` и `db=true`.
- `/health/readiness` возвращает `ready=true`.
- Ошибки в UI отображаются читабельно на русском.
- Нет 5xx в backend логах на ключевом пользовательском пути.
- Realtime работает в двух вкладках стабильно.
- Sentry smoke endpoint возвращает `200` и `event_id`.

## GitHub Actions

Для автопроверки после пуша в `main` настроить:

- Repo variable `PROD_BACKEND_URL`
- Repo variable `PROD_FRONTEND_URL`
- Repo secret `PROD_SHARE_TOKEN` (опционально, для guest smoke)
- Repo secret `PROD_CAPTCHA_TOKEN` (опционально)

Workflow: `.github/workflows/production-smoke.yml`
