# Alerts (MVP minimum)

## Backend

1. Healthcheck alert:
   - URL: `/health`
   - Trigger: `status != ok` или `db != true`.
2. Error-rate alert:
   - URL: `/health/metrics`
   - Trigger: `errors_5xx_last_5m >= 30`.

## Sentry

1. Environment: `production`.
2. Alert rule: "when event count > 0 in 5m" для `level=error`.
3. Канал доставки: email/Slack.

## Resend (email)

1. Включить webhook на `POST /api/webhooks/resend`.
2. Добавить `Authorization: Bearer <RESEND_WEBHOOK_SECRET>`.
3. Отдельный alert на события `email.bounced` и `email.complained`.
