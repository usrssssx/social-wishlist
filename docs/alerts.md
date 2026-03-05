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

## On-call notifications

1. Workflow: `.github/workflows/oncall-healthcheck.yml` (каждые 5 минут).
2. Каналы:
   - `ONCALL_SLACK_WEBHOOK_URL` (Slack)
   - `ONCALL_TELEGRAM_BOT_TOKEN` + `ONCALL_TELEGRAM_CHAT_ID` (Telegram)
   - `ONCALL_WEBHOOK_URL` (generic webhook, опционально)
3. Проверяются endpoints:
   - `/health` (`status=ok`, `db=true`)
   - `/health/readiness` (`ready=true`)
4. Скрипт отправки уведомлений: `scripts/oncall_notify.sh`.
5. Операционный runbook: `docs/runbook.md`.

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
