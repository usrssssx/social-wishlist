# Alerts (MVP minimum)

## Backend

1. Healthcheck alert:
   - URL: `/health`
   - Trigger: `status != ok` или `db != true`.
2. Readiness alert:
   - URL: `/health/readiness`
   - Trigger: `ready != true`.
3. Error-rate alert:
   - URL: `/health/metrics`
   - Trigger: `errors_5xx_last_5m >= 30`.

## Sentry

1. В backend env задать:
   - `SENTRY_DSN=<project_dsn>`
   - `ALERTS_TEST_TOKEN=<random_secret>`
2. Environment: `production`.
3. Alert rule: "when event count > 0 in 5m" для `level=error`.
4. Канал доставки: email/Slack.
5. E2E проверка после деплоя:
   - `BACKEND_URL=https://... ALERTS_TEST_TOKEN=... ./scripts/sentry_alert_smoke.sh`
   - endpoint: `POST /health/alerts/test` с заголовком `X-Alerts-Test-Token`.

## Resend (email)

1. Включить webhook на `POST /api/webhooks/resend`.
2. Добавить `Authorization: Bearer <RESEND_WEBHOOK_SECRET>`.
3. Отдельный alert на события `email.bounced` и `email.complained`.
